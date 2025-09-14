from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class MaterialBase(BaseModel):
    """강의자료 기본 스키마 - Composite Key 전략 사용"""
    id: str  # Composite Primary Key: "{course_id}_{material_id}"
    course_id: str  # 강의 ID
    material_id: str  # 강의자료 원본 ID (e-Class에서)
    user_id: str  # 사용자 ID
    title: str  # 자료 제목
    content: Optional[str] = None  # 자료 내용
    author: Optional[str] = None  # 작성자
    date: Optional[str] = None  # 작성일 (e-Class 형식)
    views: Optional[int] = 0  # 조회수
    article_id: Optional[str] = None  # 게시글 ID (e-Class)


class MaterialCreate(BaseModel):
    """강의자료 생성 요청 스키마 - ID는 자동 생성"""
    course_id: str
    material_id: str  # 원본 e-Class ID
    user_id: str
    title: str
    content: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    views: Optional[int] = 0
    article_id: Optional[str] = None


class MaterialUpdate(BaseModel):
    """강의자료 업데이트 스키마"""
    title: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    views: Optional[int] = None
    has_attachments: Optional[bool] = None
    attachments: Optional[List[Any]] = None


class MaterialInDB(MaterialBase):
    """데이터베이스의 강의자료 스키마"""
    has_attachments: Optional[bool] = False  # 첨부파일 존재 여부
    attachments: Optional[List[Any]] = None  # 첨부파일 정보 (JSONB)
    created_at: datetime  # 생성 시간
    updated_at: datetime  # 수정 시간
    
    class Config:
        from_attributes = True


class Material(MaterialInDB):
    """API 응답용 강의자료 스키마"""
    pass


class MaterialOut(MaterialBase):
    """강의자료 출력 스키마 (사용자에게 반환)"""
    has_attachments: Optional[bool] = False
    attachments: Optional[List[Any]] = None
    created_at: datetime
    updated_at: datetime


class MaterialList(BaseModel):
    """강의자료 목록 응답 스키마"""
    materials: List[MaterialOut]
    total: int


class MaterialRefreshResponse(BaseModel):
    """강의자료 새로고침 응답 스키마"""
    materials: List[Any]  # 유연한 데이터 형식 지원
    total: int
    refresh_result: Optional[Any] = None  # 새로고침 결과


class MaterialWithCourse(MaterialOut):
    """강의 정보가 포함된 강의자료 스키마"""
    course_name: Optional[str] = None
    instructor: Optional[str] = None