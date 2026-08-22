# -*- coding: utf-8 -*-
"""
@author Jan
@date 2024-09-01
@packageName 
@className
@describe
"""
import json
from abc import ABC
from typing import Any

import requests

from aegis_runner.engine.context import ExecutionContext
from aegis_runner.engine.core.processors import BaseProcessor
from aegis_runner.engine.core.elegant_processor_registry import register_processor, ProcessorCategory


@register_processor(
    processor_type="xxjob",
    category=ProcessorCategory.DATA,
    description="XXL-Job任务调度处理器，支持任务触发和管理",
    tags={"xxljob", "scheduler", "job", "data"},
    enabled=True,
    priority=50,
    dependencies=["requests"],
    version="1.0.0",
    author="Aegis Team"
)
class XxlJobProcessor(BaseProcessor):
    def __init__(self):
        super().__init__()

    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> Any:

        pass
