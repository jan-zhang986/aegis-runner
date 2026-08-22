# Aegis Runner Architecture (Cloud-Native Clean Architecture)

仓库已升级重构为现代工业级 5 层 Clean Architecture 结构 (`aegis_runner/`)：

- `aegis_runner/core`: 基础服务（配置加载 `config.py`、日志 `logging.py`、异常基类）
- `aegis_runner/domain`: 领域实体模型与传输契约（Models & Schemas，框架无关）
- `aegis_runner/engine`: 核心工作流执行引擎与 Step Handlers (HTTP / SQL / Script / Playwright)
- `aegis_runner/infrastructure`: 外部中间件实现 (Kafka Event Producer/Consumer, Redis Lock, MySQL DB, Callback)
- `aegis_runner/worker`: 云原生无状态 Worker 进程入口

标准运行入口：

- 无状态 Worker 执行引擎：`python -m aegis_runner.worker.main`
- 兼容传统入口：`python -m apps.worker.main` 与 `start_worker.py`（平滑兼容薄包装）

状态模型见 [state-model.md](./state-model.md)。
功能缺口与完善度见 [functional-gap-analysis.md](./functional-gap-analysis.md)。
