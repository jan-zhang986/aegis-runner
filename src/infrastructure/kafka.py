from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional

from aiokafka import AIOKafkaProducer

from src.core.config import get_kafka_bootstrap_servers
from src.core.logging import LOGGER


class TaskProducer:
    def __init__(self, bootstrap_servers: str):
        self.bootstrap_servers = bootstrap_servers
        self.producer: Optional[AIOKafkaProducer] = None

    async def start(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            compression_type="gzip",
            acks="all",
        )
        await self.producer.start()
        LOGGER.logger.info(f"Kafka producer started: {self.bootstrap_servers}")

    async def stop(self):
        if self.producer:
            await self.producer.stop()
            LOGGER.logger.info("Kafka producer stopped")

    async def send_task(
        self,
        task_id: str,
        parent_task_id: str,
        task_type: str,
        priority: str,
        payload: Dict[str, Any],
        created_by: str = "",
        retry_count: int = 0,
        max_retries: int = 3,
        timeout: int = 300,
        use_workflow_topic: bool = False,
    ) -> bool:
        topic = self._get_topic(priority, use_workflow_topic=use_workflow_topic)
        message = {
            "task_id": task_id,
            "parent_task_id": parent_task_id,
            "task_type": task_type,
            "priority": priority,
            "payload": payload,
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "created_by": created_by,
                "retry_count": retry_count,
                "max_retries": max_retries,
                "timeout": timeout,
            },
        }
        asyncio.create_task(self._send_task_async(topic, message, task_id))
        return True

    async def _send_task_async(self, topic: str, message: dict, task_id: str):
        record_metadata = await self.producer.send_and_wait(topic, value=message)
        LOGGER.logger.info(
            f"Task {task_id} confirmed sent to {topic} "
            f"(partition={record_metadata.partition}, offset={record_metadata.offset})"
        )

    async def send_workflow_result(self, topic: str, key: Optional[str], value: Dict[str, Any]) -> bool:
        key_bytes = key.encode("utf-8") if key else None
        record_metadata = await self.producer.send_and_wait(topic, key=key_bytes, value=value)
        LOGGER.logger.info(
            f"Workflow result sent to {topic} "
            f"(partition={record_metadata.partition}, offset={record_metadata.offset})"
        )
        return True

    async def send_step_event(self, topic: str, key: Optional[str], value: Dict[str, Any]) -> bool:
        key_bytes = key.encode("utf-8") if key else None
        record_metadata = await self.producer.send_and_wait(topic, key=key_bytes, value=value)
        LOGGER.logger.debug(
            f"Step event sent to {topic} "
            f"(partition={record_metadata.partition}, offset={record_metadata.offset})"
        )
        return True

    @staticmethod
    def _get_topic(priority: str, use_workflow_topic: bool = False) -> str:
        if use_workflow_topic:
            return {
                "urgent": "task-workflow-urgent",
                "high": "task-workflow-high",
                "normal": "task-workflow-normal",
            }.get(priority, "task-workflow-normal")
        return {
            "urgent": "task-urgent",
            "high": "task-high",
            "normal": "task-normal",
        }.get(priority, "task-normal")


_kafka_producer: Optional[TaskProducer] = None


async def get_kafka_producer() -> TaskProducer:
    global _kafka_producer
    if _kafka_producer is None:
        _kafka_producer = TaskProducer(get_kafka_bootstrap_servers())
        await _kafka_producer.start()
    return _kafka_producer


async def close_kafka_producer():
    global _kafka_producer
    if _kafka_producer:
        await _kafka_producer.stop()
        _kafka_producer = None
