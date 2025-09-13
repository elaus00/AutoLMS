from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any

from app.schemas.material import Material, MaterialList, MaterialRefreshResponse
from app.api.deps import (
    get_current_user,
    get_course_service,
    get_material_service,
    get_storage_service
)
from app.services.content.course_service import CourseService
from app.services.content.material_service import MaterialService
from app.services.storage.storage_service import StorageService

router = APIRouter()

@router.get("/", response_model=MaterialList)
async def get_materials(
    course_id: str,
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
    course_service: CourseService = Depends(get_course_service),
    material_service: MaterialService = Depends(get_material_service)
) -> Any:
    """특정 강의의 강의자료 목록 조회"""
    # 강의 존재 여부 확인
    course = await course_service.get_course(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의를 찾을 수 없습니다."
        )

    materials = await material_service.get_materials_by_course(course_id, skip=skip, limit=limit)
    total = len(materials)

    return {
        "materials": materials,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.get("/refresh", response_model=MaterialRefreshResponse)
async def refresh_materials(
    course_id: str,
    current_user: dict = Depends(get_current_user),
    course_service: CourseService = Depends(get_course_service),
    material_service: MaterialService = Depends(get_material_service)
) -> Any:
    """특정 강의의 강의자료 새로고침"""
    # 강의 존재 여부 확인
    course = await course_service.get_course(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의를 찾을 수 없습니다."
        )

    result = await material_service.refresh_all(course_id, current_user["id"], auto_download=True)

    # 새로고침 후 강의자료 목록 반환
    materials = await material_service.get_materials_by_course(course_id)
    return {
        "materials": materials,
        "total": len(materials),
        "refresh_result": result
    }

@router.get("/{material_id}", response_model=Material)
async def get_material(
    course_id: str,
    material_id: int,
    current_user: dict = Depends(get_current_user),
    course_service: CourseService = Depends(get_course_service),
    material_service: MaterialService = Depends(get_material_service)
) -> Any:
    """특정 강의자료 조회"""
    # 강의 존재 여부 확인
    course = await course_service.get_course(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의를 찾을 수 없습니다."
        )

    material = await material_service.get_material_by_id(str(material_id))
    if not material or material.course_id != course_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의자료를 찾을 수 없습니다."
        )

    return material

@router.get("/{material_id}/attachments/{attachment_id}")
async def download_material_attachment(
    course_id: str,
    material_id: int,
    attachment_id: int,
    current_user: dict = Depends(get_current_user),
    course_service: CourseService = Depends(get_course_service),
    material_service: MaterialService = Depends(get_material_service),
    storage_service: StorageService = Depends(get_storage_service)
) -> Any:
    """강의자료 첨부파일 다운로드 URL 조회"""
    # 강의 존재 여부 확인
    course = await course_service.get_course(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의를 찾을 수 없습니다."
        )

    # 강의자료 확인
    material = await material_service.get_material_by_id(str(material_id))
    if not material or material.course_id != course_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의자료를 찾을 수 없습니다."
        )

    # 첨부파일 다운로드 URL 조회
    download_url = await storage_service.get_download_url(attachment_id, current_user["id"])
    if not download_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="첨부파일을 찾을 수 없습니다."
        )

    return {"download_url": download_url}