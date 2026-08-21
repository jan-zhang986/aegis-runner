# 百度搜索功能测试

## 📋 概述

这是一个使用 `packages/engine` 中 UI 处理器测试百度搜索功能的示例 workflow。该测试会自动打开浏览器，访问百度首页，执行搜索操作，并验证搜索结果。

## 🎯 测试目标

1. ✅ 验证百度首页是否能正常加载
2. ✅ 验证搜索输入框是否可用
3. ✅ 验证搜索按钮是否可点击
4. ✅ 验证搜索结果是否正常显示
5. ✅ 捕获测试过程截图

## 📦 文件说明

- `baidu_search_test.json` - Workflow配置文件（JSON格式）
- `run_baidu_search_test.py` - 测试执行脚本
- `BAIDU_SEARCH_TEST_README.md` - 本说明文档

## 🔧 前置要求

### 1. Python环境
```bash
Python 3.7+
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 安装Playwright浏览器
```bash
playwright install chromium
```

## 🚀 快速开始

### 方法1：使用Python脚本运行（推荐）

```bash
# 进入项目根目录
cd /Users/jan/PycharmProjects/aegis-runner/packages/engine

# 运行测试脚本
python examples/run_baidu_search_test.py
```

### 方法2：使用workflow引擎直接运行

```python
import json
from packages.engine.workflow_engine import WorkflowExecutor

# 加载配置
with open('examples/baidu_search_test.json', 'r', encoding='utf-8') as f:
    workflow = json.load(f)

# 执行workflow
executor = WorkflowExecutor(workflow)
result = executor.execute()

# 查看结果
print(f"测试状态: {result.status}")
```

## 📊 Workflow节点说明

### 1. launch_browser
启动Chromium浏览器（非无头模式，可以看到浏览器界面）

```json
{
  "type": "browser_launch",
  "config": {
    "operation": "launch",
    "browser_type": "chromium",
    "headless": false
  }
}
```

### 2. navigate_to_baidu
导航到百度首页

```json
{
  "type": "ui_navigation",
  "config": {
    "operation": "navigate",
    "url": "https://www.baidu.com"
  }
}
```

### 3. wait_for_page_load
智能等待页面加载完成

```json
{
  "type": "smart_wait",
  "config": {
    "operation": "smart_wait",
    "wait_types": ["network_idle", "dom_stable"],
    "timeout": 10000
  }
}
```

### 4. input_search_keyword
在搜索框中输入关键词"人工智能"

```json
{
  "type": "ui_element",
  "config": {
    "operation": "input",
    "selector": "#kw",
    "value": "人工智能",
    "timeout": 5000
  }
}
```

### 5. click_search_button
点击搜索按钮

```json
{
  "type": "ui_element",
  "config": {
    "operation": "click",
    "selector": "#su",
    "timeout": 5000
  }
}
```

### 6. wait_for_search_results
等待搜索结果加载（带重试机制）

```json
{
  "type": "smart_wait",
  "config": {
    "operation": "element_visible",
    "selector": "#content_left",
    "timeout": 10000,
    "max_retries": 3,
    "backoff_factor": 1.5
  }
}
```

### 7. verify_search_results
获取搜索结果文本进行验证

```json
{
  "type": "ui_element",
  "config": {
    "operation": "get_text",
    "selector": "#content_left .result",
    "timeout": 5000
  }
}
```

### 8. capture_screenshot
捕获诊断信息和截图

```json
{
  "type": "observability",
  "config": {
    "operation": "capture_diagnostic",
    "node_id": "search_results",
    "capture_screenshot": true,
    "capture_console": true
  }
}
```

## 📈 预期结果

### 成功执行
```
======================================================================
百度搜索功能测试
======================================================================

✅ 已加载workflow配置
📁 配置文件: /Users/jan/PycharmProjects/aegis-runner/packages/engine/examples/baidu_search_test.json
📊 节点数量: 8

🚀 开始执行测试...

======================================================================
✅ 测试执行成功！
======================================================================

📊 测试结果摘要:

🔍 搜索结果验证:
  ✓ 成功获取搜索结果
  ✓ 结果文本长度: 1234 字符

