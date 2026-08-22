#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import os

from kafka.admin import KafkaAdminClient, NewTopic
from sqlalchemy.ext.asyncio import create_async_engine


TOPICS = (
    "task-workflow-urgent",
    "task-workflow-high",
    "task-workflow-normal",
)


def _get_database_url() -> str:
    return os.getenv(
        "DB_PRIMARY_URL",
        "mysql+asyncmy://root:root@127.0.0.1:13306/aegis_runner_e2e?charset=utf8mb4",
    )


def _get_kafka_bootstrap_servers() -> str:
    return os.getenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:19092")


async def _init_schema() -> None:
    from src.infrastructure.db.database_async import AsyncBase
    from apps.master.domain.models.task_execution import TaskExecution  # noqa: F401

    engine = create_async_engine(_get_database_url(), pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(AsyncBase.metadata.create_all)
    finally:
        await engine.dispose()


def _init_topics() -> None:
    admin = KafkaAdminClient(bootstrap_servers=_get_kafka_bootstrap_servers())
    try:
        existing = set(admin.list_topics())
        to_create = [
            NewTopic(name=topic, num_partitions=1, replication_factor=1)
            for topic in TOPICS
            if topic not in existing
        ]
        if to_create:
            admin.create_topics(new_topics=to_create, validate_only=False)
    finally:
        admin.close()


def main() -> int:
    asyncio.run(_init_schema())
    _init_topics()
    print("e2e environment initialized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
