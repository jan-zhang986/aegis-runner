# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.master.domain.models.task_execution import TaskExecution
from apps.master.domain.repositories.task_repository import TaskRepository
from aegis_runner.core.logging import LOGGER


class SQLAlchemyTaskRepository(TaskRepository):
    """基于 SQLAlchemy 的任务仓储实现。"""

    async def save_task(
        self,
        db: AsyncSession,
        task_id: str,
        parent_task_id: str,
        task_type: str,
        priority: str,
        status: str,
        payload: Dict[str, Any],
        created_by: str = "",
        retry_count: int = 0,
        max_retries: int = 3,
        timeout: int = 300,
    ) -> bool:
        try:
            task_execution = TaskExecution(
                task_id=task_id,
                parent_task_id=parent_task_id,
                task_type=task_type,
                priority=priority,
                status=status,
                payload=payload,
                created_by=created_by,
                retry_count=retry_count,
                max_retries=max_retries,
                timeout=timeout,
                created_at=datetime.now(),
            )
            db.add(task_execution)
            LOGGER.logger.debug(f"保存任务记录成功: task_id={task_id}")
            return True
        except Exception as exc:
            LOGGER.logger.error(f"保存任务记录失败: task_id={task_id}, error={exc}")
            return False

    async def update_task_status(
        self,
        db: AsyncSession,
        task_id: str,
        status: str,
        worker_id: str = "",
        progress: int = 0,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        error_message: str = "",
        retry_count: int | None = None,
        max_retries: int | None = None,
    ) -> bool:
        try:
            stmt = select(TaskExecution).where(TaskExecution.task_id == task_id)
            result = await db.execute(stmt)
            task_execution = result.scalar_one_or_none()
            if not task_execution:
                LOGGER.logger.warning(f"任务不存在: task_id={task_id}")
                return False

            task_execution.status = status
            if status == "pending":
                task_execution.worker_id = worker_id
                task_execution.progress = progress
                task_execution.started_at = started_at
                task_execution.finished_at = finished_at
                task_execution.error_message = error_message
            else:
                if worker_id:
                    task_execution.worker_id = worker_id
                if progress >= 0:
                    task_execution.progress = progress
                if started_at:
                    task_execution.started_at = started_at
                if finished_at:
                    task_execution.finished_at = finished_at
                if error_message:
                    task_execution.error_message = error_message
            if retry_count is not None:
                task_execution.retry_count = retry_count
            if max_retries is not None:
                task_execution.max_retries = max_retries

            LOGGER.logger.debug(f"更新任务状态成功: task_id={task_id}, status={status}")
            return True
        except Exception as exc:
            LOGGER.logger.error(f"更新任务状态失败: task_id={task_id}, error={exc}")
            return False

    async def query_task_by_id(self, db: AsyncSession, task_id: str) -> Optional[Dict[str, Any]]:
        try:
            stmt = select(TaskExecution).where(TaskExecution.task_id == task_id)
            result = await db.execute(stmt)
            task_execution = result.scalar_one_or_none()
            if not task_execution:
                return None

            return {
                "task_id": task_execution.task_id,
                "parent_task_id": task_execution.parent_task_id,
                "task_type": task_execution.task_type,
                "priority": task_execution.priority,
                "status": task_execution.status,
                "payload": task_execution.payload if task_execution.payload else {},
                "worker_id": task_execution.worker_id,
                "progress": task_execution.progress,
                "retry_count": task_execution.retry_count,
                "max_retries": task_execution.max_retries,
                "timeout": task_execution.timeout,
                "created_at": task_execution.created_at.isoformat() if task_execution.created_at else "",
                "started_at": task_execution.started_at.isoformat() if task_execution.started_at else "",
                "finished_at": task_execution.finished_at.isoformat() if task_execution.finished_at else "",
                "created_by": task_execution.created_by,
                "error_message": task_execution.error_message,
            }
        except Exception as exc:
            LOGGER.logger.error(f"查询任务失败: task_id={task_id}, error={exc}")
            return None

    async def query_workflow_task_by_run_id(self, db: AsyncSession, run_id: str) -> Optional[Dict[str, Any]]:
        try:
            sql = text(
                """
                SELECT task_id
                FROM task_execution
                WHERE task_type = 'workflow'
                  AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.runId')) = :run_id
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            result = await db.execute(sql, {"run_id": run_id})
            row = result.mappings().first()
            if not row:
                return None
            return await self.query_task_by_id(db, row["task_id"])
        except Exception as exc:
            LOGGER.logger.error(f"按 runId 查询工作流任务失败: run_id={run_id}, error={exc}")
            return None

    async def query_tasks_by_parent_id(self, db: AsyncSession, parent_task_id: str) -> List[Dict[str, Any]]:
        try:
            stmt = select(TaskExecution).where(
                TaskExecution.parent_task_id == parent_task_id
            ).order_by(TaskExecution.created_at)
            result = await db.execute(stmt)
            task_executions = result.scalars().all()
            return [
                {
                    "task_id": task_execution.task_id,
                    "parent_task_id": task_execution.parent_task_id,
                    "task_type": task_execution.task_type,
                    "priority": task_execution.priority,
                    "status": task_execution.status,
                    "payload": task_execution.payload if task_execution.payload else {},
                    "worker_id": task_execution.worker_id,
                    "progress": task_execution.progress,
                    "retry_count": task_execution.retry_count,
                    "max_retries": task_execution.max_retries,
                    "timeout": task_execution.timeout,
                    "created_by": task_execution.created_by,
                    "error_message": task_execution.error_message,
                    "created_at": task_execution.created_at.isoformat() if task_execution.created_at else "",
                    "started_at": task_execution.started_at.isoformat() if task_execution.started_at else "",
                    "finished_at": task_execution.finished_at.isoformat() if task_execution.finished_at else "",
                }
                for task_execution in task_executions
            ]
        except Exception as exc:
            LOGGER.logger.error(f"查询子任务失败: parent_task_id={parent_task_id}, error={exc}")
            return []
