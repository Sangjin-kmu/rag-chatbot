import tiktoken
from typing import List, Dict

class SemanticChunker:
    """의미 단위 기반 청킹 (토큰 기반)"""
    
    def __init__(self, chunk_size: int = 550, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.encoder = tiktoken.encoding_for_model("gpt-4")
    
    def chunk(self, content: str, metadata: Dict) -> List[Dict]:
        """텍스트를 청크로 분할"""
        
        # 표가 있으면 의미 단위 우선
        if metadata.get('has_table'):
            return self._chunk_with_structure(content, metadata)
        
        # 일반 텍스트는 토큰 기반
        return self._chunk_by_tokens(content, metadata)
    
    def _chunk_by_tokens(self, content: str, metadata: Dict) -> List[Dict]:
        """토큰 기반 청킹"""
        tokens = self.encoder.encode(content)
        chunks = []
        
        start = 0
        chunk_idx = 0
        
        while start < len(tokens):
            end = start + self.chunk_size
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoder.decode(chunk_tokens)
            
            chunks.append({
                'content': chunk_text,
                'metadata': {
                    **metadata,
                    'chunk_index': chunk_idx,
                    'token_count': len(chunk_tokens)
                }
            })
            
            start += self.chunk_size - self.overlap
            chunk_idx += 1
        
        return chunks
    
    def _chunk_with_structure(self, content: str, metadata: Dict) -> List[Dict]:
        """구조 기반 청킹 (표, 조항 등)"""
        chunks = []
        
        # 표 단위로 분리
        parts = content.split('\n\n')
        current_chunk = ""
        chunk_idx = 0
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # 표인지 확인
            is_table = part.startswith('|') and '---' in part
            
            # 현재 청크 + 새 파트의 토큰 수
            test_content = current_chunk + "\n\n" + part if current_chunk else part
            token_count = len(self.encoder.encode(test_content))
            
            # 토큰 초과하거나 표가 나오면 청크 분리
            if token_count > self.chunk_size or (is_table and current_chunk):
                if current_chunk:
                    chunks.append({
                        'content': current_chunk,
                        'metadata': {
                            **metadata,
                            'chunk_index': chunk_idx,
                            'token_count': len(self.encoder.encode(current_chunk))
                        }
                    })
                    chunk_idx += 1
                current_chunk = part
            else:
                current_chunk = test_content
        
        # 마지막 청크
        if current_chunk:
            chunks.append({
                'content': current_chunk,
                'metadata': {
                    **metadata,
                    'chunk_index': chunk_idx,
                    'token_count': len(self.encoder.encode(current_chunk))
                }
            })
        
        return chunks
