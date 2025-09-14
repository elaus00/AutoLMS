from typing import List, Dict, Any
import re
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class SyllabusParser:
    """강의계획서 파싱 클래스"""
    
    def clean_text(self, text: str) -> str:
        """HTML에서 추출한 텍스트 정리"""
        if not text:
            return ""
        # 공백 문자 정리
        text = re.sub(r'\s+', ' ', text.strip())
        # HTML 엔티티 변환
        text = text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>')
        return text
    
    def parse_syllabus(self, html: str) -> Dict[str, Any]:
        try:
            if not html:
                return {}
                
            soup = BeautifulSoup(html, 'html.parser')
            
            # 강의계획서 정보 초기화
            syllabus_info = {
                '수업기본정보': {},
                '담당교수정보': {},
                '강의계획': {},
                '주별강의계획': []
            }
            
            # 실제 HTML 구조 기반 파싱
            # 1. 섹션 div 찾기 (padding-top, font-weight: bold 스타일)
            section_divs = soup.find_all('div', style=lambda value: 
                value and 'padding-top' in value and 'font-weight: bold' in value)
            
            for div in section_divs:
                section_text = self.clean_text(div.text)
                logger.debug(f"찾은 섹션: {section_text}")
                
                # 섹션 구분
                if '[수업기본정보]' in section_text:
                    table = div.find_next_sibling('table')
                    if table:
                        self._parse_basic_info_table(table, syllabus_info['수업기본정보'])
                        
                elif '[담당교수정보]' in section_text:
                    table = div.find_next_sibling('table')
                    if table:
                        self._parse_instructor_info_table(table, syllabus_info['담당교수정보'])
                        
                elif '[강의계획]' in section_text:
                    table = div.find_next_sibling('table')
                    if table:
                        self._parse_course_plan_table(table, syllabus_info['강의계획'])
                        
                elif '[주별강의계획]' in section_text:
                    table = div.find_next_sibling('table')
                    if table:
                        self._parse_weekly_plan_table(table, syllabus_info['주별강의계획'])
            
            logger.info(f"강의계획서 파싱 완료: 수업기본정보 {len(syllabus_info['수업기본정보'])}개, "
                       f"담당교수정보 {len(syllabus_info['담당교수정보'])}개, "
                       f"강의계획 {len(syllabus_info['강의계획'])}개, "
                       f"주별강의계획 {len(syllabus_info['주별강의계획'])}개")
            
            return syllabus_info
            
        except Exception as e:
            logger.error(f"강의계획서 파싱 중 오류 발생: {e}")
            return {}
    
    def _extract_table_info(self, table: BeautifulSoup, info_dict: Dict[str, str]) -> None:
        """테이블 정보 추출"""
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['th', 'td'])
            if len(cells) >= 2:
                key = cells[0].text.strip()
                value = cells[1].text.strip()
                info_dict[key] = value
    
    def _extract_weekly_syllabus(self, table: BeautifulSoup, weekly_syllabus: List[Dict[str, str]]) -> None:
        """주별 강의계획 추출"""
        rows = table.find_all('tr')[1:]  # 헤더 제외
        seen_weeks = set()  # 이미 처리한 주차 추적
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 3:
                week = cols[0].text.strip()
                content = cols[1].text.strip()
                note = cols[2].text.strip()
                
                # 빈 행이거나 이미 처리한 주차라면 건너뜀
                if not (week and content) or week in seen_weeks:
                    continue
                    
                # 주차 기록
                seen_weeks.add(week)
                
                weekly_syllabus.append({
                    '주차': week,
                    '내용': content,
                    '비고': note
                })
    
    def _parse_table_based(self, soup: BeautifulSoup, syllabus_info: Dict[str, Any]) -> None:
        """테이블 기반 파싱 (섹션 구분이 없는 경우)"""
        try:
            # 모든 테이블을 찾아서 정보 추출
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                current_section = None
                
                for row in rows:
                    cells = row.find_all(['th', 'td'])
                    if not cells:
                        continue
                    
                    # 첫 번째 셀의 텍스트로 섹션 판단
                    first_cell_text = cells[0].text.strip()
                    
                    # 섹션 헤더 확인
                    if any(keyword in first_cell_text for keyword in 
                           ['수업기본정보', '담당교수정보', '강의계획', '주별강의계획']):
                        if '수업기본정보' in first_cell_text:
                            current_section = '수업기본정보'
                        elif '담당교수정보' in first_cell_text:
                            current_section = '담당교수정보'
                        elif '강의계획' in first_cell_text:
                            current_section = '강의계획'
                        elif '주별강의계획' in first_cell_text:
                            current_section = '주별강의계획'
                        continue
                    
                    # 데이터 행 처리
                    if len(cells) >= 2 and current_section and current_section != '주별강의계획':
                        key = self.clean_text(first_cell_text)
                        value = self.clean_text(cells[1].text)
                        if key and value:
                            syllabus_info[current_section][key] = value
                    
                    # 주별강의계획 처리
                    elif len(cells) >= 3 and current_section == '주별강의계획':
                        week = self.clean_text(cells[0].text)
                        content = self.clean_text(cells[1].text) 
                        note = self.clean_text(cells[2].text) if len(cells) > 2 else ""
                        
                        if week and content and week not in [item.get('주차', '') for item in syllabus_info['주별강의계획']]:
                            syllabus_info['주별강의계획'].append({
                                '주차': week,
                                '내용': content,
                                '비고': note
                            })
                    
                    # 키-값 쌍으로 된 일반적인 정보 (섹션 미지정 시 수업기본정보로 분류)
                    elif len(cells) >= 2 and not current_section:
                        key = self.clean_text(first_cell_text)
                        value = self.clean_text(cells[1].text)
                        
                        # 키워드를 기반으로 적절한 섹션에 배치
                        if any(keyword in key for keyword in ['교수', '담당', '연락처', '이메일', '상담']):
                            syllabus_info['담당교수정보'][key] = value
                        elif any(keyword in key for keyword in ['평가', '교재', '목표', '개요', '준비물']):
                            syllabus_info['강의계획'][key] = value
                        else:
                            syllabus_info['수업기본정보'][key] = value
                            
            logger.info(f"테이블 기반 파싱 완료: 수업기본정보 {len(syllabus_info['수업기본정보'])}개, 담당교수정보 {len(syllabus_info['담당교수정보'])}개, 강의계획 {len(syllabus_info['강의계획'])}개, 주별강의계획 {len(syllabus_info['주별강의계획'])}개")
            
        except Exception as e:
            logger.error(f"테이블 기반 파싱 중 오류: {e}")
            
    def _parse_basic_info_table(self, table, info_dict: Dict[str, str]) -> None:
        """수업기본정보 테이블 파싱"""
        try:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['th', 'td'])
                
                # 6개 컬럼 구조: th, td, th, td, th, td
                if len(cells) >= 6:
                    # 첫 번째 쌍
                    key1 = self.clean_text(cells[0].text)
                    value1 = self.clean_text(cells[1].text)
                    if key1 and value1:
                        info_dict[key1] = value1
                    
                    # 두 번째 쌍
                    key2 = self.clean_text(cells[2].text)
                    value2 = self.clean_text(cells[3].text)
                    if key2 and value2:
                        info_dict[key2] = value2
                    
                    # 세 번째 쌍
                    key3 = self.clean_text(cells[4].text)
                    value3 = self.clean_text(cells[5].text)
                    if key3 and value3:
                        info_dict[key3] = value3
                        
                # 2개 컬럼 구조: th, td
                elif len(cells) >= 2:
                    key = self.clean_text(cells[0].text)
                    value = self.clean_text(cells[1].text)
                    if key and value:
                        info_dict[key] = value
                        
        except Exception as e:
            logger.error(f"수업기본정보 테이블 파싱 오류: {e}")
    
    def _parse_instructor_info_table(self, table, info_dict: Dict[str, str]) -> None:
        """담당교수정보 테이블 파싱"""
        try:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['th', 'td'])
                
                # 6개 컬럼 구조: th, td, th, td, th, td
                if len(cells) >= 6:
                    # 첫 번째 쌍
                    key1 = self.clean_text(cells[0].text)
                    value1 = self.clean_text(cells[1].text)
                    if key1 and value1:
                        info_dict[key1] = value1
                    
                    # 두 번째 쌍
                    key2 = self.clean_text(cells[2].text)
                    value2 = self.clean_text(cells[3].text)
                    if key2 and value2:
                        info_dict[key2] = value2
                    
                    # 세 번째 쌍
                    key3 = self.clean_text(cells[4].text)
                    value3 = self.clean_text(cells[5].text)
                    if key3 and value3:
                        info_dict[key3] = value3
                        
                # colspan 처리 (HOMEPAGE 같은 경우)
                elif len(cells) >= 2:
                    key = self.clean_text(cells[0].text)
                    value = self.clean_text(cells[1].text)
                    if key:
                        info_dict[key] = value
                        
        except Exception as e:
            logger.error(f"담당교수정보 테이블 파싱 오류: {e}")
    
    def _parse_course_plan_table(self, table, info_dict: Dict[str, str]) -> None:
        """강의계획 테이블 파싱"""
        try:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['th', 'td'])
                
                # 2개 컬럼 구조: th, td
                if len(cells) >= 2:
                    key = self.clean_text(cells[0].text)
                    value = self.clean_text(cells[1].text)
                    
                    # br 태그를 줄바꿈으로 변환
                    if cells[1].find_all('br'):
                        value_parts = []
                        for content in cells[1].contents:
                            if hasattr(content, 'name') and content.name == 'br':
                                value_parts.append('\n')
                            else:
                                value_parts.append(str(content))
                        value = self.clean_text(''.join(value_parts))
                    
                    if key:
                        info_dict[key] = value
                        
        except Exception as e:
            logger.error(f"강의계획 테이블 파싱 오류: {e}")
    
    def _parse_weekly_plan_table(self, table, weekly_list: List[Dict[str, str]]) -> None:
        """주별강의계획 테이블 파싱"""
        try:
            rows = table.find_all('tr')
            
            # 헤더 행 건너뛰기
            data_rows = rows[1:] if len(rows) > 1 else rows
            
            for row in data_rows:
                cells = row.find_all('td')
                
                # 3개 컬럼: 주차, 내용, 비고
                if len(cells) >= 3:
                    week = self.clean_text(cells[0].text)
                    content = self.clean_text(cells[1].text)
                    note = self.clean_text(cells[2].text)
                    
                    # 주차와 내용이 있는 경우만 추가
                    if week and content:
                        weekly_list.append({
                            '주차': week,
                            '내용': content,
                            '비고': note if note else ''
                        })
                        
        except Exception as e:
            logger.error(f"주별강의계획 테이블 파싱 오류: {e}")
