# -*- coding: utf-8 -*-
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

from aegis_runner.worker.infrastructure.redis import master_gateway


def test_persist_task_status_commits_on_success():
    dbs = []

    async def gen():
        db = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        dbs.append(db)
        yield db

    async def _run():
        with patch.object(master_gateway, "get_db_write", gen):
            with patch.object(
                master_gateway,
                "update_task_status",
                new=AsyncMock(return_value=True),
            ) as upd:
                ok = await master_gateway.persist_task_status("task-99", "running")
        assert ok is True
        upd.assert_awaited_once()
        dbs[0].commit.assert_awaited_once()
        dbs[0].rollback.assert_not_called()
        return ok

    assert asyncio.run(_run()) is True


def test_persist_task_status_rolls_back_on_repo_false():
    dbs = []

    async def gen():
        db = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        dbs.append(db)
        yield db

    async def _run():
        with patch.object(master_gateway, "get_db_write", gen):
            with patch.object(
                master_gateway,
                "update_task_status",
                new=AsyncMock(return_value=False),
            ):
                ok = await master_gateway.persist_task_status("task-99", "failed")
        assert ok is False
        dbs[0].rollback.assert_awaited_once()
        dbs[0].commit.assert_not_called()
        return ok

    assert asyncio.run(_run()) is False


def test_persist_task_status_forwards_metadata_fields():
    dbs = []
    started_at = datetime(2026, 4, 16, 10, 0, 0)
    finished_at = datetime(2026, 4, 16, 10, 1, 0)

    async def gen():
        db = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        dbs.append(db)
        yield db

    async def _run():
        with patch.object(master_gateway, "get_db_write", gen):
            with patch.object(
                master_gateway,
                "update_task_status",
                new=AsyncMock(return_value=True),
            ) as upd:
                ok = await master_gateway.persist_task_status(
                    "task-100",
                    "success",
                    worker_id="worker-1",
                    progress=100,
                    started_at=started_at,
                    finished_at=finished_at,
                    error_message="",
                )
        assert ok is True
        _, kwargs = upd.await_args
        assert kwargs["task_id"] == "task-100"
        assert kwargs["status"] == "success"
        assert kwargs["worker_id"] == "worker-1"
        assert kwargs["progress"] == 100
        assert kwargs["started_at"] == started_at
        assert kwargs["finished_at"] == finished_at
        assert kwargs["error_message"] == ""
        dbs[0].commit.assert_awaited_once()
        return ok

    assert asyncio.run(_run()) is True
