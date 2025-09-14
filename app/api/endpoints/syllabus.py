from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any

from app.schemas.syllabus import Syllabus
from app.api.deps import (
    get_current_user,
    get_course_service,
    get_syllabus_service
)
from app.services.content.course_service import CourseService
from app.services.content.syllabus_service import SyllabusService

router = APIRouter()

@router.get("/", response_model=Syllabus)
async def get_syllabus(
    course_id: str,
    current_user: dict = Depends(get_current_user),
    course_service: CourseService = Depends(get_course_service),
    syllabus_service: SyllabusService = Depends(get_syllabus_service)
) -> Any:
    """특정 강의의 강의계획서 조회"""
    # 강의 존재 여부 확인
    course = await course_service.get_course(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의를 찾을 수 없습니다."
        )

    syllabus = await syllabus_service.get_syllabus_by_course(course_id=course_id)
    if not syllabus:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의계획서를 찾을 수 없습니다."
        )

    return syllabus

@router.get("/refresh", response_model=dict)
async def refresh_syllabus(
    course_id: str,
    current_user: dict = Depends(get_current_user),
    course_service: CourseService = Depends(get_course_service),
    syllabus_service: SyllabusService = Depends(get_syllabus_service)
) -> Any:
    """특정 강의의 강의계획서 새로고침"""
    # 강의 존재 여부 확인
    course = await course_service.get_course(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의를 찾을 수 없습니다."
        )

    result = await syllabus_service.refresh_all(course_id, current_user["id"])
    return {
        "course_id": course_id,
        "result": result
    }