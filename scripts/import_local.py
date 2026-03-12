"""로컬 uploads 폴더의 PDF 파일을 고속 인덱싱하는 스크립트
- 파싱+청킹을 먼저 전부 수행 (CPU 작업, 빠름)
- 임베딩+인덱싱을 배치로 처리 (API 호출, rate limit 관리)
"""
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
BATCH_SIZE = 14       # 배치당 청크 수 (Gemini 분당 15회 제한)
BATCH_WAIT = 62       # 배치 간 대기 시간 (초)

def find_pdfs(directory):
    pdfs = []
    for root, dirs, files in os.walk(directory):
        for f in files:
            if f.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, f))
    return pdfs

def main():
    pdf_files = find_pdfs(UPLOAD_DIR)
    print(f"📄 PDF 파일 {len(pdf_files)}개 발견\n")

    if not pdf_files:
        print("처리할 PDF 파일이 없습니다.")
        return

    pdf_parser = PDFToMarkdown()
    chunker = SemanticChunker(
        chunk_size=settings.chunk_size,
        overlap=settings.chunk_overlap
    )

    # ========== 1단계: 전체 파싱 + 청킹 (CPU 작업, 빠름) ==========
    print("=" * 60)
    print("1단계: 전체 PDF 파싱 + 청킹")
    print("=" * 60)

    all_chunks = []
    for i, filepath in enumerate(pdf_files):
        filename = os.path.basename(filepath)
        print(f"[{i+1}/{len(pdf_files)}] {filename} 파싱 중...")

        try:
            sections = pdf_parser.parse(filepath, filename)
            file_chunks = []
            for section in sections:
                sub_chunks = chunker.chunk(section["content"], section["metadata"])
                file_chunks.extend(sub_chunks)

            # 각 청크에 UUID 부여
            for chunk in file_chunks:
                chunk["id"] = str(uuid.uuid4())

            all_chunks.extend(file_chunks)
            print(f"  ✅ {len(sections)}페이지 → {len(file_chunks)}청크")
        except Exception as e:
            print(f"  ❌ 파싱 실패: {e}")
            continue

    print(f"\n📊 파싱 완료: 총 {len(all_chunks)}개 청크")
    if not all_chunks:
        print("인덱싱할 청크가 없습니다.")
        return

    # ========== 2단계: 배치 임베딩 + 인덱싱 ==========
    print(f"\n{'=' * 60}")
    print(f"2단계: 배치 임베딩 + 인덱싱 ({len(all_chunks)}개 청크)")
    print(f"배치 크기: {BATCH_SIZE}, 배치 간 대기: {BATCH_WAIT}초")
    total_batches = (len(all_chunks) + BATCH_SIZE - 1) // BATCH_SIZE
    est_minutes = total_batches * BATCH_WAIT / 60
    print(f"예상 배치 수: {total_batches}, 예상 소요 시간: ~{est_minutes:.0f}분")
    print("=" * 60)

    search_engine = FreeHybridSearch()
    search_engine.init_collections()

    indexed = 0
    start_time = time.time()

    for batch_idx in range(0, len(all_chunks), BATCH_SIZE):
        batch = all_chunks[batch_idx:batch_idx + BATCH_SIZE]
        batch_num = batch_idx // BATCH_SIZE + 1

        try:
            search_engine.index_chunks_batch(batch)
            indexed += len(batch)
            elapsed = time.time() - start_time
            rate = indexed / elapsed * 60 if elapsed > 0 else 0
            remaining = (len(all_chunks) - indexed) / rate if rate > 0 else 0
            print(f"  배치 {batch_num}/{total_batches}: "
                  f"{indexed}/{len(all_chunks)} 완료 "
                  f"({indexed*100//len(all_chunks)}%) "
                  f"[{rate:.1f}청크/분, 남은시간: ~{remaining:.0f}분]")
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "quota" in err_str.lower():
                print(f"  ⚠️ rate limit 도달, 90초 대기...")
                time.sleep(90)
                try:
                    search_engine.index_chunks_batch(batch)
                    indexed += len(batch)
                    print(f"  ✅ 재시도 성공")
                except Exception as e2:
                    print(f"  ❌ 재시도 실패: {e2}")
            else:
                print(f"  ❌ 배치 실패: {e}")

        # 마지막 배치가 아니면 대기
        if batch_idx + BATCH_SIZE < len(all_chunks):
            time.sleep(BATCH_WAIT)

    search_engine.close()
    total_time = time.time() - start_time
    print(f"\n🎉 완료! {indexed}/{len(all_chunks)}개 청크 인덱싱")
    print(f"⏱️  총 소요 시간: {total_time/60:.1f}분")

if __name__ == "__main__":
    main()
