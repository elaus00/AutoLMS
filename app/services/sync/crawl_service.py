import logging
from typing import Dict, Any, List
import asyncio
from datetime import datetime
import uuid

# from sqlalchemy removed

from app.services.base_service import BaseService
from app.services.session.eclass_session_manager import EclassSessionManager
from app.services.content.course_service import CourseService
from app.services.content.notice_service import NoticeService
from app.services.content.material_service import MaterialService
from app.services.content.assignment_service import AssignmentService
from app.services.content.syllabus_service import SyllabusService

logger = logging.getLogger(__name__)


class CrawlService(BaseService):
    """동기화 및 크롤링 서비스 (다양한 콘텐츠 서비스 결합)"""

    def __init__(
            self,
            eclass_session: EclassSessionManager,
            course_service: CourseService,
            notice_service: NoticeService,
            material_service: MaterialService,
            assignment_service: AssignmentService,
            syllabus_service: SyllabusService
    ):
        self.session_service = eclass_session
        self.course_service = course_service
        self.notice_service = notice_service
        self.material_service = material_service
        self.assignment_service = assignment_service
        self.syllabus_service = syllabus_service
        self.active_tasks = {}  # 활성 태스크 관리
        logger.info("CrawlService 초기화 완료")

    async def initialize(self) -> None:
        """서비스 초기화"""
        logger.info("CrawlService 시작")
        pass

    async def close(self) -> None:
        """서비스 리소스 정리"""
        logger.info("CrawlService 종료 시작")
        # 실행 중인 모든 작업 취소
        for task_id, task_info in self.active_tasks.items():
            if task_info.get("status") in ["running", "processing"]:
                if "task" in task_info and not task_info["task"].done():
                    logger.info(f"작업 {task_id} 취소")
                    task_info["task"].cancel()
                    await asyncio.sleep(0)  # 태스크 상태 반영 대기

                task_info["status"] = "canceled"
                task_info["end_time"] = datetime.now().isoformat()
        logger.info("CrawlService 종료 완료")

    async def crawl_all(
            self,
            user_id: str,
            course_id: str = None,
            auto_download: bool = False
    ) -> Dict[str, Any]:
        """
        강의의 모든 콘텐츠 크롤링 (강의 정보, 강의 계획서, 공지사항, 강의자료, 과제 등)

        Args:
            user_id: 사용자 ID
            course_id: 강의 ID (None인 경우 모든 강의)
            auto_download: 첨부파일 자동 다운로드 여부

        Returns:
            Dict[str, Any]: 크롤링 결과
        """
        result = {
            "courses": 0,
            "syllabus": {"new": 0, "errors": 0},
            "notices": {"new": 0, "errors": 0},
            "materials": {"new": 0, "errors": 0},
            "assignments": {"new": 0, "errors": 0}
        }

        start_time = datetime.now()
        logger.info(f"모든 콘텐츠 크롤링 시작 - 사용자: {user_id}")

        try:
            # 1. 강의 목록 가져오기
            courses = await self.course_service.get_courses(user_id)
            result["courses"] = len(courses)

            # 2. 특정 강의만 처리하는 경우
            if course_id:
                courses = [course for course in courses if course.get('course_id') == course_id]
                if not courses:
                    logger.warning(f"강의 {course_id}를 찾을 수 없음")
                    return result

            # 3. 각 강의별 처리
            for course in courses:
                course_id_val = course.get('course_id', '알 수 없음')
                course_name_val = course.get('course_name', '알 수 없음')
                logger.info(f"강의 {course_id_val} - {course_name_val} 크롤링 시작")

                # 3.1 강의계획서 크롤링
                try:
                    course_id_for_syllabus = course.get('course_id')
                    syllabus_result = await self.syllabus_service.refresh_all(course_id_for_syllabus, user_id)
                    result["syllabus"]["new"] += syllabus_result.get("new", 0)
                    result["syllabus"]["errors"] += syllabus_result.get("errors", 0)
                except Exception as e:
                    logger.error(f"강의계획서 크롤링 중 오류: {str(e)}")
                    result["syllabus"]["errors"] += 1

                # 3.2 공지사항 크롤링
                try:
                    course_id_for_notice = course.get('course_id')
                    notice_result = await self.crawl_notices(user_id, course_id_for_notice, auto_download)
                    result["notices"]["new"] += notice_result.get("new", 0)
                    result["notices"]["errors"] += notice_result.get("errors", 0)
                except Exception as e:
                    logger.error(f"공지사항 크롤링 중 오류: {str(e)}")
                    result["notices"]["errors"] += 1

                # 3.3 강의자료 크롤링
                try:
                    course_id_for_material = course.get('course_id')
                    material_result = await self.material_service.refresh_all(course_id_for_material, user_id, auto_download)
                    result["materials"]["new"] += material_result.get("new", 0)
                    result["materials"]["errors"] += material_result.get("errors", 0)
                except Exception as e:
                    logger.error(f"강의자료 크롤링 중 오류: {str(e)}")
                    result["materials"]["errors"] += 1

                # 3.4 과제 크롤링
                try:
                    course_id_for_assignment = course.get('course_id')
                    assignment_result = await self.crawl_assignments(user_id, course_id_for_assignment, auto_download)
                    result["assignments"]["new"] += assignment_result.get("new", 0)
                    result["assignments"]["errors"] += assignment_result.get("errors", 0)
                except Exception as e:
                    logger.error(f"과제 크롤링 중 오류: {str(e)}")
                    result["assignments"]["errors"] += 1

                logger.info(f"강의 {course_id_val} - {course_name_val} 크롤링 완료")

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.info(f"모든 콘텐츠 크롤링 완료 - 총 소요시간: {duration:.2f}초")

            # 결과에 소요시간 추가
            result["duration_seconds"] = duration

            return result

        except Exception as e:
            logger.error(f"크롤링 중 오류 발생: {str(e)}")
            return result

    async def crawl_notices(
            self,
            user_id: str,
            course_id: str,
            auto_download: bool = False
    ) -> Dict[str, Any]:
        """
        특정 강의의 공지사항 크롤링

        Args:
            user_id: 사용자 ID
            course_id: 강의 ID
            auto_download: 첨부파일 자동 다운로드 여부

        Returns:
            Dict[str, Any]: 크롤링 결과
        """
        logger.info(f"공지사항 크롤링 시작 - 강의: {course_id}, 사용자: {user_id}")

        try:
            # 공지사항 크롤링 실행
            notice_result = await self.notice_service.refresh_all(course_id, user_id, auto_download)

            logger.info(f"공지사항 크롤링 완료 - 강의: {course_id}")
            logger.info(
                f"결과: 총 {notice_result['count']}개, 새로운 {notice_result['new']}개, 건너뛴 {notice_result.get('skipped', 0)}개, 오류 {notice_result['errors']}개")

            return notice_result

        except Exception as e:
            logger.error(f"공지사항 크롤링 중 오류 발생: {str(e)}")
            return {"count": 0, "new": 0, "errors": 1}

    async def crawl_assignments(
            self,
            user_id: str,
            course_id: str,
            auto_download: bool = False
    ) -> Dict[str, Any]:
        """
        특정 강의의 과제 크롤링

        Args:
            user_id: 사용자 ID
            course_id: 강의 ID
            auto_download: 첨부파일 자동 다운로드 여부

        Returns:
            Dict[str, Any]: 크롤링 결과
        """
        logger.info(f"과제 크롤링 시작 - 강의: {course_id}, 사용자: {user_id}")

        try:
            # 과제 크롤링 실행
            assignment_result = await self.assignment_service.refresh_all(course_id, user_id, auto_download)

            logger.info(f"과제 크롤링 완료 - 강의: {course_id}")
            logger.info(
                f"결과: 총 {assignment_result['count']}개, 새로운 {assignment_result['new']}개, 건너뛴 {assignment_result.get('skipped', 0)}개, 오류 {assignment_result['errors']}개")

            return assignment_result

        except Exception as e:
            logger.error(f"과제 크롤링 중 오류 발생: {str(e)}")
            return {"count": 0, "new": 0, "errors": 1}

    async def crawl_materials(
            self,
            user_id: str,
            course_id: str,
            auto_download: bool = False
    ) -> Dict[str, Any]:
        """
        특정 강의의 강의자료 크롤링

        Args:
            user_id: 사용자 ID
            course_id: 강의 ID
            auto_download: 첨부파일 자동 다운로드 여부

        Returns:
            Dict[str, Any]: 크롤링 결과
        """
        logger.info(f"강의자료 크롤링 시작 - 강의: {course_id}, 사용자: {user_id}")

        try:
            # 강의자료 크롤링 실행
            material_result = await self.material_service.refresh_all(course_id, user_id, auto_download)

            logger.info(f"강의자료 크롤링 완료 - 강의: {course_id}")
            logger.info(
                f"결과: 총 {material_result['count']}개, 새로운 항목 {material_result['new']}개, 오류 {material_result['errors']}개")

            return material_result

        except Exception as e:
            logger.error(f"강의자료 크롤링 중 오류 발생: {str(e)}")
            return {"count": 0, "new": 0, "errors": 1}

    async def crawl_syllabus(
            self,
            user_id: str,
            course_id: str,
    ) -> Dict[str, Any]:
        """
        특정 강의의 강의계획서 크롤링

        Args:
            user_id: 사용자 ID
            course_id: 강의 ID

        Returns:
            Dict[str, Any]: 크롤링 결과
        """
        logger.info(f"강의계획서 크롤링 시작 - 강의: {course_id}, 사용자: {user_id}")

        try:
            # 강의계획서 크롤링 실행
            syllabus_result = await self.syllabus_service.refresh_all(course_id, user_id)

            logger.info(f"강의계획서 크롤링 완료 - 강의: {course_id}")
            logger.info(f"결과: 새로운 항목 {syllabus_result['new']}개, 오류 {syllabus_result['errors']}개")

            return syllabus_result

        except Exception as e:
            logger.error(f"강의계획서 크롤링 중 오류 발생: {str(e)}")
            return {"new": 0, "errors": 1}

    async def crawl_all_courses(self, user_id: str, auto_download: bool = False) -> Dict[
        str, Any]:
        """
        모든 강의 크롤링

        Args:
            user_id: 사용자 ID
            auto_download: 첨부파일 자동 다운로드 여부

        Returns:
            Dict[str, Any]: 크롤링 작업 정보
        """
        # 작업 ID 생성
        task_id = f"crawl_all_{uuid.uuid4().hex[:8]}"

        logger.info(f"모든 강의 크롤링 작업 시작: {task_id} (사용자: {user_id})")

        # 로그인 상태 확인
        eclass_session = await self.session_service.get_session(user_id)
        if not eclass_session or not await eclass_session.is_logged_in():
            logger.error("로그인되지 않은 상태에서 크롤링 시도")
            return {
                "task_id": task_id,
                "status": "error",
                "message": "로그인이 필요합니다."
            }

        # 강의 목록 가져오기
        courses = await self.course_service.get_courses(user_id)

        if not courses:
            logger.warning("크롤링할 강의가 없습니다.")
            return {
                "task_id": task_id,
                "status": "error",
                "message": "크롤링할 강의가 없습니다.",
                "courses": []
            }

        # 작업 시작
        task = asyncio.create_task(
            self._crawl_all_courses_task(user_id, courses, auto_download, task_id)
        )

        # 작업 관리
        self.active_tasks[task_id] = {
            "task": task,
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "user_id": user_id,
            "auto_download": auto_download,
            "course_count": len(courses)
        }

        return {
            "task_id": task_id,
            "status": "running",
            "message": f"모든 강의 크롤링 작업이 시작되었습니다. ({len(courses)}개)",
            "courses": [course.get('course_name', '알 수 없음') for course in courses]
        }

    async def _crawl_all_courses_task(self, user_id: str, courses: List[Any],
                                      auto_download: bool, task_id: str) -> Dict[str, Any]:
        """
        모든 강의 크롤링 작업 수행

        Args:
            user_id: 사용자 ID
            courses: 강의 목록
            auto_download: 첨부파일 자동 다운로드 여부
            task_id: 작업 ID

        Returns:
            Dict[str, Any]: 크롤링 결과
        """
        try:
            # 작업 상태 업데이트
            if task_id in self.active_tasks:
                self.active_tasks[task_id]["status"] = "processing"

            # 크롤링 결과 저장
            result = {
                "task_id": task_id,
                "user_id": user_id,
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "course_results": {},
                "summary": {
                    "total_courses": len(courses),
                    "completed": 0,
                    "failed": 0,
                    "notices": {"count": 0, "new": 0, "errors": 0},
                    "materials": {"count": 0, "new": 0, "errors": 0},
                    "assignments": {"count": 0, "new": 0, "errors": 0},
                    "syllabus": {"new": 0, "errors": 0}
                }
            }

            # 각 강의 순차적으로 크롤링
            for course in courses:
                course_id = None
                try:
                    course_id = course.get('course_id')
                    if not course_id:
                        logger.error(f"강의 ID를 찾을 수 없음: {course}")
                        result["summary"]["failed"] += 1
                        continue

                    # 개별 강의 크롤링
                    course_result = await self.crawl_course(
                        user_id, course_id, auto_download, f"{task_id}_{course_id}"
                    )

                    # 결과 저장
                    result["course_results"][course_id] = {
                        "name": course.get('name', '알 수 없음'),
                        "code": course.get('code', course.get('course_code', '')),
                        "status": course_result.get("status", "unknown"),
                        "details": course_result.get("details", {})
                    }

                    # 요약 정보 업데이트
                    if course_result.get("status") == "success":
                        result["summary"]["completed"] += 1
                        details = course_result.get("details", {})

                        for category in ["notices", "materials", "assignments", "syllabus"]:
                            if category in details:
                                for key in ["count", "new", "errors"]:
                                    if key in details[category]:
                                        result["summary"][category][key] += details[category][key]
                    else:
                        result["summary"]["failed"] += 1

                except Exception as e:
                    course_name = course.get('name', '알 수 없음') if course else '알 수 없음'
                    course_code = course.get('code', course.get('course_code', '')) if course else ''
                    error_course_id = course_id or '알 수 없음'
                    
                    logger.error(f"강의 {error_course_id} 크롤링 중 오류: {e}")
                    
                    if course_id:
                        result["course_results"][course_id] = {
                            "name": course_name,
                            "code": course_code,
                            "status": "error",
                            "message": str(e)
                        }
                    
                    result["summary"]["failed"] += 1

            # 작업 완료
            if task_id in self.active_tasks:
                self.active_tasks[task_id]["status"] = "completed"
                self.active_tasks[task_id]["end_time"] = datetime.now().isoformat()
                self.active_tasks[task_id]["result"] = result

            logger.info(f"모든 강의 크롤링 작업 완료: {task_id}")
            return result

        except Exception as e:
            logger.exception(f"모든 강의 크롤링 작업 중 오류 발생: {e}")

            # 작업 실패
            if task_id in self.active_tasks:
                self.active_tasks[task_id]["status"] = "failed"
                self.active_tasks[task_id]["error"] = str(e)
                self.active_tasks[task_id]["end_time"] = datetime.now().isoformat()

            return {
                "task_id": task_id,
                "user_id": user_id,
                "status": "error",
                "message": f"크롤링 중 오류 발생: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

    async def crawl_course(self, user_id: str, course_id: str,
                           auto_download: bool = False, task_id: str = None) -> Dict[str, Any]:
        """
        특정 강의 크롤링 작업 시작

        Args:
            user_id: 사용자 ID
            course_id: 강의 ID
            auto_download: 첨부파일 자동 다운로드 여부
            task_id: 작업 ID (지정하지 않으면 새로 생성)

        Returns:
            Dict[str, Any]: 크롤링 작업 정보
        """
        # 작업 ID 생성 (지정되지 않은 경우)
        if not task_id:
            task_id = f"crawl_{course_id}_{uuid.uuid4().hex[:8]}"

        logger.info(f"강의 크롤링 작업 시작: {task_id} (강의: {course_id}, 사용자: {user_id})")

        # 로그인 상태 확인
        eclass_session = await self.session_service.get_session(user_id)
        if not eclass_session or not await eclass_session.is_logged_in():
            logger.error("로그인되지 않은 상태에서 크롤링 시도")
            return {
                "task_id": task_id,
                "status": "error",
                "message": "로그인이 필요합니다.",
                "course_id": course_id
            }

        # 코스 정보 확인
        course = await self.course_service.get_course(course_id)
        if not course:
            logger.error(f"강의 정보 없음: {course_id}")
            return {
                "task_id": task_id,
                "status": "error",
                "message": f"강의 {course_id} 정보를 찾을 수 없습니다.",
                "course_id": course_id
            }

        # 작업 시작
        task = asyncio.create_task(
            self._crawl_course_task(user_id, course_id, auto_download, task_id)
        )

        # 작업 관리
        self.active_tasks[task_id] = {
            "task": task,
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "course_id": course_id,
            "user_id": user_id,
            "auto_download": auto_download
        }

        return {
            "task_id": task_id,
            "status": "running",
            "message": "크롤링 작업이 시작되었습니다.",
            "course_id": course_id,
            "course_name": course.get('course_name', '알 수 없음')
        }

    async def _crawl_course_task(self, user_id: str, course_id: str,
                                 auto_download: bool, task_id: str) -> Dict[str, Any]:
        """
        강의 크롤링 작업 수행

        Args:
            user_id: 사용자 ID
            course_id: 강의 ID
            auto_download: 첨부파일 자동 다운로드 여부
            task_id: 작업 ID

        Returns:
            Dict[str, Any]: 크롤링 결과
        """
        try:
            # 작업 상태 업데이트
            if task_id in self.active_tasks:
                self.active_tasks[task_id]["status"] = "processing"

            # 크롤링 결과 저장
            result = {
                "task_id": task_id,
                "course_id": course_id,
                "user_id": user_id,
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "details": {
                    "notices": {"count": 0, "new": 0, "errors": 0},
                    "materials": {"count": 0, "new": 0, "errors": 0},
                    "assignments": {"count": 0, "new": 0, "errors": 0},
                    "syllabus": {"new": 0, "errors": 0}
                }
            }

            # 1. 강의계획서 크롤링
            try:
                syllabus_result = await self.crawl_syllabus(user_id, course_id)
                result["details"]["syllabus"] = syllabus_result
            except Exception as e:
                logger.error(f"강의계획서 크롤링 중 오류: {str(e)}")
                result["details"]["syllabus"]["errors"] += 1

            # 2. 공지사항 크롤링
            try:
                notice_result = await self.crawl_notices(user_id, course_id, auto_download)
                result["details"]["notices"] = notice_result
            except Exception as e:
                logger.error(f"공지사항 크롤링 중 오류: {str(e)}")
                result["details"]["notices"]["errors"] += 1

            # 3. 강의자료 크롤링
            try:
                material_result = await self.crawl_materials(user_id, course_id, auto_download)
                result["details"]["materials"] = material_result
            except Exception as e:
                logger.error(f"강의자료 크롤링 중 오류: {str(e)}")
                result["details"]["materials"]["errors"] += 1

            # 4. 과제 크롤링
            try:
                assignment_result = await self.crawl_assignments(user_id, course_id, auto_download)
                result["details"]["assignments"] = assignment_result
            except Exception as e:
                logger.error(f"과제 크롤링 중 오류: {str(e)}")
                result["details"]["assignments"]["errors"] += 1

            # 작업 완료
            if task_id in self.active_tasks:
                self.active_tasks[task_id]["status"] = "completed"
                self.active_tasks[task_id]["end_time"] = datetime.now().isoformat()
                self.active_tasks[task_id]["result"] = result

            logger.info(f"강의 크롤링 작업 완료: {task_id}")
            return result

        except Exception as e:
            logger.exception(f"강의 크롤링 작업 중 오류 발생: {e}")

            # 작업 실패
            if task_id in self.active_tasks:
                self.active_tasks[task_id]["status"] = "failed"
                self.active_tasks[task_id]["error"] = str(e)
                self.active_tasks[task_id]["end_time"] = datetime.now().isoformat()

            return {
                "task_id": task_id,
                "course_id": course_id,
                "user_id": user_id,
                "status": "error",
                "message": f"크롤링 중 오류 발생: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        작업 상태 조회

        Args:
            task_id: 작업 ID

        Returns:
            Dict[str, Any]: 작업 상태 정보
        """
        logger.info(f"작업 {task_id} 상태 조회")

        if task_id not in self.active_tasks:
            logger.warning(f"존재하지 않는 작업 ID: {task_id}")
            return {
                "task_id": task_id,
                "status": "not_found",
                "message": "존재하지 않는 작업입니다."
            }

        task_info = self.active_tasks[task_id]
        result = {
            "task_id": task_id,
            "status": task_info["status"],
        }

        # 추가 정보가 있으면 포함
        for key in ["start_time", "end_time", "course_id", "user_id", "message", "result"]:
            if key in task_info:
                result[key] = task_info[key]

        return result

    async def cancel_task(self, task_id: str) -> bool:
        """
        작업 취소

        Args:
            task_id: 작업 ID

        Returns:
            bool: 취소 성공 여부
        """
        logger.info(f"작업 {task_id} 취소 요청")

        if task_id not in self.active_tasks:
            logger.warning(f"존재하지 않는 작업 ID: {task_id}")
            return False

        task_info = self.active_tasks[task_id]

        # 이미 완료된 작업은 취소할 수 없음
        if task_info["status"] in ["completed", "failed", "canceled"]:
            logger.warning(f"이미 {task_info['status']} 상태인 작업은 취소할 수 없습니다: {task_id}")
            return False

        # 작업 취소
        if "task" in task_info and not task_info["task"].done():
            task_info["task"].cancel()
            await asyncio.sleep(0)  # 태스크 상태 반영 대기

        # 상태 업데이트
        task_info["status"] = "canceled"
        task_info["end_time"] = datetime.now().isoformat()

        logger.info(f"작업 {task_id} 취소 완료")
        return True