# -*- coding: utf-8 -*-
"""
变量渲染与配置读取工具（单一实现，供 processors 包与各处理器引用）。
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def _get_raw_variable_from_context(context: Any, var_name: str) -> Optional[Any]:
    """从执行上下文读取变量原始值（保持类型）。"""
    if hasattr(context, "get_variable"):
        return context.get_variable(var_name)
    if hasattr(context, "_variables") and isinstance(context._variables, dict):
        return context._variables.get(var_name)
    if isinstance(context, dict):
        return context.get(var_name)
    return None


def _object_to_dict(obj: Any) -> Dict[str, Any]:
    """将 Pydantic / dataclass / 普通对象转为 dict，供递归渲染。"""
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        try:
            return obj.dict()
        except Exception:
            return dict(obj.__dict__)
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        try:
            return obj.model_dump()
        except Exception:
            return dict(obj.__dict__)
    return dict(obj.__dict__)


def render_recursive(obj: Any, context: Any) -> Any:
    """
    递归地将对象中所有 str 类型内容进行变量渲染。

    Args:
        obj: str / dict / list / 强类型对象 / 其他
        context: 需具备 get_variable 或 render_string 等能力

    Returns:
        渲染后的对象（强类型对象会被展开为 dict 再递归）
    """
    if isinstance(obj, str):
        if obj.startswith("$") and len(obj) > 1 and " " not in obj:
            raw = _get_raw_variable_from_context(context, obj[1:])
            if raw is not None:
                return raw

        if obj.startswith("${") and obj.endswith("}") and "." not in obj and "(" not in obj:
            var_name = obj[2:-1].strip()
            raw = _get_raw_variable_from_context(context, var_name)
            if raw is not None:
                return raw

        if hasattr(context, "render_string"):
            return context.render_string(obj)
        return obj

    if isinstance(obj, dict):
        return {k: render_recursive(v, context) for k, v in obj.items()}
    if isinstance(obj, list):
        return [render_recursive(i, context) for i in obj]
    if hasattr(obj, "__dict__"):
        return render_recursive(_object_to_dict(obj), context)
    return obj


def get_config_value(config: Any, key: str, default: Any = None) -> Any:
    """兼容 dict 与带属性的配置对象。"""
    if config is None:
        return default
    if isinstance(config, dict):
        return config.get(key, default)
    if hasattr(config, key):
        return getattr(config, key, default)
    return default
