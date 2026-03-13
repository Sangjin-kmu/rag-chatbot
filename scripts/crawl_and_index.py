"""공지사항 크롤링 + 인덱싱 통합 스크립트
- 최근 1년 이내 공지만 처리
- 본문 텍스트 + 첨부파일(PDF) 파싱 후 RAG 인덱싱
- 이미 인덱싱된 공지는 스킵 (URL 기준 중복 체크)

단독 실행:
  docker-compose -f deploy/docker-compose.prod.yml exec app python scripts/crawl_and_index.py

자동 스케줄: main.py의 스케줄러가 매일 새벽 3시에 실행
"""
import asyncio
import os
import sys
import re
import uuid
import time
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "https://cs.kookmin.ac.kr/news/notice/"
WAIT_MS = 1500
CUTOFF_DAYS = 365  # 최근 1년

def parse_date(date_str: str):
    """'26.03.11' → datetime"""
    try:
        parts = date_str.strip().split(".")
        if len(parts) == 3:
            year = int(parts[0])
            year = year + 2000 if year < 100 else year
            return datetime(year, int(parts[1]), int(parts[2]))
    except Exception:
        pass
    return None


def is_within_cutoff(date_str: str) -> bool:
    dt = parse_date(date_str)
    if not dt:
        return True
    return dt >= datetime.now() - timedelta(days=CUTOFF_DAYS)


def llm_filter_notices(notices: list) -> list:
    """Gemini로 공지 목록을 한 번에 필터링.
    
    notices: [{"title": str, "date": str, "url": str, ...}, ...]
    반환: 인덱싱할 공지만 남긴 리스트
    """
    import google.generativeai as genai
    from config import settings

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    today = datetime.now().strftime("%Y년 %m월 %d일")

    # 번호 매겨서 프롬프트 구성
    lines = "\n".join(
        f"{i+1}. [{n['date']}] {n['title']}"
        for i, n in enumerate(notices)
    )

    prompt = f"""오늘 날짜: {today}

아래는 대학교 소프트웨어융합대학 공지사항 목록이야.
각 공지에 대해 RAG 지식베이스(학생 질의응답 시스템)에 인덱싱할 가치가 있는지 판단해줘.

[인덱싱 O] 기준:
- 학사 규정, 졸업 요건, 수강신청 절차, 장학금, 출석인정 등 반복적으로 참조될 정보
- 제도 변경 안내, 인증 요건 등 지속적으로 유효한 정보
- 마감일이 있더라도 오늘 기준 아직 유효한 신청 안내

[인덱싱 X] 기준:
- 동아리 모집, 행사, 경진대회 등 일회성 이벤트
- 강의실 변경, 시험 날짜 변경 등 단순 공지
- 마감일이 이미 지난 신청 안내
- 특정 분반/교수 대상 단순 공지

결과를 아래 형식으로만 답해줘 (다른 말 없이):
1:O
2:X
3:O
...

공지 목록:
{lines}"""

    try:
        resp = model.generate_content(prompt)
        text = resp.text.strip()
        
        # 파싱: "1:O\n2:X\n..." → {1: True, 2: False, ...}
        decisions = {}
        for line in text.splitlines():
            line = line.strip()
            if ":" in line:
                parts = line.split(":", 1)
                try:
                    idx = int(parts[0].strip())
                    keep = parts[1].strip().upper() == "O"
                    decisions[idx] = keep
                except ValueError:
                    pass

        filtered = []
        for i, notice in enumerate(notices):
            keep = decisions.get(i + 1, True)  # 파싱 실패 시 기본 포함
            if keep:
                filtered.append(notice)
            else:
                print(f"  🤖 LLM 필터 스킵: {notice['title'][:60]}")

        print(f"  → LLM 필터: {len(notices)}개 중 {len(filtered)}개 통과")
        return filtered

    except Exception as e:
        print(f"  ⚠️ LLM 필터 실패 ({e}), 전체 포함")
        return notices


