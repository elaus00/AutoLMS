import logging
from typing import List, Dict, Any, Optional
from supabase import Client, create_client
from app.core.supabase_client import get_supabase_client
from app.core.config import settings

logger = logging.getLogger(__name__)

class AttachmentRepository:
    """Supabase를 사용한 첨부파일 저장소"""

    def __init__(self, use_service_key: bool = False):
        if use_service_key:
            # Service Key 사용 (우회 권한)
            self.supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        else:
            # 일반 클라이언트
            self.supabase: Client = get_supabase_client()
        self.table_name = "attachments"
    
    async def get_by_id(self, attachment_id: str) -> Optional[Dict[str, Any]]:
        """ID로 첨부파일 조회"""
        try:
            result = self.supabase.table(self.table_name)\
                .select("*")\
                .eq("id", attachment_id)\
                .single()\
                .execute()
            
            return result.data
        except Exception as e:
            logger.error(f"첨부파일 ID 조회 오류: {e}")
            return None
    
    async def get_all(self) -> List[Dict[str, Any]]:
        """모든 첨부파일 조회"""
        try:
            result = self.supabase.table(self.table_name)\
                .select("*")\
                .execute()
            
            return result.data
        except Exception as e:
            logger.error(f"전체 첨부파일 조회 오류: {e}")
            return []
    
    async def get_by_source(self, source_id: str, source_type: str) -> List[Dict[str, Any]]:
        """소스 ID와 타입으로 첨부파일 조회"""
        try:
            result = self.supabase.table(self.table_name)\
                .select("*")\
                .eq("source_id", source_id)\
                .eq("source_type", source_type)\
                .execute()
            
            return result.data
        except Exception as e:
            logger.error(f"첨부파일 소스별 조회 오류: {e}")
            return []
    
    async def create(self, attachment_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """새로운 첨부파일 생성"""
        try:
            result = self.supabase.table(self.table_name)\
                .insert(attachment_data)\
                .execute()
            
            if result.data:
                logger.info(f"첨부파일 생성 완료: {attachment_data.get('file_name', 'Unknown')}")
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"첨부파일 생성 오류: {e}")
            return None
    
    async def upsert(self, attachment_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """첨부파일 생성 또는 업데이트 (source_id + source_type + file_name 중복 체크)"""
        try:
            # 기존 첨부파일 검색
            existing = await self.get_by_source_and_filename(
                attachment_data.get("source_id"),
                attachment_data.get("source_type"), 
                attachment_data.get("file_name")
            )
            
            if existing:
                # 업데이트
                result = self.supabase.table(self.table_name)\
                    .update(attachment_data)\
                    .eq("id", existing["id"])\
                    .execute()
                
                if result.data:
                    logger.info(f"첨부파일 업데이트 완료: {attachment_data.get('file_name', 'Unknown')}")
                    return result.data[0]
            else:
                # 새로 생성
                result = self.supabase.table(self.table_name)\
                    .insert(attachment_data)\
                    .execute()
                
                if result.data:
                    logger.info(f"첨부파일 생성 완료: {attachment_data.get('file_name', 'Unknown')}")
                    return result.data[0]
            
            return None
        except Exception as e:
            logger.error(f"첨부파일 upsert 오류: {e}")
            return None
    
    async def get_by_source_and_filename(self, source_id: str, source_type: str, file_name: str) -> Optional[Dict[str, Any]]:
        """소스 ID, 타입, 파일명으로 첨부파일 조회"""
        try:
            result = self.supabase.table(self.table_name)\
                .select("*")\
                .eq("source_id", source_id)\
                .eq("source_type", source_type)\
                .eq("file_name", file_name)\
                .limit(1)\
                .execute()
            
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"첨부파일 조회 오류: {e}")
            return None
    
    async def update(self, attachment_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """첨부파일 업데이트"""
        try:
            result = self.supabase.table(self.table_name)\
                .update(kwargs)\
                .eq("id", attachment_id)\
                .execute()
            
            if result.data:
                logger.info(f"첨부파일 업데이트 완료: {attachment_id}")
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"첨부파일 업데이트 오류: {e}")
            return None
    
    async def delete(self, attachment_id: str) -> bool:
        """첨부파일 삭제"""
        try:
            result = self.supabase.table(self.table_name)\
                .delete()\
                .eq("id", attachment_id)\
                .execute()
            
            success = len(result.data) > 0
            if success:
                logger.info(f"첨부파일 삭제 완료: {attachment_id}")
            return success
        except Exception as e:
            logger.error(f"첨부파일 삭제 오류: {e}")
            return False

    # 첨부파일 최적화를 위한 추가 메서드들
    async def get_existing_attachment(self, course_id: str, source_type: str, source_id: str, original_filename: str) -> Optional[Dict[str, Any]]:
        """중복 방지를 위한 기존 첨부파일 확인"""
        try:
            result = self.supabase.table(self.table_name)\
                .select("*")\
                .eq("course_id", course_id)\
                .eq("source_type", source_type)\
                .eq("source_id", source_id)\
                .eq("original_filename", original_filename)\
                .limit(1)\
                .execute()

            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"기존 첨부파일 확인 오류: {e}")
            return None

    async def create_or_get_existing(self, **attachment_data) -> Dict[str, Any]:
        """첨부파일 생성 또는 기존 파일 반환 (중복 방지)"""
        try:
            # 기존 파일 확인
            existing = await self.get_existing_attachment(
                attachment_data.get("course_id"),
                attachment_data.get("source_type"),
                attachment_data.get("source_id"),
                attachment_data.get("original_filename")
            )

            if existing:
                logger.info(f"기존 첨부파일 재사용: {existing['id']}")
                return existing

            # 새 파일 생성
            result = self.supabase.table(self.table_name)\
                .insert(attachment_data)\
                .execute()

            if result.data:
                logger.info(f"새 첨부파일 생성: {attachment_data.get('original_filename')}")
                return result.data[0]

            raise Exception("첨부파일 생성 실패")

        except Exception as e:
            logger.error(f"첨부파일 생성/조회 오류: {e}")
            raise