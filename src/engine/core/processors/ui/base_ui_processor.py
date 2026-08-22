# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName src.ui.processors
@className BaseUIProcessor
@describe UI处理器基类 - 实现统一的处理器接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from src.engine.core.interfaces.processor_interface import ProcessorInterface
from src.engine.core.simple_logger import logger


class BaseUIProcessor(ProcessorInterface):
    """
    UI处理器基类
    
    所有UI处理器都应该继承这个基类，确保统一的接口实现
    """
    
    def __init__(self):
        """初始化UI处理器"""
        self.processor_type = self.__class__.__name__.lower().replace('processor', '')
        self.supported_operations = []
        self.required_config_keys = []
        self.optional_config_keys = []
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        验证配置
        
        Args:
            config: 配置字典
            
        Returns:
            配置是否有效
        """
        try:
            # 检查必需的配置键
            for key in self.required_config_keys:
                if key not in config:
                    logger.error(f"[{self.get_processor_name()}] 缺少必需的配置: {key}")
                    return False
            
            # 执行子类的自定义验证
            return self._validate_ui_config(config)
            
        except Exception as e:
            logger.error(f"[{self.get_processor_name()}] 配置验证失败: {e}")
            return False
    
    @abstractmethod
    def _validate_ui_config(self, config: Dict[str, Any]) -> bool:
        """
        验证UI特定配置
        
        Args:
            config: 配置字典
            
        Returns:
            配置是否有效
        """
        pass
    
    def get_required_config_keys(self) -> list:
        """
        获取必需的配置键
        
        Returns:
            必需的配置键列表
        """
        return self.required_config_keys
    
    def get_optional_config_keys(self) -> list:
        """
        获取可选的配置键
        
        Returns:
            可选的配置键列表
        """
        return self.optional_config_keys
    
    def get_supported_node_types(self) -> list:
        """
        获取支持的节点类型
        
        Returns:
            支持的节点类型列表
        """
        return [f"ui_{self.processor_type}"]
    
    def get_supported_operations(self) -> list:
        """
        获取支持的操作类型
        
        Returns:
            支持的操作类型列表
        """
        return self.supported_operations
    
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
            # 基础验证
            if not super().pre_execute(node_info, context):
                return False
            
            # UI特定预处理
            return self._pre_execute_ui(node_info, context)
            
        except Exception as e:
            logger.error(f"[{self.get_processor_name()}] UI预处理失败: {e}")
            return False
    
    def _pre_execute_ui(self, node_info: Dict[str, Any], context: Any) -> bool:
        """
        UI特定预处理
        
        Args:
            node_info: 节点信息
            context: 执行上下文
            
        Returns:
            是否继续执行
        """
        # 子类可以重写此方法实现自定义预处理
        return True
    
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
        try:
            # 基础后处理
            result = super().post_execute(node_info, context, result)
            
            # UI特定后处理
            return self._post_execute_ui(node_info, context, result)
            
        except Exception as e:
            logger.error(f"[{self.get_processor_name()}] UI后处理失败: {e}")
            return result
    
    def _post_execute_ui(self, node_info: Dict[str, Any], context: Any, result: Any) -> Any:
        """
        UI特定后处理
        
        Args:
            node_info: 节点信息
            context: 执行上下文
            result: 执行结果
            
        Returns:
            处理后的结果
        """
        # 子类可以重写此方法实现自定义后处理
        return result
    
    def get_ui_context(self, context: Any):
        """
        获取UI上下文
        
        Args:
            context: 执行上下文
            
        Returns:
            执行上下文本身（已包含UI功能）
        """
        # 直接返回ExecutionContext，它已经包含了所有UI功能
        return context
    
    def log_ui_operation(self, operation: str, selector: str, success: bool = True, error: str = None):
        """
        记录UI操作日志
        
        Args:
            operation: 操作类型
            selector: 选择器
            success: 是否成功
            error: 错误信息
        """
        if success:
            logger.info(f"[{self.get_processor_name()}] UI操作成功: {operation} - {selector}")
        else:
            logger.error(f"[{self.get_processor_name()}] UI操作失败: {operation} - {selector} - {error}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        获取性能指标
        
        Returns:
            性能指标字典
        """
        metrics = super().get_performance_metrics()
        metrics.update({
            "supported_operations": self.supported_operations,
            "required_config_keys": self.required_config_keys,
            "optional_config_keys": self.optional_config_keys
        })
        return metrics
