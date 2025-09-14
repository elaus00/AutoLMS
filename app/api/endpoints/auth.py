import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Any

from app.schemas.auth import UserCreate, UserLogin, Token, UserOut
from app.services.auth_service import AuthService
from app.services.session.eclass_session_manager import EclassSessionManager
from app.api.deps import get_auth_service, get_eclass_session_manager, get_current_user, get_jwt_manager, get_session_manager

logger = logging.getLogger(__name__)

router = APIRouter()

bearer_scheme = HTTPBearer()


@router.post("/register", response_model=UserOut)
async def register(
        user_in: UserCreate,
        auth_service: AuthService = Depends(get_auth_service)
) -> Any:
    """새 사용자 등록 - 이클래스 계정만으로 가입"""
    # 사용자 등록 (이클래스 계정 검증은 AuthService에서 처리)
    result = await auth_service.register(
        eclass_username=user_in.eclass_username,
        eclass_password=user_in.eclass_password
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="회원가입 중 오류가 발생했습니다."
        )

    return result.get("user", {})


@router.post("/login", response_model=Token)
async def login(
        user_login: UserLogin,
        auth_service: AuthService = Depends(get_auth_service),
) -> Any:
    """로그인 및 토큰 발급 - 이클래스 계정으로 로그인"""
    result = await auth_service.login(
        eclass_username=user_login.eclass_username,
        eclass_password=user_login.eclass_password
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이클래스 계정 정보가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # AuthService에서 이미 Supabase JWT를 반환하므로 추가 세션 생성 불필요
    return {
        "access_token": result.get("access_token"),
        "refresh_token": result.get("refresh_token"),
        "token_type": "bearer",
        "user": result.get("user", {})
    }


@router.post("/logout")
async def logout(
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
        auth_service: AuthService = Depends(get_auth_service),
        eclass_session_manager: EclassSessionManager = Depends(get_eclass_session_manager),
        current_user: dict = Depends(get_current_user)
) -> Any:
    """로그아웃 (JWT 기반)"""
    try:
        user_id = current_user.get("id")
        
        # JWT 세션 종료
        auth_result = await auth_service.logout(credentials.credentials, user_id)

        # 이클래스 세션도 함께 종료
        if user_id:
            await eclass_session_manager.invalidate_session(user_id)

        return auth_result

    except Exception as e:
        logger.error(f"로그아웃 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/verify", response_model=UserOut)
async def verify_token(
        current_user: dict = Depends(get_current_user)
) -> Any:
    """토큰 검증 (JWT 기반)"""
    return current_user


@router.post("/refresh", response_model=Token)
async def refresh_token(
        refresh_token: str,
        jwt_manager_instance = Depends(get_jwt_manager),
        session_manager_instance = Depends(get_session_manager)
) -> Any:
    """리프레시 토큰으로 새 액세스 토큰 발급"""
    try:
        # 새 액세스 토큰 생성
        new_access_token = jwt_manager_instance.refresh_access_token(refresh_token)
        
        # 기존 리프레시 토큰 유지 (필요시 갱신 로직 추가 가능)
        return {
            "access_token": new_access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"토큰 갱신 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="리프레시 토큰이 유효하지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )