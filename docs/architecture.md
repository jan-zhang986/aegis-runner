# Aegis Runner Architecture

当前仓库采用正式分层目录：

- `apps/master`: API、调度、状态查询
- `apps/worker`: 消费、执行、回写
- `packages/contracts`: Master/Worker 共享协议模型
- `packages/shared`: 日志、响应、通用工具
- `packages/engine`: 工作流执行引擎
- `configs`: 仓库级运行配置
- `deployments`: Docker、K8s、运维脚本
- `tests`: `unit/integration/e2e` 分层测试目录

入口文件：

- Master: `python -m apps.master.main`
- Worker: `python -m apps.worker.main`

兼容入口 `application.py` 和 `start_worker.py` 仍保留为薄包装。

状态模型见 [state-model.md](./state-model.md)。
功能缺口与完善度见 [functional-gap-analysis.md](./functional-gap-analysis.md)。
