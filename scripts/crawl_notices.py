"""국민대 소프트웨어학부 공지사항 크롤러
- https://cs.kookmin.ac.kr/news/notice/ 전체 크롤링
- 본문 텍스트를 PDF로 변환 + 첨부파일(PDF)이 있으면 뒤에 병합
- Playwright (헤드리스 브라우저) 사용

사용법:
  pip install playwright fpdf2 PyPDF2
  playwright install chromium
  python scripts/crawl_notices.py
"""
import asyncio
import os
import re
import json
import tempfile
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("playwright 설치 필요: pip install playwright && playwright install chromium")
    exit(1)

from fpdf import FPDF
from PyPDF2 import PdfReader, PdfWriter

# 설정
BASE_URL = "https://cs.kookmin.ac.kr/news/notice/"
OUTPUT_DIR = Path("crawled_notices")
PDF_DIR = OUTPUT_DIR / "pdf"
TEMP_DIR = OUTPUT_DIR / "temp"
WAIT_MS = 2000

# 한글 폰트 경로 (macOS)
FONT_PATH = "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
if not os.path.exists(FONT_PATH):
    FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"


class NoticePDF(FPDF):
    """한글 지원 PDF 생성기"""
    def __init__(self):
        super().__init__()
        self.add_font("Korean", "", FONT_PATH, uni=True)
        self.set_auto_page_break(auto=True, margin=20)

    def add_notice(self, title, date, author, url, content):
        self.add_page()
        # 제목
        self.set_font("Korean", size=16)
        self.multi_cell(0, 10, title)
        self.ln(3)
        # 메타 정보
        self.set_font("Korean", size=9)
        self.set_text_color(100, 100, 100)
        if date:
            self.cell(0, 5, f"날짜: {date}", new_x="LMARGIN", new_y="NEXT")
        if author:
            self.cell(0, 5, f"작성자: {author}", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 5, f"URL: {url}", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)
        # 구분선
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)
        # 본문
        self.set_text_color(0, 0, 0)
        self.set_font("Korean", size=10)
        if content:
            self.multi_cell(0, 6, content)
        else:
            self.cell(0, 6, "(본문 없음)")


def create_notice_pdf(title, date, author, url, content, output_path):
    """공지 본문을 PDF로 생성"""
    pdf = NoticePDF()
    pdf.add_notice(title, date, author, url, content)
    pdf.output(str(output_path))


def merge_pdfs(main_pdf_path, attachment_paths, output_path):
    """본문 PDF + 첨부파일 PDF들을 하나로 병합"""
    writer = PdfWriter()

    # 본문 PDF 추가
    reader = PdfReader(str(main_pdf_path))
    for page in reader.pages:
        writer.add_page(page)

    # 첨부파일 PDF들 추가
    for attach_path in attachment_paths:
        try:
            attach_reader = PdfReader(str(attach_path))
            for page in attach_reader.pages:
                writer.add_page(page)
        except Exception as e:
            print(f"    첨부파일 병합 실패 ({attach_path}): {e}")

    with open(str(output_path), "wb") as f:
        writer.write(f)


async def get_total_pages(page) -> int:
    el = await page.query_selector(".pagenation-number")
    if el:
        text = await el.inner_text()
        parts = text.strip().split("/")
        if len(parts) == 2:
            return int(parts[1].strip())
    return 1


async def get_notice_list(page) -> list:
    notices = []
    rows = await page.query_selector_all(".list-tbody ul")
    for row in rows:
        subject_el = await row.query_selector("li.subject a")
        if not subject_el:
            continue
        href = await subject_el.get_attribute("href")
        title = (await subject_el.inner_text()).strip()

        num_el = await row.query_selector("li.notice strong, li.number")
        num = ""
        if num_el:
            num = (await num_el.inner_text()).strip()

        lis = await row.query_selector_all("li")
        author = ""
        if len(lis) >= 4:
            author = (await lis[2].inner_text()).strip()

        date = ""
        date_el = await row.query_selector("li.date")
        if date_el:
            date = (await date_el.inner_text()).strip()
        elif len(lis) >= 5:
            date = (await lis[3].inner_text()).strip()

        has_attach = await row.query_selector("img[alt='file']")

        if href and title:
            full_url = f"https://cs.kookmin.ac.kr/news/notice/{href.replace('./', '')}"
            notices.append({
                "num": num, "title": title, "url": full_url,
                "author": author, "date": date, "has_attach": bool(has_attach)
            })
    return notices


