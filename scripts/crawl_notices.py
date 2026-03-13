"""국민대 소프트웨어학부 공지사항 크롤러
- https://cs.kookmin.ac.kr/news/notice/ 전체 270페이지 크롤링
- 본문 텍스트 + 첨부파일(PDF 등) 자동 다운로드
- Playwright (헤드리스 브라우저) 사용

사용법:
  pip install playwright
  playwright install chromium
  python scripts/crawl_notices.py
"""
import asyncio
import os
import re
import json
import time
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ playwright 설치 필요:")
    print("   pip install playwright")
    print("   playwright install chromium")
    exit(1)

# 설정
BASE_URL = "https://cs.kookmin.ac.kr/news/notice/"
OUTPUT_DIR = Path("crawled_notices")
ATTACH_DIR = OUTPUT_DIR / "attachments"
WAIT_MS = 2000  # 페이지 로딩 대기 (ms)


async def get_total_pages(page) -> int:
    """총 페이지 수 추출"""
    # .pagenation-number 에서 "1/270" 형태
    el = await page.query_selector(".pagenation-number")
    if el:
        text = await el.inner_text()  # "1/270"
        parts = text.strip().split("/")
        if len(parts) == 2:
            return int(parts[1].strip())
    return 1


async def get_notice_list(page) -> list:
    """현재 페이지의 공지 목록 추출"""
    notices = []
    rows = await page.query_selector_all(".list-tbody ul")

    for row in rows:
        # 제목 + 링크
        subject_el = await row.query_selector("li.subject a")
        if not subject_el:
            continue
        href = await subject_el.get_attribute("href")
        title = (await subject_el.inner_text()).strip()

        # 번호 (Notice 또는 숫자)
        num_el = await row.query_selector("li.notice strong, li.number")
        num = ""
        if num_el:
            num = (await num_el.inner_text()).strip()

        # 글쓴이
        lis = await row.query_selector_all("li")
        author = ""
        date = ""
        if len(lis) >= 4:
            author = (await lis[2].inner_text()).strip()
        # 날짜
        date_el = await row.query_selector("li.date")
        if date_el:
            date = (await date_el.inner_text()).strip()
        elif len(lis) >= 5:
            date = (await lis[3].inner_text()).strip()

        # 첨부파일 여부
        has_attach = await row.query_selector("img[alt='file']")

        if href and title:
            full_url = f"https://cs.kookmin.ac.kr/news/notice/{href.replace('./', '')}"
            notices.append({
                "num": num,
                "title": title,
                "url": full_url,
                "author": author,
                "date": date,
                "has_attach": bool(has_attach)
            })

    return notices


async def get_notice_detail(page, url: str) -> dict:
    """공지 상세 페이지에서 본문 + 첨부파일 URL 추출"""
    await page.goto(url, wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(WAIT_MS)

    # 제목
    title = ""
    for sel in [".board-view-title", ".view-title", "h2", ".subject-title"]:
        el = await page.query_selector(sel)
        if el:
            title = (await el.inner_text()).strip()
            if title:
                break
    if not title:
        title = (await page.title()).strip()

    # 본문
    content = ""
    for sel in [".board-view-content", ".view-content", ".content-view",
                ".board-content", ".view-body"]:
        el = await page.query_selector(sel)
        if el:
            content = (await el.inner_text()).strip()
            if content:
                break
    # 본문 못 찾으면 전체 content 영역에서 시도
    if not content:
        el = await page.query_selector(".content")
        if el:
            content = (await el.inner_text()).strip()

    # 날짜, 글쓴이 등 메타 정보
    meta = {}
    meta_els = await page.query_selector_all(".view-info li, .board-view-info li, .info-item")
    for mel in meta_els:
        text = (await mel.inner_text()).strip()
        if "작성일" in text or "날짜" in text or "등록일" in text:
            meta["date"] = text.split(":")[-1].strip() if ":" in text else text
        elif "글쓴이" in text or "작성자" in text:
            meta["author"] = text.split(":")[-1].strip() if ":" in text else text

    # 첨부파일 링크 수집
    attachments = []
    # 방법1: 일반적인 첨부파일 영역
    attach_links = await page.query_selector_all(
        ".board-view-file a, .view-file a, .file-list a, "
        ".attach a, a[href*='download'], a[href*='/file/']"
    )
    for link in attach_links:
        href = await link.get_attribute("href")
        name = (await link.inner_text()).strip()
        if href and name:
            full_url = href if href.startswith("http") else f"https://cs.kookmin.ac.kr{href}"
            attachments.append({"name": name, "url": full_url})

    # 방법2: 직접 파일 확장자 링크
    if not attachments:
        all_links = await page.query_selector_all("a[href]")
        for link in all_links:
            href = await link.get_attribute("href") or ""
            lower = href.lower()
            if any(ext in lower for ext in ['.pdf', '.hwp', '.hwpx', '.docx',
                                             '.doc', '.xlsx', '.xls', '.zip',
                                             '.pptx', '.ppt']):
                name = (await link.inner_text()).strip()
                if not name:
                    name = href.split("/")[-1].split("?")[0]
                full_url = href if href.startswith("http") else f"https://cs.kookmin.ac.kr{href}"
                attachments.append({"name": name, "url": full_url})

    return {
        "title": title,
        "url": url,
        "content": content,
        "meta": meta,
        "attachments": attachments
    }


async def download_file(context, url: str, filename: str) -> str:
    """첨부파일 다운로드"""
    ATTACH_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r'[\\/*?:"<>|]', '_', filename).strip()
    if not safe_name:
        safe_name = url.split("/")[-1].split("?")[0] or "file"

    filepath = ATTACH_DIR / safe_name
    if filepath.exists():
        print(f"    ⏭️  이미 존재: {safe_name}")
        return str(filepath)

    try:
        resp = await context.request.get(url)
        if resp.ok:
            body = await resp.body()
            filepath.write_bytes(body)
            size_kb = len(body) / 1024
            print(f"    📎 다운로드: {safe_name} ({size_kb:.1f}KB)")
            return str(filepath)
        else:
            print(f"    ❌ HTTP {resp.status}: {safe_name}")
    except Exception as e:
        print(f"    ❌ 다운로드 실패: {safe_name} - {e}")
    return ""


