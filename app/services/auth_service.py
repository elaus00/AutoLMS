import logging
import uuid
from fastapi import HTTPException, status
from typing import Dict, Any, Optional
from datetime import datetime

from app.core.supabase_client import get_supabase_client
from app.utils.encryption import encrypt_eclass_password, decrypt_eclass_password, is_encrypted
from app.utils.jwt_utils import jwt_manager
from app.services.session_manager import session_manager
from app.db.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

class AuthService:
    """JWT 기반 인증 서비스"""

    def __init__(self, supabase_client=None):
        self.supabase = supabase_client or get_supabase_client()
        self.user_repository = UserRepository()

    async def register(self, eclass_username: str, eclass_password: str) -> Dict[str, Any]:
        """새 사용자 등록 - 이클래스 계정만으로 가입 (JWT 기반)"""
        try:
            # 먼저 이클래스 계정 검증
            is_valid = await self.validate_eclass_credentials(eclass_username, eclass_password)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="이클래스 계정 정보가 유효하지 않습니다."
                )

            # 중복 사용자 확인 (Repository 사용)
            existing_user = await self.user_repository.get_by_eclass_username(eclass_username)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="이미 등록된 이클래스 계정입니다."
                )
            
            # Repository를 통한 사용자 생성 (upsert 사용)
            user_id = str(uuid.uuid4())
            logger.info(f"사용자 등록 시작: 이클래스 계정 {eclass_username}, user_id: {user_id}")

            # 이클래스 비밀번호 암호화
            encrypted_eclass_password = encrypt_eclass_password(eclass_password)

            # Repository를 통해 사용자 생성
            user_data = {
                'id': user_id,
                'eclass_username': eclass_username,
                'encrypted_eclass_password': encrypted_eclass_password,
                'created_at': datetime.now().isoformat()
            }

            created_user = await self.user_repository.upsert(**user_data)
            if not created_user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="사용자 생성에 실패했습니다."
                )
            logger.info(f"사용자 등록 완료: {user_id}")

            # JWT 토큰 생성
            access_token = jwt_manager.create_access_token(user_id, eclass_username)
            refresh_token = jwt_manager.create_refresh_token(user_id)

            # JWT 세션 생성
            session_data = await session_manager.create_jwt_session(
                user_id=user_id,
                eclass_username=eclass_username
            )

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": {
                    "id": user_id,
                    "eclass_username": eclass_username
                },
                "session_id": session_data.get("session_id")
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"사용자 등록 중 예외 발생: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"회원가입 처리 중 오류가 발생했습니다: {str(e)}"
            )

    async def login(self, eclass_username: str, eclass_password: str) -> Dict[str, Any]:
        """사용자 로그인 - 이클래스 계정으로 로그인 (JWT 기반)"""
        try:
            # 먼저 이클래스 계정 검증
            is_valid = await self.validate_eclass_credentials(eclass_username, eclass_password)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="이클래스 계정 정보가 올바르지 않습니다."
                )

            # 등록된 사용자인지 확인 (Repository 사용)
            user = await self.user_repository.get_by_eclass_username(eclass_username)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="등록되지 않은 이클래스 계정입니다. 먼저 회원가입을 진행해주세요."
                )
            
            user_id = user["id"]
            logger.info(f"사용자 로그인 시도: {eclass_username}, user_id: {user_id}")
            
            # 이클래스 비밀번호 업데이트 (암호화된 상태로)
            await self._update_eclass_password(user_id, eclass_password)
            
            # JWT 토큰 생성
            access_token = jwt_manager.create_access_token(user_id, eclass_username)
            refresh_token = jwt_manager.create_refresh_token(user_id)

            # JWT 세션 생성
            session_data = await session_manager.create_jwt_session(
                user_id=user_id,
                eclass_username=eclass_username
            )

            result = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": {
                    "id": user_id,
                    "eclass_username": eclass_username
                },
                "session_id": session_data.get("session_id")
            }
            
            logger.info(f"JWT 로그인 성공: user_id={user_id}")
            return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"로그인 처리 중 예외 발생: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="로그인 처리 중 오류가 발생했습니다."
            )

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """사용자 ID로 사용자 정보 조회"""
        return await self.user_repository.get_by_id(user_id)
    
    async def get_user_by_eclass_username(self, eclass_username: str) -> Optional[Dict[str, Any]]:
        """이클래스 사용자명으로 사용자 정보 조회"""
        return await self.user_repository.get_by_eclass_username(eclass_username)

    async def logout(self, token: str, user_id: str = None) -> Dict[str, Any]:
        """사용자 로그아웃 (JWT 기반)"""
        try:
            # 토큰 유효성 확인
            try:
                payload = jwt_manager.verify_token(token, "access")
                if not user_id:
                    user_id = payload.get("user_id")
                    
                if not user_id:
                    return {"status": "already_logged_out", "message": "이미 로그아웃된 상태입니다."}
                    
            except Exception:
                return {"status": "already_logged_out", "message": "이미 로그아웃된 상태입니다."}

            # 사용자의 모든 활성 세션 무효화
            try:
                invalidated_count = await session_manager.invalidate_user_sessions(user_id)
                logger.info(f"사용자 {user_id}의 {invalidated_count}개 세션 무효화 완료")
            except Exception as session_error:
                logger.warning(f"세션 무효화 중 오류 (무시): {str(session_error)}")

            return {"status": "success", "message": "로그아웃되었습니다."}

        except Exception as e:
            logger.error(f"로그아웃 처리 중 오류: {str(e)}")
            raise Exception(f"로그아웃 처리 중 오류가 발생했습니다: {str(e)}")

    async def validate_eclass_credentials(self, eclass_id: str, eclass_pw: str) -> bool:
        """
        이클래스 계정 정보의 유효성 검증

        Args:
            eclass_id: 이클래스 아이디
            eclass_pw: 이클래스 비밀번호

        Returns:
            bool: 유효한 계정 정보인 경우 True, 아니면 False
        """
        try:
            # EclassSession 인스턴스 생성
            from app.services.session.eclass_session import EclassSession

            session = EclassSession()
            # 실제 로그인 시도
            login_success = await session.login(username=eclass_id, password=eclass_pw)

            # 세션 종료 (중요: 리소스 정리)
            await session.close()

            return login_success
        except Exception as e:
            logger.error(f"이클래스 계정 검증 중 오류: {str(e)}")
            return False


    async def get_user_eclass_credentials(self, user_id: str) -> Optional[Dict[str, str]]:
        """사용자의 이클래스 계정 정보 조회"""
        try:
            # Repository를 통해 암호화된 계정 정보 조회
            credentials = await self.user_repository.get_eclass_credentials(user_id)
            if not credentials:
                logger.error(f"사용자 {user_id}를 찾을 수 없음")
                return None

            encrypted_password = credentials.get('encrypted_password')
            if not encrypted_password:
                logger.error(f"사용자 {user_id}의 이클래스 계정 정보가 없음")
                return None

            # 비밀번호 복호화
            if is_encrypted(encrypted_password):
                try:
                    decrypted_password = decrypt_eclass_password(encrypted_password)
                except Exception as decrypt_error:
                    logger.error(f"비밀번호 복호화 실패: {str(decrypt_error)}")
                    return None
            else:
                # 평문 비밀번호인 경우 (기존 데이터 호환성)
                decrypted_password = encrypted_password
                logger.warning(f"평문 비밀번호 발견: 사용자 {user_id}")

            return {
                "username": credentials.get('username'),
                "password": decrypted_password
            }
        except Exception as e:
            logger.error(f"이클래스 계정 정보 조회 중 오류: {str(e)}")
            return None

    async def _update_eclass_password(self, user_id: str, eclass_password: str) -> None:
        """이클래스 비밀번호를 암호화하여 업데이트"""
        try:
            # Repository를 통해 현재 저장된 비밀번호 확인
            credentials = await self.user_repository.get_eclass_credentials(user_id)
            if not credentials:
                return

            stored_password = credentials.get('encrypted_password', '')

            # 이미 암호화된 상태이고 복호화했을 때 같은 비밀번호인 경우 스킵
            if is_encrypted(stored_password):
                try:
                    decrypted_password = decrypt_eclass_password(stored_password)
                    if decrypted_password == eclass_password:
                        return  # 업데이트 불필요
                except Exception:
                    pass  # 복호화 실패 시 새로 암호화하여 저장

            # Repository를 통해 비밀번호 암호화하여 업데이트
            encrypted_password = encrypt_eclass_password(eclass_password)
            await self.user_repository.update_eclass_password(user_id, encrypted_password)

        except Exception as e:
            logger.error(f"이클래스 비밀번호 업데이트 중 오류: {str(e)}")
            # 비밀번호 업데이트 실패는 로그인 실패로 처리하지 않음

