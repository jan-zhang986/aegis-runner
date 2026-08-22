# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName src.core
@className ElegantProcessorRegistry
@describe 优雅的处理器注册中心 - 整合装饰器、配置驱动和自动发现
"""

import inspect
import importlib
from typing import Dict, Type, Any, Optional, Set, List, Callable, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from aegis_runner.engine.core.interfaces.processor_interface import ProcessorInterface
from aegis_runner.engine.core.simple_logger import logger
from aegis_runner.engine.core.processor_config import ProcessorConfigManager, ProcessorConfig
from aegis_runner.engine.core.processor_discovery_paths import DEFAULT_PROCESSOR_DISCOVERY_PACKAGES
from aegis_runner.engine.core.processor_package_discovery import for_each_direct_submodule


class ProcessorCategory(Enum):
    """处理器分类枚举"""
    CORE = "core"
    API = "api"
    UI = "ui"
    DATA = "data"
    WORKFLOW = "workflow"
    CUSTOM = "custom"


@dataclass
class ProcessorMetadata:
    """处理器元数据"""
    processor_type: str
    processor_class: Type[ProcessorInterface]
    module_path: str
    category: ProcessorCategory
    description: str = ""
    tags: Set[str] = field(default_factory=set)
    enabled: bool = True
    priority: int = 0
    dependencies: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    author: str = ""
    created_at: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "processor_type": self.processor_type,
            "class_name": self.processor_class.__name__,
            "module_path": self.module_path,
            "category": self.category.value,
            "description": self.description,
            "tags": list(self.tags),
            "enabled": self.enabled,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "version": self.version,
            "author": self.author,
            "created_at": self.created_at
        }


class ElegantProcessorRegistry:
    """
    优雅的处理器注册中心
    
    特性：
    1. 装饰器自动注册
    2. 配置文件驱动
    3. 自动发现机制
    4. 类型安全
    5. 元数据管理
    6. 依赖管理
    7. 版本控制
    8. 热重载
    """
    
    _processors: Dict[str, ProcessorMetadata] = {}
    _instances: Dict[str, ProcessorInterface] = {}
    _initialized = False
    _discovery_paths: Set[str] = set()
    _config_manager: Optional[ProcessorConfigManager] = None
    
    @classmethod
    def initialize(cls, 
                   config_file: Optional[str] = None,
                   discovery_paths: Optional[List[str]] = None,
                   auto_discover: bool = True):
        """
        初始化处理器注册中心
        
        Args:
            config_file: 配置文件路径
            discovery_paths: 自动发现路径列表
            auto_discover: 是否启用自动发现
        """
        if cls._initialized:
            return
        
        logger.info("[ElegantProcessorRegistry] 开始初始化优雅的处理器注册中心")
        
        # 初始化配置管理器
        cls._config_manager = ProcessorConfigManager(config_file)
        
        # 设置发现路径
        if discovery_paths:
            cls._discovery_paths.update(discovery_paths)
        else:
            cls._discovery_paths.update(DEFAULT_PROCESSOR_DISCOVERY_PACKAGES)
        
        # 从配置文件注册处理器
        cls._register_from_config()
        
        # 自动发现和注册处理器
        if auto_discover:
            cls._auto_discover_processors()
        
        cls._initialized = True
        logger.info(f"[ElegantProcessorRegistry] 处理器注册完成，共注册 {len(cls._processors)} 个处理器")
    
    @classmethod
    def _register_from_config(cls):
        """从配置文件注册处理器"""
        if not cls._config_manager:
            return
        
        enabled_configs = cls._config_manager.get_enabled_processors()
        registered_count = 0
        skipped_count = 0
        
        for config in enabled_configs:
            try:
                # 检查是否已经通过装饰器注册
                if config.processor_type in cls._processors:
                    logger.debug(f"[ElegantProcessorRegistry] 处理器 {config.processor_type} 已通过装饰器注册，跳过配置文件注册")
                    skipped_count += 1
                    continue
                
                # 动态导入处理器类
                module = importlib.import_module(config.module_path)
                processor_class = getattr(module, config.class_name)
                
                # 再次检查（因为导入时可能触发装饰器注册）
                if config.processor_type in cls._processors:
                    logger.debug(f"[ElegantProcessorRegistry] 处理器 {config.processor_type} 在导入时已注册，跳过")
                    skipped_count += 1
                    continue
                
                # 创建元数据
                metadata = ProcessorMetadata(
                    processor_type=config.processor_type,
                    processor_class=processor_class,
                    module_path=config.module_path,
                    category=ProcessorCategory(config.category),
                    description=config.description,
                    tags=set(config.tags),
                    enabled=config.enabled,
                    priority=config.priority,
                    dependencies=config.dependencies
                )
                
                cls._register_processor_metadata(metadata)
                registered_count += 1
                logger.debug(f"[ElegantProcessorRegistry] 从配置注册处理器: {config.processor_type}")
                
            except Exception as e:
                logger.debug(f"[ElegantProcessorRegistry] 从配置注册处理器失败: {config.processor_type}, 错误: {e}")
        
        if registered_count > 0:
            logger.info(f"[ElegantProcessorRegistry] 从配置注册了 {registered_count} 个处理器")
        if skipped_count > 0:
            logger.debug(f"[ElegantProcessorRegistry] 跳过了 {skipped_count} 个已注册的处理器")
    
    @classmethod
    def _auto_discover_processors(cls):
        """自动发现处理器"""
        for discovery_path in cls._discovery_paths:
            try:
                cls._discover_in_package(discovery_path)
            except Exception as e:
                logger.warning(f"[ElegantProcessorRegistry] 发现路径失败: {discovery_path}, 错误: {e}")
    
    @classmethod
    def _discover_in_package(cls, package_path: str):
        """在指定包中发现处理器"""

        def _visit(module, module_name: str) -> None:
            cls._scan_module_for_processors(module, module_name)

        for_each_direct_submodule(
            package_path,
            _visit,
            log_tag="[ElegantProcessorRegistry]",
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
                logger.debug(f"[ElegantProcessorRegistry] 自动发现处理器: {metadata.processor_type}")
    
    @classmethod
    def register_processor(cls, 
                          processor_type: str,
                          category: Union[ProcessorCategory, str] = ProcessorCategory.CUSTOM,
                          description: str = "",
                          tags: Optional[Set[str]] = None,
                          enabled: bool = True,
                          priority: int = 0,
                          dependencies: Optional[List[str]] = None,
                          version: str = "1.0.0",
                          author: str = ""):
        """
        处理器注册装饰器
        
        Args:
            processor_type: 处理器类型标识
            category: 处理器分类
            description: 处理器描述
            tags: 处理器标签
            enabled: 是否启用
            priority: 优先级
            dependencies: 依赖列表
            version: 版本号
            author: 作者
        """
        def decorator(processor_class: Type[ProcessorInterface]) -> Type[ProcessorInterface]:
            if not issubclass(processor_class, ProcessorInterface):
                raise ValueError(f"处理器类 {processor_class.__name__} 必须继承自 ProcessorInterface")
            
            # 处理分类参数
            processed_category = category
            if isinstance(processed_category, str):
                try:
                    processed_category = ProcessorCategory(processed_category)
                except ValueError:
                    processed_category = ProcessorCategory.CUSTOM
            
            metadata = ProcessorMetadata(
                processor_type=processor_type,
                processor_class=processor_class,
                module_path="",  # 将在扫描时设置
                category=processed_category,
                description=description,
                tags=tags or set(),
                enabled=enabled,
                priority=priority,
                dependencies=dependencies or [],
                version=version,
                author=author
            )
            
            # 将元数据附加到类上
            processor_class._processor_metadata = metadata
            
            # 立即注册处理器（无论注册中心是否已初始化）
            cls._register_processor_metadata(metadata)
            
            return processor_class
        
        return decorator
    
    @classmethod
    def _register_processor_metadata(cls, metadata: ProcessorMetadata):
        """注册处理器元数据"""
        if metadata.processor_type in cls._processors:
            existing = cls._processors[metadata.processor_type]
            # 如果是同一个类，静默跳过（避免重复注册警告）
            if existing.processor_class == metadata.processor_class:
                logger.debug(f"[ElegantProcessorRegistry] 处理器 {metadata.processor_type} 已注册，跳过")
                return
            # 如果是不同的类，才发出警告
            logger.warning(
                f"[ElegantProcessorRegistry] 处理器类型 {metadata.processor_type} 已存在 "
                f"({existing.processor_class.__name__})，将被覆盖为 {metadata.processor_class.__name__}"
            )
        
        cls._processors[metadata.processor_type] = metadata
        logger.debug(f"[ElegantProcessorRegistry] 注册处理器: {metadata.processor_type} -> {metadata.processor_class.__name__}")
    
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
    def get_processors_by_category(cls, category: Union[ProcessorCategory, str]) -> List[ProcessorMetadata]:
        """根据分类获取处理器"""
        if isinstance(category, str):
            try:
                category = ProcessorCategory(category)
            except ValueError:
                return []
        
        return [metadata for metadata in cls._processors.values() if metadata.category == category]
    
    @classmethod
    def get_processors_by_tag(cls, tag: str) -> List[ProcessorMetadata]:
        """根据标签获取处理器"""
        return [metadata for metadata in cls._processors.values() if tag in metadata.tags]
    
    @classmethod
    def get_enabled_processors(cls) -> List[ProcessorMetadata]:
        """获取启用的处理器"""
        return [metadata for metadata in cls._processors.values() if metadata.enabled]
    
    @classmethod
    def get_processors_by_priority(cls) -> List[ProcessorMetadata]:
        """按优先级获取处理器"""
        return sorted(cls._processors.values(), key=lambda x: x.priority, reverse=True)
    
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
            processor_type: metadata.to_dict()
            for processor_type, metadata in cls._processors.items()
        }
    
    @classmethod
    def is_processor_available(cls, processor_type: str) -> bool:
        """检查处理器是否可用"""
        metadata = cls._processors.get(processor_type)
        return metadata is not None and metadata.enabled
    
    @classmethod
    def enable_processor(cls, processor_type: str) -> bool:
        """启用处理器"""
        metadata = cls._processors.get(processor_type)
        if metadata:
            metadata.enabled = True
            logger.info(f"[ElegantProcessorRegistry] 启用处理器: {processor_type}")
            return True
        return False
    
    @classmethod
    def disable_processor(cls, processor_type: str) -> bool:
        """禁用处理器"""
        metadata = cls._processors.get(processor_type)
        if metadata:
            metadata.enabled = False
            logger.info(f"[ElegantProcessorRegistry] 禁用处理器: {processor_type}")
            return True
        return False
    
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
            
            logger.info(f"[ElegantProcessorRegistry] 重新加载处理器: {processor_type}")
            return True
            
        except Exception as e:
            logger.error(f"[ElegantProcessorRegistry] 重新加载处理器失败: {processor_type}, 错误: {e}")
            return False
    
    @classmethod
    def get_registry_summary(cls) -> Dict[str, Any]:
        """获取注册中心摘要信息"""
        categories = {}
        enabled_count = 0
        
        for metadata in cls._processors.values():
            category_name = metadata.category.value
            categories[category_name] = categories.get(category_name, 0) + 1
            if metadata.enabled:
                enabled_count += 1
        
        return {
            "initialized": cls._initialized,
            "total_processors": len(cls._processors),
            "enabled_processors": enabled_count,
            "disabled_processors": len(cls._processors) - enabled_count,
            "total_instances": len(cls._instances),
            "categories": categories,
            "discovery_paths": list(cls._discovery_paths),
            "available_processors": list(cls._processors.keys())
        }


# 创建全局实例
elegant_processor_registry = ElegantProcessorRegistry()

# 便捷的装饰器函数
def register_processor(processor_type: str, 
                     category: Union[ProcessorCategory, str] = ProcessorCategory.CUSTOM,
                     description: str = "",
                     tags: Optional[Set[str]] = None,
                     enabled: bool = True,
                     priority: int = 0,
                     dependencies: Optional[List[str]] = None,
                     version: str = "1.0.0",
                     author: str = ""):
    """便捷的处理器注册装饰器"""
    return elegant_processor_registry.register_processor(
        processor_type, category, description, tags, enabled, 
        priority, dependencies, version, author
    )
