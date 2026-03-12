from bs4 import BeautifulSoup
from typing import Dict, List
import re

class HTMLToMarkdown:
    """HTML을 구조를 살린 Markdown으로 변환"""
    
    def __init__(self):
        self.section_path = []
    
    def parse(self, html_content: str, doc_name: str) -> List[Dict]:
        """HTML을 파싱해서 구조화된 청크 리스트 반환"""
        soup = BeautifulSoup(html_content, 'html.parser')
        chunks = []
        
        # 제목 추출
        title = self._extract_title(soup)
        
        # 본문 섹션별 파싱
        sections = self._parse_sections(soup)
        
        for idx, section in enumerate(sections):
            chunk = {
                'content': section['markdown'],
                'metadata': {
                    'doc_name': doc_name,
                    'section_path': section['path'],
                    'chunk_index': idx,
                    'has_table': section['has_table'],
                    'title': title
                }
            }
            chunks.append(chunk)
        
        return chunks
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """문서 제목 추출"""
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text(strip=True)
        
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)
        
        return "제목 없음"
    
    def _parse_sections(self, soup: BeautifulSoup) -> List[Dict]:
        """섹션별로 파싱"""
        sections = []
        current_section = {'markdown': '', 'path': [], 'has_table': False}
        
        # body 내용만 추출
        body = soup.find('body') or soup
        
        for element in body.descendants:
            if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                # 이전 섹션 저장
                if current_section['markdown'].strip():
                    sections.append(current_section.copy())
                
                # 새 섹션 시작
                level = int(element.name[1])
                text = element.get_text(strip=True)
                
                # 섹션 경로 업데이트
                self.section_path = self.section_path[:level-1] + [text]
                
                current_section = {
                    'markdown': f"{'#' * level} {text}\n\n",
                    'path': ' > '.join(self.section_path),
                    'has_table': False
                }
            
            elif element.name == 'p':
                text = element.get_text(strip=True)
                if text:
                    current_section['markdown'] += f"{text}\n\n"
            
            elif element.name == 'table':
                table_md = self._table_to_markdown(element)
                current_section['markdown'] += table_md + "\n\n"
                current_section['has_table'] = True
            
            elif element.name in ['ul', 'ol']:
                list_md = self._list_to_markdown(element)
                current_section['markdown'] += list_md + "\n\n"
            
            elif element.name == 'blockquote':
                text = element.get_text(strip=True)
                if text:
                    current_section['markdown'] += f"> {text}\n\n"
        
        # 마지막 섹션 저장
        if current_section['markdown'].strip():
            sections.append(current_section)
        
        return sections
    
    def _table_to_markdown(self, table) -> str:
        """HTML 테이블을 Markdown 테이블로 변환"""
        rows = []
        
        # 헤더 추출
        thead = table.find('thead')
        if thead:
            header_row = thead.find('tr')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
                rows.append('| ' + ' | '.join(headers) + ' |')
                rows.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
        
        # 본문 추출
        tbody = table.find('tbody') or table
        for tr in tbody.find_all('tr'):
            cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
            if cells:
                rows.append('| ' + ' | '.join(cells) + ' |')
        
        return '\n'.join(rows)
    
    def _list_to_markdown(self, list_element) -> str:
        """리스트를 Markdown으로 변환"""
        lines = []
        is_ordered = list_element.name == 'ol'
        
        for idx, li in enumerate(list_element.find_all('li', recursive=False), 1):
            text = li.get_text(strip=True)
            if is_ordered:
                lines.append(f"{idx}. {text}")
            else:
                lines.append(f"- {text}")
        
        return '\n'.join(lines)
