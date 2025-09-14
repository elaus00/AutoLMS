import logging
from typing import Dict, Any, Optional
from app.db.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository):
    """Supabase를 사용한 사용자 저장소"""

    def __init__(self):
        super().__init__("users")

    async def get_by_eclass_username(self, eclass_username: str) -> Optional[Dict[str, Any]]:
        """이클래스 사용자명으로 사용자 정보 조회"""
        try:
            result = self.supabase.table(self.table_name)\
                .select('id, eclass_username, created_at')\
                .eq('eclass_username', eclass_username)\
                .single()\
                .execute()

            if result.data:
                return result.data
            return None

        except Exception as e:
            logger.debug(f"이클래스 사용자명으로 조회 실패 (신규 사용자일 수 있음): {str(e)}")
            return None

    async def get_eclass_credentials(self, user_id: str) -> Optional[Dict[str, str]]:
        """사용자의 이클래스 계정 정보 조회"""
        try:
            result = self.supabase.table(self.table_name)\
                .select('eclass_username, encrypted_eclass_password')\
                .eq('id', user_id)\
                .single()\
                .execute()

            if result.data:
                return {
                    "username": result.data.get('eclass_username'),
                    "encrypted_password": result.data.get('encrypted_eclass_password')
                }
            return None

        except Exception as e:
            logger.error(f"이클래스 계정 정보 조회 중 오류: {str(e)}")
            return None

    async def upsert(self, **kwargs) -> Optional[Dict[str, Any]]:
        """사용자 생성 또는 업데이트 (eclass_username으로 중복 체크)"""
        return await super().upsert("eclass_username", **kwargs)

    async def update_eclass_password(self, user_id: str, encrypted_password: str) -> bool:
        """이클래스 비밀번호 업데이트"""
        try:
            result = self.supabase.table(self.table_name)\
                .update({'encrypted_eclass_password': encrypted_password})\
                .eq('id', user_id)\
                .execute()

            success = bool(result.data)
            if success:
                logger.debug(f"사용자 {user_id}의 이클래스 비밀번호 업데이트 완료")
            return success

        except Exception as e:
            logger.error(f"이클래스 비밀번호 업데이트 중 오류: {str(e)}")
            return False