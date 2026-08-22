# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-10-08
@packageName src.core.processors.base
@className BaseProcessor
@describe 所有节点处理器的基类
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from src.engine.context import ExecutionContext
from src.engine.core.interfaces.processor_interface import ProcessorInterface
from src.engine.core.config_validator import config_validator, ValidationResult
from src.engine.core.simple_logger import logger
from src.engine.core.exceptions import (
    ValidationError, ExecutionError, ErrorContext, ErrorCategory,
    handle_errors, classify_error
)
from src.engine.core.error_manager import error_manager
from src.engine.models.configs import BaseConfig


class BaseProcessor(ProcessorInterface):
    """所有节点处理器的基类，定义通用接口。"""

    def __init__(self):
        """初始化处理器"""
        # 延迟初始化，避免在子类构造函数完成前调用
        self.config_schema_name = None
        self.required_config_keys = []
        self.optional_config_keys = []

    @abstractmethod
    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> Any:
        pass
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """配置验证：改为由各处理器自行校验，不再依赖集中式校验器执行路径"""
        try:
            # 仅执行子类特定的验证逻辑
            return self._validate_specific_config(config)
        except ValidationError:
            raise
        except Exception as e:
            context = ErrorContext(
                processor_type=self.__class__.__name__
            )
            raise ValidationError(
                message=f"配置验证异常: {str(e)}",
                context=context,
                original_error=e
            )
    
    def _validate_specific_config(self, config: Dict[str, Any]) -> bool:
        """子类特定的配置验证，子类可以重写"""
        return True
    
    def _get_config_schema_name(self) -> Optional[str]:
        """获取配置模式名称，子类可以重写"""
        return None
    
    def _get_required_config_keys(self) -> list:
        """获取必需配置键，子类可以重写"""
        # 如果还没有初始化，先初始化
        if not self.config_schema_name:
            self.config_schema_name = self._get_config_schema_name()
        
        if self.config_schema_name:
            schema_info = config_validator.get_schema_info(self.config_schema_name)
            if schema_info:
                return schema_info.get('required_fields', [])
        return []
    
    def _get_optional_config_keys(self) -> list:
        """获取可选配置键，子类可以重写"""
        # 如果还没有初始化，先初始化
        if not self.config_schema_name:
            self.config_schema_name = self._get_config_schema_name()
            
        if self.config_schema_name:
            schema_info = config_validator.get_schema_info(self.config_schema_name)
            if schema_info:
                return schema_info.get('optional_fields', [])
        return []
    
    def get_required_config_keys(self) -> list:
        """获取必需的配置键"""
        if not self.required_config_keys:
            self.required_config_keys = self._get_required_config_keys()
        return self.required_config_keys
    
    def get_optional_config_keys(self) -> list:
        """获取可选的配置键"""
        if not self.optional_config_keys:
            self.optional_config_keys = self._get_optional_config_keys()
        return self.optional_config_keys
    
    def get_config_info(self) -> Dict[str, Any]:
        """获取配置信息"""
        if self.config_schema_name:
            return config_validator.get_schema_info(self.config_schema_name)
        return {
            'name': self.__class__.__name__,
            'description': self.get_processor_description(),
            'required_fields': self.required_config_keys,
            'optional_fields': self.optional_config_keys
        }
    
    def execute_with_error_handling(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> Any:
        """带错误处理的执行方法"""
        try:
            # 验证配置
            config = node_info.get("data", {}).get("config", {})
            self.validate_config(config)
            
            # 执行处理器逻辑
            return self.execute(node_info, context, predecessor_results)
            
        except Exception as e:
            # 创建错误上下文
            error_context = ErrorContext(
                node_id=node_info.get('id'),
                processor_type=self.__class__.__name__,
                config=config,
                input_data=predecessor_results
            )
            
            # 分类错误
            if isinstance(e, ValidationError):
                raise e  # 验证错误直接抛出
            else:
                # 包装为执行错误
                execution_error = ExecutionError(
                    message=str(e),
                    operation=self.__class__.__name__,
                    context=error_context,
                    original_error=e,
                    retryable=True
                )
                
                # 处理错误
                error_result = error_manager.handle_error(execution_error, error_context)
                
                # 根据错误处理策略决定是否继续
                if error_result.get("continue", False):
                    logger.warning(f"[{self.__class__.__name__}] 错误已处理，继续执行: {execution_error.message}")
                    return None
                else:
                    raise execution_error

    def get_typed_config(self, node_info: dict) -> 'BaseConfig':
        """
        获取已归一化的强类型配置对象（若存在）
        返回 BaseConfig 子类实例或 None。
        """
        try:
            data = (node_info or {}).get('data') or {}
            cfg_obj = data.get('_config_obj')
            if isinstance(cfg_obj, BaseConfig):
                return cfg_obj
            return None
        except Exception:
            return None
