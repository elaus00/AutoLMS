from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class NoticeBase(BaseModel):
    """공지사항 기본 스키마 - Composite Key 전략 사용"""
    id: str  # Composite Primary Key: "{course_id}_{notice_id}"
    course_id: str  # 강의 ID
    notice_id: str  # 공지사항 원본 ID (e-Class에서)
    title: str  # 공지사항 제목
    content: Optional[str] = None  # 공지사항
    author: Optional[str] = None  # 작성자
    date: Optional[str] = None  # 작성일 (e-Class 형식)
    views: Optional[int] = 0  # 조회수
    article_id: Optional[str] = None  # 게시글 ID (e-Class)


class NoticeCreate(BaseModel):
    """공지사항 생성 요청 스키마 - ID는 자동 생성"""
    course_id: str
    notice_id: str  # 원본 e-Class ID
    title: str
    content: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    views: Optional[int] = 0
    article_id: Optional[str] = None


class NoticeUpdate(BaseModel):
    """공지사항 업데이트 스키마"""
    title: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    views: Optional[int] = None
    has_attachments: Optional[bool] = None
    attachments: Optional[List[Any]] = None


class NoticeInDB(NoticeBase):
    """데이터베이스의 공지사항 스키마"""
    has_attachments: Optional[bool] = False  # 첨부파일 존재 여부
    attachments: Optional[List[Any]] = None  # 첨부파일 정보 (JSONB)
    created_at: datetime  # 생성 시간
    updated_at: datetime  # 수정 시간
    
    class Config:
        from_attributes = True


class Notice(NoticeInDB):
    """API 응답용 공지사항 스키마"""
    pass


class NoticeOut(NoticeBase):
    """공지사항 출력 스키마 (사용자에게 반환)"""
    has_attachments: Optional[bool] = False
    attachments: Optional[List[Any]] = None
    created_at: datetime
    updated_at: datetime


class NoticeList(BaseModel):
    """공지사항 목록 응답 스키마"""
    notices: List[NoticeOut]
    total: int


class NoticeWithCourse(NoticeOut):
    """강의 정보가 포함된 공지사항 스키마"""
    course_name: Optional[str] = None
    instructor: Optional[str] = None
