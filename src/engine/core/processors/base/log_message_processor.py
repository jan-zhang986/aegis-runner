# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName src.core.processors.base
@className LogMessageProcessor
@describe 日志消息处理器
"""

from src.engine.context import ExecutionContext
from src.engine.core.processors import BaseProcessor
from src.engine.core.simple_logger import logger
from src.engine.core.elegant_processor_registry import register_processor, ProcessorCategory
from src.engine.models.response import ResponseBuilder


@register_processor(
    processor_type="log_message",
    category=ProcessorCategory.CORE,
    description="日志消息处理器，用于记录和输出日志信息",
    tags={"log", "message", "core", "debug"},
    enabled=True,
    priority=70,
    version="1.0.0",
    author="Aegis Team"
)
class LogMessageProcessor(BaseProcessor):
    def __init__(self):
        super().__init__()
    
    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> dict:
        """
        执行日志输出，并返回标准化响应结构。
        
        返回结构示例：
        {
            "status": "success",
            "processor_type": "log_message",
            "body": {
                "message": "...",
                "node_id": "xxx"
            },
            "message": "日志记录成功"
        }
        """
        config = node_info.get("data", {}).get("config", {})
        message = context.render_string(config.get("message", ""))
        node_id = node_info.get("id")
        
        # 记录详细的日志消息信息
        message_details = f"""
================== Log Message Details ==================
message  : {message}
node_id  : {node_id}
=======================================================
"""
        logger.info(message_details)

        # 使用统一的 ProcessorResponse 格式（对外返回字典）
        return ResponseBuilder.success(
            processor_type="log_message",
            body={
                "message": message,
                "node_id": node_id,
            },
            message="日志记录成功"
        ).to_dict()