# Aegis Runner Functional Gap Analysis

本文档描述仓库当前“已可用功能”、“未完成功能”和建议优先级。

## 当前已可用

- `workflow` 单任务与批量任务提交
- `workflow` Worker 消费与执行
- 任务状态查询与批量状态统计
- Redis 实时状态 + MySQL 持久状态模型
- Kafka 分发失败补偿
- Worker 关键执行字段完整回写数据库
- Master 启动与运行配置 `fail fast`
- 基础架构守卫、导入冒烟和关键主链路测试

这些能力已经能支撑当前仓库作为 `workflow` 执行平台运行。

## 当前未完成

### 平台能力

- 任务取消
- 任务重试
- 死信队列或失败重投机制
- 更完整的鉴权、权限边界和租户隔离

### 功能覆盖

- 当前主功能仍然集中在 `workflow`
- README 早期提到的 HTTP、SQL、链路、DevOps 等“平台化任务类型”没有在当前 Master 对外接口中完整落地
- 结果与观测能力仍以“执行状态可查”为主，不属于成熟的平台级运营能力

### 验证深度

- 当前已有单元测试、架构守卫测试、导入冒烟测试和一条跨层集成测试
- 还缺少真实 Kafka、Redis、MySQL 依赖参与的端到端验证
- 还缺少更贴近生产的恢复、异常、并发与稳定性验证

## 当前判断

更准确的描述不是“功能已经完善”，而是：

- `workflow` 核心主链路可用
- 架构边界已经较清晰
- 平台级能力仍未完善

## 建议优先级

1. 补真实外部依赖的端到端集成测试
2. 补任务生命周期能力：取消、重试、恢复
3. 补结果与观测能力
4. 在主链路稳定后，再扩展更多任务类型

## 当前补充

仓库已补充“真实依赖 smoke”基础设施：

- `tests/e2e/test_runtime_dependencies.py`
- `deployments/scripts/check-runtime-deps.py`

两者都只验证最小运行前提：

- MySQL 可连接并执行 `SELECT 1`
- Redis 可连接并 `PING`
- Kafka Producer 可成功启动

`e2e` 测试默认不会执行，需显式设置 `ENABLE_RUNTIME_E2E=1`。

仓库也已补充最小任务生命周期能力：

- 取消待执行任务
- 重试终态失败任务
- Worker 心跳过期后的 `running` 任务恢复为 `pending`

当前仍未完成的是更强的平台能力，例如死信队列、自动失败重投策略和更细粒度的恢复编排。

仓库也已补充第一版业务级 e2e 基础设施：

- `deployments/docker/docker-compose.e2e.yml`
- `deployments/scripts/init-e2e-environment.py`
- `deployments/scripts/run-e2e.sh`
- `tests/e2e/test_workflow_e2e.py`

这一版聚焦“单工作流成功链路”，通过真实 MySQL、Redis、Kafka、Master、Worker 验证：

- HTTP 提交任务
- Kafka 真消费
- Worker 真执行
- Redis / MySQL 状态真回写

## 相关文档

- [architecture.md](./architecture.md)
- [state-model.md](./state-model.md)
- [deployment.md](./deployment.md)
