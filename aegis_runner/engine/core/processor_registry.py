# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName src.core
@className ProcessorRegistry
@describe 统一的处理器注册中心
"""

from typing import Dict, Type, Any, Optional
from aegis_runner.engine.core.interfaces.processor_interface import ProcessorInterface
from aegis_runner.engine.core.simple_logger import logger
from aegis_runner.engine.core.elegant_processor_registry import ElegantProcessorRegistry


class ProcessorRegistry:
    """
    统一的处理器注册中心
    
    管理所有类型的处理器，包括：
    - 核心处理器（HTTP、脚本、条件等）
    - UI处理器（元素操作、截图、验证等）
    - 数据处理器（变量提取、断言等）
    """
    
    _processors: Dict[str, Type[ProcessorInterface]] = {}
    _instances: Dict[str, ProcessorInterface] = {}
    _initialized = False
    
    @classmethod
    def initialize(cls):
        """初始化处理器注册中心"""
        if cls._initialized:
            return
        
        logger.info("[ProcessorRegistry] 开始初始化处理器注册中心")
        
        # 使用优雅的处理器注册中心
        ElegantProcessorRegistry.initialize()
        
        # 同步处理器到当前注册中心
        cls._sync_from_elegant_registry()
        
        cls._initialized = True
        logger.info(f"[ProcessorRegistry] 处理器注册完成，共注册 {len(cls._processors)} 个处理器")
    
    @classmethod
    def _sync_from_elegant_registry(cls):
        """从优雅的处理器注册中心同步处理器"""
        try:
            # 直接访问优雅注册中心的处理器字典
            elegant_processors = ElegantProcessorRegistry._processors
            for processor_type, metadata in elegant_processors.items():
                cls._processors[processor_type] = metadata.processor_class
                logger.debug(f"[ProcessorRegistry] 同步处理器: {processor_type}")
        except Exception as e:
            logger.warning(f"[ProcessorRegistry] 同步处理器时出错: {e}")
    
    
    @classmethod
    def register_processor(cls, processor_type: str, processor_class: Type[ProcessorInterface]):
        """
        注册处理器
        
        Args:
            processor_type: 处理器类型
            processor_class: 处理器类
        """
        cls._processors[processor_type] = processor_class
        logger.debug(f"[ProcessorRegistry] 注册处理器: {processor_type} -> {processor_class.__name__}")
    
    @classmethod
    def get_processor(cls, processor_type: str) -> Optional[Type[ProcessorInterface]]:
        """
        获取处理器类
        
        Args:
            processor_type: 处理器类型
            
        Returns:
            处理器类
        """
        return cls._processors.get(processor_type)
    
    @classmethod
    def get_processor_instance(cls, processor_type: str) -> Optional[ProcessorInterface]:
        """
        获取处理器实例
        
        Args:
            processor_type: 处理器类型
            
        Returns:
            处理器实例
        """
        if processor_type not in cls._instances:
            processor_class = cls.get_processor(processor_type)
            if processor_class:
                cls._instances[processor_type] = processor_class()
        
        return cls._instances.get(processor_type)
    
    @classmethod
    def get_available_processors(cls) -> Dict[str, Any]:
        """
        获取所有可用的处理器
        
        Returns:
            可用处理器字典
        """
        return {
            processor_type: processor_class.__name__ 
            for processor_type, processor_class in cls._processors.items()
        }
    
    @classmethod
    def is_processor_available(cls, processor_type: str) -> bool:
        """
        检查处理器是否可用
        
        Args:
            processor_type: 处理器类型
            
        Returns:
            是否可用
        """
        return processor_type in cls._processors
    
    @classmethod
    def get_registry_summary(cls) -> Dict[str, Any]:
        """
        获取注册中心摘要信息
        
        Returns:
            注册中心摘要
        """
        return {
            "initialized": cls._initialized,
            "total_processors": len(cls._processors),
            "total_instances": len(cls._instances),
            "core_processors": len([p for p in cls._processors.keys() if not p.startswith('ui_') and not p.startswith('browser_')]),
            "ui_processors": len([p for p in cls._processors.keys() if p.startswith('ui_') or p.startswith('browser_')]),
            "data_processors": len([p for p in cls._processors.keys() if p in ['mysql', 'rocketmq', 'xxjob', 'dubbo']]),
            "available_processors": list(cls._processors.keys())
        }


# 创建全局实例
processor_registry = ProcessorRegistry()