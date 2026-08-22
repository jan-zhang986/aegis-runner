# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName src.core
@className ProcessorFactory
@describe 处理器工厂 - 使用统一的处理器注册中心
"""

import importlib
from typing import Dict, Type, Any, Optional
from src.engine.core.elegant_processor_registry import elegant_processor_registry
from src.engine.core.interfaces.processor_interface import ProcessorInterface
from src.engine.core.simple_logger import logger

# 未注册时按类型尝试加载的模块路径（兜底，避免预加载失败导致常用类型不可用）
_PROCESSOR_MODULE_FALLBACK = {
    "http_request": "packages.engine.src.core.processors.api.http_processor",
}


class ProcessorFactory:
    """
    处理器工厂 - 使用统一的处理器注册中心
    
    这个类现在作为处理器注册中心的适配器，
    提供向后兼容的接口，同时利用新的统一注册系统。
    """
    
    # 已完全采用装饰器注册与优雅注册中心。
    
    @staticmethod
    def get_processor(node_type: str) -> ProcessorInterface:
        """
        获取处理器实例
        
        Args:
            node_type: 节点类型
            
        Returns:
            处理器实例
        """
        logger.debug(f"[ProcessorFactory] 获取处理器: {node_type}")
        
        # 从优雅注册中心获取
        if elegant_processor_registry.is_processor_available(node_type):
            processor_class = elegant_processor_registry.get_processor(node_type)
            if processor_class:
                logger.debug(f"[ProcessorFactory] 从优雅注册中心获取处理器: {node_type}")
                return processor_class()

        # 兜底：按类型尝试导入对应模块后再查一次（解决预加载/环境导致未注册）
        fallback_module = _PROCESSOR_MODULE_FALLBACK.get(node_type)
        if fallback_module:
            try:
                importlib.import_module(fallback_module)
                if elegant_processor_registry.is_processor_available(node_type):
                    processor_class = elegant_processor_registry.get_processor(node_type)
                    if processor_class:
                        logger.info(f"[ProcessorFactory] 通过兜底导入获取处理器: {node_type}")
                        return processor_class()
            except Exception as e:
                logger.debug(f"[ProcessorFactory] 兜底导入 {fallback_module} 失败: {e}")

        raise ValueError(f"不支持的节点类型: {node_type}")
    
    @staticmethod
    def get_available_processors() -> Dict[str, Any]:
        """
        获取所有可用的处理器
        
        Returns:
            可用处理器字典
        """
        logger.debug("[ProcessorFactory] 获取可用处理器")
        
        # 仅从优雅注册中心获取
        processors = elegant_processor_registry.get_available_processors()
        logger.debug(f"[ProcessorFactory] 找到 {len(processors)} 个可用处理器")
        return processors
    
    @staticmethod
    def is_processor_available(node_type: str) -> bool:
        """
        检查处理器是否可用
        
        Args:
            node_type: 节点类型
            
        Returns:
            是否可用
        """
        return elegant_processor_registry.is_processor_available(node_type)
    
    @staticmethod
    def get_factory_summary() -> Dict[str, Any]:
        """
        获取工厂摘要信息
        
        Returns:
            工厂摘要
        """
        return {
            "factory_type": "ProcessorFactory",
            "description": "处理器工厂 - 使用优雅装饰器注册中心",
            "registry_available": True,
            "registry_processors": len(elegant_processor_registry.get_available_processors()),
            "total_available": len(ProcessorFactory.get_available_processors())
        }