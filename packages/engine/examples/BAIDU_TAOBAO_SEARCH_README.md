# 🔍 百度搜索Agent + 淘宝搜索衣服示例

## 📋 概述

本示例演示如何在一个工作流中：
1. ✅ 打开百度，搜索"Agent"
2. ✅ 切换到淘宝上下文
3. ✅ 打开淘宝，搜索"衣服"
4. ✅ 切换回百度查看结果

展示了**多网站上下文管理**的核心功能。

## 🎯 工作流步骤

```
启动浏览器
    ↓
打开百度（创建baidu上下文）
    ↓
等待页面加载
    ↓
输入搜索关键词：Agent
    ↓
点击搜索按钮
    ↓
等待搜索结果
    ↓
切换到淘宝上下文
    ↓
打开淘宝（创建taobao上下文）
    ↓
等待页面加载
    ↓
输入搜索关键词：衣服
    ↓
点击搜索按钮
    ↓
等待搜索结果
    ↓
切换回百度上下文
    ↓
获取百度搜索结果统计
```

## 📁 文件说明

- `baidu_taobao_search_example.json` - 工作流配置
- `run_baidu_taobao_search.py` - 执行脚本
- `BAIDU_TAOBAO_SEARCH_README.md` - 本说明文档

## 🚀 运行方式

### 方式1: 直接运行Python脚本

```bash
cd /Users/jan/PycharmProjects/aegis-runner/packages/engine
python examples/run_baidu_taobao_search.py
```

### 方式2: 使用工作流执行器

```python
from packages.engine.workflow_engine import WorkflowExecutor
import json

with open('examples/baidu_taobao_search_example.json', 'r') as f:
    workflow = json.load(f)

executor = WorkflowExecutor()
context = ExecutionContext()
result = executor.execute_workflow(workflow, context)
```

## 🔑 关键配置说明

### 1. 多网站上下文管理

```json
{
  "id": "navigate_to_baidu",
  "type": "ui_navigation",
  "data": {
    "config": {
      "operation": "navigate",
      "url": "https://www.baidu.com",
      "context_id": "baidu"  // 创建baidu上下文
    }
  }
}
```

```json
{
  "id": "switch_to_taobao",
  "type": "browser_launch",
  "data": {
    "config": {
      "operation": "switch_context",
      "context_id": "taobao"  // 切换到taobao上下文
    }
  }
}
```

### 2. 元素定位

#### 百度搜索框
- **方式1（推荐）**: 使用role定位器
  ```json
  {
    "selector": "textbox",
    "selector_type": "role"
  }
  ```

- **方式2**: 使用CSS选择器
  ```json
  {
    "selector": "#kw",
    "selector_type": "css"
  }
  ```

#### 淘宝搜索框
- 使用CSS选择器（淘宝的输入框ID为#q）
  ```json
  {
    "selector": "#q",
    "selector_type": "css"
  }
  ```

### 3. 等待策略

```json
{
  "id": "wait_for_baidu_load",
  "type": "smart_wait",
  "data": {
    "config": {
      "operation": "wait_for_element",
      "selector": "textbox",
      "selector_type": "role",
      "state": "visible",
      "timeout": 10000
    }
  }
}
```

## 📊 执行结果

成功执行后，您将看到：

```
✅ 测试执行成功！

📊 执行统计:
  - 总节点数: 15
  - 成功节点: 15
  - 失败节点: 0

🔍 搜索结果:
  - 百度搜索结果数量: 百度为您找到相关结果约...个
```

## 🔧 常见问题

### 1. 搜索框定位失败

**问题**: `Locator.click: Timeout exceeded`

**解决方案**:
- 增加等待时间：`"timeout": 30000`
- 添加显式等待节点
- 检查页面是否完全加载

### 2. 上下文切换失败

**问题**: `上下文 taobao 不存在`

**解决方案**:
- 确保先创建上下文（导航时会自动创建）
- 或手动创建上下文节点

### 3. 页面加载缓慢

**解决方案**:
- 增加超时时间
- 使用 `wait_for_network` 等待网络空闲
- 检查网络连接

## 🎨 自定义扩展

### 修改搜索关键词

```json
{
  "id": "input_baidu_search",
  "type": "ui_element",
  "data": {
    "config": {
      "operation": "input",
      "selector": "textbox",
      "selector_type": "role",
      "value": "人工智能"  // 修改这里
    }
  }
}
```

### 添加更多网站

```json
{
  "id": "switch_to_jd",
  "type": "browser_launch",
  "data": {
    "config": {
      "operation": "switch_context",
      "context_id": "jd"
    }
  }
},
{
  "id": "navigate_to_jd",
  "type": "ui_navigation",
  "data": {
    "config": {
      "operation": "navigate",
      "url": "https://www.jd.com",
      "context_id": "jd"
    }
  }
}
```

### 添加截图功能

```json
{
  "id": "capture_screenshot",
  "type": "ui_element",
  "data": {
    "config": {
      "operation": "screenshot",
      "filename": "search_results.png",
      "full_page": true
    }
  }
}
```

## 📚 相关文档

- [多网站上下文管理指南](./MULTI_WEB_CONTEXT_GUIDE.md)
- [自动鉴权导航指南](./AUTO_AUTH_NAVIGATION_GUIDE.md)
- [UI元素处理器文档](../docs/UI_ELEMENT_PROCESSOR.md)

## 💡 最佳实践

1. **使用role定位器** - 更稳定，不易受页面结构变化影响
2. **添加显式等待** - 确保元素可见后再操作
3. **合理的超时时间** - 平衡速度和稳定性
4. **上下文命名规范** - 使用有意义的context_id
5. **错误处理** - 检查执行结果，处理失败步骤

## 🎉 总结

本示例展示了：

✅ **多网站操作** - 在一个工作流中操作多个网站
✅ **上下文切换** - 自由切换不同网站的上下文
✅ **状态保持** - 切换后状态完全保留
✅ **完全隔离** - 不同网站的Cookie、Session独立

开始使用多网站工作流，让您的自动化测试更加强大！🚀
