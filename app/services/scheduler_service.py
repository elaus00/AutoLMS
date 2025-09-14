import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass

from app.services.session_manager import session_manager
from app.services.session.eclass_session_manager import EclassSessionManager
from app.core.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

@dataclass
class ScheduledTask:
    """스케줄된 작업 정의"""
    name: str
    func: Callable
    interval: int  # 실행 간격 (초)
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    enabled: bool = True
    max_retries: int = 3
    current_retries: int = 0
    running: bool = False  # 작업 실행 상태 (동시 실행 방지)

class SchedulerService:
    """백그라운드 작업 스케줄러"""
    
    def __init__(self):
        self.tasks: Dict[str, ScheduledTask] = {}
        self.running = False
        self._scheduler_task = None
        self.supabase = get_supabase_client()
    
    def add_task(self, task: ScheduledTask) -> None:
        """스케줄된 작업 추가"""
        if task.next_run is None:
            task.next_run = datetime.now() + timedelta(seconds=task.interval)
        
        self.tasks[task.name] = task
        logger.info(f"스케줄된 작업 추가: {task.name} (간격: {task.interval}초)")
    
    def remove_task(self, name: str) -> None:
        """스케줄된 작업 제거"""
        if name in self.tasks:
            del self.tasks[name]
            logger.info(f"스케줄된 작업 제거: {name}")
    
    async def start(self) -> None:
        """스케줄러 시작"""
        if self.running:
            logger.warning("스케줄러가 이미 실행 중입니다")
            return
        
        self.running = True
        logger.info("백그라운드 스케줄러 시작")
        
        # 기본 작업들 등록
        await self._register_default_tasks()
        
        # 스케줄러 메인 루프 시작
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
    
    async def stop(self) -> None:
        """스케줄러 정지"""
        self.running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        logger.info("백그라운드 스케줄러 정지")
    
    async def _scheduler_loop(self) -> None:
        """스케줄러 메인 루프"""
        while self.running:
            try:
                now = datetime.now()
                
                for task_name, task in self.tasks.items():
                    if not task.enabled:
                        continue
                    
                    # 실행 시간 체크
                    if task.next_run and now >= task.next_run:
                        await self._execute_task(task)
                
                # 1초마다 체크
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"스케줄러 루프 중 오류: {str(e)}")
                await asyncio.sleep(5)  # 오류 시 5초 대기
    
    async def _execute_task(self, task: ScheduledTask) -> None:
        """작업 실행 (동시성 제어 포함)"""

        # 동시 실행 방지 체크
        if task.running:
            logger.info(f"작업 {task.name}이 이미 실행 중입니다. 건너뜀")
            return

        task.running = True
        start_time = datetime.now()

        try:
            logger.info(f"작업 실행 시작: {task.name}")

            # 작업 실행
            if asyncio.iscoroutinefunction(task.func):
                await task.func()
            else:
                task.func()

            # 성공 시 다음 실행 시간 설정
            task.last_run = start_time
            task.next_run = task.last_run + timedelta(seconds=task.interval)
            task.current_retries = 0

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"작업 실행 완료: {task.name} (소요시간: {duration:.2f}초)")

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"작업 실행 중 오류 ({task.name}): {str(e)} (소요시간: {duration:.2f}초)")

            # 재시도 로직
            task.current_retries += 1
            if task.current_retries < task.max_retries:
                # 재시도를 위해 짧은 간격으로 다음 실행 시간 설정
                task.next_run = datetime.now() + timedelta(seconds=30)
                logger.warning(f"작업 재시도 예정: {task.name} ({task.current_retries}/{task.max_retries})")
            else:
                # 최대 재시도 횟수 초과 시 정상 간격으로 재설정
                task.last_run = start_time
                task.next_run = task.last_run + timedelta(seconds=task.interval)
                task.current_retries = 0
                logger.error(f"작업 최대 재시도 초과, 다음 주기로 연기: {task.name}")

        finally:
            # 반드시 실행 상태 해제
            task.running = False
    
    async def _register_default_tasks(self) -> None:
        """기본 작업들 등록"""
        
        # 1. 만료된 JWT 세션 정리 (30분마다)
        cleanup_sessions_task = ScheduledTask(
            name="cleanup_expired_sessions",
            func=self._cleanup_expired_sessions,
            interval=1800  # 30분
        )
        self.add_task(cleanup_sessions_task)
        
        # 2. 이클래스 세션 건강 체크 (10분마다)
        check_eclass_sessions_task = ScheduledTask(
            name="check_eclass_sessions_health",
            func=self._check_eclass_sessions_health,
            interval=600  # 10분
        )
        self.add_task(check_eclass_sessions_task)
        
        # 3. 자동 콘텐츠 새로고침 (1시간마다)
        auto_refresh_content_task = ScheduledTask(
            name="auto_refresh_content",
            func=self._auto_refresh_content,
            interval=3600  # 1시간
        )
        self.add_task(auto_refresh_content_task)
        
        # 4. 시스템 상태 모니터링 (5분마다)
        system_health_task = ScheduledTask(
            name="system_health_check",
            func=self._system_health_check,
            interval=300  # 5분
        )
        self.add_task(system_health_task)
    
    async def _cleanup_expired_sessions(self) -> None:
        """만료된 JWT 세션 정리"""
        try:
            cleaned_count = await session_manager.cleanup_expired_sessions()
            logger.info(f"만료된 세션 {cleaned_count}개 정리 완료")
        except Exception as e:
            logger.error(f"세션 정리 중 오류: {str(e)}")
    
    async def _check_eclass_sessions_health(self) -> None:
        """이클래스 세션 건강 체크"""
        try:
            eclass_manager = EclassSessionManager()
            await eclass_manager.check_sessions_health()
        except Exception as e:
            logger.error(f"이클래스 세션 건강 체크 중 오류: {str(e)}")
    
    async def _auto_refresh_content(self) -> None:
        """자동 콘텐츠 새로고침"""
        try:
            # 활성 사용자들의 콘텐츠를 자동으로 새로고침
            # 현재 시간에서 24시간 이내에 활동한 사용자들 조회
            cutoff_time = (datetime.now() - timedelta(hours=24)).isoformat()
            
            # sessions와 users 테이블 JOIN하여 eclass_username 조회
            result = self.supabase.table('sessions')\
                .select('user_id, users!sessions_user_id_fkey(eclass_username)')\
                .gt('last_used', cutoff_time)\
                .eq('is_active', True)\
                .execute()
            
            active_users = result.data if result.data else []
            
            for user in active_users:
                try:
                    user_id = user['user_id']
                    logger.info(f"사용자 {user_id} 콘텐츠 자동 새로고침 시작")
                    
                    # 사용자 강의 목록 조회
                    courses_result = self.supabase.table('user_courses')\
                        .select('course_id')\
                        .eq('user_id', user_id)\
                        .execute()
                    
                    if courses_result.data:
                        # TODO: 각 강의의 공지사항, 과제, 강의자료 자동 새로고침
                        # 현재는 로그만 기록
                        course_count = len(courses_result.data)
                        logger.info(f"사용자 {user_id}의 {course_count}개 강의 새로고침 예정")
                    
                except Exception as user_error:
                    logger.error(f"사용자 {user.get('user_id', 'Unknown')} 콘텐츠 새로고침 중 오류: {str(user_error)}")
                    continue
                    
        except Exception as e:
            logger.error(f"자동 콘텐츠 새로고침 중 오류: {str(e)}")
    
    async def _system_health_check(self) -> None:
        """시스템 상태 모니터링"""
        try:
            # 1. 데이터베이스 연결 상태 확인
            try:
                self.supabase.table('users').select('count').limit(1).execute()
                logger.debug("데이터베이스 연결 상태 정상")
            except Exception as db_error:
                logger.error(f"데이터베이스 연결 오류: {str(db_error)}")
            
            # 2. 활성 세션 수 모니터링
            try:
                sessions_result = self.supabase.table('sessions')\
                    .select('count')\
                    .eq('is_active', True)\
                    .execute()
                
                active_session_count = len(sessions_result.data) if sessions_result.data else 0
                logger.debug(f"활성 세션 수: {active_session_count}")
                
                # 너무 많은 세션이 활성화된 경우 경고
                if active_session_count > 1000:
                    logger.warning(f"활성 세션이 너무 많습니다: {active_session_count}")
                    
            except Exception as session_error:
                logger.error(f"세션 상태 확인 중 오류: {str(session_error)}")
            
        except Exception as e:
            logger.error(f"시스템 상태 확인 중 오류: {str(e)}")
    
    def get_task_status(self) -> Dict:
        """모든 작업의 상태 조회"""
        status = {
            "scheduler_running": self.running,
            "total_tasks": len(self.tasks),
            "tasks": {}
        }
        
        for name, task in self.tasks.items():
            status["tasks"][name] = {
                "enabled": task.enabled,
                "interval": task.interval,
                "last_run": task.last_run.isoformat() if task.last_run else None,
                "next_run": task.next_run.isoformat() if task.next_run else None,
                "current_retries": task.current_retries,
                "max_retries": task.max_retries
            }
        
        return status

# 싱글톤 인스턴스
scheduler_service = SchedulerService()