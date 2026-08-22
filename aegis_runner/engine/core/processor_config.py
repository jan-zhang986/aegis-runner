# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName src.core
@className ProcessorConfig
@describe 处理器配置管理 - 支持YAML/JSON配置文件
"""

import json
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict

from aegis_runner.engine.core.simple_logger import logger


@dataclass
class ProcessorConfig:
    """处理器配置"""
    processor_type: str
    module_path: str
    class_name: str
    category: str
    description: str = ""
    tags: List[str] = None
    enabled: bool = True
    priority: int = 0
    dependencies: List[str] = None
    version: str = "1.0.0"
    author: str = ""
    created_at: str = ""
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.dependencies is None:
            self.dependencies = []


class ProcessorConfigManager:
    """处理器配置管理器"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or "processor_config.yaml"
        self.configs: Dict[str, ProcessorConfig] = {}
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        config_path = Path(self.config_file)
        
        if not config_path.exists():
            logger.warning(f"[ProcessorConfigManager] 配置文件不存在: {self.config_file}")
            self._create_default_config()
            return
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                if config_path.suffix.lower() in ['.yaml', '.yml']:
                    data = yaml.safe_load(f)
                elif config_path.suffix.lower() == '.json':
                    data = json.load(f)
                else:
                    logger.error(f"[ProcessorConfigManager] 不支持的配置文件格式: {config_path.suffix}")
                    return
            
            self._parse_config_data(data)
            logger.info(f"[ProcessorConfigManager] 成功加载 {len(self.configs)} 个处理器配置")
            
        except Exception as e:
            logger.error(f"[ProcessorConfigManager] 加载配置文件失败: {e}")
            self._create_default_config()
    
    def _parse_config_data(self, data: Dict[str, Any]):
        """解析配置数据"""
        processors = data.get('processors', [])
        
        for proc_data in processors:
            try:
                config = ProcessorConfig(**proc_data)
                self.configs[config.processor_type] = config
            except Exception as e:
                logger.warning(f"[ProcessorConfigManager] 解析处理器配置失败: {proc_data}, 错误: {e}")
    
    def _create_default_config(self):
        """创建默认配置文件"""
        default_config = {
            "processors": [
                {
                    "processor_type": "http_request",
                    "module_path": "packages.engine.src.core.processors.api.http_processor",
                    "class_name": "HttpProcessor",
                    "category": "api",
                    "description": "HTTP请求处理器",
                    "tags": ["http", "api", "network"],
                    "enabled": True,
                    "priority": 100,
                    "dependencies": []
                },
                {
                    "processor_type": "script",
                    "module_path": "packages.engine.src.core.processors.base.script_processor",
                    "class_name": "ScriptProcessor",
                    "category": "core",
                    "description": "脚本执行处理器",
                    "tags": ["script", "execution", "core"],
                    "enabled": True,
                    "priority": 90,
                    "dependencies": []
                },
                {
                    "processor_type": "ui_element",
                    "module_path": "packages.engine.src.core.processors.ui.element_processor",
                    "class_name": "ElementProcessor",
                    "category": "ui",
                    "description": "UI元素操作处理器",
                    "tags": ["ui", "element", "interaction"],
                    "enabled": True,
                    "priority": 80,
                    "dependencies": []
                }
            ]
        }
        
        try:
            config_path = Path(self.config_file)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                if config_path.suffix.lower() in ['.yaml', '.yml']:
                    yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
                else:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[ProcessorConfigManager] 创建默认配置文件: {self.config_file}")
            
        except Exception as e:
            logger.error(f"[ProcessorConfigManager] 创建默认配置文件失败: {e}")
    
    def get_processor_config(self, processor_type: str) -> Optional[ProcessorConfig]:
        """获取处理器配置"""
        return self.configs.get(processor_type)
    
    def get_processors_by_category(self, category: str) -> List[ProcessorConfig]:
        """根据分类获取处理器配置"""
        return [config for config in self.configs.values() if config.category == category]
    
    def get_enabled_processors(self) -> List[ProcessorConfig]:
        """获取启用的处理器配置"""
        return [config for config in self.configs.values() if config.enabled]
    
    def get_processors_by_priority(self) -> List[ProcessorConfig]:
        """按优先级获取处理器配置"""
        return sorted(self.configs.values(), key=lambda x: x.priority, reverse=True)
    
    def add_processor_config(self, config: ProcessorConfig):
        """添加处理器配置"""
        self.configs[config.processor_type] = config
        logger.info(f"[ProcessorConfigManager] 添加处理器配置: {config.processor_type}")
    
    def remove_processor_config(self, processor_type: str) -> bool:
        """移除处理器配置"""
        if processor_type in self.configs:
            del self.configs[processor_type]
            logger.info(f"[ProcessorConfigManager] 移除处理器配置: {processor_type}")
            return True
        return False
    
    def save_config(self):
        """保存配置到文件"""
        try:
            config_data = {
                "processors": [asdict(config) for config in self.configs.values()]
            }
            
            config_path = Path(self.config_file)
            with open(config_path, 'w', encoding='utf-8') as f:
                if config_path.suffix.lower() in ['.yaml', '.yml']:
                    yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
                else:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[ProcessorConfigManager] 配置已保存到: {self.config_file}")
            
        except Exception as e:
            logger.error(f"[ProcessorConfigManager] 保存配置失败: {e}")
    
    def reload_config(self):
        """重新加载配置"""
        self.configs.clear()
        self._load_config()
        logger.info("[ProcessorConfigManager] 配置已重新加载")
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        categories = {}
        enabled_count = 0
        
        for config in self.configs.values():
            categories[config.category] = categories.get(config.category, 0) + 1
            if config.enabled:
                enabled_count += 1
        
        return {
            "total_processors": len(self.configs),
            "enabled_processors": enabled_count,
            "disabled_processors": len(self.configs) - enabled_count,
            "categories": categories,
            "config_file": self.config_file
        }


# 创建全局配置管理器实例
processor_config_manager = ProcessorConfigManager()