async def get_notice_detail(page, url: str) -> dict:
    await page.goto(url, wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(WAIT_MS)

    title = ""
    for sel in [".board-view-title", ".view-title", "h2", ".subject-title"]:
        el = await page.query_selector(sel)
        if el:
            title = (await el.inner_text()).strip()
            if title:
                break
    if not title:
        title = (await page.title()).strip()

    content = ""
    for sel in [".board-view-content", ".view-content", ".content-view",
                ".board-content", ".view-body"]:
        el = await page.query_selector(sel)
        if el:
            content = (await el.inner_text()).strip()
            if content:
                break
    if not content:
        el = await page.query_selector(".content")
        if el:
            content = (await el.inner_text()).strip()

    meta = {}
    meta_els = await page.query_selector_all(".view-info li, .board-view-info li, .info-item")
    for mel in meta_els:
        text = (await mel.inner_text()).strip()
        if any(k in text for k in ["작성일", "날짜", "등록일"]):
            meta["date"] = text.split(":")[-1].strip() if ":" in text else text
        elif any(k in text for k in ["글쓴이", "작성자"]):
            meta["author"] = text.split(":")[-1].strip() if ":" in text else text

    attachments = []
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
        "title": title, "url": url, "content": content,
        "meta": meta, "attachments": attachments
    }


async def download_file(context, url: str, filename: str, dest_dir: Path) -> str:
    """첨부파일 다운로드"""
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r'[\\/*?:"<>|]', '_', filename).strip()
    if not safe_name:
        safe_name = url.split("/")[-1].split("?")[0] or "file"

    filepath = dest_dir / safe_name
    if filepath.exists():
        return str(filepath)

    try:
        resp = await context.request.get(url)
        if resp.ok:
            body = await resp.body()
            filepath.write_bytes(body)
            size_kb = len(body) / 1024
            print(f"    다운로드: {safe_name} ({size_kb:.1f}KB)")
            return str(filepath)
        else:
            print(f"    HTTP {resp.status}: {safe_name}")
    except Exception as e:
        print(f"    다운로드 실패: {safe_name} - {e}")
    return ""


async def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # 1단계: 공지 목록 수집
        print("=" * 60)
        print("1단계: 공지 목록 수집")
        print("=" * 60)

        await page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        total_pages = await get_total_pages(page)
        print(f"총 {total_pages} 페이지 발견")

        # 크롤링할 페이지 수 (전체: total_pages, 테스트: 1)
        CRAWL_PAGES = 1

        all_notices = []
        for pn in range(CRAWL_PAGES):
            url = f"{BASE_URL}?&pn={pn}"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(WAIT_MS)
            notices = await get_notice_list(page)
            all_notices.extend(notices)
            if (pn + 1) % 10 == 0 or pn == 0:
                print(f"  페이지 {pn+1}/{CRAWL_PAGES} - 누적 {len(all_notices)}개")

        # 중복 제거
        seen = set()
        unique = []
        for n in all_notices:
            if n["url"] not in seen:
                seen.add(n["url"])
                unique.append(n)

        print(f"\n총 {len(unique)}개 고유 공지 수집 완료")

        # 2단계: 상세 크롤링 + PDF 변환
        print(f"\n{'=' * 60}")
        print("2단계: 상세 크롤링 + PDF 변환")
        print("=" * 60)

        results = []
        total = len(unique)
        for i, notice in enumerate(unique):
            short_title = notice["title"][:45]
            print(f"\n[{i+1}/{total}] {short_title}...")

            try:
                detail = await get_notice_detail(page, notice["url"])
                detail["num"] = notice.get("num", "")
                detail["author"] = notice.get("author", "") or detail.get("meta", {}).get("author", "")
                detail["date"] = notice.get("date", "") or detail.get("meta", {}).get("date", "")

                # 파일명 생성
                safe_title = re.sub(r'[\\/*?:"<>|]', '_', detail["title"])[:80].strip()
                pdf_filename = f"{safe_title}.pdf"

                # 본문 PDF 생성
                body_pdf_path = TEMP_DIR / f"body_{i}.pdf"
                create_notice_pdf(
                    detail["title"], detail["date"], detail["author"],
                    detail["url"], detail.get("content", ""),
                    body_pdf_path
                )

                # 첨부파일 다운로드 (PDF만 병합 대상)
                pdf_attachments = []
                for attach in detail.get("attachments", []):
                    local = await download_file(context, attach["url"], attach["name"], TEMP_DIR)
                    attach["local_path"] = local
                    if local and local.lower().endswith(".pdf"):
                        pdf_attachments.append(local)

                # 최종 PDF 생성 (본문 + 첨부 PDF 병합)
                final_pdf_path = PDF_DIR / pdf_filename
                if pdf_attachments:
                    print(f"    PDF 병합: 본문 + 첨부 {len(pdf_attachments)}개")
                    merge_pdfs(body_pdf_path, pdf_attachments, final_pdf_path)
                else:
                    # 첨부 PDF 없으면 본문 PDF만 복사
                    import shutil
                    shutil.copy2(str(body_pdf_path), str(final_pdf_path))

                detail["pdf_path"] = str(final_pdf_path)
                results.append(detail)
                print(f"    PDF 저장: {pdf_filename}")

            except Exception as e:
                print(f"    실패: {e}")

            await page.wait_for_timeout(500)

        await browser.close()

    # 임시 파일 정리
    import shutil
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)

    # 결과 JSON 저장
    json_path = OUTPUT_DIR / "notices_full.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"크롤링 완료!")
    print(f"  공지: {len(results)}개")
    print(f"  PDF 저장: {PDF_DIR}/")
    print(f"  전체 데이터: {json_path}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
