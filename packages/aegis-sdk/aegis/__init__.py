# -*- coding: utf-8 -*-
"""
Aegis Test as Code SDK
提供 @aegis.case, @aegis.feature, with aegis.step 等装饰器与上下文管理器，
支持风险元数据标注 (risk)、证据附加 (evidence)、运行时上下文追踪与流式步骤打屏。
"""
import time
import functools
import contextvars
from typing import Optional, List, Dict, Any

from aegis.protocol import AegisEvent, EventType, StepStatus
from aegis.reporter import BaseReporter, CompositeReporter, ConsoleReporter

# 上下文变量 (保证异步与多线程安全)
_current_case_ctx: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar("_current_case_ctx", default=None)
_current_run_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("_current_run_id_ctx", default=None)
_current_step_evidence_ctx: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar("_current_step_evidence_ctx", default={})


class _StepContext:
    def __init__(self, name: str, evidence: Optional[Dict[str, Any]] = None):
        self.name = name
        self.evidence: Dict[str, Any] = dict(evidence or {})
        self.start_time: float = 0
        self.end_time: float = 0
        self.status: str = StepStatus.PENDING.value
        self.error: Optional[Exception] = None
        self._token = None

    def attach_evidence(self, key: str, value: Any) -> '_StepContext':
        """在步骤内动态追加证据 (如接口响应、数据库记录)"""
        self.evidence[key] = value
        return self

    def __enter__(self):
        self.start_time = time.time()
        self.status = StepStatus.RUNNING.value
        self._token = _current_step_evidence_ctx.set(self.evidence)

        # 触发步骤开始事件
        _AegisCore.emit_step_event(EventType.STEP_START.value, self.name, StepStatus.RUNNING.value, 0, self.evidence)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration_ms = int((self.end_time - self.start_time) * 1000)

        # 收集上下文内动态附加的证据
        step_evidence = _current_step_evidence_ctx.get()
        if self._token:
            _current_step_evidence_ctx.reset(self._token)

        if exc_val is not None:
            self.status = StepStatus.FAILED.value
            self.error = exc_val
            _AegisCore.emit_step_event(
                EventType.STEP_END.value,
                self.name,
                StepStatus.FAILED.value,
                duration_ms,
                step_evidence,
                error=str(exc_val)
            )
        else:
            self.status = StepStatus.PASSED.value
            _AegisCore.emit_step_event(
                EventType.STEP_END.value,
                self.name,
                StepStatus.PASSED.value,
                duration_ms,
                step_evidence
            )
        return False  # 不吞异常，正常向上抛出给 pytest


