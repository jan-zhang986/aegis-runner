# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-10-13
@packageName src.core.interfaces
@className ProcessorInterface
@describe 处理器统一接口定义
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from aegis_runner.engine.core.simple_logger import logger


class ProcessorInterface(ABC):
    """
    处理器统一接口
    
    所有处理器都必须实现这个接口，确保一致性和可扩展性
    """
    
    @abstractmethod
    def execute(self, node_info: Dict[str, Any], context: Any, predecessor_results: Dict[str, Any]) -> Any:
        """
        执行处理器逻辑
        
        Args:
            node_info: 节点信息，包含配置数据
            context: 执行上下文
            predecessor_results: 前置节点结果
            
        Returns:
            处理结果
            
        Raises:
            Exception: 处理过程中的任何异常
        """
        pass
    
    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        验证配置
        
        Args:
            config: 配置字典
            
        Returns:
            配置是否有效
            
        Raises:
            ValueError: 配置无效时抛出
        """
        pass
    
    def get_processor_type(self) -> str:
        """
        获取处理器类型
        
        Returns:
            处理器类型名称
        """
        class_name = self.__class__.__name__
        # 移除常见的后缀
        if class_name.endswith('Processor'):
            return class_name[:-9].lower()
        return class_name.lower()
    
    def get_processor_name(self) -> str:
        """
        获取处理器名称
        
        Returns:
            处理器显示名称
        """
        return self.__class__.__name__
    
    def get_processor_description(self) -> str:
        """
        获取处理器描述
        
        Returns:
            处理器功能描述
        """
        return self.__class__.__doc__ or "无描述信息"
    
    def is_async(self) -> bool:
        """
        检查处理器是否支持异步执行
        
        Returns:
            是否支持异步
        """
        return False
    
    def get_required_config_keys(self) -> list:
        """
        获取必需的配置键
        
        Returns:
            必需的配置键列表
        """
        return []
    
    def get_optional_config_keys(self) -> list:
        """
        获取可选的配置键
        
        Returns:
            可选的配置键列表
        """
        return []
    
    def get_supported_node_types(self) -> list:
        """
        获取支持的节点类型
        
        Returns:
            支持的节点类型列表
        """
        return [self.get_processor_type()]
    
    def pre_execute(self, node_info: Dict[str, Any], context: Any) -> bool:
        """
        执行前预处理
        
        Args:
            node_info: 节点信息
            context: 执行上下文
            
        Returns:
            是否继续执行
        """
        try:
            config = node_info.get("data", {}).get("config", {})
            return self.validate_config(config)
        except Exception as e:
            logger.error(f"[{self.get_processor_name()}] 预处理失败: {e}")
            return False
    
    def post_execute(self, node_info: Dict[str, Any], context: Any, result: Any) -> Any:
        """
        执行后后处理
        
        Args:
            node_info: 节点信息
            context: 执行上下文
            result: 执行结果
            
        Returns:
            处理后的结果
        """
        return result
    
    def get_error_message(self, error: Exception) -> str:
        """
        获取格式化的错误消息
        
        Args:
            error: 异常对象
            
        Returns:
            格式化的错误消息
        """
        return f"[{self.get_processor_name()}] 执行失败: {str(error)}"
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        获取性能指标
        
        Returns:
            性能指标字典
        """
        return {
            "processor_type": self.get_processor_type(),
            "processor_name": self.get_processor_name(),
            "is_async": self.is_async(),
            "supported_types": self.get_supported_node_types()
        }
