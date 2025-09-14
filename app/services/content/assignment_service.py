import logging
from typing import List, Dict, Any, Optional

from app.services.base_service import BaseService
from app.services.session import EclassSessionManager
from app.services.parsers.assignment_parser import AssignmentParser
from app.services.storage.storage_service import StorageService
from app.db.repositories.assignment_repository import AssignmentRepository
from app.db.repositories.attachment_repository import AttachmentRepository

logger = logging.getLogger(__name__)

class AssignmentService(BaseService):
    """과제 서비스"""
    
    def __init__(
        self,
        session_service: EclassSessionManager,
        assignment_parser: AssignmentParser,
        assignment_repository: AssignmentRepository,
        attachment_repository: AttachmentRepository,
        storage_service: StorageService
    ):
        self.session_service = session_service
        self.parser = assignment_parser
        self.repository = assignment_repository
        self.attachment_repository = attachment_repository
        self.storage_service = storage_service
        logger.info("AssignmentService 초기화 완료")
    
    async def initialize(self) -> None:
        """서비스 초기화"""
        logger.info("AssignmentService 시작")
        pass

    async def close(self) -> None:
        """서비스 리소스 정리"""
        logger.info("AssignmentService 종료")
        pass


    async def get_assignments(self, user_id: str, course_id: str) -> List[Dict[str, Any]]:
        """
        특정 강의의 과제 목록 조회
        
        Args:
            user_id: 사용자 ID
            course_id: 강의 ID

        Returns:
            List[Assignment]: 과제 목록
        """
        try:
            logger.info(f"사용자 {user_id}의 강의 {course_id} 과제 조회")
            
            # 1. 강의 접근 권한 확인
            from app.core.security import verify_course_access
            await verify_course_access(user_id, course_id)
            
            # 2. 데이터베이스에서 과제 조회
            assignments = await self.repository.get_by_course_id(course_id)
            
            # 3. 과제가 없으면 새로고침 시도
            if not assignments:
                logger.info(f"강의 {course_id}의 과제가 없습니다. 새로고침을 시도합니다.")
                result = await self.refresh_all(course_id, user_id)
                if result["new"] > 0:
                    # 새로고침 후 다시 조회
                    assignments = await self.repository.get_by_course_id(course_id)
            
            # 4. 과제 목록 반환
            logger.info(f"강의 {course_id}의 과제 {len(assignments)}개 반환")
            return assignments
            
        except Exception as e:
            logger.error(f"과제 조회 중 오류: {str(e)}")
            return []
    
    async def get_assignment(self, user_id: str, course_id: str, assignment_id: str) -> Optional[Dict[str, Any]]:
        """
        특정 과제 조회
        
        Args:
            user_id: 사용자 ID
            course_id: 강의 ID
            assignment_id: 과제 ID

        Returns:
            Optional[Assignment]: 과제 정보
        """
        try:
            logger.info(f"사용자 {user_id}의 강의 {course_id}, 과제 {assignment_id} 조회")
            
            # 1. 접근 권한 확인
            from app.core.security import verify_course_access
            await verify_course_access(user_id, course_id)
            
            # 2. 과제 조회
            assignment = await self.repository.get_by_id(assignment_id)
            
            # 3. 과제가 해당 강의에 속하는지 확인
            if not assignment or assignment.course_id != course_id:
                logger.warning(f"강의 {course_id}에 속한 과제 {assignment_id}를 찾을 수 없습니다.")
                return None
            
            # 4. 첨부파일 정보 조회
            # 참고: 메모리 객체의 속성을 추가하는 방식으로 첨부파일 정보를 추가
            # 실제 DB 모델에는 이 필드가 없지만 응답 시 포함됨
            try:
                attachments = await self.attachment_repository.get_by_source(
                    str(assignment.id), "assignments"
                )
                if hasattr(assignment, "attachments"):
                    assignment.attachments = attachments
                else:
                    # DB 모델에 없는 필드를 추가 (객체 메모리에만 존재)
                    setattr(assignment, "attachments", attachments)
            except Exception as e:
                logger.warning(f"첨부파일 정보 조회 중 오류: {str(e)}")
                # 오류가 발생해도 과제 정보는 반환
            
            logger.info(f"과제 {assignment_id} 조회 완료")
            return assignment
            
        except Exception as e:
            logger.error(f"과제 조회 중 오류: {str(e)}")
            return None
    
    async def refresh_all(
        self, 
        course_id: str, 
        user_id: str, 
        auto_download: bool = False
    ) -> Dict[str, Any]:
        """
        특정 강의의 과제 새로고침
        
        Args:
            course_id: 강의 ID
            user_id: 사용자 ID
            auto_download: 첨부파일 자동 다운로드 여부
            
        Returns:
            Dict[str, Any]: 새로고침 결과
        """
        result = {"count": 0, "new": 0, "skipped": 0, "errors": 0}
        
        try:
            # 1. 세션 가져오기
            eclass_session = await self.session_service.get_session(user_id)
            if not eclass_session:
                logger.error(f"이클래스 세션을 가져올 수 없음")
                result["errors"] += 1
                return result
            
            # 2. 먼저 강의실 접근 (자연스러운 탐색 패턴)
            course_main_url = await eclass_session.access_course(course_id)
            if not course_main_url:
                logger.error(f"강의실 접근 실패: {course_id}")
                result["errors"] += 1
                return result
            
            # 강의실 메인 페이지 방문 (Referer 설정을 위해)
            await eclass_session.get(course_main_url)
            
            # 3. 과제 목록 페이지 접근
            base_url = "https://eclass.seoultech.ac.kr"
            assignment_url = f"{base_url}/ilos/st/course/report_list.acl"
            
            data = {
                'KJKEY': course_id,
                'start': '1',
                'display': '100',
                'SCH_VALUE': '',
                'encoding': 'utf-8'
            }
            
            # Referer를 강의실 메인 페이지로 설정하여 자연스러운 탐색 시뮬레이션
            response = await eclass_session.get(assignment_url, params=data, referer=course_main_url)
            if not response:
                logger.error("과제 목록 요청 실패")
                result["errors"] += 1
                return result
            
            # 3. 목록 파싱
            assignments = self.parser.parse_list(response.text)
            if not assignments:
                logger.info(f"강의 {course_id}의 과제가 없습니다.")
                return result
            
            # 4. 각 과제 처리 (서비스 레벨 중복 체크 추가)
            for assignment in assignments:
                result["count"] += 1
                assignment_id = assignment.get("assignment_id")

                if not assignment_id:
                    result["errors"] += 1
                    continue

                # 중복 확인: 이미 DB에 존재하는지 체크
                composite_id = self.repository.generate_composite_id(course_id, assignment_id)
                existing_assignment = await self.repository.get_by_id(composite_id)

                if existing_assignment:
                    logger.debug(f"과제 {assignment_id}는 이미 존재합니다. 건너뛰기")
                    result["skipped"] += 1
                    continue

                try:
                    
                    # 상세 페이지 요청
                    detail_url = assignment.get("url")
                    detail_response = await eclass_session.get(detail_url)
                    if not detail_response:
                        logger.error(f"과제 상세 정보 요청 실패: {assignment_id}")
                        result["errors"] += 1
                        continue
                    
                    # 상세 정보 파싱 (AJAX 요청 포함)
                    assignment_detail = await self.parser.parse_detail_with_attachments(
                        eclass_session, 
                        detail_response.text, 
                        course_id
                    )
                    
                    # 기본 필드 정보 병합
                    assignment.update(assignment_detail)
                    
                    # DB 저장
                    assignment_data = {
                        'assignment_id': assignment_id,
                        'course_id': course_id,
                        'title': assignment.get('title'),
                        'content': assignment_detail.get('content', ''),
                        'start_date': assignment.get('start_date'),
                        'end_date': assignment.get('end_date', assignment_detail.get('due_date')),
                        'status': assignment.get('status', 'active')
                    }
                    
                    upserted_assignment = await self.repository.upsert(**assignment_data)
                    if upserted_assignment:
                        result["new"] += 1
                    
                    # 첨부파일 처리
                    if auto_download and assignment.get("attachments"):
                        attachment_count = await self._process_attachments(
                            user_id,
                            eclass_session,
                            assignment["attachments"],
                            upserted_assignment.get('id'),
                            course_id
                        )
                        logger.info(f"처리된 첨부파일 수: {attachment_count}")
                    
                except Exception as e:
                    logger.error(f"과제 {assignment_id} 처리 중 오류: {str(e)}")
                    result["errors"] += 1

            # 최종 로깅
            logger.info(f"과제 크롤링 완료 - 총 {result['count']}개, 새로운 {result['new']}개, 건너뛴 {result['skipped']}개, 오류 {result['errors']}개")

            return result
            
        except Exception as e:
            logger.error(f"과제 크롤링 중 오류 발생: {str(e)}")
            result["errors"] += 1
            return result

    async def _process_attachments(
            self,
            user_id: str,
            eclass_session,
            attachments: List[Dict[str, Any]],
            source_id: int,
            course_id: str
    ) -> int:
        """
        첨부파일 처리 및 저장

        Args:
            eclass_session: 이클래스 세션 객체
            attachments: 첨부파일 정보 목록
            source_id: 소스(강의자료) ID
            course_id: 강의 ID

        Returns:
            int: 처리된 첨부파일 수
        """
        count = 0

        # 첨부파일 저장소와 스토리지 서비스가 클래스에 없으면 추가
        if not hasattr(self, 'attachment_repository'):
            from app.db.repositories.attachment_repository import AttachmentRepository
            self.attachment_repository = AttachmentRepository()

        if not hasattr(self, 'storage_service'):
            from app.services.storage.storage_service import StorageService
            self.storage_service = StorageService()

        # 각 첨부파일 처리
        for attachment in attachments:
            try:
                # 첨부파일 정보 로깅
                file_name = attachment.get("file_name", "")
                original_url = attachment.get("original_url", "")

                if not file_name or not original_url:
                    logger.warning(f"첨부파일 정보 부족: {attachment}")
                    continue

                logger.info(f"첨부파일 처리 시작: {file_name}")

                # 이클래스에서 파일 다운로드
                try:
                    # GET 요청으로 파일 다운로드
                    download_response = await eclass_session.get(original_url)
                    if not download_response:
                        logger.error(f"파일 다운로드 실패: {file_name}")
                        continue

                    # 파일 내용 추출
                    file_content = download_response.content
                    file_size = len(file_content)

                    if file_size == 0:
                        logger.warning(f"다운로드한 파일 크기가 0입니다: {file_name}")
                        continue

                    logger.info(f"파일 다운로드 완료: {file_name} ({file_size} 바이트)")
                except Exception as e:
                    logger.error(f"파일 다운로드 중 오류: {str(e)}")
                    continue

                # 스토리지에 업로드
                storage_path = await self.storage_service.upload_file(
                    file_content,
                    file_name,
                    course_id,
                    "materials"  # 콘텐츠 타입
                )

                if not storage_path:
                    logger.error(f"파일 업로드 실패: {file_name}")
                    continue

                logger.info(f"파일 업로드 완료: {storage_path}")

                # 첨부파일 메타데이터 저장
                attachment_data = {
                    "source_type": "materials",
                    "source_id": str(source_id),
                    "file_name": file_name,
                    "file_size": file_size,
                    "content_type": attachment.get("content_type", ""),
                    "storage_path": storage_path,
                    "original_url": original_url,
                    "course_id": course_id
                }

                # 데이터베이스에 저장
                await self.attachment_repository.upsert(attachment_data)
                count += 1
                logger.info(f"첨부파일 메타데이터 저장 완료: {file_name}")

            except Exception as e:
                logger.error(f"첨부파일 '{attachment.get('file_name', '알 수 없음')}' 처리 중 오류: {str(e)}")

        return count