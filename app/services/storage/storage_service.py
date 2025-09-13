import logging
import os
from typing import Optional, BinaryIO, Union

from app.services.base_service import BaseService
from app.core.config import settings

logger = logging.getLogger(__name__)

class StorageService(BaseService):
    """파일 스토리지 서비스"""
    
    def __init__(self):
        self.local_download_dir = settings.DOWNLOAD_DIR
        logger.info("StorageService 초기화 완료")
        
        # Supabase 클라이언트 초기화 (설정된 경우)
        self.supabase = None
        self.bucket_name = settings.SUPABASE_BUCKET
        
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY:
            try:
                from supabase import create_client
                self.supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
                logger.info("Supabase 스토리지 클라이언트 초기화 완료 (Service Key 사용)")
            except Exception as e:
                logger.error(f"Supabase 클라이언트 초기화 중 오류 발생: {str(e)}")
    
    async def initialize(self) -> None:
        """서비스 초기화"""
        logger.info("StorageService 시작")
        # 로컬 디렉토리 생성
        os.makedirs(self.local_download_dir, exist_ok=True)
    
    async def close(self) -> None:
        """서비스 리소스 정리"""
        logger.info("StorageService 종료")
        pass
    
    async def upload_file(
        self, 
        file_data: Union[bytes, BinaryIO], 
        filename: str, 
        course_id: str, 
        content_type: str
    ) -> str:
        """
        파일을 스토리지에 업로드
        
        Args:
            file_data: 파일 데이터 (바이트)
            filename: 파일 이름
            course_id: 강의 ID
            content_type: 콘텐츠 타입 ('notices', 'materials', 'assignments' 등)
            
        Returns:
            str: 스토리지 경로
        """
        try:
            # 파일 경로 생성
            file_path = f"{course_id}/{content_type}/{filename}"
            
            # Supabase Storage에 업로드
            if self.supabase:
                try:
                    storage = self.supabase.storage.from_(self.bucket_name)
                    
                    # 바이트 데이터인 경우
                    if isinstance(file_data, bytes):
                        response = storage.upload(file_path, file_data)
                    # 파일 객체인 경우
                    else:
                        file_data.seek(0)  # 파일 포인터를 처음으로 이동
                        response = storage.upload(file_path, file_data.read())
                        
                    logger.info(f"파일 '{filename}' 업로드 완료: {file_path}")
                    return file_path
                except Exception as e:
                    logger.error(f"Supabase 업로드 중 오류: {str(e)}")

            # Supabase가 설정되지 않은 경우나 업로드 실패 시 로컬에 저장
            return await self._save_file_locally(file_data, course_id, content_type, filename)
            
        except Exception as e:
            logger.error(f"파일 '{filename}' 업로드 중 오류 발생: {str(e)}")
            # 실패 시 로컬에 저장 시도
            return await self._save_file_locally(file_data, course_id, content_type, filename)
    
    async def _save_file_locally(
        self, 
        file_data: Union[bytes, BinaryIO], 
        course_id: str, 
        content_type: str, 
        filename: str
    ) -> str:
        """
        파일을 로컬에 저장
        
        Args:
            file_data: 파일 데이터
            course_id: 강의 ID
            content_type: 콘텐츠 타입
            filename: 파일 이름
            
        Returns:
            str: 로컬 파일 경로
        """
        try:
            # 저장 디렉토리 생성
            save_dir = os.path.join(self.local_download_dir, course_id, content_type)
            os.makedirs(save_dir, exist_ok=True)
            
            # 파일 저장
            file_path = os.path.join(save_dir, filename)
            
            # 바이트 데이터인 경우
            if isinstance(file_data, bytes):
                with open(file_path, 'wb') as f:
                    f.write(file_data)
            # 파일 객체인 경우
            else:
                file_data.seek(0)  # 파일 포인터를 처음으로 이동
                with open(file_path, 'wb') as f:
                    f.write(file_data.read())
            
            logger.info(f"파일 '{filename}' 로컬 저장 완료: {file_path}")
            
            # 로컬 경로 반환
            return f"local://{course_id}/{content_type}/{filename}"
            
        except Exception as e:
            logger.error(f"파일 '{filename}' 로컬 저장 중 오류 발생: {str(e)}")
            return ""
    
    async def get_file_url(self, storage_path: str) -> Optional[str]:
        """
        파일의 URL 생성
        
        Args:
            storage_path: 스토리지 경로
            
        Returns:
            Optional[str]: 파일 URL
        """
        if not storage_path:
            return None
            
        # 로컬 파일인 경우
        if storage_path.startswith("local://"):
            local_path = storage_path.replace("local://", "")
            full_path = os.path.join(self.local_download_dir, local_path)
            
            if os.path.exists(full_path):
                return f"file://{full_path}"
            else:
                logger.warning(f"로컬 파일을 찾을 수 없음: {full_path}")
                return None
                
        # Supabase Storage 파일인 경우
        try:
            if self.supabase:
                storage = self.supabase.storage.from_(self.bucket_name)
                signed_url = storage.create_signed_url(storage_path, 60 * 60)  # 1시간 유효
                return signed_url['signedURL']
        except Exception as e:
            logger.error(f"서명된 URL 생성 중 오류 발생: {str(e)}")
            
        return None
    
    async def delete_file(self, storage_path: str) -> bool:
        """
        파일 삭제
        
        Args:
            storage_path: 스토리지 경로
            
        Returns:
            bool: 삭제 성공 여부
        """
        if not storage_path:
            return False
            
        # 로컬 파일인 경우
        if storage_path.startswith("local://"):
            try:
                local_path = storage_path.replace("local://", "")
                full_path = os.path.join(self.local_download_dir, local_path)
                
                if os.path.exists(full_path):
                    os.remove(full_path)
                    logger.info(f"로컬 파일 삭제 완료: {full_path}")
                    return True
                else:
                    logger.warning(f"삭제할 로컬 파일을 찾을 수 없음: {full_path}")
                    return False
            except Exception as e:
                logger.error(f"로컬 파일 삭제 중 오류 발생: {str(e)}")
                return False
                
        # Supabase Storage 파일인 경우
        try:
            if self.supabase:
                storage = self.supabase.storage.from_(self.bucket_name)
                storage.remove(storage_path)
                logger.info(f"Supabase 파일 삭제 완료: {storage_path}")
                return True
        except Exception as e:
            logger.error(f"Supabase 파일 삭제 중 오류 발생: {str(e)}")
            
        return False
    
    # SQLAlchemy 의존성이 있는 메서드들은 향후 Supabase repository로 이관 예정
