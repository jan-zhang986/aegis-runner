## Aegis-Runner

> 基于自研工作流引擎的分布式自动化测试平台，采用 Master-Worker 分布式架构，支持大规模并发测试任务执行。

### 🎯 当前核心特性

- ✅ **分布式架构**: Master-Worker 架构，支持水平扩展
- ✅ **任务队列**: 基于 Kafka 的优先级任务队列
- ✅ **自动扩缩容**: 基于 K8s HPA 的自动扩缩容
- ✅ **实时日志**: 支持实时查看任务执行日志
- ✅ **工作流执行**: 当前主链路聚焦 `workflow` 任务执行
- ⚠️ **平台能力**: 取消、重试、恢复等能力仍待继续完善



## 运行条件
> 列出运行该项目所必须的条件和相关依赖  
> 安装依赖 pip install -r requirements.txt
> 导出依赖 pipreqs ./ --encoding=utf8 --force
* python 3.8
* fastapi
* mysql




## 运行说明
> 安装好依赖后，推荐直接使用 `apps/master/main.py` 和 `apps/worker/main.py` 作为正式入口
* 配置文件位于 `configs/application.yml`


## 测试说明
* 支持复杂场景用例设计
* 支持用例依赖设置，提取上个用例参数给下个case进行执行
* 支持用例编排
* 支持单个用例执行、多个用例批量执行


## 后续计划
* 支持yml 文件导入执行
* 支持UI自动化测试
* 自测性能测试、并发测试
* 用例流程编排拖拽
* 用例录制


## 当前进展
* 动态切换环境（待完成）
* 测试报告收集与执行（待完成）
*


## 技术架构

### 后端技术栈
- **Web 框架**: FastAPI
- **测试引擎**: 自研 Workflow Engine (`packages/engine`)
- **ORM**: SQLAlchemy 2.0
- **数据库**: MySQL 8.0
- **缓存**: Redis 6.0
- **消息队列**: Kafka 2.8
- **容器编排**: Kubernetes

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    Master (API Server)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  API Routes  │→ │ TaskSplitter │→ │    Kafka     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                              ↓
        ┌─────────────────────┴─────────────────────┐
        ↓                     ↓                     ↓
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   Worker 1    │    │   Worker 2    │    │   Worker N    │
│ ┌───────────┐ │    │ ┌───────────┐ │    │ ┌───────────┐ │
│ │TaskExecutor│ │    │ │TaskExecutor│ │    │ │TaskExecutor│ │
│ └───────────┘ │    │ └───────────┘ │    │ └───────────┘ │
└───────────────┘    └───────────────┘    └───────────────┘
```

## 📚 文档

- [架构说明](docs/architecture.md) - 当前正式目录与分层边界
- [功能缺口分析](docs/functional-gap-analysis.md) - 当前已完成与未完成能力
- [部署说明](docs/deployment.md) - 部署目录与入口约定
- [K8s 部署指南（中文）](docs/deployment_zh.md) - Kubernetes 部署步骤

## 🚀 快速开始

### 本地开发

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动 Master (API Server)
python -m apps.master.main

# 3. 启动 Worker (执行机)
python -m apps.worker.main
```

### 运行时依赖检查

```bash
# 检查 MySQL / Redis / Kafka 是否满足最小启动前提
python deployments/scripts/check-runtime-deps.py

# 显式启用真实依赖 e2e smoke
ENABLE_RUNTIME_E2E=1 pytest tests/e2e/test_runtime_dependencies.py
```

### 业务级端到端验证

```bash
# 使用真实 MySQL / Redis / Kafka + Master + Worker 跑最小业务 e2e
./deployments/scripts/run-e2e.sh
```

对应测试文件：

- `tests/e2e/test_workflow_e2e.py`

### 本地真实 workflow 冒烟

在 Master 和 Worker 已启动的前提下，可直接执行：

```bash
python deployments/scripts/run-real-smoke.py
```

默认会顺序验证：

- 空 workflow
- `log_message` 节点
- `http_request` 节点（请求本地 Master `/health`）

可选环境变量：

- `MASTER_SMOKE_BASE_URL`
- `WORKER_HEALTH_URL`
- `MASTER_API_TOKEN`
- `SMOKE_TIMEOUT_SECONDS`

### K8s 部署

```bash
# 1. 给脚本添加执行权限
chmod +x deployments/scripts/deploy.sh
chmod +x deployments/scripts/scale-workers.sh

# 2. 部署到测试环境
./deployments/scripts/deploy.sh test

# 3. 部署到生产环境
./deployments/scripts/deploy.sh prod

# 4. 扩容 Worker
./deployments/scripts/scale-workers.sh 10
```

详细部署步骤请参考 [K8s 部署指南（中文）](docs/deployment_zh.md)

## grpc 代码生成
```bash
python -m grpc_tools.protoc -I=. --python_out=. --grpc_python_out=. dubbo.proto
```

kubectl exec -it <kafka-pod-name> -n <namespace> -- bash

# 创建 6 个 Topics
kafka-topics.sh --create --topic task-urgent --bootstrap-server localhost:9092 --partitions 3 --replication-factor 2
kafka-topics.sh --create --topic task-high --bootstrap-server localhost:9092 --partitions 3 --replication-factor 2
kafka-topics.sh --create --topic task-normal --bootstrap-server localhost:9092 --partitions 3 --replication-factor 2

workflow 
kafka-topics.sh --create --topic task-workflow-urgent --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
# 创建高优先级任务队列
kafka-topics.sh --create --topic task-workflow-high --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
# 创建普通任务队列
kafka-topics.sh --create --topic task-workflow-normal --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1


# 验证
kafka-topics.sh --list --bootstrap-server localhost:9092
# aegis-runner
