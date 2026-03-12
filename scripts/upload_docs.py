#!/usr/bin/env python3
"""문서 일괄 업로드 스크립트"""

import requests
from pathlib import Path
import sys

def upload_documents(api_base: str, token: str, docs_dir: str):
    """디렉토리의 모든 문서 업로드"""
    docs_path = Path(docs_dir)
    
    if not docs_path.exists():
        print(f"❌ 디렉토리가 없습니다: {docs_dir}")
        return
    
    # 지원 파일 확장자
    extensions = ['.pdf', '.html', '.htm']
    files = []
    
    for ext in extensions:
        files.extend(docs_path.glob(f"**/*{ext}"))
    
    if not files:
        print(f"❌ 업로드할 파일이 없습니다: {docs_dir}")
        return
    
    print(f"📁 {len(files)}개 파일 발견")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    for idx, file_path in enumerate(files, 1):
        print(f"\n[{idx}/{len(files)}] {file_path.name} 업로드 중...")
        
        try:
            with open(file_path, 'rb') as f:
                files_data = {"file": (file_path.name, f)}
                
                response = requests.post(
                    f"{api_base}/upload",
                    files=files_data,
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ 성공: {data['chunks']}개 청크 인덱싱")
                else:
                    print(f"❌ 실패: {response.status_code} - {response.text}")
        
        except Exception as e:
            print(f"❌ 오류: {e}")
    
    print(f"\n✅ 업로드 완료: {len(files)}개 파일")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("사용법: python upload_docs.py <API_BASE> <TOKEN> <DOCS_DIR>")
        print("예시: python upload_docs.py http://localhost:8000 YOUR_TOKEN ./documents")
        sys.exit(1)
    
    api_base = sys.argv[1]
    token = sys.argv[2]
    docs_dir = sys.argv[3]
    
    upload_documents(api_base, token, docs_dir)
