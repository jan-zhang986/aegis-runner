#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Worker 运行时：Kafka 消费、健康检查、任务执行与状态回写。

兼容入口 `start_worker.py` 仅负责启动本模块中的 `main()`。
"""
import asyncio
import json
import os
import socket
import sys
import threading
import time
from datetime import datetime
from datetime import timedelta

import psutil
from aiohttp import web
from aiokafka import AIOKafkaConsumer

from src.infrastructure.redis.master_gateway import (
    get_worker_redis_client,
    persist_task_status,
    get_endpoint_logger,
    get_logger,
    query_recoverable_tasks,
    reset_task_after_recovery,
)

LOGGER = get_logger()

# 全局状态
worker_id = None
consumer = None
redis_client = None
running = True
heartbeat_task = None
recovery_task = None
health_server = None
health_thread = None
health_loop = None
start_time = None
task_semaphore = None

max_concurrent_tasks = int(
    os.environ.get("WORKER_CONCURRENCY")
    or os.environ.get("WORKER_MAX_CONCURRENT")
    or "10"
)

WORKFLOW_TOPICS = (
    "task-workflow-urgent",
    "task-workflow-high",
    "task-workflow-normal",
)
WORKER_HEALTH_PORT = int(os.getenv("WORKER_HEALTH_PORT", "8080"))
TASK_RECOVERY_INTERVAL_SECONDS = int(os.getenv("TASK_RECOVERY_INTERVAL_SECONDS", "30"))
TASK_RECOVERY_MIN_AGE_SECONDS = int(os.getenv("TASK_RECOVERY_MIN_AGE_SECONDS", "90"))


def signal_handler(sig, frame):
    global running
    print("\n\n收到退出信号，正在关闭执行机...")
    running = False


async def health_check_handler(request):
    global worker_id, running, start_time
    try:
        cpu_usage = psutil.cpu_percent(interval=0)
        memory = psutil.virtual_memory()
        uptime_seconds = 0
        if start_time:
            uptime_seconds = int((datetime.now() - start_time).total_seconds())
        response = web.json_response(
            {
                "status": "ok",
                "worker_id": worker_id or "unknown",
                "running": running,
                "cpu_usage": f"{cpu_usage}%",
                "memory_usage": f"{memory.percent}%",
                "uptime_seconds": uptime_seconds,
                "timestamp": datetime.now().isoformat(),
            }
        )
        response.headers["Connection"] = "close"
        return response
    except Exception:
        response = web.json_response(
            {
                "status": "ok",
                "worker_id": worker_id or "unknown",
                "running": running,
                "timestamp": datetime.now().isoformat(),
            }
        )
        response.headers["Connection"] = "close"
        return response


async def readiness_check_handler(request):
    global running
    response = web.json_response(
        {
            "status": "ready" if running else "not_ready",
            "running": running,
            "timestamp": datetime.now().isoformat(),
        }
    )
    response.headers["Connection"] = "close"
    return response


def run_health_server_in_thread():
    global health_loop, health_server
    health_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(health_loop)

    async def start_server():
        global health_server
        app = web.Application()
        app.router.add_get("/health", health_check_handler)
        app.router.add_get("/healthz", health_check_handler)
        app.router.add_get("/readyz", readiness_check_handler)
        runner = web.AppRunner(app, access_log=None, shutdown_timeout=10)
        await runner.setup()
        site = web.TCPSite(
            runner,
            "0.0.0.0",
            WORKER_HEALTH_PORT,
            backlog=128,
            reuse_address=True,
            reuse_port=False,
        )
        await site.start()
        health_server = runner
        LOGGER.logger.info(
            f"Health check server started on http://0.0.0.0:{WORKER_HEALTH_PORT} (in separate thread)"
        )
        while running:
            await asyncio.sleep(1)

    try:
        health_loop.run_until_complete(start_server())
    except Exception as e:
        LOGGER.logger.error(f"Health server thread error: {e}")
    finally:
        health_loop.close()


def start_health_server():
    global health_thread
    health_thread = threading.Thread(target=run_health_server_in_thread, daemon=True)
    health_thread.start()
    time.sleep(1)
    print(f" 健康检查服务: http://0.0.0.0:{WORKER_HEALTH_PORT}/health")


def stop_health_server():
    global health_server, health_loop, health_thread
    if health_loop and health_server:
        try:
            asyncio.run_coroutine_threadsafe(health_server.cleanup(), health_loop)
            LOGGER.logger.info("Health check server stopped")
        except Exception as e:
            LOGGER.logger.warning(f"Failed to stop health server: {e}")
    if health_thread and health_thread.is_alive():
        health_thread.join(timeout=2)


async def register_worker():
    global worker_id, redis_client
    hostname = socket.gethostname()
    timestamp = int(time.time())
    worker_id = f"worker-{hostname}-{timestamp}"
    redis_client = await get_worker_redis_client()
    cpu_count = psutil.cpu_count()
    memory = psutil.virtual_memory()
    worker_key = f"worker:{worker_id}"
    worker_info = {
        "worker_id": worker_id,
        "status": "idle",
        "current_tasks": "0",
        "max_tasks": str(max_concurrent_tasks),
        "cpu_usage": "0.0",
        "memory_usage": str(memory.percent),
        "ip": socket.gethostbyname(hostname),
        "hostname": hostname,
        "cpu_count": str(cpu_count),
        "registered_at": str(int(time.time())),
        "last_heartbeat": str(int(time.time())),
    }
    for key, value in worker_info.items():
        await redis_client.client.hset(worker_key, key, value)
    await redis_client.client.expire(worker_key, 60)
    LOGGER.logger.info(f"Worker registered: {worker_id}")
    return worker_id


async def send_heartbeat():
    global worker_id, redis_client, running
    while running:
        try:
            cpu_usage = psutil.cpu_percent(interval=0.1)
            memory_usage = psutil.virtual_memory().percent
            worker_key = f"worker:{worker_id}"
            await redis_client.client.hset(worker_key, "last_heartbeat", str(int(time.time())))
            await redis_client.client.hset(worker_key, "cpu_usage", str(cpu_usage))
            await redis_client.client.hset(worker_key, "memory_usage", str(memory_usage))
            await redis_client.client.expire(worker_key, 60)
            LOGGER.logger.debug(f"Heartbeat sent: {worker_id}")
            await asyncio.sleep(5)
        except Exception as e:
            LOGGER.logger.error(f"Heartbeat error: {e}")
            await asyncio.sleep(5)


async def recover_stale_running_tasks():
    global redis_client, running

    while running:
        try:
            started_before = datetime.now() - timedelta(seconds=TASK_RECOVERY_MIN_AGE_SECONDS)
            active_workers = await redis_client.get_all_workers()
            active_worker_ids = set(active_workers.keys())
            recoverable_tasks = await query_recoverable_tasks(started_before=started_before)
            recovered_count = 0

            for task in recoverable_tasks:
                task_id = task.get("task_id")
                task_worker_id = task.get("worker_id", "")
                if task_worker_id and task_worker_id in active_worker_ids:
                    continue

                success = await reset_task_after_recovery(task_id)
                if not success:
                    continue

                await redis_client.set_task_status(task_id=task_id, status="pending", progress=0)
                await redis_client.update_task_field(task_id, "worker_id", "")
                await redis_client.update_task_field(task_id, "started_at", "")
                await redis_client.update_task_field(task_id, "finished_at", "")
                await redis_client.update_task_field(task_id, "error_message", "")
                recovered_count += 1

            if recovered_count:
                LOGGER.logger.warning(f"Recovered {recovered_count} stale running task(s)")
        except Exception as e:
            LOGGER.logger.error(f"Task recovery error: {e}")

        await asyncio.sleep(TASK_RECOVERY_INTERVAL_SECONDS)


async def consume_tasks():
    global consumer, worker_id, redis_client, running, task_semaphore

    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    group_id = os.getenv("KAFKA_GROUP_ID", "worker-group-workflow")

    LOGGER.logger.info(f"Kafka Bootstrap Servers: {bootstrap_servers}")
    LOGGER.logger.info(f"Kafka Group ID: {group_id}")
    LOGGER.logger.info(f"仅订阅 workflow topics: {WORKFLOW_TOPICS}")

    consumer = AIOKafkaConsumer(
        *WORKFLOW_TOPICS,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        session_timeout_ms=300000,
        heartbeat_interval_ms=30000,
        max_poll_interval_ms=1800000,
        max_poll_records=10,
        max_partition_fetch_bytes=100 * 1024 * 1024,
        request_timeout_ms=300000,
        fetch_max_wait_ms=500,
    )

    max_retries = 3
    retry_count = 0
    while retry_count < max_retries:
        try:
            await consumer.start()
            LOGGER.logger.info(f"Kafka consumer started (attempt {retry_count + 1})")
            break
        except Exception as e:
            retry_count += 1
            LOGGER.logger.error(f"Kafka connection failed ({retry_count}/{max_retries}): {e}")
            if retry_count >= max_retries:
                raise
            await asyncio.sleep(10)

    running_tasks = set()

    try:
        last_commit_time = time.time()
        while running:
            current_running = len([t for t in running_tasks if not t.done()])
            available_slots = max(1, max_concurrent_tasks - current_running)
            max_fetch = min(available_slots, 5)
            msg_batch = await consumer.getmany(timeout_ms=100, max_records=max_fetch)

            messages_received = 0
            messages_to_commit = {}

            if msg_batch:
                total_msgs = sum(len(msgs) for msgs in msg_batch.values())
                LOGGER.logger.debug(f"Fetched {total_msgs} messages from {len(msg_batch)} partitions")

            for topic_partition, messages in msg_batch.items():
                for msg in messages:
                    try:
                        task_data = json.loads(msg.value.decode("utf-8"))
                        task_id = task_data.get("task_id", "unknown")
                        task_type = task_data.get("task_type", "")

                        LOGGER.logger.info(f"Received task: {task_id} from topic: {msg.topic}")

                        if task_type != "workflow":
                            LOGGER.logger.warning(f"非 workflow 任务已跳过: task_id={task_id}, type={task_type}")
                            if topic_partition not in messages_to_commit:
                                messages_to_commit[topic_partition] = []
                            messages_to_commit[topic_partition].append(msg)
                            continue

                        task_status = await redis_client.client.hget(f"task:{task_id}", "status")
                        task_status_str = (
                            task_status.decode("utf-8") if isinstance(task_status, bytes) else (task_status or "")
                        )
                        if task_status_str and task_status_str in ["running", "success", "failed", "timeout", "cancelled"]:
                            LOGGER.logger.warning(
                                f"Task {task_id} already in status {task_status_str}, skipping"
                            )
                            if topic_partition not in messages_to_commit:
                                messages_to_commit[topic_partition] = []
                            messages_to_commit[topic_partition].append(msg)
                            continue

                        task = asyncio.create_task(execute_task_with_semaphore(task_data, msg, topic_partition))
                        running_tasks.add(task)
                        task.add_done_callback(running_tasks.discard)
                        messages_received += 1
                    except Exception as e:
                        LOGGER.logger.error(f"Task processing error: {e}")
                        import traceback

                        traceback.print_exc()
                        if topic_partition not in messages_to_commit:
                            messages_to_commit[topic_partition] = []
                        messages_to_commit[topic_partition].append(msg)

            if messages_to_commit:
                try:
                    from aiokafka.structs import TopicPartition

                    offsets = {}
                    for tp, msgs in messages_to_commit.items():
                        if msgs:
                            last_msg = msgs[-1]
                            offsets[TopicPartition(topic=last_msg.topic, partition=last_msg.partition)] = (
                                last_msg.offset + 1
                            )
                    if offsets:
                        await consumer.commit(offsets=offsets)
                except Exception as e:
                    LOGGER.logger.warning(f"Failed to commit offsets: {e}")

            if messages_received > 0:
                continue

            current_time = time.time()
            if current_time - last_commit_time > 10:
                try:
                    await consumer.commit()
                    last_commit_time = current_time
                except Exception as e:
                    LOGGER.logger.warning(f"Failed to commit offset: {e}")

            if len(running_tasks) > 100:
                for t in [t for t in running_tasks if t.done()]:
                    running_tasks.discard(t)

        if running_tasks:
            await asyncio.gather(*running_tasks, return_exceptions=True)
    finally:
        await consumer.stop()
        LOGGER.logger.info("Kafka consumer stopped")


async def execute_task_with_semaphore(task_data, msg=None, topic_partition=None):
    global task_semaphore, redis_client, worker_id, consumer

    task_id = task_data.get("task_id", "unknown")
    task_start_time = time.time()

    async with task_semaphore:
        try:
            task_status = await redis_client.client.hget(f"task:{task_id}", "status")
            task_status_str = (
                task_status.decode("utf-8") if isinstance(task_status, bytes) else (task_status or "")
            )
            if task_status_str and task_status_str in ["running", "success", "failed", "timeout", "cancelled"]:
                if msg and topic_partition:
                    try:
                        from aiokafka.structs import TopicPartition

                        offsets = {TopicPartition(topic=msg.topic, partition=msg.partition): msg.offset + 1}
                        await consumer.commit(offsets=offsets)
                    except Exception as e:
                        LOGGER.logger.warning(f"Failed to commit offset for skipped task: {e}")
                return

            worker_key = f"worker:{worker_id}"
            current_tasks_str = await redis_client.client.hget(worker_key, "current_tasks")
            current_tasks = int(current_tasks_str) if current_tasks_str else 0
            await redis_client.client.hset(worker_key, "status", "busy")
            await redis_client.client.hset(worker_key, "current_tasks", str(current_tasks + 1))

            task_timeout = int(os.environ.get("TASK_TIMEOUT_SECONDS", "3600"))
            task_success = False
            try:
                await asyncio.wait_for(execute_task(task_data), timeout=task_timeout)
                task_success = True
            except asyncio.TimeoutError:
                finished_at = datetime.now()
                timeout_message = f"Task timeout after {task_timeout}s"
                LOGGER.logger.error(f"[{task_id}] Task timeout after {task_timeout}s")
                await redis_client.client.hset(f"task:{task_id}", "status", "timeout")
                await redis_client.client.hset(f"task:{task_id}", "progress", "100")
                await redis_client.client.hset(f"task:{task_id}", "finished_at", finished_at.isoformat())
                await redis_client.client.hset(f"task:{task_id}", "error_message", timeout_message)
                await update_task_status_in_db(
                    task_id,
                    "timeout",
                    worker_id_value=worker_id,
                    progress=100,
                    finished_at=finished_at,
                    error_message=timeout_message,
                )
                if msg and topic_partition:
                    try:
                        from aiokafka.structs import TopicPartition

                        offsets = {TopicPartition(topic=msg.topic, partition=msg.partition): msg.offset + 1}
                        await consumer.commit(offsets=offsets)
                    except Exception as commit_error:
                        LOGGER.logger.warning(f"Failed to commit offset for timeout task: {commit_error}")

            if msg and topic_partition and task_success:
                try:
                    from aiokafka.structs import TopicPartition

                    offsets = {TopicPartition(topic=msg.topic, partition=msg.partition): msg.offset + 1}
                    await consumer.commit(offsets=offsets)
                except Exception as e:
                    LOGGER.logger.warning(f"Failed to commit offset for completed task: {e}")

            current_tasks_str = await redis_client.client.hget(worker_key, "current_tasks")
            current_tasks = int(current_tasks_str) if current_tasks_str else 1
            new_count = max(0, current_tasks - 1)
            await redis_client.client.hset(worker_key, "status", "idle" if new_count == 0 else "busy")
            await redis_client.client.hset(worker_key, "current_tasks", str(new_count))

        except Exception as e:
            LOGGER.logger.error(f"[{task_id}] Task execution error: {e}")
            import traceback

            traceback.print_exc()
            try:
                await redis_client.client.hset(f"task:{task_id}", "status", "failed")
                await redis_client.client.hset(f"task:{task_id}", "error_message", str(e))
                await update_task_status_in_db(
                    task_id,
                    "failed",
                    worker_id_value=worker_id,
                    error_message=str(e),
                )
            except Exception as update_error:
                LOGGER.logger.error(f"Failed to update task status after error: {update_error}")
            finally:
                if msg and topic_partition:
                    try:
                        from aiokafka.structs import TopicPartition

                        offsets = {TopicPartition(topic=msg.topic, partition=msg.partition): msg.offset + 1}
                        await consumer.commit(offsets=offsets)
                    except Exception as commit_error:
                        LOGGER.logger.warning(f"Failed to commit offset for failed task: {commit_error}")


async def update_task_status_in_db(
    task_id,
    status,
    *,
    worker_id_value=None,
    progress=None,
    started_at=None,
    finished_at=None,
    error_message=None,
):
    try:
        success = await persist_task_status(
            task_id=task_id,
            status=status,
            worker_id=worker_id_value,
            progress=progress,
            started_at=started_at,
            finished_at=finished_at,
            error_message=error_message,
        )
        if success:
            LOGGER.logger.debug(f"Database status updated: {task_id} -> {status}")
        else:
            LOGGER.logger.warning(f"Failed to update database: {task_id} -> {status}")
    except Exception as e:
        LOGGER.logger.error(f"Database update error: {e}")


async def execute_task(task_data):
    global redis_client, worker_id

    task_id = task_data.get("task_id", "unknown")
    task_type = task_data.get("task_type", "workflow")
    payload = task_data.get("payload", {})
    parent_task_id = task_data.get("parent_task_id")
    metadata = task_data.get("metadata", {})
    author = metadata.get("created_by", worker_id)
    handler_id = None
    started_at = datetime.now()

    if task_type != "workflow":
        error_message = f"Unsupported task_type: {task_type}"
        LOGGER.logger.error(f"仅支持 workflow，收到: {task_type}")
        await redis_client.client.hset(f"task:{task_id}", "status", "failed")
        await redis_client.client.hset(f"task:{task_id}", "error_message", error_message)
        await update_task_status_in_db(
            task_id,
            "failed",
            error_message=error_message,
        )
        return

    try:
        LOGGER.logger.info("=" * 60)
        LOGGER.logger.info(f"开始执行任务: {task_id} (workflow)")
        LOGGER.logger.info(f"Parent Task ID (tracerId): {parent_task_id}")
        LOGGER.logger.info("=" * 60)

        if parent_task_id:
            handler_id = get_endpoint_logger(parent_task_id)
            LOGGER.logger.info(f"Console log handler added for tracerId={parent_task_id}")

        await redis_client.client.hset(f"task:{task_id}", "status", "running")
        await redis_client.client.hset(f"task:{task_id}", "progress", "0")
        await redis_client.client.hset(f"task:{task_id}", "worker_id", worker_id)
        await redis_client.client.hset(f"task:{task_id}", "started_at", started_at.isoformat())
        await update_task_status_in_db(
            task_id,
            "running",
            worker_id_value=worker_id,
            progress=0,
            started_at=started_at,
        )

        result = await execute_task_async(task_data, handler_id, parent_task_id, author)

        await redis_client.client.hset(f"task:{task_id}", "progress", "100")

        if result is None:
            finished_at = datetime.now()
            await redis_client.client.hset(f"task:{task_id}", "status", "failed")
            await redis_client.client.hset(f"task:{task_id}", "error_message", "execute_task_async returned None")
            await redis_client.client.hset(f"task:{task_id}", "finished_at", finished_at.isoformat())
            await update_task_status_in_db(
                task_id,
                "failed",
                worker_id_value=worker_id,
                progress=100,
                finished_at=finished_at,
                error_message="execute_task_async returned None",
            )
            if handler_id is not None:
                try:
                    LOGGER.logger.remove(handler_id)
                except Exception:
                    pass
            return

        if result.get("success"):
            finished_at = datetime.now()
            should_write_redis = True
            workflow_result = result.get("result", {}) if isinstance(result, dict) else {}
            total_steps = workflow_result.get("totalSteps", 0)
            if total_steps > 50:
                should_write_redis = False
                LOGGER.logger.info(f"工作流节点数({total_steps})大于50，跳过Redis结果写入")

            if should_write_redis:
                try:
                    await redis_client.client.hset(f"task:{task_id}", "status", "success")
                    await redis_client.client.hset(f"task:{task_id}", "finished_at", finished_at.isoformat())
                except Exception as e:
                    LOGGER.logger.warning(f"保存任务状态到Redis失败: {e}")
                try:
                    if result.get("result"):
                        result_data = result.get("result")
                        if hasattr(result_data, "model_dump"):
                            result_data = result_data.model_dump()
                        elif hasattr(result_data, "dict"):
                            result_data = result_data.dict()
                        await redis_client.client.hset(
                            f"task:{task_id}", "result", json.dumps(result_data, default=str)
                        )
                except Exception as e:
                    LOGGER.logger.warning(f"保存任务结果到Redis失败: {e}")

            await update_task_status_in_db(
                task_id,
                "success",
                worker_id_value=worker_id,
                progress=100,
                finished_at=finished_at,
                error_message="",
            )
            LOGGER.logger.info(f"任务执行成功: {task_id}")
            wf = result.get("result", {}) if isinstance(result, dict) else {}
            LOGGER.logger.info(f"   状态: {wf.get('status', 'UNKNOWN')}")
            LOGGER.logger.info(f"   总步骤: {wf.get('totalSteps', 0)}")
        else:
            finished_at = datetime.now()
            error_message = result.get("error") or result.get("message") or "Unknown error"
            await redis_client.client.hset(f"task:{task_id}", "status", "failed")
            await redis_client.client.hset(f"task:{task_id}", "error_message", error_message)
            await redis_client.client.hset(f"task:{task_id}", "finished_at", finished_at.isoformat())
            await update_task_status_in_db(
                task_id,
                "failed",
                worker_id_value=worker_id,
                progress=100,
                finished_at=finished_at,
                error_message=error_message,
            )
            LOGGER.logger.error(f"任务执行失败: {task_id}, 原因: {error_message}")

        if handler_id is not None:
            try:
                await asyncio.sleep(0.5)
                LOGGER.logger.remove(handler_id)
                LOGGER.logger.info(f"Console log handler removed for tracerId={parent_task_id}")
            except Exception as remove_error:
                LOGGER.logger.warning(f"Failed to remove log handler: {remove_error}")

        LOGGER.logger.info("=" * 60)
        LOGGER.logger.info(f"任务完成: {parent_task_id if parent_task_id else task_id}")
        LOGGER.logger.info("=" * 60)

    except Exception as e:
        finished_at = datetime.now()
        LOGGER.logger.error(f"任务执行异常: {task_id}, error: {e}")
        import traceback

        traceback.print_exc()
        if handler_id is not None:
            try:
                LOGGER.logger.remove(handler_id)
            except Exception:
                pass
        await redis_client.client.hset(f"task:{task_id}", "status", "failed")
        await redis_client.client.hset(f"task:{task_id}", "error_message", str(e))
        await redis_client.client.hset(f"task:{task_id}", "finished_at", finished_at.isoformat())
        await update_task_status_in_db(
            task_id,
            "failed",
            worker_id_value=worker_id,
            progress=100,
            finished_at=finished_at,
            error_message=str(e),
        )


async def execute_task_async(task_data, handler_id, parent_task_id, _author):
    task_id = task_data.get("task_id", "unknown")
    payload = task_data.get("payload", {})

    try:
        LOGGER.logger.info(f"执行工作流任务: task_id={task_id}")

        from src.worker.executors.workflow_executor import WorkflowExecutor
        from src.infrastructure.callback.callback_service import WorkflowCallbackService, send_single_workflow_callback

        result = await WorkflowExecutor.execute_workflow(payload, task_data)

        if result is None:
            return {"success": False, "error": "_execute_workflow returned None"}

        if WorkflowCallbackService.is_enabled():
            try:
                run_id = payload.get("runId") or (result.get("result") or {}).get("runId", task_id)
                report_id = payload.get("reportId", "")
                await send_single_workflow_callback(
                    run_id=run_id,
                    task_id=task_id,
                    parent_task_id=parent_task_id,
                    report_id=report_id,
                    success=result.get("success", False),
                    result_dict=result.get("result", {}),
                    message=result.get("message", ""),
                    error=result.get("error"),
                )
            except Exception as callback_error:
                LOGGER.logger.warning(f"回调通知异常（不影响任务结果）: {callback_error}")

        return result

    except Exception as e:
        LOGGER.logger.error(f"工作流任务执行失败: task_id={task_id}, error: {e}", exc_info=True)
        try:
            from src.infrastructure.callback.callback_service import WorkflowCallbackService, send_single_workflow_callback

            if WorkflowCallbackService.is_enabled():
                run_id = payload.get("runId", task_id)
                report_id = payload.get("reportId", "")
                await send_single_workflow_callback(
                    run_id=run_id,
                    task_id=task_id,
                    parent_task_id=parent_task_id or "",
                    report_id=report_id,
                    success=False,
                    result_dict={},
                    message="工作流执行失败",
                    error=str(e),
                )
        except Exception as callback_error:
            LOGGER.logger.warning(f"失败回调通知异常: {callback_error}")
        return {"success": False, "error": str(e)}


async def unregister_worker():
    global worker_id, redis_client
    if worker_id and redis_client:
        try:
            await redis_client.client.delete(f"worker:{worker_id}")
            LOGGER.logger.info(f"Worker unregistered: {worker_id}")
        except Exception as e:
            LOGGER.logger.error(f"Unregister error: {e}")


async def main():
    global heartbeat_task, recovery_task, running, start_time, task_semaphore

    CYAN, BLUE, GREEN, YELLOW, RESET = "\033[36m", "\033[34m", "\033[32m", "\033[33m", "\033[0m"
    banner = f"""
{CYAN}    Aegis Runner {YELLOW}Worker{GREEN} (workflow-only){RESET}
"""
    print(banner)

    start_time = datetime.now()

    try:
        print("\n[1/6] 启动健康检查服务...")
        start_health_server()

        print("\n[2/6] 注册执行机到Redis...")
        wid = await register_worker()
        print(f" 执行机ID: {wid}")

        print("\n[3/6] 启动心跳任务...")
        heartbeat_task = asyncio.create_task(send_heartbeat())

        print("\n[4/6] 启动任务恢复巡检...")
        recovery_task = asyncio.create_task(recover_stale_running_tasks())

        print(f"\n[5/6] 初始化并发控制（最大并发: {max_concurrent_tasks}）...")
        task_semaphore = asyncio.Semaphore(max_concurrent_tasks)

        print("\n[6/6] 启动任务消费（仅 workflow topics）...")
        consumer_task = asyncio.create_task(consume_tasks())

        print("\n" + "=" * 60)
        print("   执行机启动完成，等待 workflow 任务...")
        print("=" * 60)
        print(f"\n执行机ID: {wid}")
        print(f"Topics: {', '.join(WORKFLOW_TOPICS)}")
        print(f"健康检查: http://0.0.0.0:{WORKER_HEALTH_PORT}/health\n")

        await asyncio.gather(heartbeat_task, recovery_task, consumer_task)

    except KeyboardInterrupt:
        print("\n\n收到键盘中断，正在关闭...")
        running = False
    except Exception as e:
        print(f"\n\n 执行机启动失败: {e}")
        import traceback

        traceback.print_exc()
    finally:
        print("\n正在清理资源...")
        running = False
        if heartbeat_task:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
        if recovery_task:
            recovery_task.cancel()
            try:
                await recovery_task
            except asyncio.CancelledError:
                pass
        await unregister_worker()
        stop_health_server()
        print("\n执行机已关闭")
