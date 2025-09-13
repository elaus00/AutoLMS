import logging
from typing import List, Dict, Any, Optional
from supabase import Client
from app.core.supabase_client import get_supabase_client
from app.core.id_utils import generate_notice_id
from app.db.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)

class NoticeRepository(BaseRepository):
    """Supabase를 사용한 공지사항 저장소"""
    
    def __init__(self):
        super().__init__("notices")
    
    async def get_by_id(self, notice_id: str) -> Optional[Dict[str, Any]]:
        """공지사항 ID로 공지사항 조회"""
        try:
            result = self.supabase.table(self.table_name)\
                .select("*")\
                .eq("id", notice_id)\
                .single()\
                .execute()
            
            return result.data
        except Exception as e:
            logger.error(f"공지사항 ID 조회 오류: {e}")
            return None
    
    async def get_by_course_id(self, course_id: str) -> List[Dict[str, Any]]:
        """강의 ID로 공지사항 조회"""
        try:
            result = self.supabase.table(self.table_name)\
                .select("*")\
                .eq("course_id", course_id)\
                .order("created_at", desc=True)\
                .execute()
            
            return result.data
        except Exception as e:
            logger.error(f"공지사항 강의별 조회 오류: {e}")
            return []
    

    async def create(self, **kwargs) -> Optional[Dict[str, Any]]:
        """새로운 공지사항 생성"""
        try:
            # notice_id 필드 처리
            if "notice_id" not in kwargs and "article_id" in kwargs:
                kwargs["notice_id"] = kwargs["article_id"]
            
            # Composite ID 자동 생성
            if "course_id" in kwargs and "notice_id" in kwargs:
                composite_id = generate_notice_id(kwargs["course_id"], kwargs["notice_id"])
                kwargs["id"] = composite_id
            
            result = self.supabase.table(self.table_name)\
                .insert(kwargs)\
                .execute()
            
            if result.data:
                logger.info(f"공지사항 생성 완료: {kwargs.get('title', 'Unknown')}")
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"공지사항 생성 오류: {e}")
            return None
    
    async def upsert(self, **kwargs) -> Optional[Dict[str, Any]]:
        """공지사항 생성 또는 업데이트 (composite ID로 중복 체크)"""
        # notice_id 필드 처리
        if "notice_id" not in kwargs and "article_id" in kwargs:
            kwargs["notice_id"] = kwargs["article_id"]

        # Composite ID 자동 생성
        if "course_id" in kwargs and "notice_id" in kwargs:
            composite_id = self.generate_composite_id(kwargs["course_id"], kwargs["notice_id"])
            kwargs["id"] = composite_id

        return await super().upsert("id", **kwargs)
    
    async def update(self, notice_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """공지사항 업데이트"""
        try:
            result = self.supabase.table(self.table_name)\
                .update(kwargs)\
                .eq("id", notice_id)\
                .execute()
            
            if result.data:
                logger.info(f"공지사항 업데이트 완료: {notice_id}")
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"공지사항 업데이트 오류: {e}")
            return None
    
    async def delete(self, notice_id: str) -> bool:
        """공지사항 삭제"""
        try:
            result = self.supabase.table(self.table_name)\
                .delete()\
                .eq("id", notice_id)\
                .execute()
            
            success = len(result.data) > 0
            if success:
                logger.info(f"공지사항 삭제 완료: {notice_id}")
            return success
        except Exception as e:
            logger.error(f"공지사항 삭제 오류: {e}")
            return False
