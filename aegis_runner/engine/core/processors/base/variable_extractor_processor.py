# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-10-13
@packageName src.core.processors.base
@className VariableExtractorProcessor
@describe 变量提取处理器
"""

import json
import jmespath
from jmespath import functions

try:
    from jmespath.exceptions import JMESPathError as _JMESPathError
except Exception:
    class _JMESPathError(Exception):
        pass
from typing import Dict, Any
from aegis_runner.engine.context import ExecutionContext
from aegis_runner.engine.core.processors import BaseProcessor, render_recursive
from aegis_runner.engine.core.simple_logger import logger
from aegis_runner.engine.core.elegant_processor_registry import register_processor, ProcessorCategory

class JMESPathCustomFunctions(functions.Functions):

    # 2. 使用装饰器定义函数接收的参数类型为 string
    @functions.signature({'types': ['string']})
    def _func_parse_json(self, json_string):
        """定义一个名为 parse_json 的 JMESPath 函数"""
        try:
            return json.loads(json_string)
        except (TypeError, ValueError):
            return None  # 如果解析失败返回 None


options = jmespath.Options(custom_functions=JMESPathCustomFunctions())


@register_processor(
    processor_type="variable_extractor",
    category=ProcessorCategory.CORE,
    description="变量提取处理器，使用JMESPath语法从数据中提取变量",
    tags={"variable", "extract", "jmespath", "data"},
    enabled=True,
    priority=75,
    version="1.0.0",
    author="Jan"
)
class VariableExtractorProcessor(BaseProcessor):
    """变量提取器，使用JMESPath语法"""
    
    def __init__(self):
        super().__init__()
    
    def _get_config_schema_name(self) -> str:
        """获取配置模式名称"""
        return "variable_extractor"
    
    def _validate_specific_config(self, config: Dict[str, Any]) -> bool:
        """变量提取特定的配置验证"""
        extractions = config.get("extractions", [])
        if not extractions:
            logger.error(f"[VariableExtractorProcessor] extractions不能为空")
            return False
        
        if not isinstance(extractions, list):
            logger.error(f"[VariableExtractorProcessor] extractions必须是列表类型")
            return False
        
        # 验证每个提取规则
        for i, extraction in enumerate(extractions):
            if not isinstance(extraction, dict):
                logger.error(f"[VariableExtractorProcessor] 提取规则 {i+1} 必须是字典类型")
                return False
            
            if "source_path" not in extraction:
                logger.error(f"[VariableExtractorProcessor] 提取规则 {i+1} 缺少 source_path")
                return False
            
            if "var_name" not in extraction:
                logger.error(f"[VariableExtractorProcessor] 提取规则 {i+1} 缺少 var_name")
                return False
        
        return True
    
    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> dict:
        """
        执行变量提取
        
        Args:
            node_info: 节点配置信息
            context: 执行上下文
            predecessor_results: 前置节点结果
            
        Returns:
            Dict: 提取的变量
        """
        error_msg = None
        status = "SUCCESS"
        logger.info(f"开始执行变量提取 - 节点: {node_info.get('id')}")
        
        # 获取输入数据
        input_data = list(predecessor_results.values())[0]
        
        # 优先 VariableExtractorConfig
        config_obj = self.get_typed_config(node_info)
        config = None
        if config_obj:
            config = config_obj
        else:
            config = node_info.get("data", {}).get("config", {})
        
        # 全量递归渲染配置
        config = render_recursive(config, context)
        
        extractions = getattr(config, 'extractions', None) if hasattr(config, 'extractions') else config.get('extractions', [])

        extracted_vars = {}
        
        for i, item in enumerate(extractions):
            # 如果 ExtractionRule 对象（强类型）
            if hasattr(item, 'source_path') or hasattr(item, 'var_name'):
                jmespath_query = getattr(item, 'source_path', None) or getattr(item, 'jmespath_query', None) or getattr(item, 'path', None)
                var_name = getattr(item, 'var_name', None) or getattr(item, 'name', None)
                default_value = getattr(item, 'default_value', None) if hasattr(item, 'default_value') else getattr(item, 'default', None)
            else:  # dict
                jmespath_query = item.get("source_path") or item.get("jmespath_query") or item.get("path")
                var_name = item.get("var_name") or item.get("name")
                default_value = item.get("default_value") if item.get("default_value") is not None else item.get("default")
            
            if not jmespath_query:
                logger.error(f"JMESPath查询表达式不能为空 - 节点: {node_info.get('id')}")
                raise ValueError("JMESPath查询表达式不能为空")
            if not var_name:
                logger.error(f"变量名不能为空 - 节点: {node_info.get('id')}")
                raise ValueError("变量名不能为空")
            
            try:
                # 使用JMESPath查询
                # logger.info(input_data)
                value = jmespath.search(jmespath_query, input_data,options=options)
                
                # 处理查询结果
                if value is None:
                    if default_value is not None:
                        value = default_value
                    else:
                        logger.error(f"JMESPath查询 '{jmespath_query}' 未找到匹配结果 - 节点: {node_info.get('id')}")
                        raise ValueError(f"JMESPath查询 '{jmespath_query}' 未找到匹配结果")
                
                # 设置变量到上下文
                context.set_variable(var_name, value)
                extracted_vars[var_name] = value
                
            except _JMESPathError as e:
                error_msg = f"JMESPath查询语法错误: {str(e)}"
                status = "FAILED"
                raise ValueError(error_msg)
            except Exception as e:
                error_msg = f"变量提取失败: {str(e)}"
                status = "FAILED"

                raise ValueError(error_msg)
            finally:
        
                # 记录详细的变量提取信息
                extraction_details = f"""
================== Variable Extraction Details =========================================
Global variable:{context.get_variables}
input_data: {json.dumps(input_data, indent=4, ensure_ascii=False)}
extractions: {json.dumps([self._as_dict_safe(x) for x in extractions], indent=4, ensure_ascii=False)}
extracted_vars: {json.dumps(extracted_vars, indent=4, ensure_ascii=False)}
variables_count: {len(extracted_vars)}
node_id: {node_info.get('id')}
ERROR: {error_msg}
============================Variable Extraction {status}=================================
        """
                logger.info(extraction_details)

        return extracted_vars
    def _as_dict_safe(self, x):
        try:
            return x.to_dict() if hasattr(x, 'to_dict') else dict(x)
        except Exception:
            return str(x)