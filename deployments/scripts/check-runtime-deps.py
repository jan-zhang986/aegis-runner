#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.infrastructure.kafka import TaskProducer
from src.core.infrastructure.redis_client import RedisClient
from src.core.config import (
    RuntimeConfigError,
    get_db_pool_settings,
    get_kafka_bootstrap_servers,
    get_primary_db_url,
    get_redis_settings,
)


async def _check_mysql() -> None:
    engine = create_async_engine(get_primary_db_url(), **get_db_pool_settings())
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            value = result.scalar()
            if value != 1:
                raise RuntimeError(f"MySQL 健康检查返回异常结果: {value}")
    finally:
        await engine.dispose()


async def _check_redis() -> None:
    client = RedisClient(**get_redis_settings())
    try:
        await client.connect()
        pong = await client.client.ping()
        if pong is not True:
            raise RuntimeError(f"Redis ping 失败: {pong}")
    finally:
        await client.close()


async def _check_kafka() -> None:
    producer = TaskProducer(get_kafka_bootstrap_servers())
    try:
        await producer.start()
    finally:
        await producer.stop()


async def main() -> int:
    checks = [
        ("MySQL", _check_mysql),
        ("Redis", _check_redis),
        ("Kafka", _check_kafka),
    ]

    for name, check in checks:
        print(f"[CHECK] {name}")
        try:
            await check()
        except RuntimeConfigError as exc:
            print(f"[FAIL] {name}: 配置错误: {exc}")
            return 1
        except Exception as exc:
            print(f"[FAIL] {name}: {exc}")
            return 1
        else:
            print(f"[ OK ] {name}")

    print("[ OK ] 运行时依赖检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
