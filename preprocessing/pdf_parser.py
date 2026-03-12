import pdfplumber
from typing import Dict, List
import re

class PDFToMarkdown:
    """PDF를 구조를 살린 Markdown으로 변환"""
    
    def parse(self, pdf_path: str, doc_name: str) -> List[Dict]:
        """PDF를 파싱해서 구조화된 청크 리스트 반환 (메모리 절약형)
        1GB 메모리 환경(t3.micro)에서도 1000페이지 PDF 처리 가능"""
        chunks = []

        # 먼저 총 페이지 수만 확인
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)

        # 50페이지씩 나눠서 처리 (메모리 절약)
        batch_size = 50
        for start in range(0, total_pages, batch_size):
            end = min(start + batch_size, total_pages)

            with pdfplumber.open(pdf_path, pages=list(range(start, end))) as pdf:
                for idx, page in enumerate(pdf.pages):
                    page_num = start + idx + 1

                    text = page.extract_text() or ""
                    tables = page.extract_tables()
                    section_path = self._extract_section_path(text)

                    markdown_content = text
                    if tables:
                        for table in tables:
                            table_md = self._table_to_markdown(table)
                            markdown_content += f"\n\n{table_md}\n\n"

                    if markdown_content.strip():
                        chunks.append({
                            'content': markdown_content,
                            'metadata': {
                                'doc_name': doc_name,
                                'section_path': section_path,
                                'page': page_num,
                                'has_table': len(tables) > 0,
                                'total_pages': total_pages
                            }
                        })

            # 배치 간 메모리 해제
            import gc
            gc.collect()

        return chunks
    
    def _extract_section_path(self, text: str) -> str:
        """텍스트에서 섹션 경로 추출 (제1장, 제1조 등)"""
        patterns = [
            r'제\s*(\d+)\s*장[:\s]+([^\n]+)',
            r'제\s*(\d+)\s*조[:\s]+([^\n]+)',
            r'제\s*(\d+)\s*절[:\s]+([^\n]+)',
        ]
        
        sections = []
        for pattern in patterns:
            matches = re.findall(pattern, text[:500])  # 앞부분만 검색
            if matches:
                for match in matches[:1]:  # 첫 번째만
                    sections.append(f"제{match[0]}장: {match[1].strip()}")
        
        return ' > '.join(sections) if sections else "본문"
    
    def _table_to_markdown(self, table: List[List]) -> str:
        """PDF 테이블을 Markdown 테이블로 변환"""
        if not table or not table[0]:
            return ""
        
        rows = []
        
        # 헤더
        header = table[0]
        rows.append('| ' + ' | '.join(str(cell or '') for cell in header) + ' |')
        rows.append('| ' + ' | '.join(['---'] * len(header)) + ' |')
        
        # 본문
        for row in table[1:]:
            if row:
                rows.append('| ' + ' | '.join(str(cell or '') for cell in row) + ' |')
        
        return '\n'.join(rows)
