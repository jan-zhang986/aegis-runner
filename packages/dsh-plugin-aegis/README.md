# @vanguard/dsh-plugin-aegis

Enterprise Test-as-Code & Quality Gate Plugin for **DeepSeek Harness (`dsh`)**.

## 🚀 概述

本插件将 AegisOne 企业级 Test-as-Code 骨架与风控门禁无缝挂载至 **DeepSeek Harness** 客户端中，为 DeepSeek 模型赋予四大核心工程能力：
1. **`aegis_scaffold`**：根据业务需求秒级生成标准多语言用例骨架（Python / Java / Go）。
2. **`aegis_scan`**：毫秒级全库静态 AST 盘点，用例资产对齐 Git 代码，告别过期的 Web 表单。
3. **`aegis_diff`**：自动识别 Git 变更代码中的未测盲区（Gap Analysis），驱动 Agent 主动补齐测试。
4. **`aegis_run`**：驱动本地测试极速运行，自动输出具有审计效力的**发布前质量风控五问答卷（Q1~Q5）**。

---

## 📦 安装与配置

在你的 DeepSeek Harness profile 目录（例如 `~/.dsh/profiles/web/cordis.patch.yml`）中添加如下配置即可：

```yaml
- id: "@vanguard/dsh-plugin-aegis"
  config:
    # 待测工程代码仓库根目录 (默认当前工作区)
    workspaceRoot: "."
    # Python 解释器路径
    pythonPath: "python3"
```

启动 DeepSeek Harness 客户端：
```bash
npx @deepseek-ai/dsh web
```

---

## 🛠️ Agent 工具调度契约

### 1. `aegis_scaffold`
```json
{
  "lang": "python",
  "req": "REQ-TRADE-REFUND",
  "risk": "P0",
  "title": "验证退款金额超出支付金额时的防资损异常拦截"
}
```

### 2. `aegis_scan`
```json
{
  "dir": "."
}
```

### 3. `aegis_diff`
```json
{
  "base": "HEAD~1"
}
```

### 4. `aegis_run`
```json
{
  "target": "tests/test_refund.py",
  "lang": "python"
}
```

---

## 📋 发布质量风控五问 (Q1~Q5) 门禁输出规范

每次运行 `aegis_run`，不仅输出常规的 `PASSED` / `FAILED`，还会返回结构化门禁裁决：
* **`q1_core_risk`**：核心风险辨析与高危接口调用链；
* **`q2_verification_evidence`**：执行目标、耗时、步骤日志与断言快照；
* **`q3_uncovered_risk`**：变动代码中未测物理行与免测归因；
* **`q4_release_impact`**：发布裁决（APPROVED / RELEASE BLOCKED）与影响范围；
* **`q5_post_release_observability`**：线上监控告警对齐建议（5xx 突增、P99 延迟等）。
