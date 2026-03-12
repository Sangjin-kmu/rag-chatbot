"""로컬 uploads 폴더의 PDF 파일을 인덱싱하는 스크립트 (빠른 버전)"""
import os
import uuid
import time
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search.free_hybrid_search import FreeHybridSearch
from preprocessing.pdf_parser import PDFToMarkdown
from preprocessing.chunker import SemanticChunker
from config import settings

UPLOAD_DIR = "uploads"

def find_pdfs(directory):
    pdfs = []
    for root, dirs, files in os.walk(directory):
        for f in files:
            if f.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, f))
    return pdfs

def main():
    pdf_files = find_pdfs(UPLOAD_DIR)
    print(f"📄 PDF 파일 {len(pdf_files)}개 발견")

    if not pdf_files:
        print("처리할 PDF 파일이 없습니다.")
        return

    search_engine = FreeHybridSearch()
    search_engine.init_collections()
    pdf_parser = PDFToMarkdown()
    chunker = SemanticChunker(
        chunk_size=settings.chunk_size,
        overlap=settings.chunk_overlap
    )

    total_chunks = 0
    embed_count = 0  # 분당 임베딩 카운터
    minute_start = time.time()

    for i, filepath in enumerate(pdf_files):
        filename = os.path.basename(filepath)
        print(f"\n[{i+1}/{len(pdf_files)}] {filename}")

        try:
            chunks = pdf_parser.parse(filepath, filename)
            print(f"  📝 파싱: {len(chunks)}개 섹션")
        except Exception as e:
            print(f"  ❌ 파싱 실패: {e}")
            continue

        all_chunks = []
        for chunk in chunks:
            sub_chunks = chunker.chunk(chunk["content"], chunk["metadata"])
            all_chunks.extend(sub_chunks)
        print(f"  🔪 청킹: {len(all_chunks)}개 청크")

        for j, chunk in enumerate(all_chunks):
            # 분당 14회 제한 관리
            embed_count += 1
            if embed_count >= 14:
                elapsed = time.time() - minute_start
                if elapsed < 62:
                    wait = 62 - elapsed
                    print(f"  ⏳ {wait:.0f}초 대기 ({j+1}/{len(all_chunks)})")
                    time.sleep(wait)
                embed_count = 0
                minute_start = time.time()

            chunk_id = str(uuid.uuid4())
            retry = 0
            while retry < 3:
                try:
                    search_engine.index_chunk(
                        chunk_id=chunk_id,
                        content=chunk["content"],
                        metadata=chunk["metadata"]
                    )
                    break
                except Exception as e:
                    retry += 1
                    if "429" in str(e) or "quota" in str(e).lower():
                        print(f"  ⚠️ rate limit, 65초 대기...")
                        time.sleep(65)
                        embed_count = 0
                        minute_start = time.time()
                    else:
                        print(f"  ❌ 실패: {e}")
                        break

        total_chunks += len(all_chunks)
        print(f"  ✅ 완료 (누적 {total_chunks}개)")

    search_engine.close()
    print(f"\n🎉 완료! {len(pdf_files)}개 PDF, {total_chunks}개 청크")

if __name__ == "__main__":
    main()
