import logging
from typing import List, Dict, Any, Optional
from supabase import Client
from app.core.supabase_client import get_supabase_client
from app.core.id_utils import generate_notice_id, is_valid_composite_id
from app.db.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)

class AssignmentRepository(BaseRepository):
    """Supabase를 사용한 과제 저장소"""
    
    def __init__(self):
        super().__init__("assignments")
    
    async def get_by_id(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        """ID로 과제 조회"""
        try:
            result = self.supabase.table(self.table_name)\
                .select("*")\
                .eq("id", assignment_id)\
                .single()\
                .execute()
            
            return result.data
        except Exception as e:
            logger.error(f"과제 ID 조회 오류: {e}")
            return None
    
    async def get_by_course_id(self, course_id: str) -> List[Dict[str, Any]]:
        """강의 ID로 과제 조회"""
        try:
            result = self.supabase.table(self.table_name)\
                .select("*")\
                .eq("course_id", course_id)\
                .order("created_at", desc=True)\
                .execute()
            
            return result.data
        except Exception as e:
            logger.error(f"과제 강의별 조회 오류: {e}")
            return []
    
    
    async def create(self, **kwargs) -> Optional[Dict[str, Any]]:
        """새로운 과제 생성"""
        try:
            # assignment_id 필드 처리
            if "assignment_id" not in kwargs and "article_id" in kwargs:
                kwargs["assignment_id"] = kwargs["article_id"]
            
            # Composite ID 자동 생성
            if "course_id" in kwargs and "assignment_id" in kwargs:
                assignment_id = kwargs["assignment_id"]
                
                # assignment_id가 이미 composite 형태인지 확인
                if is_valid_composite_id(assignment_id) and assignment_id.startswith(kwargs["course_id"]):
                    # 이미 composite 형태이면 그대로 사용
                    composite_id = assignment_id
                else:
                    # 기존 방식: course_id + "_" + assignment_id
                    composite_id = generate_notice_id(kwargs["course_id"], assignment_id)
                
                kwargs["id"] = composite_id
            
            result = self.supabase.table(self.table_name)\
                .insert(kwargs)\
                .execute()
            
            if result.data:
                logger.info(f"과제 생성 완료: {kwargs.get('title', 'Unknown')}")
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"과제 생성 오류: {e}")
            return None
    
    async def upsert(self, **kwargs) -> Optional[Dict[str, Any]]:
        """과제 생성 또는 업데이트 (assignment_id로 중복 체크)"""
        # assignment_id 필드 처리
        if "assignment_id" not in kwargs and "article_id" in kwargs:
            kwargs["assignment_id"] = kwargs["article_id"]

        # Composite ID 자동 생성
        if "course_id" in kwargs and "assignment_id" in kwargs:
            assignment_id = kwargs["assignment_id"]

            # assignment_id가 이미 composite 형태인지 확인
            if is_valid_composite_id(assignment_id) and assignment_id.startswith(kwargs["course_id"]):
                composite_id = assignment_id
            else:
                composite_id = self.generate_composite_id(kwargs["course_id"], assignment_id)

            kwargs["id"] = composite_id

        return await super().upsert("assignment_id", **kwargs)

    async def update(self, assignment_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """과제 업데이트"""
        try:
            result = self.supabase.table(self.table_name)\
                .update(kwargs)\
                .eq("id", assignment_id)\
                .execute()
            
            if result.data:
                logger.info(f"과제 업데이트 완료: {assignment_id}")
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"과제 업데이트 오류: {e}")
            return None
    
    async def delete(self, assignment_id: str) -> bool:
        """과제 삭제"""
        try:
            result = self.supabase.table(self.table_name)\
                .delete()\
                .eq("id", assignment_id)\
                .execute()
            
            success = len(result.data) > 0
            if success:
                logger.info(f"과제 삭제 완료: {assignment_id}")
            return success
        except Exception as e:
            logger.error(f"과제 삭제 오류: {e}")
            return False