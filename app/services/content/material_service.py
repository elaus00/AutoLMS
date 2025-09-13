import logging
import re
from typing import Dict, Any, List, Optional

from app.services.auth_service import AuthService
from app.services.base_service import BaseService
from app.services.session import EclassSessionManager
from app.services.parsers.material_parser import MaterialParser
from app.services.storage.storage_service import StorageService
from app.db.repositories.material_repository import MaterialRepository
from app.db.repositories.attachment_repository import AttachmentRepository

logger = logging.getLogger(__name__)

class MaterialService(BaseService):
    """강의자료 서비스"""
    def __init__(
            self,
            eclass_session: EclassSessionManager,
            material_parser: MaterialParser,
            material_repository: MaterialRepository,
            attachment_repository: AttachmentRepository,
            storage_service: StorageService,
            auth_service: AuthService
    ):
        # BaseService에는 __init__이 없으므로 super() 호출 제거
        # 모든 필요한 속성들을 직접 설정
        self.session_service = eclass_session
        self.parser = material_parser
        self.repository = material_repository
        self.auth_service = auth_service
        self.attachment_repository = attachment_repository
        self.storage_service = storage_service
    
    async def initialize(self) -> None:
        """서비스 초기화"""
        logger.info("MaterialService 초기화 시작")
        
        # 필요한 초기화 작업 수행
        if hasattr(self.storage_service, 'initialize'):
            await self.storage_service.initialize()
        
        logger.info("MaterialService 초기화 완료")
    
    async def close(self) -> None:
        """서비스 리소스 정리"""
        logger.info("MaterialService 리소스 정리 시작")
        
        # 필요한 정리 작업 수행
        if hasattr(self.storage_service, 'close'):
            await self.storage_service.close()
        
        logger.info("MaterialService 리소스 정리 완료")

    async def refresh_all(
        self, 
        course_id: str, 
        user_id: str, 
        auto_download: bool = False
    ) -> Dict[str, Any]:
        """
        특정 강의의 강의자료 새로고침
        
        Args:
            course_id: 강의 ID
            user_id: 사용자 ID
            auto_download: 첨부파일 자동 다운로드 여부
            
        Returns:
            Dict[str, Any]: 새로고침 결과
        """
        result = {"count": 0, "new": 0, "errors": 0}
        
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
            
            # 3. 강의자료 목록 페이지 접근
            base_url = "https://eclass.seoultech.ac.kr"
            material_url = f"{base_url}/ilos/st/course/lecture_material_list.acl"
            
            data = {
                'KJKEY': course_id,
                'start': '1',
                'display': '100',
                'SCH_VALUE': '',
                'encoding': 'utf-8'
            }
            
            # Referer를 강의실 메인 페이지로 설정하여 자연스러운 탐색 시뮬레이션
            response = await eclass_session.get(material_url, params=data, referer=course_main_url)
            if not response:
                logger.error("강의자료 목록 요청 실패")
                result["errors"] += 1
                return result
            
            # 3. 목록 파싱
            materials = self.parser.parse_list(response.text)
            if not materials:
                logger.info(f"강의 {course_id}의 강의자료가 없습니다.")
                return result
            
            # 4. 각 강의자료 처리 (DB 레벨 중복 체크로 대체)
            for material in materials:
                result["count"] += 1
                article_id = material.get("article_id")
                
                if not article_id:
                    result["errors"] += 1
                    continue
                
                try:
                    
                    # 상세 페이지 요청
                    detail_url = material.get("url")
                    detail_response = await eclass_session.get(detail_url)
                    if not detail_response:
                        logger.error(f"강의자료 상세 정보 요청 실패: {article_id}")
                        result["errors"] += 1
                        continue
                    
                    # 상세 정보 파싱 (AJAX 요청 포함)
                    material_detail = await self.parser.parse_detail_with_attachments(
                        eclass_session, 
                        detail_response.text, 
                        course_id
                    )
                    
                    # 기본 필드 정보 병합
                    material.update(material_detail)
                    
                    # DB 저장
                    material_data = {
                        'user_id': user_id,  # 필수 필드 추가
                        'material_id': article_id, 
                        'course_id': course_id,
                        'title': material.get('title'),
                        'content': material_detail.get('content', ''),
                        'author': material.get('author'),
                        'date': material.get('date'),
                        'views': material.get('views')
                    }
                    
                    upserted_material = await self.repository.upsert(**material_data)
                    if upserted_material:
                        result["new"] += 1
                    
                    # 첨부파일 처리
                    if auto_download and material.get("attachments"):
                        attachment_count = await self._process_attachments(
                            eclass_session,
                            material["attachments"],
                            upserted_material.get('id'),
                            course_id
                        )
                        logger.info(f"처리된 첨부파일 수: {attachment_count}")
                    
                except Exception as e:
                    logger.error(f"강의자료 {article_id} 처리 중 오류: {str(e)}")
                    result["errors"] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"강의자료 크롤링 중 오류 발생: {str(e)}")
            result["errors"] += 1
            return result

    async def _process_attachments(
            self,
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

                # 파일명 정리 (sanitize)
                safe_file_name = self.sanitize_filename(file_name)

                logger.info(f"첨부파일 처리 시작: {file_name} -> {safe_file_name}")

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

                # 스토리지에 업로드 (안전한 파일명 사용)
                storage_path = await self.storage_service.upload_file(
                    file_content,
                    safe_file_name,
                    course_id,
                    "materials"  # 콘텐츠 타입
                )

                if not storage_path:
                    logger.error(f"파일 업로드 실패: {file_name}")
                    continue

                logger.info(f"파일 업로드 완료: {storage_path}")

                # 첨부파일 메타데이터 저장 (원본 파일명과 안전한 파일명 모두 저장)
                attachment_data = {
                    "source_type": "materials",
                    "source_id": str(source_id),
                    "file_name": safe_file_name,  # 실제 저장된 파일명
                    # "original_file_name": file_name,  # 원본 파일명 (표시용)
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

    async def get_materials_by_course(self, course_id: str, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """
        특정 강의의 모든 강의자료 조회
        
        Args:
            course_id: 강의 ID
            skip: 건너뛸 개수
            limit: 제한 개수
            
        Returns:
            List[Dict[str, Any]]: 강의자료 목록
        """
        try:
            materials = await self.repository.get_by_course_id(course_id)
            return materials[skip:skip+limit]
        except Exception as e:
            logger.error(f"강의자료 목록 조회 중 오류: {str(e)}")
            return []

    async def get_material_by_id(self, material_id: str) -> Optional[Dict[str, Any]]:
        """
        ID로 강의자료 조회
        
        Args:
            material_id: 강의자료 ID
            
        Returns:
            Optional[Dict[str, Any]]: 강의자료 정보
        """
        try:
            material = await self.repository.get_by_id(material_id)
            return material
        except Exception as e:
            logger.error(f"강의자료 ID 조회 중 오류: {str(e)}")
            return None

    def sanitize_filename(self, filename: str) -> str:
        """
        Supabase Storage 업로드용 안전한 파일명으로 변환
        - 용량 정보(_1.1MB, _2.5KB 등) 제거
        - 한글, 공백, 특수문자 제거
        - 영문, 숫자, 점, 언더바만 허용
        """
        logger.info(f"원본 파일명: {filename}")
        
        # 1. 용량 정보 제거 - 더 간단하고 안전한 패턴
        # 예: "파일명.pdf (3MB)" -> "파일명.pdf"
        filename = re.sub(r'\s*\(\d+(\.\d+)?(MB|KB|GB|B)\)\s*', '', filename, flags=re.IGNORECASE)
        
        # 2. 끝에 있는 용량 정보 제거
        # 예: "파일명_1.1MB.pdf" -> "파일명.pdf"
        filename = re.sub(r'_\d+(\.\d+)?(MB|KB|GB|B)', '', filename, flags=re.IGNORECASE)
        
        # 3. 공백을 언더바로 변경
        filename = filename.replace(' ', '_')
        
        # 4. 한글, 특수문자 제거 - 영문, 숫자, 점, 언더바, 하이픈만 허용
        filename = re.sub(r'[^0-9A-Za-z._-]', '', filename)
        
        # 5. 연속된 언더바나 점 정리
        filename = re.sub(r'[_.-]{2,}', '_', filename)
        
        # 6. 시작/끝 언더바나 점 제거
        filename = filename.strip('_.-')
        
        # 7. 빈 파일명 방지
        if not filename:
            filename = "unnamed_file"
        
        logger.info(f"정리된 파일명: {filename}")
        return filename