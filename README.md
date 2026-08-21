# Aegis Runner

Aegis 测试平台的分布式工作流执行引擎。Master 负责任务接入与调度，Worker 负责真正执行；前端仓库是 [`aegis-next-web`](https://github.com/jan-zhang986/aegis-next-web)。

当前主链路已经能跑通：提交 workflow → Kafka 分发 → Worker 执行 → Redis / MySQL 回写状态 → 回调 Aegis。平台级能力（死信队列、细粒度恢复编排、完整鉴权）仍在补齐。

## 它做什么

| 能力 | 状态 |
|------|------|
| 单条 / 批量提交 workflow | 可用 |
| 按优先级通过 Kafka 分发给 Worker | 可用 |
| 查询任务状态、结果、实时日志、SSE 推送 | 可用 |
| 取消待执行任务、重试失败任务 | 可用 |
| Worker 心跳过期后，把卡住的 `running` 任务恢复为 `pending` | 可用 |
| 水平扩展 Worker、K8s HPA | 可用 |
| 死信队列、自动失败重投、租户隔离 | 未完成 |

本仓库不是测试管理后台。用例编排、报告展示、拖拽编辑在 `aegis-next-web`；这里只负责把工作流跑起来。

## 架构

```
aegis-next-web / Aegis 平台
        │
        ▼
┌───────────────────────────┐
│  Master  (FastAPI :8100)  │
│  提交任务 · 查状态 · 日志  │
└─────────────┬─────────────┘
              │  Kafka
              │  task-workflow-{urgent,high,normal}
              ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Worker 1 │  │ Worker 2 │  │ Worker N │
│  engine  │  │  engine  │  │  engine  │
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │
     ▼             ▼             ▼
 Redis 实时状态 · MySQL 持久记录 · 回调 Aegis
```

- **Redis**：运行中任务的实时状态（进度、Worker、结果缓存）。
- **MySQL**：持久执行记录；Redis 过期后查询走数据库。
- **Kafka**：按优先级分发 workflow 任务。Master 启动时不会自动建 Topic，需要预先创建。

更细的状态约定见 [docs/state-model.md](docs/state-model.md)。

## 目录

```
apps/master/          Master：API、调度、状态查询
apps/worker/          Worker：消费、执行、回写、回调
packages/engine/      工作流引擎（节点处理器）
packages/contracts/   Master / Worker 共享协议
packages/shared/      配置、日志、Kafka、通用响应
configs/              application.yml，本地覆盖用 application_local.yml
deployments/          Docker、K8s、运维脚本
tests/                unit / integration / e2e
docs/                 架构、状态模型、部署
```

入口：

```bash
python -m apps.master.main    # Master，默认 0.0.0.0:8100
python -m apps.worker.main    # Worker
```

`application.py`、`start_worker.py` 仍是薄包装，新代码请走上面两个入口。

## 运行条件

- Python 3.12
- MySQL 8
- Redis
- Kafka（Topic：`task-workflow-urgent` / `task-workflow-high` / `task-workflow-normal`）

```bash
pip install -r requirements.txt
```

引擎额外依赖见 [`packages/engine/requirements.txt`](packages/engine/requirements.txt)。配置从 `configs/application.yml` 读取，同目录的 `application_local.yml` 会覆盖它，适合放本机地址和密钥（不要提交真实密钥）。

环境变量可覆盖配置，常用项：

| 变量 | 作用 |
|------|------|
| `MASTER_HOST` / `MASTER_PORT` | Master 监听地址，默认 `0.0.0.0:8100` |
| `MASTER_API_TOKEN` | 设置后，业务接口需要请求头 `X-Master-Token` |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | 数据库；也可用 `DB_PRIMARY_URL` |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` | Redis |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka |
| `WORKER_HEALTH_PORT` | Worker 健康检查端口，默认 `8080` |
| `CORS_ALLOW_ORIGINS` | Master CORS，逗号分隔 |

## 本地启动

1. 准备 MySQL、Redis、Kafka，并创建三个 workflow Topic。
2. 按环境改 `configs/application_local.yml`（至少数据库、Redis、Kafka、回调地址）。
3. 启动：

```bash
python -m apps.master.main
python -m apps.worker.main
```

4. 检查依赖和冒烟：

```bash
python deployments/scripts/check-runtime-deps.py
python deployments/scripts/run-real-smoke.py
```

冒烟默认打本地 Master `http://127.0.0.1:18100`。若 Master 跑在 8100，设置：

```bash
MASTER_SMOKE_BASE_URL=http://127.0.0.1:8100 \
WORKER_HEALTH_URL=http://127.0.0.1:8080/health \
python deployments/scripts/run-real-smoke.py
```

它会依次验证空 workflow、`log_message`、以及请求 Master `/health` 的 `http_request`。

完整业务 e2e（真实 MySQL / Redis / Kafka + Master + Worker）：

```bash
./deployments/scripts/run-e2e.sh
```

## API

健康检查不鉴权；其余接口在配置了 `MASTER_API_TOKEN` 时需要 `X-Master-Token`。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health`、`/healthz` | 存活检查 |
| GET | `/health/database`、`/health/pool` | 数据库与连接池 |
| POST | `/workflow/debug/execute` | 提交单条 workflow |
| POST | `/workflow/execute/batch` | 批量提交 |
| GET | `/workflow/{id}/status` | 工作流状态 |
| GET | `/workflow/{id}/batch/status` | 批量状态（走 MySQL 聚合） |
| POST | `/workflow/{id}/batch/cancel` | 取消批量中的待执行任务 |
| POST | `/workflow/{id}/batch/retry` | 重试批量中的失败任务 |
| GET | `/workflow/{id}/console` | 实时日志 |
| GET | `/workflow/{id}/stream` | SSE 状态推送 |
| GET | `/task/{task_id}/status` | 任务状态（先 Redis，未命中再 MySQL） |
| GET | `/task/{task_id}/result` | 任务结果 |
| POST | `/task/{task_id}/cancel` | 取消待执行任务 |
| POST | `/task/{task_id}/retry` | 重试终态失败任务 |

提交成功后返回 `tracerId` / `task_id`，用它们查状态。执行完成后 Worker 会按 `callback.workflow.url` POST 结果。

## 工作流引擎

Worker 通过 `packages/engine` 执行 JSON 工作流（`nodes` + `edges`）。常见节点：

| 类型 | 用途 |
|------|------|
| `http_request` / `dubbo` | HTTP、Dubbo 调用 |
| `mysql` / `redis` / `mongodb` / `rocketmq` | 数据与消息 |
| `xxl_job` | XXL-JOB |
| `oss` | 对象存储 |
| `script` / `assertion` / `condition` / `sleep` / `log_message` / `variable_extractor` | 控制与断言 |
| `loop` / `sub_workflow` | 循环、子流程 |
| `browser_launch` / `ui_navigation` / `ui_element` / `smart_wait` 等 | Playwright UI |

示例和节点说明在 `packages/engine/examples/`、`packages/engine/docs/`。

## 测试

```bash
pytest tests/unit tests/integration
ENABLE_RUNTIME_E2E=1 pytest tests/e2e/test_runtime_dependencies.py
./deployments/scripts/run-e2e.sh
```

- `tests/unit`、`tests/integration`：不依赖真实中间件。
- `tests/e2e/test_runtime_dependencies.py`：只检查 MySQL / Redis / Kafka 能连通，需 `ENABLE_RUNTIME_E2E=1`。
- `tests/e2e/test_workflow_e2e.py`：真实依赖下的成功主链路，由 `run-e2e.sh` 拉起。

## 部署

镜像入口与本地相同：`python -m apps.master.main` / `python -m apps.worker.main`。

```bash
chmod +x deployments/scripts/deploy.sh deployments/scripts/scale-workers.sh
./deployments/scripts/deploy.sh test    # 或 prod
./deployments/scripts/scale-workers.sh 10
```

K8s 清单在 `deployments/k8s/`，资源名以 `aegis-runner-` 为前缀。逐步说明见 [docs/deployment_zh.md](docs/deployment_zh.md)。部署前确认三个 Kafka Topic 已存在。

## 文档

- [架构与目录边界](docs/architecture.md)
- [任务状态模型](docs/state-model.md)
- [已完成与缺口](docs/functional-gap-analysis.md)
- [部署目录约定](docs/deployment.md)
- [K8s 部署指南](docs/deployment_zh.md)
