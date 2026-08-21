# Workflow Engine

自动化测试工作流引擎：通过 JSON（`nodes` / `edges`）或 Python 构建流程，在 **Aegis Runner Worker** 中由 `workflow_engine.WorkflowExecutor` 执行。

## 与 aegis-runner 的关系

- Worker：`apps/worker/executors/workflow_executor.py` 将 `packages/engine` 加入 `sys.path` 并调用 `workflow_engine.WorkflowExecutor`。
- 依赖：除项目根目录 `requirements.txt` 外，引擎额外依赖见同目录 [`requirements.txt`](requirements.txt)。

## 本地开发

```bash
cd packages/engine
pip install -r requirements.txt
```

示例与说明见 `examples/`、`docs/`。

## 许可证

以仓库内 `LICENSE` 为准（若存在）。
