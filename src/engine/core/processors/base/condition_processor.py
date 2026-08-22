
# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName src.core.processors.base
@className ConditionProcessor
@describe 条件判断处理器
"""

from typing import Any, Dict
from src.engine.context import ExecutionContext
from src.engine.core.processors import BaseProcessor, render_recursive
from src.engine.core.simple_logger import logger
from src.engine.core.elegant_processor_registry import register_processor, ProcessorCategory
from src.engine.core.safe_eval import safe_eval
from src.engine.models.response import ResponseBuilder


@register_processor(
    processor_type="condition",
    category=ProcessorCategory.CORE,
    description="条件判断处理器，支持复杂的条件逻辑",
    tags={"condition", "logic", "core", "control"},
    enabled=True,
    priority=85,
    version="1.0.0",
    author="Aegis Team"
)
class ConditionProcessor(BaseProcessor):
    def __init__(self):
        super().__init__()
    
    def _get_config_schema_name(self) -> str:
        """获取配置模式名称"""
        return "condition"
    
    def _validate_specific_config(self, config: Dict[str, Any]) -> bool:
        """条件特定的配置验证"""
        expression = config.get("expression", "")
        if not expression or not expression.strip():
            logger.error(f"[ConditionProcessor] 表达式不能为空")
            return False
        
        return True
    
    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> dict:
        """
        执行条件判断，返回标准化响应结构。
        
        返回结构示例：
        {
            "status": "success",
            "processor_type": "condition",
            "body": {
                "expression": "...",
                "result": true
            },
            "message": "条件评估成功"
        }
        """
        config = node_info.get("data", {}).get("config", {})
        
        # 全量递归渲染配置
        config = render_recursive(config, context)
        
        expression = config.get("expression", "False")

        logger.debug(f"[ConditionProcessor] 评估表达式: {expression}")
        
        # 使用安全的表达式求值器（替代危险的 eval）
        try:
            # 提供上下文变量供表达式使用
            names = {}
            if hasattr(context, 'get_variables'):
                # get_variables 是一个 @property，直接访问（不带括号）
                variables = context.get_variables
                # 确保是字典类型
                if isinstance(variables, dict):
                    names = variables.copy()
                else:
                    logger.warning(f"[ConditionProcessor] get_variables 返回的不是字典: {type(variables)}")
            
            logger.debug(f"[ConditionProcessor] 可用变量: {list(names.keys())}")  # 完整显示所有变量
            eval_result = safe_eval(expression, names)
            logger.debug(f"[ConditionProcessor] 表达式结果: {eval_result}")
            body = {
                "expression": expression,
                "result": bool(eval_result),
            }
            return ResponseBuilder.success(
                processor_type="condition",
                body=body,
                message="条件评估成功",
                status_code=200
            ).to_dict()
        except Exception as e:
            import traceback
            logger.error(f"[ConditionProcessor] 表达式求值失败: {expression}, 错误: {str(e)}\n堆栈:\n{traceback.format_exc()}")
            # 默认返回失败响应，但 result 置为 False，方便上游分支逻辑继续工作
            body = {
                "expression": expression,
                "result": False,
                "error": str(e),
            }
            return ResponseBuilder.error(
                processor_type="condition",
                error=f"条件评估失败: {str(e)}",
                error_code="CONDITION_EVAL_ERROR",
                status_code=500,
                body=body
            ).to_dict()

