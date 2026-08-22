# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName src.ui.utils
@className UIUtils
@describe UI工具类 - 提供常用的UI操作工具方法
"""

import time
import json
from typing import Dict, Any, List, Optional
from aegis_runner.engine.core.simple_logger import logger


class UIUtils:
    """UI工具类"""
    
    @staticmethod
    def generate_timestamp() -> str:
        """生成时间戳字符串"""
        return str(int(time.time()))
    
    @staticmethod
    def generate_unique_id(prefix: str = "ui") -> str:
        """生成唯一ID"""
        return f"{prefix}_{int(time.time() * 1000)}"
    
    @staticmethod
    def safe_json_loads(json_str: str, default: Any = None) -> Any:
        """安全的JSON解析"""
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return default
    
    @staticmethod
    def safe_json_dumps(obj: Any, default: str = "{}") -> str:
        """安全的JSON序列化"""
        try:
            return json.dumps(obj, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return default
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """格式化持续时间"""
        if seconds < 1:
            return f"{int(seconds * 1000)}ms"
        elif seconds < 60:
            return f"{seconds:.1f}s"
        else:
            minutes = int(seconds // 60)
            remaining_seconds = seconds % 60
            return f"{minutes}m {remaining_seconds:.1f}s"
    
    @staticmethod
    def validate_selector(selector: str, selector_type: str) -> bool:
        """验证选择器格式"""
        if not selector or not selector.strip():
            return False
        
        selector = selector.strip()
        
        if selector_type == "css":
            # 基本的CSS选择器验证
            return len(selector) > 0 and not selector.startswith("//")
        elif selector_type == "xpath":
            # 基本的XPath验证
            return len(selector) > 0 and (selector.startswith("/") or selector.startswith("./"))
        elif selector_type in ["text", "id", "class", "name", "placeholder"]:
            return len(selector) > 0
        else:
            return len(selector) > 0
    
    @staticmethod
    def normalize_selector(selector: str, selector_type: str) -> str:
        """标准化选择器"""
        if not selector:
            return ""
        
        selector = selector.strip()
        
        if selector_type == "id" and not selector.startswith("#"):
            return f"#{selector}"
        elif selector_type == "class" and not selector.startswith("."):
            return f".{selector}"
        elif selector_type == "name":
            return f"[name='{selector}']"
        elif selector_type == "placeholder":
            return f"[placeholder='{selector}']"
        
        return selector
    
    @staticmethod
    def extract_element_info(element_data: Dict[str, Any]) -> Dict[str, Any]:
        """提取元素信息"""
        return {
            "tag": element_data.get("tag", ""),
            "text": element_data.get("text", ""),
            "attributes": element_data.get("attributes", {}),
            "position": element_data.get("position", {}),
            "size": element_data.get("size", {}),
            "visible": element_data.get("visible", True)
        }
    
    @staticmethod
    def build_error_message(operation: str, error: str, context: Dict[str, Any] = None) -> str:
        """构建错误消息"""
        base_message = f"UI操作失败: {operation}"
        
        if context:
            if "selector" in context:
                base_message += f" (选择器: {context['selector']})"
            if "page_id" in context:
                base_message += f" (页面: {context['page_id']})"
        
        base_message += f" - {error}"
        return base_message
    
    @staticmethod
    def merge_configs(base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
        """合并配置"""
        result = base_config.copy()
        result.update(override_config)
        return result
    
    @staticmethod
    def get_default_timeout() -> int:
        """获取默认超时时间"""
        return 30000  # 30秒
    
    @staticmethod
    def get_default_wait_time() -> int:
        """获取默认等待时间"""
        return 1000  # 1秒
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """验证URL格式"""
        if not url:
            return False
        
        url = url.strip()
        return url.startswith(("http://", "https://", "file://", "data:"))
    
    @staticmethod
    def normalize_url(url: str) -> str:
        """标准化URL"""
        if not url:
            return ""
        
        url = url.strip()
        if not url.startswith(("http://", "https://", "file://", "data:")):
            url = f"https://{url}"
        
        return url
