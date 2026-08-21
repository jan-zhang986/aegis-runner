# -*- coding: utf-8 -*-
import asyncio
from unittest.mock import AsyncMock, patch

from apps.master.api.routes.health_router import (
    health_check,
    readiness_check,
    metrics,
    database_health,
    pool_health,
)


def test_health_check_returns_ok_payload():
    async def _run():
        response = await health_check()
        assert response["status"] == "ok"
        assert response["service"] == "aegis-runner"

    asyncio.run(_run())


def test_readiness_check_reports_ready_when_primary_and_replica_ok():
    async def _run():
        with patch(
            "apps.master.api.routes.health_router.check_db_health",
            new=AsyncMock(return_value={"primary": "ok", "replica": "ok"}),
        ), patch(
            "apps.master.api.routes.health_router.get_pool_status",
            return_value={"primary": {"size": 1}, "replica": {"size": 1}},
        ):
            response = await readiness_check()

        assert response["status"] == "ready"
        assert response["checks"]["primary_database"] is True
        assert response["checks"]["replica_database"] is True

    asyncio.run(_run())


def test_metrics_returns_prometheus_payload():
    async def _run():
        with patch(
            "apps.master.api.routes.health_router.get_pool_status",
            return_value={
                "primary": {"size": 1, "checked_out": 0, "overflow": 0, "checked_in": 1},
                "replica": {"size": 1, "checked_out": 0, "overflow": 0, "checked_in": 1},
            },
        ):
            response = await metrics()

        assert response.media_type == "text/plain; version=0.0.4; charset=utf-8"
        assert b"db_pool_size" in response.body

    asyncio.run(_run())


def test_database_health_returns_success_response():
    async def _run():
        with patch(
            "apps.master.api.routes.health_router.check_db_health",
            new=AsyncMock(return_value={"primary": "ok", "replica": "ok"}),
        ), patch(
            "apps.master.api.routes.health_router.get_pool_status",
            return_value={"primary": {"size": 1}, "replica": {"size": 1}},
        ):
            response = await database_health()

        assert response.code == 200
        assert response.data["database_health"]["primary"] == "ok"
        assert "pool_status" in response.data

    asyncio.run(_run())


def test_pool_health_returns_warning_when_utilization_high():
    async def _run():
        with patch(
            "apps.master.api.routes.health_router.get_pool_status",
            return_value={
                "primary": {"utilization": 85},
                "replica": {"utilization": 10},
            },
        ):
            response = await pool_health()

        assert response.code == 200
        assert response.data["warnings"] == ["主库连接池利用率过高: 85%"]

    asyncio.run(_run())
