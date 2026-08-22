# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName
@className EnterpriseLogger
@describe 企业级日志系统
"""

import os
import sys
import json
import inspect
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, Union, List
from pathlib import Path
from loguru import logger
from enum import Enum
from colorama import Fore, Back, Style, init

# 初始化colorama
init(autoreset=True)


class LogLevel(Enum):
    """日志级别枚举"""
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(Enum):
    """日志分类枚举"""
    SYSTEM = "SYSTEM"           # 系统日志
    WORKFLOW = "WORKFLOW"       # 工作流日志
    NODE = "NODE"              # 节点日志
    EXECUTION = "EXECUTION"     # 执行日志
    DATA = "DATA"              # 数据日志
    ERROR = "ERROR"            # 错误日志
    PERFORMANCE = "PERFORMANCE" # 性能日志


class LogConfig:
    """日志配置类"""
    
    def __init__(self):
        self.enabled = True  # 启用日志系统
        self.level = LogLevel.INFO  # 恢复INFO级别
        self.categories = {
            LogCategory.SYSTEM: False,  # 关闭系统日志
            LogCategory.WORKFLOW: False,  # 关闭工作流日志
            LogCategory.NODE: False,  # 关闭节点日志
            LogCategory.EXECUTION: True,  # 保留执行日志（包含执行时间）
            LogCategory.DATA: False,  # 默认关闭数据日志
            LogCategory.ERROR: True,  # 保留错误日志
            LogCategory.PERFORMANCE: True  # 保留性能日志（执行时间等）
        }
        self.output_console = True  # 启用控制台输出
        self.output_file = False  # 禁用文件输出
        self.log_dir = "logs"
        self.max_file_size = "10 MB"
        self.retention = "30 days"
        self.rotation = "1 day"
        self.format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[category]: <12} | {extra[name]: <20} | {extra[location]: <50} | {message}"
        self.data_format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[category]: <12} | {extra[name]: <20} | {extra[location]: <50} | {message}\n{extra}"
        
        # 颜色配置
        self.enable_colors = True
        self.color_config = {
            "TRACE": Fore.CYAN,
            "DEBUG": Fore.BLUE,
            "INFO": Fore.GREEN,
            "SUCCESS": Fore.GREEN + Style.BRIGHT,
            "WARNING": Fore.YELLOW,
            "ERROR": Fore.RED,
            "CRITICAL": Fore.RED + Back.WHITE + Style.BRIGHT
        }
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "enabled": self.enabled,
            "level": self.level.value,
            "categories": {cat.value: enabled for cat, enabled in self.categories.items()},
            "output_console": self.output_console,
            "output_file": self.output_file,
            "log_dir": self.log_dir,
            "max_file_size": self.max_file_size,
            "retention": self.retention,
            "rotation": self.rotation,
            "format": self.format,
            "enable_colors": self.enable_colors,
            "color_config": self.color_config
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LogConfig':
        """从字典创建配置"""
        config = cls()
        config.enabled = data.get("enabled", True)
        config.level = LogLevel(data.get("level", "INFO"))
        config.output_console = data.get("output_console", True)
        config.output_file = data.get("output_file", True)
        config.log_dir = data.get("log_dir", "logs")
        config.max_file_size = data.get("max_file_size", "10 MB")
        config.retention = data.get("retention", "30 days")
        config.rotation = data.get("rotation", "1 day")
        config.format = data.get("format", config.format)
        
        # 恢复分类配置
        categories = data.get("categories", {})
        for cat_name, enabled in categories.items():
            try:
                cat = LogCategory(cat_name)
                config.categories[cat] = enabled
            except ValueError:
                pass
                
        return config


