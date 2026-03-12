from typing import List, Dict

class SemanticChunker:
    """의미 단위 기반 청킹 (문자 기반)"""
    
    def __init__(self, chunk_size: int = 2000, overlap: int = 400):
        self.chunk_size = chunk_size  # 문자 수
        self.overlap = overlap
    
    def chunk(self, content: str, metadata: Dict) -> List[Dict]:
        """텍스트를 청크로 분할"""
        
        # 표가 있으면 의미 단위 우선
        if metadata.get('has_table'):
            return self._chunk_with_structure(content, metadata)
        
        # 일반 텍스트는 문자 기반
        return self._chunk_by_chars(content, metadata)
    
    def _chunk_by_chars(self, content: str, metadata: Dict) -> List[Dict]:
        """문자 기반 청킹"""
        chunks = []
        start = 0
        chunk_idx = 0
        
        while start < len(content):
            end = start + self.chunk_size
            chunk_text = content[start:end]
            
            chunks.append({
                'content': chunk_text,
                'metadata': {
                    **metadata,
                    'chunk_index': chunk_idx,
                    'char_count': len(chunk_text)
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
            
            # 현재 청크 + 새 파트의 길이
            test_content = current_chunk + "\n\n" + part if current_chunk else part
            
            # 길이 초과하거나 표가 나오면 청크 분리
            if len(test_content) > self.chunk_size or (is_table and current_chunk):
                if current_chunk:
                    chunks.append({
                        'content': current_chunk,
                        'metadata': {
                            **metadata,
                            'chunk_index': chunk_idx,
                            'char_count': len(current_chunk)
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
                    'char_count': len(current_chunk)
                }
            })
        
        return chunks
