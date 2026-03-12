"""로컬 uploads 폴더의 PDF 파일을 인덱싱하는 스크립트"""
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
    """재귀적으로 PDF 파일 찾기"""
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

    for i, filepath in enumerate(pdf_files):
        filename = os.path.basename(filepath)
        print(f"\n[{i+1}/{len(pdf_files)}] {filename}")

        try:
            chunks = pdf_parser.parse(filepath, filename)
            print(f"  📝 파싱 완료: {len(chunks)}개 섹션")
        except Exception as e:
            print(f"  ❌ 파싱 실패: {e}")
            continue

        all_chunks = []
        for chunk in chunks:
            sub_chunks = chunker.chunk(chunk["content"], chunk["metadata"])
            all_chunks.extend(sub_chunks)
        print(f"  🔪 청킹 완료: {len(all_chunks)}개 청크")

        for j, chunk in enumerate(all_chunks):
            chunk_id = str(uuid.uuid4())
            try:
                search_engine.index_chunk(
                    chunk_id=chunk_id,
                    content=chunk["content"],
                    metadata=chunk["metadata"]
                )
            except Exception as e:
                print(f"  ⚠️ 청크 {j} 실패: {e}")
                print("  ⏳ 60초 대기 후 재시도...")
                time.sleep(60)
                try:
                    search_engine.index_chunk(
                        chunk_id=chunk_id,
                        content=chunk["content"],
                        metadata=chunk["metadata"]
                    )
                except Exception as e2:
                    print(f"  ❌ 재시도 실패: {e2}")
                    continue

            if (j + 1) % 10 == 0:
                print(f"  ⏳ rate limit 방지 대기...")
                time.sleep(65)

        total_chunks += len(all_chunks)
        print(f"  ✅ 인덱싱 완료")

    search_engine.close()
    print(f"\n🎉 완료! 총 {len(pdf_files)}개 PDF, {total_chunks}개 청크 인덱싱됨")

if __name__ == "__main__":
    main()
