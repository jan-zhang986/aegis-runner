# -*- coding: utf-8 -*-
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import BackgroundTasks

from apps.master.api.routes.workflow_router import batch_execute_workflow, get_batch_workflow_status
from apps.master.application.use_cases.task_splitter import Task
from aegis_runner.domain.models import BatchWorkflowExecuteRequest


class _Request:
    state = SimpleNamespace(user=SimpleNamespace(username="integration-tester"))


class _FakeAsyncSessionCM:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _InMemoryTaskRepository:
    def __init__(self):
        self.tasks = {}

    async def save_task(
        self,
        db,
        task_id,
        parent_task_id,
        task_type,
        priority,
        status,
        payload,
        created_by="",
        retry_count=0,
        max_retries=3,
        timeout=300,
    ):
        self.tasks[task_id] = {
            "task_id": task_id,
            "parent_task_id": parent_task_id,
            "task_type": task_type,
            "priority": priority,
            "status": status,
            "payload": payload,
            "worker_id": "",
            "progress": 0,
            "retry_count": retry_count,
            "max_retries": max_retries,
            "timeout": timeout,
            "created_by": created_by,
            "error_message": "",
            "created_at": "",
            "started_at": "",
            "finished_at": "",
        }
        return True

    async def update_task_status(self, db, task_id, status, **kwargs):
        task = self.tasks[task_id]
        task["status"] = status
        for key, value in kwargs.items():
            if value is not None and key in task:
                task[key] = value
        return True

    async def query_task_by_id(self, db, task_id):
        return self.tasks.get(task_id)

    async def query_tasks_by_parent_id(self, db, parent_task_id):
        return [task for task in self.tasks.values() if task["parent_task_id"] == parent_task_id]


class _FakeRedisClient:
    def __init__(self):
        self.task_statuses = {}
        self.client = self

    async def set_task_status(self, task_id, status, progress=0, **kwargs):
        current = self.task_statuses.setdefault(task_id, {})
        current.update({"status": status, "progress": progress, **kwargs})

    async def update_task_field(self, task_id, field, value):
        current = self.task_statuses.setdefault(task_id, {})
        current[field] = value

    async def get_task_status(self, task_id):
        return self.task_statuses.get(task_id)

    async def hget(self, key, field):
        task_id = key.replace("task:", "", 1)
        value = self.task_statuses.get(task_id, {}).get(field)
        return value


def test_batch_workflow_submission_and_status_query_flow():
    async def _run():
        request_data = BatchWorkflowExecuteRequest(
            workflows=[
                {
                    "workflow": {"nodes": [], "edges": [], "id": "wf-1"},
                    "variables": {"case": 1},
                    "runId": "run-1",
                },
                {
                    "workflow": {"nodes": [], "edges": [], "id": "wf-2"},
                    "variables": {"case": 2},
                    "runId": "run-2",
                },
            ],
            priority="normal",
            maxBatchSize=10,
            reportId="report-1",
        )

        background_tasks = BackgroundTasks()
        repository = _InMemoryTaskRepository()
        redis_client = _FakeRedisClient()
        kafka = AsyncMock()
        kafka.send_tasks_batch = AsyncMock(return_value={"success": 2, "failed": 0, "details": []})

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()

        def fake_sessionmaker(*_a, **_k):
            def factory():
                return _FakeAsyncSessionCM(mock_db)

            return factory

        with patch(
            "apps.master.application.services.workflow_service.get_task_repository",
            return_value=repository,
        ), patch(
            "apps.master.api.routes.workflow_router.get_task_repository",
            return_value=repository,
        ), patch(
            "apps.master.application.services.workflow_service.get_redis_client",
            new=AsyncMock(return_value=redis_client),
        ), patch(
            "apps.master.api.routes.workflow_router.get_redis_client",
            new=AsyncMock(return_value=redis_client),
        ), patch(
            "apps.master.application.services.workflow_service.get_kafka_producer",
            new=AsyncMock(return_value=kafka),
        ), patch(
            "apps.master.application.services.workflow_service.create_async_engine",
            return_value=mock_engine,
        ), patch(
            "apps.master.application.services.workflow_service.async_sessionmaker",
            side_effect=fake_sessionmaker,
        ):
            submit_resp = await batch_execute_workflow(request_data, _Request(), background_tasks)
            tracer_id = submit_resp.data["tracerId"]

            assert submit_resp.code == 200
            assert submit_resp.data["total_tasks"] == 2
            assert len(background_tasks.tasks) == 1

            for task in background_tasks.tasks:
                await task()

            status_resp = await get_batch_workflow_status(tracer_id, db_read=AsyncMock())

        assert status_resp.code == 200
        assert status_resp.data["tracer_id"] == tracer_id
        assert status_resp.data["total"] == 2
        assert status_resp.data["status_count"]["pending"] == 2
        assert status_resp.data["overall_status"] == "running"
        kafka.send_tasks_batch.assert_awaited_once()
        mock_engine.dispose.assert_awaited_once()

    asyncio.run(_run())