async def crawl_and_index(search_engine=None, log_callback=None):
    """공지사항 크롤링 + 인덱싱 메인 함수"""

    async def log(msg):
        print(msg)
        if log_callback:
            await log_callback(msg)

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        await log("❌ playwright 미설치")
        return 0

    # search_engine이 없으면 직접 생성
    own_engine = False
    if search_engine is None:
        from search.free_hybrid_search import FreeHybridSearch
        search_engine = FreeHybridSearch()
        search_engine.init_collections()
        own_engine = True

    from preprocessing.pdf_parser import PDFToMarkdown
    from preprocessing.chunker import SemanticChunker
    from config import settings

    chunker = SemanticChunker(chunk_size=settings.chunk_size, overlap=settings.chunk_overlap)
    pdf_parser = PDFToMarkdown()

    # 이미 인덱싱된 공지 URL 목록 조회
    indexed_urls = set(search_engine.get_indexed_sources())

    total_indexed = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()

        # 1단계: 공지 목록 수집 (최근 1년치만)
        await log("📋 공지 목록 수집 중...")
        await page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        # 총 페이지 수
        el = await page.query_selector(".pagenation-number")
        total_pages = 1
        if el:
            text = await el.inner_text()
            parts = text.strip().split("/")
            if len(parts) == 2:
                total_pages = int(parts[1].strip())

        notices_to_process = []
        stop_crawl = False

        for pn in range(total_pages):
            if stop_crawl:
                break

            url = f"{BASE_URL}?&pn={pn}"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(WAIT_MS)

            rows = await page.query_selector_all(".list-tbody ul")
            page_has_recent = False

            for row in rows:
                subject_el = await row.query_selector("li.subject a")
                if not subject_el:
                    continue
                href = await subject_el.get_attribute("href")
                title = (await subject_el.inner_text()).strip()
                date_el = await row.query_selector("li.date")
                date_str = (await date_el.inner_text()).strip() if date_el else ""
                has_attach = bool(await row.query_selector("img[alt='file']"))

                if not href:
                    continue

                notice_url = f"https://cs.kookmin.ac.kr/news/notice/{href.replace('./', '')}"

                if not is_within_cutoff(date_str):
                    stop_crawl = True
                    break

                page_has_recent = True

                if notice_url in indexed_urls:
                    continue  # 이미 인덱싱됨

                notices_to_process.append({
                    "title": title,
                    "url": notice_url,
                    "date": date_str,
                    "has_attach": has_attach
                })

            if not page_has_recent and pn > 0:
                break

        await log(f"  → 신규 공지 {len(notices_to_process)}개 처리 예정 (LLM 필터 전)")

        # LLM 필터: Gemini가 인덱싱 가치 판단
        if notices_to_process:
            notices_to_process = llm_filter_notices(notices_to_process)

        # 2단계: 각 공지 상세 크롤링 + 인덱싱
        for i, notice in enumerate(notices_to_process):
            await log(f"[{i+1}/{len(notices_to_process)}] {notice['title'][:50]}")
            try:
                await page.goto(notice["url"], wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(WAIT_MS)

                # 본문 추출
                content = ""
                for sel in [".board-view-content", ".view-content", ".content-view", ".board-content"]:
                    el = await page.query_selector(sel)
                    if el:
                        content = (await el.inner_text()).strip()
                        if content:
                            break

                # 본문 인덱싱
                if content:
                    chunks = chunker.chunk(content, {
                        "doc_name": f"[공지] {notice['title'][:80]}",
                        "source_url": notice["url"],
                        "date": notice["date"],
                        "section_path": "공지사항",
                        "page": 1,
                        "has_table": False
                    })
                    batch = [{"id": str(uuid.uuid4()), **c} for c in chunks]
                    search_engine.index_chunks_batch(batch)
                    total_indexed += len(batch)
                    await log(f"  📝 {notice['title'][:40]} → 본문 {len(batch)}청크 DB저장 완료")

                # 첨부파일 처리
                if notice["has_attach"]:
                    attach_links = await page.query_selector_all(
                        ".board-view-file a, .view-file a, .file-list a, "
                        "a[href*='download'], a[href*='/file/']"
                    )
                    # 확장자 직접 탐지
                    if not attach_links:
                        all_links = await page.query_selector_all("a[href]")
                        attach_links = []
                        for link in all_links:
                            href = (await link.get_attribute("href") or "").lower()
                            if any(ext in href for ext in ['.pdf', '.hwp', '.docx', '.doc', '.xlsx']):
                                attach_links.append(link)

                    for link in attach_links:
                        href = await link.get_attribute("href") or ""
                        name = (await link.inner_text()).strip() or href.split("/")[-1]
                        full_url = href if href.startswith("http") else f"https://cs.kookmin.ac.kr{href}"

                        # PDF만 파싱 (HWP 등은 스킵)
                        if not href.lower().endswith(".pdf"):
                            continue

                        try:
                            resp = await context.request.get(full_url)
                            if not resp.ok:
                                continue
                            body = await resp.body()

                            # 임시 파일로 저장 후 파싱
                            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                                tmp.write(body)
                                tmp_path = tmp.name

                            sections = pdf_parser.parse(tmp_path, name)
                            os.unlink(tmp_path)

                            attach_chunks = []
                            for sec in sections:
                                sec["metadata"]["source_url"] = notice["url"]
                                sec["metadata"]["doc_name"] = f"[공지첨부] {name}"
                                sub = chunker.chunk(sec["content"], sec["metadata"])
                                attach_chunks.extend(sub)

                            if attach_chunks:
                                batch = [{"id": str(uuid.uuid4()), **c} for c in attach_chunks]
                                search_engine.index_chunks_batch(batch)
                                total_indexed += len(batch)
                                await log(f"  📎 첨부 {name}: {len(batch)}청크 DB저장 완료")

                        except Exception as e:
                            await log(f"  ❌ 첨부파일 처리 실패: {name} - {e}")

            except Exception as e:
                await log(f"  ❌ 실패: {e}")

            await page.wait_for_timeout(500)

        await browser.close()

    if own_engine:
        search_engine.close()

    await log(f"✅ 공지 크롤링 완료: {total_indexed}개 청크 인덱싱")
    return total_indexed


if __name__ == "__main__":
    asyncio.run(crawl_and_index())
