# -*- coding: utf-8 -*-
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

from src.runner.runtime import main as worker_runtime


def test_update_task_status_in_db_passes_extended_fields():
    async def _run():
        started_at = datetime(2026, 4, 16, 10, 0, 0)
        finished_at = datetime(2026, 4, 16, 10, 1, 0)

        with patch.object(
            worker_runtime,
            "persist_task_status",
            new=AsyncMock(return_value=True),
        ) as persist_task_status:
            await worker_runtime.update_task_status_in_db(
                "task-1",
                "success",
                worker_id_value="worker-1",
                progress=100,
                started_at=started_at,
                finished_at=finished_at,
                error_message="",
            )

        _, kwargs = persist_task_status.await_args
        assert kwargs == {
            "task_id": "task-1",
            "status": "success",
            "worker_id": "worker-1",
            "progress": 100,
            "started_at": started_at,
            "finished_at": finished_at,
            "error_message": "",
        }

    asyncio.run(_run())


def test_execute_task_with_semaphore_skips_cancelled_task():
    async def _run():
        worker_runtime.task_semaphore = asyncio.Semaphore(1)
        worker_runtime.worker_id = "worker-1"
        worker_runtime.consumer = AsyncMock()
        redis_client = AsyncMock()
        redis_client.client.hget = AsyncMock(return_value="cancelled")
        worker_runtime.redis_client = redis_client

        msg = type("Msg", (), {"topic": "task-workflow-normal", "partition": 0, "offset": 3})()
        topic_partition = object()

        with patch.object(worker_runtime, "execute_task", new=AsyncMock()) as execute_task:
            await worker_runtime.execute_task_with_semaphore(
                {"task_id": "task-cancelled"},
                msg=msg,
                topic_partition=topic_partition,
            )

        execute_task.assert_not_awaited()
        worker_runtime.consumer.commit.assert_awaited_once()

    asyncio.run(_run())


def test_recover_stale_running_tasks_only_resets_tasks_from_inactive_workers():
    async def _run():
        redis_client = AsyncMock()
        redis_client.get_all_workers = AsyncMock(return_value={"worker-live": {"status": "busy"}})
        redis_client.set_task_status = AsyncMock()
        redis_client.update_task_field = AsyncMock()
        worker_runtime.redis_client = redis_client
        worker_runtime.running = True

        recoverable_tasks = [
            {"task_id": "task-stale", "worker_id": "worker-dead", "started_at": datetime(2026, 4, 17, 10, 0, 0)},
            {"task_id": "task-live", "worker_id": "worker-live", "started_at": datetime(2026, 4, 17, 10, 0, 0)},
        ]

        async def stop_after_one_iteration(_seconds):
            worker_runtime.running = False

        with patch.object(
            worker_runtime,
            "query_recoverable_tasks",
            new=AsyncMock(return_value=recoverable_tasks),
        ), patch.object(
            worker_runtime,
            "reset_task_after_recovery",
            new=AsyncMock(return_value=True),
        ) as reset_task_after_recovery, patch.object(
            worker_runtime.asyncio,
            "sleep",
            new=stop_after_one_iteration,
        ):
            await worker_runtime.recover_stale_running_tasks()

        reset_task_after_recovery.assert_awaited_once_with("task-stale")
        redis_client.set_task_status.assert_awaited_once_with(task_id="task-stale", status="pending", progress=0)
        assert redis_client.update_task_field.await_count == 4

    asyncio.run(_run())


def test_worker_health_port_can_be_overridden():
    assert isinstance(worker_runtime.WORKER_HEALTH_PORT, int)
