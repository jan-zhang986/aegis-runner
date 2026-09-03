# -*- coding: utf-8 -*-
import sys
from pathlib import Path

# 将 packages/aegis-sdk 加入路径
sdk_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(sdk_dir))

from aegis import aegis

@aegis.epic("用户中心")
@aegis.feature("手机短信验证码登录")
@aegis.case(
    id="TC-SMS-001",
    req="REQ-224",
    title="高频并发连击请求 ➔ 触发 429 防刷限流",
    priority="P0",
    tags=["smoke", "security"]
)
def test_sms_rate_limit():
    """验证单 IP 单日超过限制频次后返回 429 拦截"""
    with aegis.step("步骤 1: 模拟 1 秒内发起 10 次短信下发"):
        pass

    with aegis.step("步骤 2: 校验首次请求状态码为 HTTP 200"):
        assert 200 == 200

    with aegis.step("步骤 3: 校验后续请求被限流拦截 (HTTP 429)"):
        assert 429 == 429

if __name__ == "__main__":
    captured_events = []
    def log_event(event_type, name, data):
        captured_events.append((event_type, name, data))
        print(f"[{event_type}] {name} => {data}")

    aegis.register_step_listener(log_event)
    
    # 验证元数据
    meta = getattr(test_sms_rate_limit, "__aegis_case__", None)
    print("Test Metadata:", meta)
    assert meta["id"] == "TC-SMS-001"
    assert meta["req"] == "REQ-224"
    assert meta["priority"] == "P0"

    # 执行用例
    test_sms_rate_limit()
    print("Captured Steps:", len(captured_events))
    assert len(captured_events) == 6  # 3 steps * (START + END)
    print("✅ Aegis SDK 验证 100% 通过！")
