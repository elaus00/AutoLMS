from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any, Optional

from app.schemas.notice import Notice, NoticeList
from app.api.deps import (
    get_current_user,
    get_course_service,
    get_notice_service,
    get_storage_service
)
from app.services.content.course_service import CourseService
from app.services.content.notice_service import NoticeService
from app.services.storage.storage_service import StorageService

router = APIRouter()

@router.get("/", response_model=NoticeList)
async def get_notices(
    course_id: str,
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
    course_service: CourseService = Depends(get_course_service),
    notice_service: NoticeService = Depends(get_notice_service)
) -> Any:
    """특정 강의의 공지사항 목록 조회"""
    # 강의 존재 여부 확인
    course = await course_service.get_course(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의를 찾을 수 없습니다."
        )

    notices = await notice_service.get_notices_by_course(course_id, skip=skip, limit=limit)
    total = len(notices)

    return {
        "notices": notices,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.get("/refresh", response_model=dict)
async def refresh_notices(
    course_id: str,
    current_user: dict = Depends(get_current_user),
    course_service: CourseService = Depends(get_course_service),
    notice_service: NoticeService = Depends(get_notice_service)
) -> Any:
    """특정 강의의 공지사항 새로고침"""
    # 강의 존재 여부 확인
    course = await course_service.get_course(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의를 찾을 수 없습니다."
        )

    result = await notice_service.refresh_all(course_id, current_user["id"], auto_download=True)
    return {
        "course_id": course_id,
        "result": result
    }

@router.get("/{notice_id}", response_model=Notice)
async def get_notice(
    course_id: str,
    notice_id: int,
    current_user: dict = Depends(get_current_user),
    course_service: CourseService = Depends(get_course_service),
    notice_service: NoticeService = Depends(get_notice_service)
) -> Any:
    """특정 공지사항 조회"""
    # 강의 존재 여부 확인
    course = await course_service.get_course(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의를 찾을 수 없습니다."
        )

    notice = await notice_service.get_notice_by_id(notice_id)
    if not notice or notice.course_id != course_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="공지사항을 찾을 수 없습니다."
        )

    return notice

@router.get("/{notice_id}/attachments/{attachment_id}")
async def download_notice_attachment(
    course_id: str,
    notice_id: int,
    attachment_id: int,
    current_user: dict = Depends(get_current_user),
    course_service: CourseService = Depends(get_course_service),
    notice_service: NoticeService = Depends(get_notice_service),
    storage_service: StorageService = Depends(get_storage_service)
) -> Any:
    """공지사항 첨부파일 다운로드 URL 조회"""
    # 강의 존재 여부 확인
    course = await course_service.get_course(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의를 찾을 수 없습니다."
        )

    # 공지사항 확인
    notice = await notice_service.get_notice_by_id(notice_id)
    if not notice or notice.course_id != course_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="공지사항을 찾을 수 없습니다."
        )

    # 첨부파일 다운로드 URL 조회
    download_url = await storage_service.get_download_url(attachment_id, current_user["id"])
    if not download_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="첨부파일을 찾을 수 없습니다."
        )

    return {"download_url": download_url}