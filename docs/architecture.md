# Aegis Runner Architecture (Cloud-Native Clean Architecture)

仓库已全面升级重构为极简工业级 5 层 Clean Architecture 结构 (`src/`)：

- `src/core`: 基础服务（配置加载 `config.py`、日志 `logging.py`、异常与工具）
- `src/domain`: 领域实体模型与传输契约（Models & Schemas，框架无关）
- `src/engine`: 核心工作流执行引擎与 Step Handlers (HTTP / SQL / Script / Playwright)
- `src/infrastructure`: 外部中间件实现 (Kafka Event Producer/Consumer, Redis Lock, MySQL DB, Callback)
- `src/worker`: 云原生无状态 Worker 进程入口

标准运行入口：

- 无状态 Worker 执行引擎：`python3 -m src.worker.main`
- 快捷启动脚本：`python3 start_worker.py`

状态模型见 [state-model.md](./state-model.md)。
功能缺口与完善度见 [functional-gap-analysis.md](./functional-gap-analysis.md)。
