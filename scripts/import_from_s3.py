"""S3 버킷에서 PDF 파일을 다운로드하여 RAG DB에 인덱싱하는 스크립트"""
import boto3
import os
import uuid
import time
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search.free_hybrid_search import FreeHybridSearch
from preprocessing.pdf_parser import PDFToMarkdown
from preprocessing.chunker import SemanticChunker
from config import settings

BUCKET = "school-rag-kb-apne2"
PREFIX = "rules/"
DOWNLOAD_DIR = "/tmp/s3_docs"

def main():
    # S3 클라이언트
    s3 = boto3.client("s3", region_name="ap-northeast-2")
    
    # 다운로드 폴더 생성
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    # S3에서 PDF 파일 목록 가져오기
    print("📥 S3에서 파일 목록 가져오는 중...")
    pdf_files = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith(".pdf"):
                pdf_files.append(key)
    
    print(f"📄 PDF 파일 {len(pdf_files)}개 발견")
    
    if not pdf_files:
        print("처리할 PDF 파일이 없습니다.")
        return
    
    # 초기화
    search_engine = FreeHybridSearch()
    search_engine.init_collections()
    pdf_parser = PDFToMarkdown()
    chunker = SemanticChunker(
        chunk_size=settings.chunk_size,
        overlap=settings.chunk_overlap
    )
    
    total_chunks = 0
    
    for i, key in enumerate(pdf_files):
        filename = os.path.basename(key)
        local_path = os.path.join(DOWNLOAD_DIR, filename)
        
        print(f"\n[{i+1}/{len(pdf_files)}] {key}")
        
        # 다운로드
        try:
            s3.download_file(BUCKET, key, local_path)
            print(f"  ✅ 다운로드 완료")
        except Exception as e:
            print(f"  ❌ 다운로드 실패: {e}")
            continue
        
        # 파싱
        try:
            chunks = pdf_parser.parse(local_path, filename)
            print(f"  📝 파싱 완료: {len(chunks)}개 섹션")
        except Exception as e:
            print(f"  ❌ 파싱 실패: {e}")
            continue
        
        # 청킹
        all_chunks = []
        for chunk in chunks:
            sub_chunks = chunker.chunk(chunk["content"], chunk["metadata"])
            all_chunks.extend(sub_chunks)
        print(f"  🔪 청킹 완료: {len(all_chunks)}개 청크")
        
        # 인덱싱 (rate limit 대응: 청크마다 딜레이)
        for j, chunk in enumerate(all_chunks):
            chunk_id = str(uuid.uuid4())
            try:
                search_engine.index_chunk(
                    chunk_id=chunk_id,
                    content=chunk["content"],
                    metadata=chunk["metadata"]
                )
            except Exception as e:
                print(f"  ⚠️ 청크 {j} 인덱싱 실패: {e}")
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
            
            # Gemini 임베딩 rate limit 방지 (분당 15회)
            if (j + 1) % 10 == 0:
                print(f"  ⏳ rate limit 방지 대기 (10청크 처리됨)...")
                time.sleep(65)
        
        total_chunks += len(all_chunks)
        print(f"  ✅ 인덱싱 완료")
        
        # 파일 삭제
        os.remove(local_path)
    
    search_engine.close()
    print(f"\n🎉 완료! 총 {len(pdf_files)}개 PDF, {total_chunks}개 청크 인덱싱됨")

if __name__ == "__main__":
    main()
