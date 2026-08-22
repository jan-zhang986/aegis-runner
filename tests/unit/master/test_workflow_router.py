# -*- coding: utf-8 -*-
"""workflow_router：参数校验仅返回 400（ValueError），其它异常为 500。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from apps.master.api.routes.workflow_router import (
    execute_workflow,
    get_batch_workflow_status,
    cancel_batch_workflow,
    retry_batch_workflow,
    get_workflow_status,
)
from src.domain.models import WorkflowDebugExecuteRequest


class _Request:
    state = SimpleNamespace(user=SimpleNamespace(username="tester"))


def test_debug_execute_validation_empty_workflow_returns_400():
    async def _run():
        req = WorkflowDebugExecuteRequest(runId="r1", workflow={})
        return await execute_workflow(req, _Request(), db_write=AsyncMock())

    out = asyncio.run(_run())
    assert out.code == 400
    assert "参数校验失败" in out.message


def test_debug_execute_submit_failure_returns_500():
    wf = {"nodes": [], "edges": [], "workflowId": "w1"}

    async def _run():
        req = WorkflowDebugExecuteRequest(runId="r1", workflow=wf)
        with patch(
            "apps.master.api.routes.workflow_router.WorkflowService.submit_single_workflow",
            new=AsyncMock(side_effect=RuntimeError("db unavailable")),
        ):
            return await execute_workflow(req, _Request(), db_write=AsyncMock())

    out = asyncio.run(_run())
    assert out.code == 500
    assert "工作流任务创建失败" in out.message


def test_debug_execute_success():
    wf = {"nodes": [], "edges": [], "workflowId": "w1"}
    submit = AsyncMock(
        return_value=SimpleNamespace(task_id="tid-1", tracer_id="tid-1")
    )

    async def _run():
        req = WorkflowDebugExecuteRequest(runId="run-ok", workflow=wf)
        with patch(
            "apps.master.api.routes.workflow_router.WorkflowService.submit_single_workflow",
            new=submit,
        ):
            return await execute_workflow(req, _Request(), db_write=AsyncMock())

    out = asyncio.run(_run())
    assert out.code == 200
    assert out.data["task_id"] == "tid-1"
    assert out.data["tracerId"] == "tid-1"
    assert submit.await_count == 1


def test_get_workflow_status_falls_back_to_run_id_lookup():
    async def _run():
        redis_client = AsyncMock()
        redis_client.get_task_status = AsyncMock(return_value=None)
        redis_client.client.hget = AsyncMock(return_value=None)

        repo = AsyncMock()
        repo.query_task_by_id = AsyncMock(return_value=None)
        repo.query_workflow_task_by_run_id = AsyncMock(
            return_value={
                "task_id": "tid-run-1",
                "status": "success",
                "progress": 100,
                "worker_id": "worker-1",
                "started_at": "2026-04-20T16:00:00",
                "finished_at": "2026-04-20T16:00:01",
            }
        )

        with patch(
            "apps.master.api.routes.workflow_router.get_redis_client",
            new=AsyncMock(return_value=redis_client),
        ), patch(
            "apps.master.api.routes.workflow_router.get_task_repository",
            return_value=repo,
        ):
            response = await get_workflow_status("run-legacy-1", db_read=AsyncMock())

        assert response.code == 200
        assert response.data["tracer_id"] == "run-legacy-1"
        assert response.data["task_id"] == "tid-run-1"
        assert response.data["status"] == "success"
        assert response.data["source"] == "database"

    asyncio.run(_run())


def test_get_batch_workflow_status_reports_cancelled_tasks():
    async def _run():
        repo = AsyncMock()
        repo.query_tasks_by_parent_id = AsyncMock(
            return_value=[
                {
                    "task_id": "t-1",
                    "status": "cancelled",
                    "progress": 100,
                    "started_at": "",
                    "finished_at": "2026-04-17T12:00:00",
                    "worker_id": "",
                    "error_message": "Task cancelled before execution",
                },
                {
                    "task_id": "t-2",
                    "status": "success",
                    "progress": 100,
                    "started_at": "2026-04-17T11:00:00",
                    "finished_at": "2026-04-17T11:01:00",
                    "worker_id": "worker-1",
                    "error_message": "",
                },
            ]
        )

        with patch(
            "apps.master.api.routes.workflow_router.get_redis_client",
            new=AsyncMock(return_value=AsyncMock()),
        ), patch(
            "apps.master.api.routes.workflow_router.get_task_repository",
            return_value=repo,
        ):
            response = await get_batch_workflow_status("tracer-1", db_read=AsyncMock())

        assert response.code == 200
        assert response.data["status_count"]["cancelled"] == 1
        assert response.data["completed"] == 2
        assert response.data["overall_status"] == "completed_with_cancellations"

    asyncio.run(_run())


def test_cancel_batch_workflow_returns_counts():
    async def _run():
        with patch(
            "apps.master.api.routes.workflow_router.WorkflowService.cancel_batch_tasks",
            new=AsyncMock(return_value={"found": True, "cancelled": 2, "skipped": 1, "total": 3}),
        ):
            response = await cancel_batch_workflow("tracer-2", db_write=AsyncMock())

        assert response.code == 200
        assert response.data["cancelled"] == 2
        assert response.data["skipped"] == 1
        assert response.data["total"] == 3

    asyncio.run(_run())


def test_retry_batch_workflow_returns_counts():
    async def _run():
        with patch(
            "apps.master.api.routes.workflow_router.WorkflowService.retry_batch_tasks",
            new=AsyncMock(return_value={"found": True, "retried": 2, "skipped": 1, "total": 3}),
        ):
            response = await retry_batch_workflow("tracer-3", db_write=AsyncMock())

        assert response.code == 200
        assert response.data["retried"] == 2
        assert response.data["skipped"] == 1
        assert response.data["total"] == 3

    asyncio.run(_run())
