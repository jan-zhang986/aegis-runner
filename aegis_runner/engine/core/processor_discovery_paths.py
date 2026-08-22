# -*- coding: utf-8 -*-
"""
处理器自动发现默认包路径（单一来源，供 workflow_engine / 注册中心共用）。
"""

from typing import Tuple

# 与 ElegantProcessorRegistry 默认 discovery 保持一致
DEFAULT_PROCESSOR_DISCOVERY_PACKAGES: Tuple[str, ...] = (
    "packages.engine.src.core.processors.base",
    "packages.engine.src.core.processors.ui",
    "packages.engine.src.core.processors.data",
    "packages.engine.src.core.processors.api",
    "packages.engine.src.core.processors.workflow",
    "packages.engine.src.core.processors.job",
)
