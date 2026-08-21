# 🚀 快速开始 - 百度搜索测试

## 📝 简介

这是一个使用 `packages/engine` 测试百度搜索功能的完整示例。

## ⚡ 快速运行（3步）

### 步骤1：验证环境配置

```bash
cd /Users/jan/PycharmProjects/aegis-runner/packages/engine
python examples/verify_baidu_test_setup.py
```

这会检查：
- ✅ Python版本
- ✅ 依赖包
- ✅ Playwright浏览器
- ✅ 配置文件
- ✅ 网络连接

### 步骤2：运行测试

```bash
python examples/run_baidu_search_test.py
```

### 步骤3：查看结果

测试完成后，您会看到：
- 测试执行状态
- 搜索结果验证信息
- 截图保存路径（在 `diagnostic_data/` 目录）

## 📁 相关文件

| 文件 | 说明 |
|------|------|
| `baidu_search_test.json` | Workflow配置文件 |
| `run_baidu_search_test.py` | 测试执行脚本 |
| `verify_baidu_test_setup.py` | 环境验证脚本 |
| `BAIDU_SEARCH_TEST_README.md` | 详细说明文档 |

## 🔧 故障排查

### 问题：Playwright浏览器未安装

```bash
playwright install chromium
```

### 问题：依赖包缺失

```bash
pip install -r requirements.txt
```

### 问题：网络连接失败

检查防火墙设置，确保能访问 www.baidu.com

## 📚 详细文档

查看完整文档：[BAIDU_SEARCH_TEST_README.md](./BAIDU_SEARCH_TEST_README.md)

## 🎯 测试流程

```
启动浏览器 
    ↓
访问百度首页
    ↓
等待页面加载
    ↓
输入搜索关键词
    ↓
点击搜索按钮
    ↓
等待搜索结果
    ↓
验证结果显示
    ↓
保存截图和诊断信息
```

## 💡 自定义测试

修改 `baidu_search_test.json` 中的配置即可：

```json
{
  "id": "input_search_keyword",
  "data": {
    "config": {
      "value": "您想搜索的内容"  // 修改这里
    }
  }
}
```

## 🎉 预期结果示例

```
======================================================================
百度搜索功能测试
======================================================================

✅ 已加载workflow配置
📁 配置文件: examples/baidu_search_test.json
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

## 🆘 获取帮助

如有问题，请查看：
1. [详细文档](./BAIDU_SEARCH_TEST_README.md)
2. [UI处理器指南](../docs/UI_PROCESSOR_ENHANCEMENTS.md)
3. [项目README](../README.md)
