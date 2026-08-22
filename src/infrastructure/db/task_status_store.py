from __future__ import annotations

from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.logging import LOGGER
from src.core.config import get_primary_db_url


_worker_engine = create_async_engine(get_primary_db_url(), pool_pre_ping=True)
_worker_sessionmaker = async_sessionmaker(
    _worker_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db_write() -> AsyncGenerator[AsyncSession, None]:
    async with _worker_sessionmaker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def update_task_status(
    db: AsyncSession,
    task_id: str,
    status: str,
    worker_id: str | None = None,
    progress: int | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    error_message: str | None = None,
) -> bool:
    update_fields = ["status = :status"]
    params = {"task_id": task_id, "status": status}

    if worker_id is not None:
        update_fields.append("worker_id = :worker_id")
        params["worker_id"] = worker_id
    if progress is not None:
        update_fields.append("progress = :progress")
        params["progress"] = progress
    if started_at is not None:
        update_fields.append("started_at = :started_at")
        params["started_at"] = started_at
    if finished_at is not None:
        update_fields.append("finished_at = :finished_at")
        params["finished_at"] = finished_at
    if error_message is not None:
        update_fields.append("error_message = :error_message")
        params["error_message"] = error_message

    result = await db.execute(
        text(f"UPDATE task_execution SET {', '.join(update_fields)} WHERE task_id = :task_id"),
        params,
    )
    updated = (result.rowcount or 0) > 0
    if not updated:
        LOGGER.logger.warning(f"任务不存在: task_id={task_id}")
    return updated


async def query_recoverable_running_tasks(
    db: AsyncSession,
    *,
    started_before: datetime,
) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT task_id, worker_id, started_at
            FROM task_execution
            WHERE status = 'running'
              AND started_at IS NOT NULL
              AND started_at < :started_before
            """
        ),
        {"started_before": started_before},
    )
    rows = result.fetchall()
    return [
        {
            "task_id": row[0],
            "worker_id": row[1] or "",
            "started_at": row[2],
        }
        for row in rows
    ]


async def reset_task_for_recovery(
    db: AsyncSession,
    task_id: str,
) -> bool:
    result = await db.execute(
        text(
            """
            UPDATE task_execution
            SET status = 'pending',
                worker_id = '',
                progress = 0,
                started_at = NULL,
                finished_at = NULL,
                error_message = ''
            WHERE task_id = :task_id
              AND status = 'running'
            """
        ),
        {"task_id": task_id},
    )
    updated = (result.rowcount or 0) > 0
    if not updated:
        LOGGER.logger.warning(f"任务恢复重置失败或无需重置: task_id={task_id}")
    return updated