📸 诊断信息:
  ✓ 截图已保存: diagnostic_data/search_results_20251031_123456.png
  ✓ 控制台日志: 5 条

======================================================================
🎉 百度搜索功能测试完成！
```

### 失败处理
如果测试失败，脚本会输出：
- 失败的节点ID
- 详细的错误信息
- 诊断信息（如果可用）

## 🎨 自定义测试

### 修改搜索关键词
编辑 `baidu_search_test.json`，找到 `input_search_keyword` 节点：

```json
{
  "id": "input_search_keyword",
  "type": "ui_element",
  "data": {
    "config": {
      "operation": "input",
      "selector": "#kw",
      "value": "修改为你想搜索的内容",  // 修改这里
      "timeout": 5000
    }
  }
}
```

### 使用无头模式运行
如果不想看到浏览器界面，修改 `launch_browser` 节点：

```json
{
  "id": "launch_browser",
  "type": "browser_launch",
  "data": {
    "config": {
      "operation": "launch",
      "browser_type": "chromium",
      "headless": true  // 改为 true
    }
  }
}
```

### 添加更多验证
可以添加额外的节点来验证更多内容，例如：

```json
{
  "id": "verify_title",
  "type": "ui_element",
  "data": {
    "config": {
      "operation": "get_attribute",
      "selector": "title",
      "attribute": "text",
      "timeout": 5000
    }
  }
}
```

## 📝 注意事项

1. **网络要求**：需要能访问百度（www.baidu.com）
2. **浏览器驱动**：确保已安装Playwright的Chromium驱动
3. **元素选择器**：百度可能会更新页面结构，如果选择器失效，需要更新配置
4. **超时设置**：根据网络速度可能需要调整timeout值
5. **截图保存**：截图会保存在 `diagnostic_data/` 目录下

## 🔍 故障排查

### 问题1：找不到元素
**原因**：百度页面结构可能已更新  
**解决**：
1. 手动打开百度，按F12打开开发者工具
2. 检查搜索框和按钮的实际选择器
3. 更新workflow配置中的选择器

### 问题2：浏览器启动失败
**原因**：Playwright浏览器未安装  
**解决**：
```bash
playwright install chromium
```

### 问题3：网络超时
**原因**：网络连接问题或百度响应慢  
**解决**：增加timeout值
```json
{
  "timeout": 30000  // 增加到30秒
}
```

### 问题4：权限错误
**原因**：文件写入权限问题  
**解决**：确保有 `diagnostic_data/` 目录的写入权限

## 🚀 进阶用法

### 1. 添加性能监控
在workflow中添加性能监控节点：

```json
{
  "id": "measure_performance",
  "type": "performance",
  "data": {
    "config": {
      "operation": "measure_page_load",
      "url": "https://www.baidu.com"
    }
  }
}
```

### 2. 添加视觉回归测试
捕获基线图像：

```json
{
  "id": "visual_baseline",
  "type": "visual_regression",
  "data": {
    "config": {
      "operation": "capture_baseline",
      "baseline_name": "baidu_search_results",
      "full_page": true
    }
  }
}
```

### 3. 多设备测试
测试响应式布局：

```json
{
  "id": "responsive_test",
  "type": "responsive",
  "data": {
    "config": {
      "operation": "test_responsive_layout",
      "url": "https://www.baidu.com",
      "devices": ["iphone_13", "ipad_pro", "desktop_fhd"]
    }
  }
}
```

## 📚 相关文档

- [UI处理器增强功能指南](../docs/UI_PROCESSOR_ENHANCEMENTS.md)
- [智能等待机制](../docs/UI_PROCESSOR_ENHANCEMENTS.md#增强等待机制)
- [可观测性和诊断](../docs/UI_PROCESSOR_ENHANCEMENTS.md#可观测性和诊断)
- [处理器响应标准](../docs/PROCESSOR_RESPONSE_STANDARD.md)

## 🤝 贡献

如果您发现问题或有改进建议，欢迎提交Issue或Pull Request！

## 📄 许可

本示例遵循仓库当前许可证约定。
