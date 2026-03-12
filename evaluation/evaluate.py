import json
import requests
from typing import List, Dict
from pathlib import Path

class RAGEvaluator:
    """RAG 시스템 평가"""
    
    def __init__(self, api_base: str, token: str):
        self.api_base = api_base
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}"}
    
    def evaluate(self, gold_set_path: str) -> Dict:
        """골드셋으로 평가"""
        with open(gold_set_path, 'r', encoding='utf-8') as f:
            gold_set = json.load(f)
        
        results = {
            "total": len(gold_set),
            "correct": 0,
            "retrieval_success": 0,
            "by_type": {}
        }
        
        for item in gold_set:
            question = item["question"]
            expected = item["answer"]
            q_type = item["type"]
            
            # API 호출
            response = requests.post(
                f"{self.api_base}/",
                json={"message": question},
                headers=self.headers
            )
            
            if response.status_code != 200:
                print(f"❌ API 오류: {question}")
                continue
            
            data = response.json()
            answer = data["answer"]
            sources = data["sources"]
            
            # 검색 성공 여부
            if sources:
                results["retrieval_success"] += 1
            
            # 답변 정확도 (간단한 포함 여부 체크)
            if expected is None:
                # 답변 불가형
                if "찾을 수 없" in answer or "모른" in answer:
                    results["correct"] += 1
                    print(f"✅ {q_type}: {question}")
                else:
                    print(f"❌ {q_type}: {question} (환각 발생)")
            else:
                if expected in answer:
                    results["correct"] += 1
                    print(f"✅ {q_type}: {question}")
                else:
                    print(f"❌ {q_type}: {question}")
                    print(f"   기대: {expected}")
                    print(f"   실제: {answer[:100]}")
            
            # 타입별 집계
            if q_type not in results["by_type"]:
                results["by_type"][q_type] = {"total": 0, "correct": 0}
            
            results["by_type"][q_type]["total"] += 1
            if expected is None:
                if "찾을 수 없" in answer or "모른" in answer:
                    results["by_type"][q_type]["correct"] += 1
            else:
                if expected in answer:
                    results["by_type"][q_type]["correct"] += 1
        
        # 결과 출력
        print("\n" + "="*50)
        print("평가 결과")
        print("="*50)
        print(f"전체 정확도: {results['correct']}/{results['total']} ({results['correct']/results['total']*100:.1f}%)")
        print(f"검색 성공률: {results['retrieval_success']}/{results['total']} ({results['retrieval_success']/results['total']*100:.1f}%)")
        
        print("\n타입별 정확도:")
        for q_type, stats in results["by_type"].items():
            acc = stats["correct"] / stats["total"] * 100
            print(f"  {q_type}: {stats['correct']}/{stats['total']} ({acc:.1f}%)")
        
        return results

if __name__ == "__main__":
    # 사용 예시
    evaluator = RAGEvaluator(
        api_base="http://localhost:8000",
        token="YOUR_TOKEN_HERE"
    )
    
    results = evaluator.evaluate("evaluation/gold_set.json")
