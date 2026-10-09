# -*- coding: utf-8 -*-
import sys
from pathlib import Path

# 将 packages/aegis-sdk 加入路径
sdk_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(sdk_dir))

from aegis import aegis, AegisEvent
from aegis.reporter import BaseReporter

class MockCollectorReporter(BaseReporter):
    def __init__(self):
        self.events = []

    def report(self, event: AegisEvent) -> None:
        self.events.append(event)


@aegis.epic("用户中心")
@aegis.feature("手机短信验证码登录")
@aegis.case(
    id="TC-SMS-001",
    req="REQ-224",
    title="高频并发连击请求 ➔ 触发 429 防刷限流",
    risk="短信通道被恶意刷爆导致资损与服务瘫痪",
    priority="P0",
    tags=["smoke", "security"]
)
def test_sms_rate_limit():
    """验证单 IP 单日超过限制频次后返回 429 拦截"""
    with aegis.step("步骤 1: 模拟 1 秒内发起 10 次短信下发", evidence={"concurrent_count": 10}):
        aegis.attach_evidence("redis_key", "rate_limit:sms:13800000001")

    with aegis.step("步骤 2: 校验首次请求状态码为 HTTP 200"):
        assert 200 == 200
        aegis.attach_evidence("status_code", 200)

    with aegis.step("步骤 3: 校验后续请求被限流拦截 (HTTP 429)"):
        assert 429 == 429
        aegis.attach_evidence("status_code", 429)


if __name__ == "__main__":
    collector = MockCollectorReporter()
    aegis.add_reporter(collector)

    # 1. 验证元数据与 risk 字段
    meta = getattr(test_sms_rate_limit, "__aegis_case__", None)
    print("Test Metadata:", meta)
    assert meta["id"] == "TC-SMS-001"
    assert meta["req"] == "REQ-224"
    assert meta["risk"] == "短信通道被恶意刷爆导致资损与服务瘫痪"
    assert meta["priority"] == "P0"

    # 2. 执行用例
    test_sms_rate_limit()

    # 3. 校验上报的结构化事件
    event_types = [e.event_type for e in collector.events]
    print("Captured Event Types:", event_types)
    # 应有 CASE_START, STEP_START*3, STEP_END*3, CASE_END
    assert "CASE_START" in event_types
    assert "CASE_END" in event_types
    assert event_types.count("STEP_START") == 3
    assert event_types.count("STEP_END") == 3

    # 4. 校验证据传递
    step1_end = [e for e in collector.events if e.event_type == "STEP_END" and "步骤 1" in e.step_name][0]
    print("Step 1 Evidence:", step1_end.evidence)
    assert step1_end.evidence.get("concurrent_count") == 10
    assert step1_end.evidence.get("redis_key") == "rate_limit:sms:13800000001"
    assert step1_end.risk == "短信通道被恶意刷爆导致资损与服务瘫痪"
    assert step1_end.status == "PASSED"

    print("\n✅ Aegis SDK 1.1.0 核心事件流与风险元数据验证 100% 通过！")
