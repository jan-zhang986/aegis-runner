# -*- coding: utf-8 -*-
"""
验证 pytest 插件生命周期与钩子模拟测试
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

# 将 packages/aegis-sdk 加入路径
sdk_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(sdk_dir))

from aegis import aegis
from aegis.protocol import EventType, StepStatus
import aegis.plugin as plugin


def test_plugin_hooks_simulation():
    # 1. 模拟 pytest config
    mock_config = MagicMock()
    mock_config.getoption.side_effect = lambda opt: {
        "--aegis-server": "http://127.0.0.1:8989",
        "--aegis-run-id": "RUN-TEST-001",
        "--aegis-token": "test-token",
        "--aegis-jsonl": None,
        "--aegis-no-console": True,
        "--aegis-disable": False,
    }.get(opt, False)

    # 2. 模拟捕获事件
    captured = []
    class DummyReporter:
        def report(self, event):
            captured.append(event)
        def close(self):
            pass

    aegis.add_reporter(DummyReporter())

    # 3. 执行 pytest_configure
    plugin.pytest_configure(mock_config)
    assert aegis.get_run_id() == "RUN-TEST-001"

    # 4. 模拟 sessionstart
    mock_session = MagicMock()
    mock_session.config = mock_config
    plugin.pytest_sessionstart(mock_session)
    assert any(e.event_type == EventType.RUN_START.value for e in captured)

    # 5. 模拟 pytest 用例运行
    @aegis.case(id="TC-PLUGIN-01", req="REQ-101", title="插件钩子测试", risk="插件状态未正常同步")
    def sample_test():
        with aegis.step("步骤 A"):
            pass

    mock_item = MagicMock()
    mock_item.obj = sample_test

    # 运行 protocol 包装器
    gen = plugin.pytest_runtest_protocol(mock_item, None)
    next(gen)  # 前置 setup，注入 context
    assert aegis.get_current_case()["id"] == "TC-PLUGIN-01"
    assert aegis.get_current_case()["risk"] == "插件状态未正常同步"

    # 真正执行函数
    sample_test()

    try:
        next(gen)
    except StopIteration:
        pass

    assert aegis.get_current_case() is None  # 执行完已清理

    # 6. 模拟 sessionfinish
    plugin.pytest_sessionfinish(mock_session, 0)
    assert any(e.event_type == EventType.RUN_END.value and e.status == StepStatus.PASSED.value for e in captured)

    print("\n✅ Pytest 插件生命周期 (plugin.py) 模拟校验 100% 通过！")


if __name__ == "__main__":
    test_plugin_hooks_simulation()
