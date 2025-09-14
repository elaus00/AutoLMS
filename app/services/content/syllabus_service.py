import logging
from typing import Dict, Any, Optional

# from sqlalchemy removed

from app.services.base_service import BaseService
from app.services.session.eclass_session_manager import EclassSessionManager
from app.services.parsers.syllabus_parser import SyllabusParser
from app.db.repositories.syllabus_repository import SyllabusRepository
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

class SyllabusService(BaseService):
    """강의계획서 관련 서비스"""
    
    def __init__(
        self,
        eclass_session: EclassSessionManager,
        syllabus_parser: SyllabusParser,
        syllabus_repository: SyllabusRepository,
        auth_service: AuthService
    ):
        self.eclass_session_service = eclass_session
        self.parser = syllabus_parser
        self.repository = syllabus_repository
        self.auth_service = auth_service
        logger.info("SyllabusService 초기화 완료")
    
    async def initialize(self) -> None:
        """서비스 초기화"""
        logger.info("SyllabusService 시작")
        pass
    
    async def close(self) -> None:
        """서비스 리소스 정리"""
        logger.info("SyllabusService 종료")
        pass
    
    async def get_syllabus_by_course(self, course_id: str) -> Optional[Dict[str, Any]]:
        """
        강의 ID로 강의계획서 조회 (JWT 토큰 기반 시스템용)
        
        Args:
            course_id: 강의 ID
            
        Returns:
            Optional[Dict[str, Any]]: 강의계획서 정보
        """
        logger.info(f"강의 {course_id}의 강의계획서 조회 (JWT 기반)")
        
        try:
            # 데이터베이스에서 강의계획서 조회
            syllabus = await self.repository.get_by_course_id(course_id)
            
            if syllabus:
                logger.info(f"저장된 강의계획서 반환 (course_id: {course_id})")
                return syllabus
            
            logger.info(f"강의계획서가 없음 (course_id: {course_id})")
            return None
            
        except Exception as e:
            logger.error(f"강의계획서 조회 중 오류 발생: {str(e)}")
            return None
    
    async def get_syllabus(
        self, 
        user_id: str, 
        course_id: str, 
        force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        강의계획서 조회
        
        Args:
            user_id: 사용자 ID
            course_id: 강의 ID
            force_refresh: 강제 새로고침 여부
            
        Returns:
            Optional[Dict[str, Any]]: 강의계획서 정보
        """
        logger.info(f"강의 {course_id}의 강의계획서 조회 시작 (user_id: {user_id})")
        
        # 이미 저장된 강의계획서 확인
        if not force_refresh:
            existing_syllabus = await self.repository.get_by_course_id(course_id)
            if existing_syllabus:
                logger.info(f"저장된 강의계획서 반환 (course_id: {course_id})")
                return existing_syllabus if existing_syllabus else None
        
        # 새로운 강의계획서 조회
        try:
            # 이클래스 세션 가져오기
            eclass_session = await self.eclass_session_service.get_session(user_id)
            if not eclass_session:
                logger.error("이클래스 세션을 가져올 수 없음")
                return None

            # 이클래스 ID 조회
            eclass_credentials = await self.auth_service.get_user_eclass_credentials(user_id)
            if not eclass_credentials or not eclass_credentials.get("username"):
                logger.error(f"사용자 {user_id}의 이클래스 계정 정보를 찾을 수 없음")
                return None

            eclass_id = eclass_credentials["username"]

            # 1. 먼저 강의실 접근 (다른 서비스와 동일한 패턴)
            course_main_url = await eclass_session.access_course(course_id)
            if not course_main_url:
                logger.error(f"강의실 접근 실패: {course_id}")
                return None
            
            # 강의실 메인 페이지 방문 (Referer 설정을 위해)
            await eclass_session.get(course_main_url)

            # 2. 강의계획서 페이지 접근 (올바른 URL 사용)
            base_url = "https://eclass.seoultech.ac.kr"
            syllabus_url = f"{base_url}/ilos/st/course/plan_view.acl"
            
            data = {
                'KJKEY': course_id,
                'encoding': 'utf-8'
            }
            
            # Referer를 강의실 메인 페이지로 설정하여 자연스러운 탐색 시뮬레이션
            response = await eclass_session.get(syllabus_url, params=data, referer=course_main_url)
            if not response:
                logger.error(f"강의계획서 페이지 요청 실패 (course_id: {course_id})")
                return None
            
            # 방화벽 차단 체크
            if "Web firewall security policies" in response.text:
                logger.error(f"방화벽에 의해 차단됨 (course_id: {course_id})")
                return None
            
            # 강의계획서 파싱
            syllabus_data = self.parser.parse_syllabus(response.text)
            if not syllabus_data:
                logger.warning(f"강의계획서 파싱 결과 없음 (course_id: {course_id})")
                return None
            
            # DB 스키마에 맞게 데이터 매핑
            syllabus_json = self._map_to_schema(syllabus_data, course_id)
            
            # 저장소에 저장 (course_id 기반 upsert)
            saved_syllabus = await self.repository.upsert(**syllabus_json)
            
            if saved_syllabus:
                logger.info(f"강의계획서 조회 완료 (course_id: {course_id})")
                return saved_syllabus
            else:
                logger.error(f"강의계획서 저장 실패 (course_id: {course_id})")
                return None
            
        except Exception as e:
            logger.error(f"강의계획서 조회 중 오류 발생: {str(e)}")
            return None
    
    async def refresh_syllabus(self, user_id: str, course_id: str) -> Dict[str, Any]:
        """
        강의계획서 새로고침
        
        Args:
            user_id: 사용자 ID
            course_id: 강의 ID

        Returns:
            Dict[str, Any]: 새로고침 결과
        """
        result = {"count": 0, "success": 0, "errors": 0}
        
        try:
            result["count"] = 1
            syllabus = await self.get_syllabus(user_id, course_id, force_refresh=True)
            
            if syllabus:
                result["success"] = 1
            else:
                result["errors"] = 1
                
        except Exception as e:
            logger.error(f"강의계획서 새로고침 중 오류 발생: {str(e)}")
            result["count"] = 1
            result["errors"] = 1
        
        return result
        
    async def refresh_all(self, course_id: str, user_id: str) -> Dict[str, Any]:
        """
        강의계획서 새로고침 (다른 서비스와 형식 통일)
        
        Args:
            course_id: 강의 ID
            user_id: 사용자 ID
            
        Returns:
            Dict[str, Any]: 새로고침 결과
        """
        # refresh_syllabus 메서드를 호출하여 새로고침 작업 수행
        result = await self.refresh_syllabus(user_id, course_id)
        
        # 결과 형식 변환 (다른 서비스와 형식 통일)
        # 'count'/'success' 대신 'count'/'new' 사용
        return {
            "count": result.get("count", 0),
            "new": result.get("success", 0),
            "errors": result.get("errors", 0)
        }
    
    def _map_to_schema(self, syllabus_data: Dict[str, Any], course_id: str) -> Dict[str, Any]:
        """
        파싱된 강의계획서 데이터를 DB 스키마에 맞게 매핑
        
        Args:
            syllabus_data: 파싱된 강의계획서 데이터
            course_id: 강의 ID
            
        Returns:
            Dict[str, Any]: DB 스키마에 맞는 데이터
        """
        basic_info = syllabus_data.get('수업기본정보', {})
        instructor_info = syllabus_data.get('담당교수정보', {})
        course_plan = syllabus_data.get('강의계획', {})
        weekly_plan = syllabus_data.get('주별강의계획', [])
        
        # 새로운 구조화된 스키마에 맞게 모든 필드 매핑
        mapped_data = {
            'course_id': course_id,
            
            # 수업기본정보 관련 필드들
            'course_name': basic_info.get('과목명', basic_info.get('교과목명', None)),
            'course_code': basic_info.get('과목코드', basic_info.get('교과목번호/강좌번호', None)),
            'year_semester': basic_info.get('학기', basic_info.get('년도/학기', basic_info.get('년도-학기', None))),
            'course_type': basic_info.get('이수구분', basic_info.get('과목구분', None)),
            'credits': basic_info.get('학점', None),
            'class_time': basic_info.get('수업시간', basic_info.get('강의시간', None)),
            'department': basic_info.get('소속', basic_info.get('개설학과', None)),
            
            # 담당교수정보 관련 필드들
            'professor_name': instructor_info.get('담당교수', instructor_info.get('교수명', None)),
            'professor_email': instructor_info.get('이메일', instructor_info.get('E-mail', instructor_info.get('EMAIL', None))),
            'phone': instructor_info.get('전화번호', instructor_info.get('연락처', None)),
            'office': instructor_info.get('연구실', instructor_info.get('사무실', None)),
            'office_hours': instructor_info.get('상담시간', instructor_info.get('오피스아워', None)),
            'homepage': instructor_info.get('홈페이지', instructor_info.get('HOMEPAGE', None)),
            
            # 강의계획 관련 필드들
            'course_overview': course_plan.get('강의개요', course_plan.get('과목개요', None)),
            'objectives': course_plan.get('교육목표', course_plan.get('수업목표', None)),
            'learning_outcomes': course_plan.get('학습성과', course_plan.get('핵심역량', None)),
            'textbooks': course_plan.get('교재', course_plan.get('주교재', None)),
            'equipment': course_plan.get('준비물', course_plan.get('수업준비사항', None)),
            'evaluation_method': course_plan.get('평가방법', course_plan.get('성적평가방법', None)),
            
            # 주별강의계획 (jsonb로 유지)
            'weekly_plans': weekly_plan if weekly_plan else None
        }
        
        # None 값과 빈 문자열 정리
        for key, value in mapped_data.items():
            if value == '' or (isinstance(value, str) and value.strip() == ''):
                mapped_data[key] = None
        
        # 매핑된 필드 수 계산 (None이 아닌 구조화된 필드들만)
        structured_fields = [
            'course_name', 'course_code', 'year_semester', 'course_type', 'credits', 'class_time', 'department',
            'professor_name', 'professor_email', 'phone', 'office', 'office_hours', 'homepage',
            'course_overview', 'objectives', 'learning_outcomes', 'textbooks', 'equipment', 'evaluation_method'
        ]
        mapped_count = len([f for f in structured_fields if mapped_data.get(f) is not None])
        
        logger.info(f"스키마 매핑 완료 (course_id: {course_id}): {mapped_count}개 구조화된 필드 매핑됨")
        
        return mapped_data
