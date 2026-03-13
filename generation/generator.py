from typing import List, Dict
import google.generativeai as genai
from config import settings

class AnswerGenerator:
    """근거 기반 답변 생성 (Gemini)"""
    
    def __init__(self):
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
    
    def generate(self, query: str, contexts: List[Dict], history: str = "") -> Dict:
        """답변 생성"""
        
        # 컨텍스트 포맷팅
        context_text = self._format_contexts(contexts)
        
        # 프롬프트 구성
        system_prompt = """당신은 국민대학교 학칙 및 학사규정 전문가입니다.

규칙:
1. 주어진 문서 조각만을 근거로 답변하세요
2. 근거가 부족하면 추측하지 말고 "제공된 문서에서 해당 정보를 찾을 수 없습니다"라고 답하세요
3. 숫자, 날짜, 조항은 원문 표현을 그대로 사용하세요
4. 답변 끝에 사용한 문서명과 섹션을 [출처: 문서명 - 섹션] 형식으로 표시하세요
5. 여러 문서를 참고했다면 모두 표시하세요"""

        user_prompt = f"""{system_prompt}

질문: {query}

참고 문서:
{context_text}

위 문서를 바탕으로 질문에 답변해주세요."""

        if history:
            user_prompt = f"이전 대화:\n{history}\n\n{user_prompt}"
        
        # Gemini 호출
        response = self.model.generate_content(user_prompt)
        answer = response.text
        
        # 출처 정보 구성
        sources = self._build_sources(contexts)
        
        return {
            "answer": answer,
            "sources": sources,
            "context_count": len(contexts)
        }
    
    def _format_contexts(self, contexts: List[Dict]) -> str:
        """컨텍스트를 프롬프트용 텍스트로 포맷팅"""
        formatted = []
        
        for idx, ctx in enumerate(contexts, 1):
            metadata = ctx['metadata']
            content = ctx['content']
            
            doc_info = f"[문서 {idx}]"
            doc_info += f"\n문서명: {metadata.get('doc_name', '알 수 없음')}"
            
            if metadata.get('section_path'):
                doc_info += f"\n섹션: {metadata['section_path']}"
            
            if metadata.get('page'):
                doc_info += f"\n페이지: {metadata['page']}"
            
            doc_info += f"\n\n내용:\n{content}\n"
            
            formatted.append(doc_info)
        
        return "\n---\n".join(formatted)
    
    def _build_sources(self, contexts: List[Dict]) -> List[Dict]:
        """출처 정보 구성 — rerank_score 기반 필터링"""
        sources = []
        seen = set()  # 중복 문서 제거
        
        for ctx in contexts:
            metadata = ctx['metadata']
            doc_name = metadata.get('doc_name', '알 수 없음')
            
            # 같은 문서 중복 출처 방지 (페이지가 다르면 허용)
            dedup_key = f"{doc_name}_{metadata.get('page', '')}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            
            source = {
                "uri": doc_name,
                "page": metadata.get('page'),
                "section": metadata.get('section_path', ''),
                "has_table": metadata.get('has_table', False),
                "source_url": metadata.get('source_url', ''),
                "rerank_score": round(ctx.get('rerank_score', 0), 3)
            }
            
            sources.append(source)
        
        return sources