async def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ATTACH_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # ============================================================
        # 1단계: 전체 공지 목록 수집
        # ============================================================
        print("=" * 60)
        print("1단계: 공지 목록 수집")
        print("=" * 60)

        await page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        total_pages = await get_total_pages(page)
        print(f"총 {total_pages} 페이지 발견")

        # 테스트: 첫 페이지만 (전체 크롤링 시 range(total_pages)로 변경)
        TEST_PAGES = 1

        all_notices = []
        for pn in range(TEST_PAGES):
            url = f"{BASE_URL}?&pn={pn}"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(WAIT_MS)

            notices = await get_notice_list(page)
            all_notices.extend(notices)

            if (pn + 1) % 10 == 0 or pn == 0:
                print(f"  페이지 {pn+1}/{total_pages} — 누적 {len(all_notices)}개")

        # 중복 제거 (URL 기준)
        seen = set()
        unique = []
        for n in all_notices:
            if n["url"] not in seen:
                seen.add(n["url"])
                unique.append(n)

        print(f"\n📄 총 {len(unique)}개 고유 공지 수집 완료")

        # 목록 저장
        list_path = OUTPUT_DIR / "notice_list.json"
        with open(list_path, "w", encoding="utf-8") as f:
            json.dump(unique, f, ensure_ascii=False, indent=2)
        print(f"  목록 저장: {list_path}")

        # ============================================================
        # 2단계: 각 공지 상세 크롤링 + 첨부파일 다운로드
        # ============================================================
        print(f"\n{'=' * 60}")
        print("2단계: 상세 페이지 크롤링 + 첨부파일 다운로드")
        print("=" * 60)

        results = []
        total = len(unique)
        for i, notice in enumerate(unique):
            short_title = notice["title"][:45]
            print(f"\n[{i+1}/{total}] {short_title}...")

            try:
                detail = await get_notice_detail(page, notice["url"])
                # 목록에서 가져온 메타 정보 병합
                detail["num"] = notice.get("num", "")
                detail["author"] = notice.get("author", "") or detail.get("meta", {}).get("author", "")
                detail["date"] = notice.get("date", "") or detail.get("meta", {}).get("date", "")
                detail["has_attach"] = notice.get("has_attach", False)

                # 첨부파일 다운로드
                for attach in detail.get("attachments", []):
                    local = await download_file(context, attach["url"], attach["name"])
                    attach["local_path"] = local

                results.append(detail)

                # 본문 텍스트 파일 저장
                safe_title = re.sub(r'[\\/*?:"<>|]', '_', detail["title"])[:80]
                txt_path = OUTPUT_DIR / f"{i+1:04d}_{safe_title}.txt"
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(f"제목: {detail['title']}\n")
                    f.write(f"번호: {detail['num']}\n")
                    f.write(f"글쓴이: {detail['author']}\n")
                    f.write(f"날짜: {detail['date']}\n")
                    f.write(f"URL: {detail['url']}\n")
                    if detail["attachments"]:
                        f.write(f"첨부파일: {len(detail['attachments'])}개\n")
                        for a in detail["attachments"]:
                            f.write(f"  - {a['name']}\n")
                    f.write(f"\n{'=' * 60}\n\n")
                    f.write(detail.get("content", "(본문 없음)"))

            except Exception as e:
                print(f"  ❌ 실패: {e}")

            # 서버 부하 방지
            await page.wait_for_timeout(500)

        await browser.close()

    # 전체 결과 JSON 저장
    json_path = OUTPUT_DIR / "notices_full.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 통계
    attach_count = sum(len(r.get("attachments", [])) for r in results)
    print(f"\n{'=' * 60}")
    print(f"🎉 크롤링 완료!")
    print(f"  공지: {len(results)}개")
    print(f"  첨부파일: {attach_count}개")
    print(f"  텍스트 저장: {OUTPUT_DIR}/")
    print(f"  첨부파일 저장: {ATTACH_DIR}/")
    print(f"  전체 데이터: {json_path}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
