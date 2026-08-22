# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName src.core
@className ProcessorRegistryV2
@describe 优雅的处理器注册中心 - 使用装饰器和自动发现机制
"""

import inspect
import importlib
from typing import Dict, Type, Any, Optional, Set, List, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.engine.core.interfaces.processor_interface import ProcessorInterface
from src.engine.core.simple_logger import logger
from src.engine.core.processor_discovery_paths import DEFAULT_PROCESSOR_DISCOVERY_PACKAGES
from src.engine.core.processor_package_discovery import for_each_direct_submodule


@dataclass
class ProcessorMetadata:
    """处理器元数据"""
    processor_type: str
    processor_class: Type[ProcessorInterface]
    module_path: str
    category: str
    description: str = ""
    tags: Set[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = set()


class ProcessorRegistryV2:
    """
    优雅的处理器注册中心 V2
    
    特性：
    - 装饰器自动注册
    - 插件自动发现
    - 类型安全
    - 配置驱动
    - 元数据管理
    """
    
    _processors: Dict[str, ProcessorMetadata] = {}
    _instances: Dict[str, ProcessorInterface] = {}
    _initialized = False
    _discovery_paths: Set[str] = set()
    
    @classmethod
    def initialize(cls, discovery_paths: Optional[List[str]] = None):
        """
        初始化处理器注册中心
        
        Args:
            discovery_paths: 自动发现路径列表
        """
        if cls._initialized:
            return
        
        logger.info("[ProcessorRegistryV2] 开始初始化优雅的处理器注册中心")
        
        # 设置发现路径
        if discovery_paths:
            cls._discovery_paths.update(discovery_paths)
        else:
            cls._discovery_paths.update(DEFAULT_PROCESSOR_DISCOVERY_PACKAGES)
        
        # 自动发现和注册处理器
        cls._auto_discover_processors()
        
        cls._initialized = True
        logger.info(f"[ProcessorRegistryV2] 处理器注册完成，共注册 {len(cls._processors)} 个处理器")
    
    @classmethod
    def _auto_discover_processors(cls):
        """自动发现处理器"""
        for discovery_path in cls._discovery_paths:
            try:
                cls._discover_in_package(discovery_path)
            except Exception as e:
                logger.warning(f"[ProcessorRegistryV2] 发现路径失败: {discovery_path}, 错误: {e}")
    
    @classmethod
    def _discover_in_package(cls, package_path: str):
        """在指定包中发现处理器"""

        def _visit(module, module_name: str) -> None:
            cls._scan_module_for_processors(module, module_name)

        for_each_direct_submodule(
            package_path,
            _visit,
            log_tag="[ProcessorRegistryV2]",
            module_import_error_level="debug",
        )
    
    @classmethod
    def _scan_module_for_processors(cls, module, module_name: str):
        """扫描模块中的处理器"""
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, ProcessorInterface) and 
                obj != ProcessorInterface and
                hasattr(obj, '_processor_metadata')):
                
                metadata = obj._processor_metadata
                metadata.module_path = module_name
                cls._register_processor_metadata(metadata)
                logger.debug(f"[ProcessorRegistryV2] 自动发现处理器: {metadata.processor_type}")
    
    @classmethod
    def register_processor(cls, 
                          processor_type: str,
                          category: str = "general",
                          description: str = "",
                          tags: Optional[Set[str]] = None):
        """
        处理器注册装饰器
        
        Args:
            processor_type: 处理器类型标识
            category: 处理器分类
            description: 处理器描述
            tags: 处理器标签
        """
        def decorator(processor_class: Type[ProcessorInterface]) -> Type[ProcessorInterface]:
            if not issubclass(processor_class, ProcessorInterface):
                raise ValueError(f"处理器类 {processor_class.__name__} 必须继承自 ProcessorInterface")
            
            metadata = ProcessorMetadata(
                processor_type=processor_type,
                processor_class=processor_class,
                module_path="",  # 将在扫描时设置
                category=category,
                description=description,
                tags=tags or set()
            )
            
            # 将元数据附加到类上
            processor_class._processor_metadata = metadata
            
            # 如果注册中心已初始化，立即注册
            if cls._initialized:
                cls._register_processor_metadata(metadata)
            
            return processor_class
        
        return decorator
    
    @classmethod
    def _register_processor_metadata(cls, metadata: ProcessorMetadata):
        """注册处理器元数据"""
        if metadata.processor_type in cls._processors:
            logger.warning(f"[ProcessorRegistryV2] 处理器类型 {metadata.processor_type} 已存在，将被覆盖")
        
        cls._processors[metadata.processor_type] = metadata
        logger.debug(f"[ProcessorRegistryV2] 注册处理器: {metadata.processor_type} -> {metadata.processor_class.__name__}")
    
    @classmethod
    def get_processor(cls, processor_type: str) -> Optional[Type[ProcessorInterface]]:
        """获取处理器类"""
        metadata = cls._processors.get(processor_type)
        return metadata.processor_class if metadata else None
    
    @classmethod
    def get_processor_instance(cls, processor_type: str) -> Optional[ProcessorInterface]:
        """获取处理器实例"""
        if processor_type not in cls._instances:
            processor_class = cls.get_processor(processor_type)
            if processor_class:
                cls._instances[processor_type] = processor_class()
        
        return cls._instances.get(processor_type)
    
    @classmethod
    def get_processor_metadata(cls, processor_type: str) -> Optional[ProcessorMetadata]:
        """获取处理器元数据"""
        return cls._processors.get(processor_type)
    
    @classmethod
    def get_processors_by_category(cls, category: str) -> List[ProcessorMetadata]:
        """根据分类获取处理器"""
        return [metadata for metadata in cls._processors.values() if metadata.category == category]
    
    @classmethod
    def get_processors_by_tag(cls, tag: str) -> List[ProcessorMetadata]:
        """根据标签获取处理器"""
        return [metadata for metadata in cls._processors.values() if tag in metadata.tags]
    
    @classmethod
    def search_processors(cls, query: str) -> List[ProcessorMetadata]:
        """搜索处理器"""
        query_lower = query.lower()
        results = []
        
        for metadata in cls._processors.values():
            if (query_lower in metadata.processor_type.lower() or
                query_lower in metadata.description.lower() or
                query_lower in metadata.processor_class.__name__.lower() or
                any(query_lower in tag.lower() for tag in metadata.tags)):
                results.append(metadata)
        
        return results
    
    @classmethod
    def get_available_processors(cls) -> Dict[str, Any]:
        """获取所有可用的处理器"""
        return {
            processor_type: {
                "class_name": metadata.processor_class.__name__,
                "category": metadata.category,
                "description": metadata.description,
                "tags": list(metadata.tags),
                "module_path": metadata.module_path
            }
            for processor_type, metadata in cls._processors.items()
        }
    
    @classmethod
    def is_processor_available(cls, processor_type: str) -> bool:
        """检查处理器是否可用"""
        return processor_type in cls._processors
    
    @classmethod
    def get_registry_summary(cls) -> Dict[str, Any]:
        """获取注册中心摘要信息"""
        categories = {}
        for metadata in cls._processors.values():
            categories[metadata.category] = categories.get(metadata.category, 0) + 1
        
        return {
            "initialized": cls._initialized,
            "total_processors": len(cls._processors),
            "total_instances": len(cls._instances),
            "categories": categories,
            "discovery_paths": list(cls._discovery_paths),
            "available_processors": list(cls._processors.keys())
        }
    
    @classmethod
    def reload_processor(cls, processor_type: str) -> bool:
        """重新加载处理器"""
        metadata = cls._processors.get(processor_type)
        if not metadata:
            return False
        
        try:
            # 重新导入模块
            module = importlib.reload(importlib.import_module(metadata.module_path))
            processor_class = getattr(module, metadata.processor_class.__name__)
            
            # 更新处理器类
            metadata.processor_class = processor_class
            
            # 清除实例缓存
            if processor_type in cls._instances:
                del cls._instances[processor_type]
            
            logger.info(f"[ProcessorRegistryV2] 重新加载处理器: {processor_type}")
            return True
            
        except Exception as e:
            logger.error(f"[ProcessorRegistryV2] 重新加载处理器失败: {processor_type}, 错误: {e}")
            return False


# 创建全局实例
processor_registry_v2 = ProcessorRegistryV2()

# 便捷的装饰器函数
def register_processor(processor_type: str, 
                     category: str = "general",
                     description: str = "",
                     tags: Optional[Set[str]] = None):
    """便捷的处理器注册装饰器"""
    return processor_registry_v2.register_processor(
        processor_type, category, description, tags
    )
