# XXL-Job 处理器测试指南

## 📋 概述

这是一个使用 `packages/engine` 中 XXL-Job 处理器触发任务的测试示例。该测试演示了如何使用 XXL-Job 处理器触发任务执行。

## 🎯 功能特性

1. ✅ 通过 Handler 名称触发任务（需要数据库支持）
2. ✅ 传递任务执行参数（JSON 格式）
3. ✅ 支持多租户
4. ✅ 支持变量引用
5. ✅ 支持从上下文获取数据库连接

## 📦 文件说明

- `xxljob_processor_example.py` - Python 测试用例（单元测试）
- `xxljob_workflow_example.json` - Workflow 配置文件（JSON 格式）
- `run_xxljob_test.py` - 测试执行脚本
- `XXLJOB_PROCESSOR_README.md` - 本说明文档

## 🔧 前置要求

### 1. Python 环境
```bash
Python 3.7+
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. XXL-Job 服务器
- 需要运行 XXL-Job 管理平台
- 需要配置数据库（MySQL）

### 4. 数据库配置
- 需要在 XXL-Job 数据库中注册任务
- 需要配置数据库连接信息

## 📝 配置参数说明

### 必需参数

1. **xxjob_url** (string) - XXL-Job 管理平台 URL
   - 示例：`"http://job.dev.example.com"`
   - 说明：XXL-Job 管理后台地址

2. **executor_handler** (string) - 执行器 Handler 名称
   - 示例：`"demoJobHandler"`
   - 说明：任务在 XXL-Job 中注册的 Handler 名称

### 可选参数

3. **username** (string) - 登录用户名
   - 默认值：`"admin"`

4. **password** (string) - 登录密码
   - 默认值：`"123456"`

5. **app_code** (string) - 应用代码
   - 默认值：`"developer"`

6. **executor_param** (string) - 任务执行参数（JSON 字符串）
   - 示例：`'{"taskId": 12345, "action": "process"}'`
   - 说明：传递给任务执行器的参数，必须是有效的 JSON 字符串

7. **site_tenant** (string) - 站点租户
   - 默认值：`"DEFAULT"`

8. **address_list** (string) - 执行器地址列表
   - 说明：指定执行器地址，为空则自动选择

9. **db_name** (string) - 数据库名称
   - 默认值：`"xxl_job"`
   - 说明：用于从上下文获取数据库连接

10. **output_variable** (string) - 输出变量名
    - 默认值：`"xxljob_result"`
    - 说明：执行结果会保存到该变量名

## 🚀 快速开始

### 方法1：使用 Python 脚本运行（推荐）

```bash
# 进入项目根目录
cd /Users/jan/PycharmProjects/aegis-runner/packages/engine

# 运行测试脚本
python examples/run_xxljob_test.py
```

### 方法2：使用 Python 模块运行

```bash
# 进入项目根目录
cd /Users/jan/PycharmProjects/aegis-runner/packages/engine

# 运行测试模块
python -m examples.xxljob_processor_example
```

### 方法3：使用 workflow 引擎运行

```python
import json
from packages.engine.workflow_engine import WorkflowExecutor

# 加载配置
with open('examples/xxljob_workflow_example.json', 'r', encoding='utf-8') as f:
    workflow = json.load(f)

# 执行 workflow
executor = WorkflowExecutor(workflow)
result = executor.execute()

# 查看结果
print(f"测试状态: {result.status}")
```

## 📊 测试用例说明

### 1. 配置验证测试

测试配置参数验证逻辑，包括：
- 缺少必需字段的验证
- 空值的验证
- 有效配置的验证

### 2. 配置键测试

测试必需和可选配置键的定义。

### 3. 基本功能测试

测试基本的任务触发功能，包括：
- 登录 XXL-Job 平台
- 查询任务 ID
- 触发任务执行
- 获取执行结果

### 4. 变量功能测试

测试使用上下文变量的功能，包括：
- 在配置中使用 `${variable}` 引用变量
- 变量值的渲染
- 变量传递

### 5. JSON 参数测试

测试使用复杂 JSON 参数的功能。

### 6. 数据库客户端测试

测试从上下文获取数据库连接的功能。

## 💡 使用示例

### 示例1：基本使用

```python
from src.core.processors.job.xxljob_processor import XxlJobProcessor
from src.context import ExecutionContext

