#!/usr/bin/env python3
"""검색 테스트 스크립트"""

import requests
import sys
import json

def test_search(api_base: str, token: str, query: str):
    """검색 테스트"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print(f"🔍 질문: {query}\n")
    
    response = requests.post(
        f"{api_base}/",
        json={"message": query},
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"❌ 오류: {response.status_code}")
        print(response.text)
        return
    
    data = response.json()
    
    print("="*60)
    print("답변:")
    print("="*60)
    print(data["answer"])
    print()
    
    print("="*60)
    print(f"출처 ({len(data['sources'])}개):")
    print("="*60)
    
    for idx, source in enumerate(data["sources"], 1):
        print(f"\n[{idx}] {source['uri']}")
        if source.get('section'):
            print(f"    섹션: {source['section']}")
        if source.get('page'):
            print(f"    페이지: {source['page']}")
        print(f"    내용: {source['snippet'][:100]}...")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("사용법: python test_search.py <API_BASE> <TOKEN> <QUERY>")
        print('예시: python test_search.py http://localhost:8000 YOUR_TOKEN "졸업 학점은?"')
        sys.exit(1)
    
    api_base = sys.argv[1]
    token = sys.argv[2]
    query = sys.argv[3]
    
    test_search(api_base, token, query)
