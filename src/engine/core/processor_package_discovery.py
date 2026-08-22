# -*- coding: utf-8 -*-
"""
处理器包内直属子模块的导入与遍历（workflow_engine 预加载与注册中心自动发现共用）。
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from types import ModuleType
from typing import Callable, Iterable, Literal, Optional

from src.engine.core.simple_logger import logger


def for_each_direct_submodule(
    package_path: str,
    visitor: Optional[Callable[[ModuleType, str], None]],
    *,
    log_tag: str,
    module_import_error_level: Literal["debug", "warning"] = "debug",
) -> None:
    """
    导入 package_path，遍历其目录下直属的非包子模块并 import_module；
    成功时调用 visitor(module, module_name)；失败按级别打日志（与原先各调用方一致）。
    """
    try:
        package = importlib.import_module(package_path)
        pfile = getattr(package, "__file__", None)
        if not pfile:
            raise ImportError(f"包 {package_path} 无 __file__，无法枚举子模块")
        package_dir = Path(pfile).parent
    except Exception as e:
        logger.warning(f"{log_tag} 发现包失败: {package_path}, 错误: {e}")
        return

    for _finder, name, ispkg in pkgutil.iter_modules([str(package_dir)]):
        if ispkg:
            continue
        module_name = f"{package_path}.{name}"
        try:
            module = importlib.import_module(module_name)
            if visitor is not None:
                visitor(module, module_name)
        except Exception as e:
            if module_import_error_level == "warning":
                logger.warning(
                    f"{log_tag} 预加载处理器模块 {module_name} 失败: {e}，该类型可能不可用"
                )
            else:
                logger.debug(f"{log_tag} 扫描模块失败: {module_name}, 错误: {e}")


def preload_processor_packages(package_paths: Iterable[str], *, log_tag: str) -> None:
    """仅做 import 副作用，用于在 registry initialize 之前触发装饰器注册。"""
    for package_path in package_paths:
        for_each_direct_submodule(
            package_path,
            None,
            log_tag=log_tag,
            module_import_error_level="warning",
        )
