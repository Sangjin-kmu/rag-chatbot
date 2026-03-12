"""로컬 uploads 폴더의 PDF 파일을 고속 인덱싱 (메모리 절약형)
- 파일 단위로 파싱→청킹→인덱싱 (한 파일 끝나면 메모리 해제)
- 배치 임베딩 + rate limit 자동 관리
"""
import os
import uuid
import time
import gc
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search.free_hybrid_search import FreeHybridSearch
from preprocessing.pdf_parser import PDFToMarkdown
from preprocessing.chunker import SemanticChunker
from config import settings

UPLOAD_DIR = "uploads"
BATCH_SIZE = 14       # Gemini 무료: 14, 유료 Tier1: 100
BATCH_WAIT = 62       # Gemini 무료: 62, 유료 Tier1: 5

def find_pdfs(directory):
    pdfs = []
    for root, dirs, files in os.walk(directory):
        for f in files:
            if f.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, f))
    return pdfs

def index_batch(search_engine, batch):
    """배치 인덱싱 + rate limit 재시도"""
    retry = 0
    while retry < 3:
        try:
            search_engine.index_chunks_batch(batch)
            return True
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                retry += 1
                wait = 90 * retry
                print(f"    ⚠️ rate limit, {wait}초 대기 (재시도 {retry}/3)")
                time.sleep(wait)
            else:
                print(f"    ❌ 실패: {e}")
                return False
    return False

def main():
    pdf_files = find_pdfs(UPLOAD_DIR)
    print(f"📄 PDF 파일 {len(pdf_files)}개 발견")
    if not pdf_files:
        return

    search_engine = FreeHybridSearch()
    search_engine.init_collections()
    pdf_parser = PDFToMarkdown()
    chunker = SemanticChunker(
        chunk_size=settings.chunk_size,
        overlap=settings.chunk_overlap
    )

    total_indexed = 0
    start_time = time.time()

    for i, filepath in enumerate(pdf_files):
        filename = os.path.basename(filepath)
        print(f"\n[{i+1}/{len(pdf_files)}] {filename}")

        # 파싱
        try:
            sections = pdf_parser.parse(filepath, filename)
            print(f"  📝 {len(sections)}페이지 파싱 완료")
        except Exception as e:
            print(f"  ❌ 파싱 실패: {e}")
            continue

        # 청킹
        file_chunks = []
        for section in sections:
            sub = chunker.chunk(section["content"], section["metadata"])
            file_chunks.extend(sub)
        # 섹션 메모리 해제
        del sections
        gc.collect()

        print(f"  🔪 {len(file_chunks)}개 청크")

        # UUID 부여
        for c in file_chunks:
            c["id"] = str(uuid.uuid4())

        # 배치 인덱싱
        file_indexed = 0
        for batch_idx in range(0, len(file_chunks), BATCH_SIZE):
            batch = file_chunks[batch_idx:batch_idx + BATCH_SIZE]

            if index_batch(search_engine, batch):
                file_indexed += len(batch)
                total_indexed += len(batch)
                elapsed = time.time() - start_time
                rate = total_indexed / elapsed * 60 if elapsed > 0 else 0
                print(f"    {file_indexed}/{len(file_chunks)} "
                      f"(전체 {total_indexed}, {rate:.0f}청크/분)")

            # 마지막 배치가 아니면 대기
            if batch_idx + BATCH_SIZE < len(file_chunks):
                time.sleep(BATCH_WAIT)

        # 파일 처리 끝나면 메모리 해제
        del file_chunks
        gc.collect()
        print(f"  ✅ 완료")

    search_engine.close()
    total_time = time.time() - start_time
    print(f"\n🎉 완료! {total_indexed}개 청크 인덱싱, {total_time/60:.1f}분 소요")

if __name__ == "__main__":
    main()