# 创建处理器
processor = XxlJobProcessor()

# 创建上下文
context = ExecutionContext()

# 配置节点
node_info = {
    "id": "xxljob_node",
    "type": "xxljob",
    "data": {
        "config": {
            "xxjob_url": "http://job.dev.example.com",
            "username": "admin",
            "password": "123456",
            "executor_handler": "demoJobHandler",
            "executor_param": '{"param": "value"}',
            "site_tenant": "DEFAULT"
        }
    }
}

# 执行处理器
result = processor.execute(node_info, context, {})
print(result)
```

### 示例2：使用变量

```python
# 设置上下文变量
context.set_variable("xxljob_url", "http://job.dev.example.com")
context.set_variable("handler_name", "demoJobHandler")
context.set_variable("task_id", 12345)

# 配置节点（使用变量）
node_info = {
    "id": "xxljob_node",
    "type": "xxljob",
    "data": {
        "config": {
            "xxjob_url": "${xxljob_url}",
            "executor_handler": "${handler_name}",
            "executor_param": '{"taskId": ${task_id}}',
            "site_tenant": "DEFAULT"
        }
    }
}

# 执行处理器
result = processor.execute(node_info, context, {})
```

### 示例3：使用数据库客户端

```python
from src.clients.sql_client import SQLClient

# 创建数据库客户端
db_client = SQLClient(
    host="localhost",
    port=3306,
    user="root",
    password="root",
    database="xxl_job"
)

# 将数据库客户端设置到上下文
context.set_variable("xxl_job", db_client)

# 配置节点
node_info = {
    "id": "xxljob_node",
    "type": "xxljob",
    "data": {
        "config": {
            "xxjob_url": "http://job.dev.example.com",
            "executor_handler": "demoJobHandler",
            "db_name": "xxl_job",  # 从上下文获取数据库连接
            "executor_param": '{"param": "value"}'
        }
    }
}

# 执行处理器
result = processor.execute(node_info, context, {})
```

## ⚠️ 注意事项

1. **executor_param 格式**：必须是有效的 JSON 字符串，例如：`'{"key": "value"}'`

2. **数据库连接**：通过 Handler 名称触发任务需要数据库支持，用于查询任务 ID

3. **数据库配置获取**：支持以下方式获取数据库连接：
   - 从上下文变量中获取 SQLClient 实例
   - 从上下文变量中获取数据库配置字典
   - 从环境配置中获取数据库配置

4. **任务注册**：确保任务已在 XXL-Job 中注册，Handler 名称正确

5. **权限配置**：确保登录用户有权限触发任务

## 🔍 故障排查

### 问题1：配置验证失败

**错误信息**：`xxjob_url 不能为空` 或 `executor_handler 不能为空`

**解决方法**：检查配置中是否包含必需的参数

### 问题2：登录失败

**错误信息**：`登录失败` 或 `401 Unauthorized`

**解决方法**：
- 检查用户名和密码是否正确
- 检查 XXL-Job 服务器是否运行
- 检查网络连接是否正常

### 问题3：任务不存在

**错误信息**：`任务不存在` 或 `Handler 未找到`

**解决方法**：
- 检查 Handler 名称是否正确
- 检查任务是否已在 XXL-Job 中注册
- 检查数据库连接是否正常

### 问题4：数据库连接失败

**错误信息**：`无法获取数据库连接`

**解决方法**：
- 检查数据库配置是否正确
- 检查数据库服务是否运行
- 检查上下文变量中是否有数据库配置

## 📚 相关文档

- [XXL-Job 官方文档](https://www.xuxueli.com/xxl-job/)
- [Engine 文档](../../README.md)
- [处理器使用手册](../docs/脚本处理器使用手册.md)

## 📝 更新日志

- **v1.0.0** (2025-01-XX)
  - 初始版本
  - 支持基本任务触发功能
  - 支持变量引用
  - 支持数据库连接
