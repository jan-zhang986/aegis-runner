# -*- coding: utf-8 -*-
import asyncio
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from aegis_runner.infrastructure.kafka import TaskProducer
from aegis_runner.core.infrastructure.redis_client import RedisClient
from aegis_runner.core.config import (
    get_db_pool_settings,
    get_kafka_bootstrap_servers,
    get_primary_db_url,
    get_redis_settings,
)


def _require_runtime_e2e_enabled() -> None:
    if os.getenv("ENABLE_RUNTIME_E2E") != "1":
        pytest.skip("真实依赖 e2e 未启用，设置 ENABLE_RUNTIME_E2E=1 后运行")


def test_runtime_dependencies_smoke():
    _require_runtime_e2e_enabled()

    async def _run():
        engine = create_async_engine(get_primary_db_url(), **get_db_pool_settings())
        redis_client = RedisClient(**get_redis_settings())
        kafka_producer = TaskProducer(get_kafka_bootstrap_servers())

        try:
            async with engine.connect() as connection:
                result = await connection.execute(text("SELECT 1"))
                assert result.scalar() == 1

            await redis_client.connect()
            assert await redis_client.client.ping() is True

            await kafka_producer.start()
            assert kafka_producer.producer is not None
        finally:
            await kafka_producer.stop()
            await redis_client.close()
            await engine.dispose()

    asyncio.run(_run())
