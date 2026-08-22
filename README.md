# Aegis Runner (云原生分布式工作流执行引擎)

Aegis 自动化测试平台的云原生无状态工作流执行引擎。彻底去除了 Master/Slave 选主单点依赖，采用 **无状态 Peer-to-Peer 节点池架构 + Kafka 双向事件驱动 + 5 层 Clean Architecture** 设计。

与前端仓库 [`aegis-next-web`](https://github.com/jan-zhang986/aegis-next-web) 及核心后端 [`aegis-next-server`](https://github.com/jan-zhang986/vanguard-testops) 完全打通。

---

## 🏛️ 云原生全无状态架构 (Masterless Architecture)

```
[ aegis-next-web 前端 ] ◄───── WebSocket 实时打屏 ───── [ aegis-next-server ]
                                                              │ (异步下发)
                                                              ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                           Kafka 消息通道                                   │
│   - task-workflow-dispatch  (异步任务下发)                                 │
│   - workflow-step-event     (实时节点步骤打屏事件)                         │
│   - workflow-run-result     (终态结果持久化事件)                           │
└──────────────┬─────────────────────────────────────────────────────────────┘
               │
               │ (Kafka Consumer Group 自动竞争消费 + CAS & Redis 幂等去重)
               ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                 Aegis Runner 执行节点池 (Stateless Runner Nodes)           │
│   - 无 Master 选主单点，全员 Pod 无状态且完全平等                             │
│   - 依托 K8s HPA / KEDA 根据 Kafka 队列堆积量实现自动弹性扩缩容             │
└────────────────────────────────────────────────────────────────────────────┘
```

- **高可用与防死锁**：服务端任务下发与节点执行完全解耦，即便服务重新发布，Kafka 消息依然留存，状态不丢失。
- **节点级实时打屏**：Runner 节点每执行一个 Step（HTTP/SQL/Script/UI），即时抛出 `workflow-step-event` 事件消息，前端 WebSocket 实时高亮与打屏输出。
- **严格幂等控制**：采用 CAS 数据库状态机 + Redis `SETNX` 去重锁，杜绝 Kafka 最少一次交付（At-Least-Once）导致的重复覆盖。

---

## 📂 项目代码分层 (Clean Architecture Layout)

统一采用标准的 **`src/`** 顶级 Python 包，工业级 5 层高内聚分层：

```
aegis-runner/
├── src/                          # 顶级唯一代码包
│   ├── core/                     # 配置加载 (config.py)、日志 (logging.py)、异常与工具 (utils/)
│   ├── domain/                   # 领域模型与传输 Schema (models.py, responses.py)
│   ├── engine/                   # 工作流核心编排引擎 (workflow_engine.py, context.py, processors/)
│   ├── infrastructure/           # Kafka (kafka/)、Redis (redis/)、MySQL (db/)、事件回调 (callback/)
│   └── runner/                   # 云原生无状态 Aegis Runner 运行进程 (main.py, runtime.py)
├── configs/                      # application.yml 运行配置
├── deployments/                  # Dockerfile & K8s 部署清单 (k8s/, docker/)
├── tests/                        # unit / integration / e2e 自动化测试
├── start_runner.py               # 快捷启动脚本 (python3 -m src.runner.main)
├── docs/architecture.md          # 架构分层规范文档
└── README.md
```

---

## ⚡ 核心能力矩阵

| 能力 | 说明 | 状态 |
|:---|:---|:---|
| **单条/批量工作流调度** | 纯异步解耦调度，支持任意复杂 DAG 图 | ✅ 可用 |
| **Kafka 优先级分发** | 支持 `urgent` / `high` / `normal` 优先级分发 | ✅ 可用 |
| **实时打屏与日志流** | 节点步骤实时上报 Kafka，直推 WebSocket | ✅ 可用 |
| **取消与暂停控制** | 支持运行中任务中途安全 Cancellation | ✅ 可用 |
| **异常恢复与自动重试** | 超时自动重投、心跳失效恢复 Pending | ✅ 可用 |
| **云原生弹性伸缩** | 支持 K8s HPA 及 KEDA Kafka 堆积触发扩缩 | ✅ 可用 |
| **死信队列 (DLQ)** | 多次重投失败自动转入死信队列隔离 | ✅ 可用 |

---

## 🚀 快速开始

### 1. 运行条件
- Python >= 3.10
- MySQL >= 8.0
- Redis >= 6.0
- Kafka >= 2.8

### 2. 依赖安装
```bash
pip install -r requirements.txt
```

### 3. 配置管理
配置文件存放在 `configs/application.yml`，本地开发可新建 `configs/application_local.yml` 自动覆盖配置。

常用环境变量重写：
| 环境变量 | 作用 | 默认值 |
|:---|:---|:---|
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka 连接地址 | `127.0.0.1:9092` |
| `DB_HOST` / `DB_PORT` | MySQL 数据库连接 | `127.0.0.1:3306` |
| `REDIS_HOST` / `REDIS_PORT` | Redis 连接 | `127.0.0.1:6379` |
| `WORKER_CONCURRENCY` | 单节点最大任务并发数 | `10` |

### 4. 启动 Runner 节点

使用标准包路径启动：
```bash
python3 -m src.runner.main
```

或使用快捷启动脚本：
```bash
python3 start_runner.py
```

---

## 🔧 节点处理器类型 (Node Processors)

引擎内置覆盖主流自动化测试场景的 Step Processor：

| 分类 | 节点类型 | 作用 |
|:---|:---|:---|
| **接口与调用** | `http_request` / `dubbo` | HTTP API 请求、Dubbo 泛化调用 |
| **数据与消息** | `mysql` / `redis` / `mongodb` / `rocketmq` | 数据库读写、MQ 消息发送校验 |
| **脚本与断言** | `script` / `assertion` / `condition` / `variable_extractor` | Python/Shell 自定义脚本、正则/JSONPath 断言提取 |
| **控制流** | `loop` / `sub_workflow` / `sleep` | 循环控制、子工作流嵌套、等待延迟 |
| **UI 自动化** | `browser_launch` / `ui_navigation` / `ui_element` / `smart_wait` | 基于 Playwright 的 Web UI 自动化与智能等待 |

---

## 🧪 测试与校验

```bash
# 1. 运行单元测试与集成测试
pytest tests/unit tests/integration

# 2. 运行运行时依赖检测
python3 deployments/scripts/check-runtime-deps.py

# 3. 运行端到端 E2E 测试
./deployments/scripts/run-e2e.sh
```

---

## 📄 文档导航

- [架构设计与分层规范](docs/architecture.md)
- [任务状态模型](docs/state-model.md)
- [已完成功能与分析](docs/functional-gap-analysis.md)
