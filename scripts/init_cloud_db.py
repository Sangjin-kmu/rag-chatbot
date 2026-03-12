#!/usr/bin/env python3
"""클라우드 DB 초기화 스크립트"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from search.hybrid_search import HybridSearch
from config import settings

def main():
    print("🔧 클라우드 DB 초기화 시작...")
    
    print(f"📍 Qdrant URL: {settings.qdrant_url}")
    print(f"📍 Elasticsearch URL: {settings.elasticsearch_url}")
    
    try:
        search_engine = HybridSearch()
        
        print("🗑️  기존 컬렉션 삭제...")
        search_engine.delete_all()
        
        print("🆕 새 컬렉션 생성...")
        search_engine.init_collections()
        
        print("✅ 초기화 완료!")
        print("")
        print("다음 단계:")
        print("  1. 문서 업로드: python scripts/upload_docs.py <API_BASE> <TOKEN> <DOCS_DIR>")
        print("  2. 또는 웹 UI에서 업로드: http://your-server:8000/static/index.html")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
