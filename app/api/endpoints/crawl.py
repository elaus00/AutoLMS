import logging

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import Any, Dict, Optional

from app.api.deps import (
    get_current_user,
    get_course_service,
    get_notice_service,
    get_material_service,
    get_assignment_service,
    get_syllabus_service, get_crawl_service
)
from app.services import CrawlService
from app.services.content.course_service import CourseService
from app.services.content.notice_service import NoticeService
from app.services.content.material_service import MaterialService
from app.services.content.assignment_service import AssignmentService
from app.services.content.syllabus_service import SyllabusService

router = APIRouter()

logger = logging.getLogger(__name__)

@router.post("/sync/course/{course_id}")
async def sync_course(
        course_id: str,
        auto_download: bool = True,
        current_user: dict = Depends(get_current_user),
        course_service: CourseService = Depends(get_course_service),
        notice_service: NoticeService = Depends(get_notice_service),
        material_service: MaterialService = Depends(get_material_service),
        assignment_service: AssignmentService = Depends(get_assignment_service),
        syllabus_service: SyllabusService = Depends(get_syllabus_service)
) -> Dict[str, Any]:
    """특정 강의 전체 동기화"""
    try:
        # 강의 존재 확인
        course = await course_service.get_course(course_id)
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="강의를 찾을 수 없습니다."
            )

        # 각 콘텐츠 타입별 동기화 실행
        result = {
            "course_id": course_id,
            "course_name": course.get('name', course_id),
            "status": "success",
            "details": {
                "notices": await notice_service.refresh_all(course_id, current_user["id"], auto_download),
                "materials": await material_service.refresh_all(course_id, current_user["id"], auto_download),
                "assignments": await assignment_service.refresh_all(course_id, current_user["id"], auto_download),
                "syllabus": await syllabus_service.refresh_all(course_id, current_user["id"])
            }
        }

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"동기화 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/sync/all")
async def sync_all_courses(
        background_tasks: BackgroundTasks,
        auto_download: bool = True,
        current_user: dict = Depends(get_current_user),
        course_service: CourseService = Depends(get_course_service),
        notice_service: NoticeService = Depends(get_notice_service),
        material_service: MaterialService = Depends(get_material_service),
        assignment_service: AssignmentService = Depends(get_assignment_service),
        syllabus_service: SyllabusService = Depends(get_syllabus_service)
) -> Dict[str, Any]:
    """모든 강의 동기화"""
    try:
        # 강의 목록 새로고침
        courses = await course_service.get_courses(current_user["id"])

        if not courses:
            return {
                "status": "error",
                "message": "동기화할 강의가 없습니다.",
                "courses": []
            }

        # 각 강의별 동기화 작업 준비
        async def sync_course_background(course_id: str) -> Dict[str, Any]:
            return await sync_course(
                course_id=course_id,
                auto_download=auto_download,
                current_user=current_user,
                course_service=course_service,
                notice_service=notice_service,
                material_service=material_service,
                assignment_service=assignment_service,
                syllabus_service=syllabus_service
            )

        # 백그라운드 작업으로 동기화 실행
        for course in courses:
            if isinstance(course, dict):
                course_id = course.get('id') or course.get('course_id')
            else:
                course_id = getattr(course, 'id', None) or getattr(course, 'course_id', None)
            logger.info(f"크롤링 시작할 강의: {course} -> course_id: {course_id}")
            background_tasks.add_task(sync_course_background, course_id)

        return {
            "status": "started",
            "message": f"모든 강의 동기화가 시작되었습니다 ({len(courses)}개)",
            "courses": [{
                "id": course.get('id') or course.get('course_id') if isinstance(course, dict)
                     else getattr(course, 'id', None) or getattr(course, 'course_id', None),
                "name": course.get('name') or course.get('course_name') if isinstance(course, dict)
                       else getattr(course, 'name', None) or getattr(course, 'course_name', None)
            } for course in courses]
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"동기화 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/status/{task_id}")
async def get_sync_status(
        task_id: str,
        current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """동기화 작업 상태 확인"""
    # task_id에 해당하는 작업 상태 반환
    # 이 부분은 작업 추적 시스템에 따라 구현 필요
    return {
        "task_id": task_id,
        "status": "not_implemented",
        "message": "작업 상태 추적 기능이 구현되지 않았습니다."
    }


@router.post("/cancel/{task_id}")
async def cancel_sync(
        task_id: str,
        current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """동기화 작업 취소"""
    # task_id에 해당하는 작업 취소
    # 이 부분은 작업 추적 시스템에 따라 구현 필요
    return {
        "task_id": task_id,
        "status": "not_implemented",
        "message": "작업 취소 기능이 구현되지 않았습니다."
    }


@router.post("/all")
async def crawl_all_courses(
        background_tasks: BackgroundTasks,
        auto_download: bool = True,
        current_user: dict = Depends(get_current_user),
        course_service: CourseService = Depends(get_course_service),
        crawl_service: CrawlService = Depends(get_crawl_service)
) -> Any:
    """모든 강의 자동 크롤링 시작"""
    try:
        logger.info(f"모든 강의 크롤링 시작 - 사용자: {current_user['id']}, 자동 다운로드: {auto_download}")

        # 실제 크롤링 작업은 CrawlService를 통해 수행
        result = await crawl_service.crawl_all_courses(
            user_id=current_user["id"],
            auto_download=auto_download
        )

        logger.info(f"크롤링 완료 - 결과: {result.get('status', 'unknown')}")
        return result
    except Exception as e:
        logger.exception(f"크롤링 중 예외 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"크롤링 중 오류 발생: {str(e)}"
        )