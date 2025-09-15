import asyncio
import logging
import time
from typing import Dict, Optional
from contextlib import asynccontextmanager
import weakref

logger = logging.getLogger(__name__)


class ArticleLockManager:
    """
    ARTL_NUM 기반 동시성 제어를 위한 Lock Manager
    동일한 article_id(ARTL_NUM)에 대해서는 순차적 처리를 보장
    """

    def __init__(self, cleanup_interval: int = 300):  # 5분마다 정리
        self._locks: Dict[str, asyncio.Lock] = {}
        self._last_used: Dict[str, float] = {}
        self._cleanup_interval = cleanup_interval
        self._cleanup_task: Optional[asyncio.Task] = None
        self._main_lock = asyncio.Lock()
        logger.info("ArticleLockManager 초기화 완료")

    async def initialize(self) -> None:
        """Lock Manager 초기화 및 정리 작업 시작"""
        self._cleanup_task = asyncio.create_task(self._cleanup_unused_locks())
        logger.info("ArticleLockManager 정리 작업 시작")

    async def close(self) -> None:
        """리소스 정리"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        self._locks.clear()
        self._last_used.clear()
        logger.info("ArticleLockManager 종료 완료")

    async def get_lock(self, article_id: str) -> asyncio.Lock:
        """
        특정 article_id에 대한 Lock 반환

        Args:
            article_id: ARTL_NUM (예: 7789096)

        Returns:
            asyncio.Lock: 해당 article_id에 대한 전용 Lock
        """
        async with self._main_lock:
            if article_id not in self._locks:
                self._locks[article_id] = asyncio.Lock()
                logger.debug(f"새로운 Lock 생성: {article_id}")

            # 사용 시간 업데이트
            self._last_used[article_id] = time.time()
            return self._locks[article_id]

    @asynccontextmanager
    async def acquire_lock(self, article_id: str):
        """
        Context Manager로 Lock 사용

        사용법:
        async with lock_manager.acquire_lock("7789096"):
            # 동일한 article_id에 대해서는 순차 처리 보장
            await process_article(article_id)
        """
        lock = await self.get_lock(article_id)
        logger.debug(f"Lock 획득 시도: {article_id}")

        async with lock:
            logger.debug(f"Lock 획득 완료: {article_id}")
            try:
                yield
            finally:
                logger.debug(f"Lock 해제: {article_id}")

    async def _cleanup_unused_locks(self) -> None:
        """사용하지 않는 Lock들을 주기적으로 정리 (메모리 누수 방지)"""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)

                current_time = time.time()
                cutoff_time = current_time - (self._cleanup_interval * 2)  # 10분 이상 미사용 시 정리

                async with self._main_lock:
                    to_remove = []
                    for article_id, last_used in self._last_used.items():
                        if last_used < cutoff_time:
                            # Lock이 현재 사용 중이 아니면 정리
                            lock = self._locks.get(article_id)
                            if lock and not lock.locked():
                                to_remove.append(article_id)

                    for article_id in to_remove:
                        del self._locks[article_id]
                        del self._last_used[article_id]
                        logger.debug(f"미사용 Lock 정리: {article_id}")

                    if to_remove:
                        logger.info(f"{len(to_remove)}개의 미사용 Lock 정리 완료")

            except asyncio.CancelledError:
                logger.info("Lock 정리 작업 취소됨")
                break
            except Exception as e:
                logger.error(f"Lock 정리 중 오류: {str(e)}")

    def get_stats(self) -> Dict[str, int]:
        """현재 관리 중인 Lock 통계"""
        return {
            "active_locks": len(self._locks),
            "locked_count": sum(1 for lock in self._locks.values() if lock.locked())
        }


# 전역 인스턴스 (싱글톤 패턴)
_global_article_lock_manager: Optional[ArticleLockManager] = None


def get_article_lock_manager() -> ArticleLockManager:
    """전역 ArticleLockManager 인스턴스 반환"""
    global _global_article_lock_manager
    if _global_article_lock_manager is None:
        _global_article_lock_manager = ArticleLockManager()
    return _global_article_lock_manager


async def initialize_article_lock_manager() -> None:
    """전역 ArticleLockManager 초기화"""
    lock_manager = get_article_lock_manager()
    await lock_manager.initialize()


async def close_article_lock_manager() -> None:
    """전역 ArticleLockManager 종료"""
    global _global_article_lock_manager
    if _global_article_lock_manager:
        await _global_article_lock_manager.close()
        _global_article_lock_manager = None