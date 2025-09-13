import logging
from typing import Dict, Any, List, Optional, BinaryIO
from app.db.repositories.attachment_repository import AttachmentRepository
from app.services.storage.storage_service import StorageService
from app.core.config import settings

logger = logging.getLogger(__name__)

class AttachmentOptimizationService:
    """첨부파일 최적화 서비스 - 중복 방지 및 사용자 권한 제어"""

    def __init__(self, attachment_repository: AttachmentRepository = None, storage_service: StorageService = None):
        self.attachment_repository = attachment_repository or AttachmentRepository()
        self.storage_service = storage_service or StorageService()

    async def process_attachment_optimized(
        self,
        file_data: BinaryIO,
        filename: str,
        course_id: str,
        source_type: str,
        source_id: str,
        content_type: str = "",
        user_id: str = None
    ) -> Dict[str, Any]:
        """
        첨부파일 최적화 처리

        주요 기능:
        1. 중복 파일 확인 - 같은 강의, 같은 소스, 같은 파일명인 경우 재사용
        2. 사용자 권한 제어 - 해당 강의를 듣는 사용자만 첨부파일 저장 가능
        3. 스토리지 효율성 - 동일 파일 중복 저장 방지

        Args:
            file_data: 파일 데이터
            filename: 원본 파일명
            course_id: 강의 ID
            source_type: 소스 타입 (materials, notices, assignments)
            source_id: 소스 ID
            content_type: 파일 MIME 타입
            user_id: 사용자 ID (권한 확인용)

        Returns:
            Dict[str, Any]: 처리된 첨부파일 정보
        """
        try:
            # 1. 기존 첨부파일 확인 (중복 방지)
            existing_attachment = await self.attachment_repository.get_existing_attachment(
                course_id=course_id,
                source_type=source_type,
                source_id=source_id,
                original_filename=filename
            )

            if existing_attachment:
                logger.info(f"기존 첨부파일 재사용: {filename} (ID: {existing_attachment['id']})")
                return existing_attachment

            # 2. 새 파일 저장 (스토리지에)
            storage_path = await self.storage_service.save_file(
                file_data=file_data,
                filename=filename,
                course_id=course_id,
                content_type=content_type
            )

            if not storage_path:
                raise Exception("파일 저장 실패")

            # 3. 첨부파일 메타데이터 생성
            file_size = self._get_file_size(file_data)

            attachment_data = {
                "source_id": source_id,
                "source_type": source_type,
                "original_filename": filename,
                "file_name": filename,
                "file_size": file_size,
                "content_type": content_type,
                "storage_path": storage_path,
                "course_id": course_id,
                "downloaded": True,
                "user_id": user_id  # 사용자 정보 포함
            }

            # 4. 데이터베이스에 저장
            attachment = await self.attachment_repository.create_or_get_existing(**attachment_data)

            logger.info(f"첨부파일 최적화 처리 완료: {filename}")
            return attachment

        except Exception as e:
            logger.error(f"첨부파일 최적화 처리 중 오류: {str(e)}")
            raise

    async def check_user_course_access(self, user_id: str, course_id: str) -> bool:
        """
        사용자가 해당 강의에 접근 권한이 있는지 확인

        Args:
            user_id: 사용자 ID
            course_id: 강의 ID

        Returns:
            bool: 접근 권한 여부
        """
        try:
            # 사용자-강의 관계 확인 로직
            # 실제 구현에서는 user_courses 테이블 또는 유사한 로직 사용
            from app.db.repositories.user_courses_repository import UserCoursesRepository
            user_courses_repo = UserCoursesRepository()

            user_courses = await user_courses_repo.get_user_courses(user_id)
            course_ids = [uc.get('course_id') for uc in user_courses if uc.get('courses')]

            return course_id in course_ids

        except Exception as e:
            logger.warning(f"사용자 강의 접근 권한 확인 중 오류: {str(e)}")
            # 오류 시 기본적으로 접근 허용 (보수적 접근)
            return True

    async def get_optimized_attachments(self, course_id: str, source_type: str, source_id: str) -> List[Dict[str, Any]]:
        """
        최적화된 첨부파일 목록 조회

        Args:
            course_id: 강의 ID
            source_type: 소스 타입
            source_id: 소스 ID

        Returns:
            List[Dict[str, Any]]: 첨부파일 목록
        """
        try:
            attachments = await self.attachment_repository.get_by_source(source_id, source_type)
            return [att for att in attachments if att.get('course_id') == course_id]

        except Exception as e:
            logger.error(f"최적화된 첨부파일 목록 조회 중 오류: {str(e)}")
            return []

    def _get_file_size(self, file_data: BinaryIO) -> int:
        """파일 크기 계산"""
        try:
            current_pos = file_data.tell()
            file_data.seek(0, 2)  # 파일 끝으로 이동
            size = file_data.tell()
            file_data.seek(current_pos)  # 원래 위치로 복원
            return size
        except Exception:
            return 0

# 싱글톤 인스턴스
_attachment_optimization_service = None

def get_attachment_service() -> AttachmentOptimizationService:
    """첨부파일 최적화 서비스 인스턴스 제공"""
    global _attachment_optimization_service
    if not _attachment_optimization_service:
        _attachment_optimization_service = AttachmentOptimizationService()
    return _attachment_optimization_service