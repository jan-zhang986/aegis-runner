# XXL-Job 单节点批量执行测试指南

## 📋 概述

这是一个简单的 XXL-Job 测试用例，只包含一个节点，用于测试 workflow 批量执行接口。

## 🎯 功能特性

- ✅ 单个 XXL-Job 节点
- ✅ 使用批量执行接口 `/workflow/execute/batch`
- ✅ 支持变量配置
- ✅ 支持状态查询

## 📦 文件说明

- `xxljob_single_node_batch_test.json` - 工作流配置文件（单个节点）
- `run_xxljob_batch_test.py` - 批量执行测试脚本
- `XXLJOB_BATCH_TEST_README.md` - 本说明文档

## 🔧 前置要求

### 1. Python 环境
```bash
Python 3.7+
```

### 2. 安装依赖
```bash
pip install requests
```

### 3. API 服务
- 需要运行 workflow API 服务
- 默认地址：`http://localhost:8000`（可在脚本中修改）

### 4. XXL-Job 服务器（可选）
- 如果测试实际执行，需要 XXL-Job 服务器运行
- 如果只测试接口调用，可以不需要

## 🚀 快速开始

### 方法1：使用 Python 脚本运行（推荐）

```bash
# 进入项目根目录
cd /Users/jan/PycharmProjects/aegis-runner/packages/engine

# 运行测试脚本
python examples/run_xxljob_batch_test.py
```

### 方法2：使用 curl 直接调用 API

```bash
# 1. 准备请求数据
cat > batch_request.json << 'EOF'
{
  "workflows": [
    {
      "workflow": {
        "name": "XXL-Job 单节点批量测试用例",
        "work_id": "xxljob_single_node_batch_test",
        "work_name": "XXL-Job 单节点测试",
        "nodes": [
          {
            "id": "trigger_xxljob",
            "type": "xxljob",
            "name": "触发XXL-Job任务",
            "data": {
              "config": {
                "xxjob_url": "http://job.dev.example.com",
                "username": "admin",
                "password": "123456",
                "executor_handler": "demoJobHandler",
                "executor_param": "{\"taskId\": 12345, \"action\": \"test\"}",
                "site_tenant": "DEFAULT",
                "db_name": "xxl_job",
                "output_variable": "job_result"
              }
            }
          }
        ],
        "edges": []
      },
      "variables": {
        "xxljob_url": "http://job.dev.example.com",
        "username": "admin",
        "password": "123456"
      },
      "runId": "test_run_001"
    }
  ],
  "priority": "normal",
  "maxBatchSize": 1000
}
EOF

# 2. 调用批量执行接口
curl -X POST "http://localhost:8000/workflow/execute/batch" \
  -H "Content-Type: application/json" \
  -d @batch_request.json

# 3. 查询执行状态（使用返回的 tracerId）
curl -X GET "http://localhost:8000/workflow/{tracerId}/batch/status"
```

## 📝 工作流配置说明

### 节点配置

工作流只包含一个 XXL-Job 节点：

```json
{
  "id": "trigger_xxljob",
  "type": "xxljob",
  "name": "触发XXL-Job任务",
  "data": {
    "config": {
      "xxjob_url": "http://job.dev.example.com",
      "username": "admin",
      "password": "123456",
      "executor_handler": "demoJobHandler",
      "executor_param": "{\"taskId\": 12345, \"action\": \"test\"}",
      "site_tenant": "DEFAULT",
      "db_name": "xxl_job",
      "output_variable": "job_result"
    }
  }
}
```

### 配置参数

- **xxjob_url** (必需) - XXL-Job 管理平台 URL
- **executor_handler** (必需) - 执行器 Handler 名称
- **username** (可选) - 登录用户名，默认 "admin"
- **password** (可选) - 登录密码，默认 "123456"
- **executor_param** (可选) - 任务执行参数（JSON 字符串）
- **site_tenant** (可选) - 站点租户，默认 "DEFAULT"
- **db_name** (可选) - 数据库名称，用于从上下文获取数据库连接
- **output_variable** (可选) - 输出变量名，默认 "xxljob_result"

## 🔍 API 接口说明

### 批量执行接口

**接口地址**: `POST /workflow/execute/batch`

**请求体**:
```json
{
  "workflows": [
    {
      "workflow": { /* 工作流定义 */ },
      "variables": { /* 初始变量 */ },
      "runId": "运行ID"
    }
  ],
  "priority": "normal",
  "maxBatchSize": 1000
}
```

**响应**:
```json
{
  "code": 200,
  "message": "批量工作流任务提交成功",
  "data": {
    "tracerId": "追踪ID"
  }
}
```

### 状态查询接口

**接口地址**: `GET /workflow/{tracerId}/batch/status`

**响应**:
```json
{
  "code": 200,
  "data": {
    "tracerId": "追踪ID",
    "total": 1,
    "completed": 1,
    "failed": 0,
    "status": "completed"
  }
}
```

## 💡 使用示例

### 示例1：基本使用

```python
from run_xxljob_batch_test import (
    load_workflow_from_file,
    create_batch_request,
    batch_execute_workflow_api
)

# 加载工作流
workflow = load_workflow_from_file("xxljob_single_node_batch_test.json")

# 创建批量请求
batch_request = create_batch_request(
    workflow=workflow,
    variables={"custom_var": "value"},
    run_id="my_test_run"
)

# 执行
response = batch_execute_workflow_api("http://localhost:8000", batch_request)
print(response)
```

### 示例2：批量执行多个工作流

```python
# 加载多个工作流
workflow1 = load_workflow_from_file("xxljob_single_node_batch_test.json")
workflow2 = load_workflow_from_file("xxljob_single_node_batch_test.json")

# 创建批量请求（包含多个工作流）
batch_request = {
    "workflows": [
        {
            "workflow": workflow1,
            "runId": "run_001"
        },
        {
            "workflow": workflow2,
            "runId": "run_002"
        }
    ],
    "priority": "normal",
    "maxBatchSize": 1000
}

# 执行
response = batch_execute_workflow_api("http://localhost:8000", batch_request)
```

## ⚠️ 注意事项

1. **API 地址配置**：请根据实际情况修改脚本中的 `api_base_url`
2. **认证信息**：如果 API 需要认证，请在 `headers` 中添加认证信息
3. **XXL-Job 配置**：请根据实际情况修改工作流中的 XXL-Job 配置参数
4. **网络连接**：确保能够访问 API 服务和 XXL-Job 服务器
5. **批量限制**：单次批量执行数量不能超过 `maxBatchSize`（默认 1000）

## 🔍 故障排查

### 问题1：API 连接失败

**错误信息**：`Connection refused` 或 `Timeout`

**解决方法**：
- 检查 API 服务是否运行
- 检查 `api_base_url` 配置是否正确
- 检查网络连接

### 问题2：认证失败

**错误信息**：`401 Unauthorized` 或 `403 Forbidden`

**解决方法**：
- 检查是否需要添加认证头
- 检查认证信息是否正确

### 问题3：工作流验证失败

**错误信息**：`工作流数据必须包含 nodes 和 edges 字段`

**解决方法**：
- 检查工作流 JSON 格式是否正确
- 确保包含 `nodes` 和 `edges` 字段（即使 `edges` 为空数组）

## 📚 相关文档

- [XXL-Job 处理器说明](./XXLJOB_PROCESSOR_README.md)
- [工作流引擎文档](../README.md)
- 批量执行接口文档：`apps/master/api/routes/workflow_router.py`

## 📝 更新日志

- **v1.0.0** (2025-01-XX)
  - 初始版本
  - 支持单节点 XXL-Job 批量执行
  - 支持状态查询
