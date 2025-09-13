from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any

from app.schemas.assignment import Assignment, AssignmentList
from app.api.deps import (
    get_current_user,
    get_course_service,
    get_assignment_service,
    get_storage_service
)
from app.services.content.course_service import CourseService
from app.services.content.assignment_service import AssignmentService
from app.services.storage.storage_service import StorageService

router = APIRouter()

@router.get("/", response_model=AssignmentList)
async def get_assignments(
    course_id: str,
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
    course_service: CourseService = Depends(get_course_service),
    assignment_service: AssignmentService = Depends(get_assignment_service)
) -> Any:
    """특정 강의의 과제 목록 조회"""
    # 강의 존재 여부 확인
    course = await course_service.get_course(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의를 찾을 수 없습니다."
        )

    assignments = await assignment_service.get_assignments(current_user["id"], course_id)
    total = len(assignments)

    return {
        "assignments": assignments,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.get("/refresh", response_model=dict)
async def refresh_assignments(
    course_id: str,
    current_user: dict = Depends(get_current_user),
    course_service: CourseService = Depends(get_course_service),
    assignment_service: AssignmentService = Depends(get_assignment_service)
) -> Any:
    """특정 강의의 과제 새로고침"""
    # 강의 존재 여부 확인
    course = await course_service.get_course(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의를 찾을 수 없습니다."
        )

    result = await assignment_service.refresh_all(course_id, current_user["id"], auto_download=True)
    return {
        "course_id": course_id,
        "result": result
    }

@router.get("/{assignment_id}", response_model=Assignment)
async def get_assignment(
    course_id: str,
    assignment_id: int,
    current_user: dict = Depends(get_current_user),
    course_service: CourseService = Depends(get_course_service),
    assignment_service: AssignmentService = Depends(get_assignment_service)
) -> Any:
    """특정 과제 조회"""
    # 강의 존재 여부 확인
    course = await course_service.get_course(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의를 찾을 수 없습니다."
        )

    assignment = await assignment_service.get_assignment(current_user["id"], course_id, str(assignment_id))
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="과제를 찾을 수 없습니다."
        )

    return assignment

@router.get("/{assignment_id}/attachments/{attachment_id}")
async def download_assignment_attachment(
    course_id: str,
    assignment_id: int,
    attachment_id: int,
    current_user: dict = Depends(get_current_user),
    course_service: CourseService = Depends(get_course_service),
    assignment_service: AssignmentService = Depends(get_assignment_service),
    storage_service: StorageService = Depends(get_storage_service)
) -> Any:
    """과제 첨부파일 다운로드 URL 조회"""
    # 강의 존재 여부 확인
    course = await course_service.get_course(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의를 찾을 수 없습니다."
        )

    # 과제 확인
    assignment = await assignment_service.get_assignment(current_user["id"], course_id, str(assignment_id))
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="과제를 찾을 수 없습니다."
        )

    # 첨부파일 다운로드 URL 조회
    download_url = await storage_service.get_download_url(attachment_id, current_user["id"])
    if not download_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="첨부파일을 찾을 수 없습니다."
        )

    return {"download_url": download_url}