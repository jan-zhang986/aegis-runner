# -*- coding: utf-8 -*-
"""
Aegis Test as Code SDK
提供 @aegis.case, @aegis.feature, with aegis.step 等轻量装饰器与上下文管理器，
用于在原生测试工程中声明用例元数据，并支持平台 AST 解析与流式步骤打屏。
"""
import time
import functools
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

class _StepContext:
    def __init__(self, name: str, parent: Optional['_StepContext'] = None):
        self.name = name
        self.parent = parent
        self.start_time: float = 0
        self.end_time: float = 0
        self.status: str = "PENDING"
        self.error: Optional[Exception] = None

    def __enter__(self):
        self.start_time = time.time()
        self.status = "RUNNING"
        # 触发步骤开始回调/事件 (如果有 listener)
        _AegisCore.on_step_start(self.name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration_ms = int((self.end_time - self.start_time) * 1000)
        if exc_val is not None:
            self.status = "FAILED"
            self.error = exc_val
            _AegisCore.on_step_end(self.name, status="FAILED", duration_ms=duration_ms, error=str(exc_val))
        else:
            self.status = "PASSED"
            _AegisCore.on_step_end(self.name, status="PASSED", duration_ms=duration_ms)
        return False  # 正常向上抛出异常，不吞异常

class _AegisCore:
    _step_listeners = []

    @classmethod
    def register_step_listener(cls, listener_fn):
        cls._step_listeners.append(listener_fn)

    @classmethod
    def on_step_start(cls, step_name: str):
        for listener in cls._step_listeners:
            try:
                listener("START", step_name, {})
            except Exception:
                pass

    @classmethod
    def on_step_end(cls, step_name: str, status: str, duration_ms: int, error: Optional[str] = None):
        for listener in cls._step_listeners:
            try:
                listener("END", step_name, {"status": status, "duration_ms": duration_ms, "error": error})
            except Exception:
                pass

    @staticmethod
    def step(name: str):
        """步骤上下文管理器: with aegis.step('步骤说明'):"""
        return _StepContext(name)

    @staticmethod
    def case(
        id: str,
        req: str,
        title: Optional[str] = None,
        priority: str = "P1",
        tags: Optional[List[str]] = None,
        description: Optional[str] = None,
    ):
        """
        用例装饰器: 声明用例元数据与需求溯源
        @aegis.case(id="TC-001", req="REQ-224", title="验证码防刷限流", priority="P0")
        """
        def decorator(func):
            # 将元数据绑定到函数属性，支持运行时反射与 AST 静态提取
            meta = {
                "id": id,
                "req": req,
                "title": title or func.__name__,
                "priority": priority,
                "tags": tags or [],
                "description": description or func.__doc__ or "",
                "function_name": func.__name__,
            }
            func.__aegis_case__ = meta

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper
        return decorator

    @staticmethod
    def feature(name: str):
        """功能模块装饰器"""
        def decorator(func):
            func.__aegis_feature__ = name
            return func
        return decorator

    @staticmethod
    def epic(name: str):
        """史诗模块装饰器"""
        def decorator(func):
            func.__aegis_epic__ = name
            return func
        return decorator

# 单例导出
aegis = _AegisCore()
__all__ = ["aegis"]
