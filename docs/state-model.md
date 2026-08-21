# Task State Model

## Purpose

Aegis Runner keeps task state in two places on purpose:

- `Redis`: realtime execution state for running tasks and workers
- `MySQL`: durable execution record and query fallback

This split is intentional. New code should preserve the responsibility boundary below instead of treating the two stores as interchangeable copies.

## Source Of Truth

- `Redis` is the source of truth for live task progress.
- `MySQL` is the source of truth for durable task history.
- Query APIs should prefer `Redis` for live task state and fall back to `MySQL` when `Redis` has no task entry.

## Redis Responsibilities

Redis stores short-lived execution state under `task:{task_id}`:

- `status`
- `progress`
- `worker_id`
- `started_at`
- `finished_at`
- `retry_count`
- `error_message` when present
- `result` for workflow result payload when the result is small enough to keep in cache

Redis also stores worker heartbeat data under `worker:{worker_id}`.

Characteristics:

- low latency
- expires automatically
- may be incomplete for historical tasks after TTL expiration
- preferred by status query endpoints while a task is active

## MySQL Responsibilities

MySQL stores durable task records in `task_execution` and task results in `task_result`.

`task_execution` is expected to retain:

- task identity fields
- status
- worker metadata
- progress
- started/finished timestamps
- error message
- retry metadata

Characteristics:

- persistent
- fallback source after Redis TTL expiry
- used for historical queries and aggregate statistics

## Query Contract

Current query behavior must remain:

1. `/task/{task_id}/status` checks Redis first.
2. If Redis misses, it falls back to MySQL.
3. The response includes `source = "redis"` or `source = "database"` to make provenance explicit.

Batch workflow status follows the durable path:

- `/workflow/{tracerId}/batch/status` aggregates from MySQL child task records.

## Write Contract

- Master writes initial task state to MySQL first, then seeds Redis as pending state.
- Worker updates Redis for realtime execution changes.
- Worker must also update MySQL with durable execution fields, not just `status`.
- Worker runs a recovery sweep for stale `running` tasks whose owning worker heartbeat has expired.
- Recovered tasks are reset to `pending` so Kafka redelivery or manual retry can resume them.

## Invariants

- Redis and MySQL may differ briefly during in-flight execution.
- Redis expiration must not make historical status queries unusable.
- If a task reaches a terminal state, MySQL must contain enough fields to answer fallback status queries.
- New code must not bypass shared runtime/config and directly introduce a third status store.
- A task in `running` state must not remain stuck forever after its worker disappears; it must eventually be recovered or explicitly failed.