class _AegisCore:
    _composite_reporter = CompositeReporter()
    _legacy_step_listeners = []

    @classmethod
    def get_reporter(cls) -> CompositeReporter:
        return cls._composite_reporter

    @classmethod
    def add_reporter(cls, reporter: BaseReporter) -> None:
        cls._composite_reporter.add_reporter(reporter)

    @classmethod
    def register_step_listener(cls, listener_fn):
        """兼容遗留 listener_fn(event_type, step_name, data)"""
        cls._legacy_step_listeners.append(listener_fn)

    @classmethod
    def set_run_id(cls, run_id: str) -> None:
        _current_run_id_ctx.set(run_id)

    @classmethod
    def get_run_id(cls) -> Optional[str]:
        return _current_run_id_ctx.get()

    @classmethod
    def set_current_case(cls, meta: Optional[Dict[str, Any]]) -> None:
        _current_case_ctx.set(meta)

    @classmethod
    def get_current_case(cls) -> Optional[Dict[str, Any]]:
        return _current_case_ctx.get()

    @classmethod
    def emit_event(cls, event: AegisEvent) -> None:
        cls._composite_reporter.report(event)

    @classmethod
    def emit_step_event(
        cls,
        event_type: str,
        step_name: str,
        status: str,
        duration_ms: int,
        evidence: Dict[str, Any],
        error: Optional[str] = None
    ) -> None:
        case_meta = cls.get_current_case() or {}
        event = AegisEvent(
            event_type=event_type,
            run_id=cls.get_run_id(),
            case_id=case_meta.get("id"),
            req_id=case_meta.get("req"),
            risk=case_meta.get("risk"),
            title=case_meta.get("title"),
            priority=case_meta.get("priority"),
            feature=case_meta.get("feature"),
            epic=case_meta.get("epic"),
            step_name=step_name,
            status=status,
            duration_ms=duration_ms,
            evidence=evidence,
            error=error,
        )
        cls.emit_event(event)

        # 触发遗留 step 监听器
        simple_type = "START" if event_type == EventType.STEP_START.value else "END"
        payload = {"status": status, "duration_ms": duration_ms, "evidence": evidence, "error": error}
        for listener in cls._legacy_step_listeners:
            try:
                listener(simple_type, step_name, payload)
            except Exception:
                pass

    @staticmethod
    def step(name: str, evidence: Optional[Dict[str, Any]] = None):
        """
        步骤上下文管理器:
        with aegis.step('步骤说明', evidence={'param': 1}):
            aegis.attach_evidence('resp_code', 200)
        """
        return _StepContext(name, evidence=evidence)

    @staticmethod
    def attach_evidence(key: str, value: Any) -> None:
        """在当前正在执行的步骤中动态附加证据"""
        current = _current_step_evidence_ctx.get()
        if isinstance(current, dict):
            current[key] = value

    @staticmethod
    def case(
        id: str,
        req: str,
        title: Optional[str] = None,
        risk: Optional[str] = None,
        priority: str = "P1",
        tags: Optional[List[str]] = None,
        description: Optional[str] = None,
    ):
        """
        用例装饰器: 声明用例元数据、需求溯源与业务风险
        @aegis.case(
            id="TC-001",
            req="REQ-224",
            title="高频并发连击请求触发 429 防刷限流",
            risk="高频短信轰炸导致通道被封禁与财务资损",
            priority="P0"
        )
        """
        def decorator(func):
            meta = {
                "id": id,
                "req": req,
                "title": title or func.__name__,
                "risk": risk,
                "priority": priority,
                "tags": tags or [],
                "description": description or func.__doc__ or "",
                "function_name": func.__name__,
                "feature": getattr(func, "__aegis_feature__", None),
                "epic": getattr(func, "__aegis_epic__", None),
            }
            func.__aegis_case__ = meta

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                token = _current_case_ctx.set(meta)
                start_time = time.time()
                
                # 发送 CASE_START 事件
                _AegisCore.emit_event(AegisEvent(
                    event_type=EventType.CASE_START.value,
                    run_id=_AegisCore.get_run_id(),
                    case_id=meta["id"],
                    req_id=meta["req"],
                    risk=meta["risk"],
                    title=meta["title"],
                    priority=meta["priority"],
                    feature=meta.get("feature"),
                    epic=meta.get("epic"),
                ))
                
                try:
                    res = func(*args, **kwargs)
                    duration_ms = int((time.time() - start_time) * 1000)
                    _AegisCore.emit_event(AegisEvent(
                        event_type=EventType.CASE_END.value,
                        run_id=_AegisCore.get_run_id(),
                        case_id=meta["id"],
                        req_id=meta["req"],
                        risk=meta["risk"],
                        title=meta["title"],
                        priority=meta["priority"],
                        status=StepStatus.PASSED.value,
                        duration_ms=duration_ms,
                    ))
                    return res
                except Exception as e:
                    duration_ms = int((time.time() - start_time) * 1000)
                    _AegisCore.emit_event(AegisEvent(
                        event_type=EventType.CASE_END.value,
                        run_id=_AegisCore.get_run_id(),
                        case_id=meta["id"],
                        req_id=meta["req"],
                        risk=meta["risk"],
                        title=meta["title"],
                        priority=meta["priority"],
                        status=StepStatus.FAILED.value,
                        duration_ms=duration_ms,
                        error=str(e),
                    ))
                    raise
                finally:
                    _current_case_ctx.reset(token)

            return wrapper
        return decorator

    @staticmethod
    def feature(name: str):
        """功能模块装饰器"""
        def decorator(func):
            func.__aegis_feature__ = name
            if hasattr(func, "__aegis_case__"):
                func.__aegis_case__["feature"] = name
            return func
        return decorator

    @staticmethod
    def epic(name: str):
        """史诗模块装饰器"""
        def decorator(func):
            func.__aegis_epic__ = name
            if hasattr(func, "__aegis_case__"):
                func.__aegis_case__["epic"] = name
            return func
        return decorator


# 常用工具与扩展导出
from aegis.parser import parse_test_file, scan_test_directory
from aegis.fixtures import AegisHttpClient

# 单例导出
aegis = _AegisCore()
__all__ = [
    "aegis",
    "AegisEvent",
    "EventType",
    "StepStatus",
    "parse_test_file",
    "scan_test_directory",
    "AegisHttpClient",
]

