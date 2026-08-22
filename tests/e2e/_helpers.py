# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def require_business_e2e_enabled() -> None:
    if os.getenv("ENABLE_BUSINESS_E2E") != "1":
        pytest.skip("业务 e2e 未启用，设置 ENABLE_BUSINESS_E2E=1 后运行")


def base_url() -> str:
    return os.getenv("MASTER_E2E_BASE_URL", "http://127.0.0.1:18100")


def auth_headers() -> dict[str, str]:
    token = os.getenv("MASTER_API_TOKEN", "").strip()
    headers = {}
    if token:
        headers["X-Master-Token"] = token
    return headers


def mysql_url() -> str:
    return (
        f"mysql+asyncmy://{os.getenv('MYSQL_E2E_USER', 'root')}:"
        f"{os.getenv('MYSQL_E2E_PASSWORD', 'root')}@"
        f"{os.getenv('MYSQL_E2E_HOST', '127.0.0.1')}:"
        f"{os.getenv('MYSQL_E2E_PORT', '13306')}/"
        f"{os.getenv('MYSQL_E2E_DATABASE', 'aegis_runner_e2e')}?charset=utf8mb4"
    )


def poll_task_status(client: httpx.Client, task_id: str, *, timeout_seconds: int = 60) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_payload = None
    while time.time() < deadline:
        response = client.get(f"/task/{task_id}/status", headers=auth_headers())
        if response.status_code == 200:
            payload = response.json()
            last_payload = payload
            status = payload.get("data", {}).get("status")
            if status in {"success", "failed", "timeout", "cancelled"}:
                return payload
        time.sleep(1)
    raise AssertionError(f"task {task_id} did not reach terminal state in time: last={last_payload}")


def poll_task_status_value(
    client: httpx.Client,
    task_id: str,
    expected_status: str,
    *,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_payload = None
    while time.time() < deadline:
        response = client.get(f"/task/{task_id}/status", headers=auth_headers())
        if response.status_code == 200:
            payload = response.json()
            last_payload = payload
            if payload.get("data", {}).get("status") == expected_status:
                return payload
        time.sleep(1)
    raise AssertionError(f"task {task_id} did not reach status={expected_status}: last={last_payload}")


async def _query_task_row_async(task_id: str) -> dict[str, Any] | None:
    engine = create_async_engine(mysql_url(), pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT task_id, parent_task_id, task_type, priority, status, progress,
                           worker_id, retry_count, max_retries, timeout, error_message
                    FROM task_execution
                    WHERE task_id = :task_id
                    """
                ),
                {"task_id": task_id},
            )
            row = result.mappings().first()
            return dict(row) if row else None
    finally:
        await engine.dispose()


def query_task_row(task_id: str) -> dict[str, Any] | None:
    return asyncio.run(_query_task_row_async(task_id))


async def _insert_running_task_async(task_id: str, *, worker_id: str) -> None:
    engine = create_async_engine(mysql_url(), pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            created_at = datetime.now() - timedelta(minutes=10)
            started_at = datetime.now() - timedelta(minutes=5)
            await connection.execute(
                text(
                    """
                    INSERT INTO task_execution (
                        task_id, parent_task_id, task_type, priority, status, payload,
                        worker_id, progress, retry_count, max_retries, timeout,
                        error_message, created_by, created_at, started_at, finished_at
                    ) VALUES (
                        :task_id, :parent_task_id, :task_type, :priority, :status, :payload,
                        :worker_id, :progress, :retry_count, :max_retries, :timeout,
                        :error_message, :created_by, :created_at, :started_at, :finished_at
                    )
                    """
                ),
                {
                    "task_id": task_id,
                    "parent_task_id": task_id,
                    "task_type": "workflow",
                    "priority": "normal",
                    "status": "running",
                    "payload": "{}",
                    "worker_id": worker_id,
                    "progress": 10,
                    "retry_count": 0,
                    "max_retries": 3,
                    "timeout": 300,
                    "error_message": "",
                    "created_by": "e2e",
                    "created_at": created_at,
                    "started_at": started_at,
                    "finished_at": None,
                },
            )
    finally:
        await engine.dispose()


def insert_running_task(task_id: str, *, worker_id: str) -> None:
    asyncio.run(_insert_running_task_async(task_id, worker_id=worker_id))


def redis_client():
    redis = pytest.importorskip("redis")
    return redis.Redis(
        host=os.getenv("REDIS_E2E_HOST", "127.0.0.1"),
        port=int(os.getenv("REDIS_E2E_PORT", "16379")),
        db=0,
        decode_responses=True,
    )
