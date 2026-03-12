from typing import List, Dict
import openai
from config import settings

class AnswerGenerator:
    """근거 기반 답변 생성"""
    
    def __init__(self):
        openai.api_key = settings.openai_api_key
    
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

        user_prompt = f"""질문: {query}

참고 문서:
{context_text}

위 문서를 바탕으로 질문에 답변해주세요."""

        if history:
            user_prompt = f"이전 대화:\n{history}\n\n{user_prompt}"
        
        # GPT 호출
        response = openai.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=1000
        )
        
        answer = response.choices[0].message.content
        
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
        """출처 정보 구성"""
        sources = []
        
        for ctx in contexts:
            metadata = ctx['metadata']
            
            source = {
                "uri": metadata.get('doc_name', '알 수 없음'),
                "page": metadata.get('page'),
                "section": metadata.get('section_path', ''),
                "snippet": ctx['content'][:200] + "..." if len(ctx['content']) > 200 else ctx['content'],
                "has_table": metadata.get('has_table', False)
            }
            
            sources.append(source)
        
        return sources
