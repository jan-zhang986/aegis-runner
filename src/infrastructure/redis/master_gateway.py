from datetime import datetime

from src.infrastructure.redis.redis_client import get_redis_client
from src.core.logging import LOGGER, add_endpoint_logger
from src.infrastructure.db.task_status_store import (
    get_db_write,
    query_recoverable_running_tasks,
    reset_task_for_recovery,
    update_task_status,
)


async def get_worker_redis_client():
    return await get_redis_client()


async def persist_task_status(
    task_id: str,
    status: str,
    worker_id: str | None = None,
    progress: int | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    error_message: str | None = None,
) -> bool:
    async for db in get_db_write():
        try:
            success = await update_task_status(
                db=db,
                task_id=task_id,
                status=status,
                worker_id=worker_id,
                progress=progress,
                started_at=started_at,
                finished_at=finished_at,
                error_message=error_message,
            )
            if success:
                await db.commit()
            else:
                await db.rollback()
            return success
        except Exception:
            await db.rollback()
            raise
    return False


def get_endpoint_logger(endpoint: str):
    return add_endpoint_logger(endpoint)


def get_logger():
    return LOGGER


async def query_recoverable_tasks(started_before: datetime) -> list[dict]:
    async for db in get_db_write():
        return await query_recoverable_running_tasks(db=db, started_before=started_before)
    return []


async def reset_task_after_recovery(task_id: str) -> bool:
    async for db in get_db_write():
        try:
            success = await reset_task_for_recovery(db=db, task_id=task_id)
            if success:
                await db.commit()
            else:
                await db.rollback()
            return success
        except Exception:
            await db.rollback()
            raise
    return False
