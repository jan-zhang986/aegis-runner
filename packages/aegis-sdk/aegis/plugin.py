# -*- coding: utf-8 -*-
"""
Aegis Pytest 官方插件 (pytest-plugin)
自动拦截 pytest session 与用例执行生命周期，
自动注入 reporter 并流式分发 CASE / STEP 事件。
"""
import os
import time
from typing import Optional

try:
    import pytest
    _pytest_hookimpl = pytest.hookimpl
except ImportError:
    # 允许在无 pytest 环境下导入与模拟测试
    pytest = None
    class _DummyHook:
        @staticmethod
        def hookimpl(hookwrapper=False):
            def dec(f):
                return f
            return dec
    _pytest_hookimpl = _DummyHook.hookimpl

from aegis import aegis
from aegis.protocol import AegisEvent, EventType, StepStatus
from aegis.reporter import ConsoleReporter, HttpReporter, JsonLinesReporter


def pytest_addoption(parser):
    """注册 Aegis pytest 命令行参数与 ini 配置"""
    group = parser.getgroup("aegis", "Aegis Test as Code 平台集成配置")
    
    group.addoption(
        "--aegis-server",
        action="store",
        default=os.getenv("AEGIS_SERVER_URL", "http://127.0.0.1:8989"),
        help="Aegis Server 或 Local Companion 访问地址 (默认: http://127.0.0.1:8989)",
    )
    group.addoption(
        "--aegis-run-id",
        action="store",
        default=os.getenv("AEGIS_RUN_ID", f"RUN-{int(time.time())}"),
        help="本次测试执行批次 ID (默认自动生成时间戳)",
    )
    group.addoption(
        "--aegis-token",
        action="store",
        default=os.getenv("AEGIS_TOKEN", None),
        help="Aegis 平台认证 Token",
    )
    group.addoption(
        "--aegis-jsonl",
        action="store",
        default=os.getenv("AEGIS_JSONL_PATH", None),
        help="将事件流持久化保存的本地 jsonl 文件路径",
    )
    group.addoption(
        "--aegis-no-console",
        action="store_true",
        default=False,
        help="关闭控制台彩色格式化步骤输出",
    )
    group.addoption(
        "--aegis-disable",
        action="store_true",
        default=False,
        help="完全禁用 Aegis 插件及其事件上报",
    )


def pytest_configure(config):
    """初始化 Aegis 核心配置与 Reporters"""
    if config.getoption("--aegis-disable"):
        return

    run_id = config.getoption("--aegis-run-id")
    aegis.set_run_id(run_id)

    # 1. 本地控制台打屏
    if not config.getoption("--aegis-no-console"):
        aegis.add_reporter(ConsoleReporter(verbose=True))

    # 2. Local Companion / Server HTTP 上报
    server_url = config.getoption("--aegis-server")
    token = config.getoption("--aegis-token")
    if server_url:
        aegis.add_reporter(HttpReporter(target_url=server_url, token=token))

    # 3. 本地 JsonLines 持久化
    jsonl_path = config.getoption("--aegis-jsonl")
    if jsonl_path:
        aegis.add_reporter(JsonLinesReporter(file_path=jsonl_path))


def pytest_sessionstart(session):
    """测试会话开始"""
    if session.config.getoption("--aegis-disable"):
        return
    
    run_id = aegis.get_run_id()
    aegis.emit_event(AegisEvent(
        event_type=EventType.RUN_START.value,
        run_id=run_id,
        title=f"Pytest Session Start: {session.name if hasattr(session, 'name') else 'TestRun'}",
    ))


def pytest_sessionfinish(session, exitstatus):
    """测试会话结束，上报并刷新缓冲区"""
    if session.config.getoption("--aegis-disable"):
        return

    status = StepStatus.PASSED.value if exitstatus == 0 else StepStatus.FAILED.value
    run_id = aegis.get_run_id()
    aegis.emit_event(AegisEvent(
        event_type=EventType.RUN_END.value,
        run_id=run_id,
        status=status,
    ))
    aegis.get_reporter().close()


@_pytest_hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    """提取用例元数据并设置上下文"""
    test_func = getattr(item, "obj", None)
    case_meta = getattr(test_func, "__aegis_case__", None)
    
    if case_meta:
        aegis.set_current_case(case_meta)
    else:
        # 非 @aegis.case 装饰的原生测试，构建基本元数据
        aegis.set_current_case({
            "id": getattr(item, "nodeid", str(item)),
            "req": None,
            "title": getattr(item, "name", str(item)),
            "risk": None,
            "priority": "P2",
        })

    try:
        yield
    finally:
        aegis.set_current_case(None)
