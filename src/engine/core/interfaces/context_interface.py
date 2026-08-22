# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-10-13
@packageName src.core.interfaces
@className ContextInterface
@describe 上下文统一接口定义
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List, Callable


class ContextInterface(ABC):
    """
    上下文统一接口
    
    定义执行上下文的标准接口，支持变量管理、函数注册等功能
    """
    
    # ========== 变量管理 ==========
    
    @abstractmethod
    def set_variable(self, key: str, value: Any) -> None:
        """设置变量"""
        pass
    
    @abstractmethod
    def get_variable(self, key: str) -> Any:
        """获取变量"""
        pass
    
    @abstractmethod
    def has_variable(self, key: str) -> bool:
        """检查变量是否存在"""
        pass
    
    @abstractmethod
    def remove_variable(self, key: str) -> bool:
        """移除变量"""
        pass
    
    @abstractmethod
    def get_all_variables(self) -> Dict[str, Any]:
        """获取所有变量"""
        pass
    
    @abstractmethod
    def clear_variables(self) -> None:
        """清空所有变量"""
        pass
    
    # ========== 节点结果管理 ==========
    
    @abstractmethod
    def set_node_result(self, node_id: str, result: Any) -> None:
        """设置节点结果"""
        pass
    
    @abstractmethod
    def get_node_result(self, node_id: str) -> Any:
        """获取节点结果"""
        pass
    
    @abstractmethod
    def has_node_result(self, node_id: str) -> bool:
        """检查节点结果是否存在"""
        pass
    
    @abstractmethod
    def remove_node_result(self, node_id: str) -> bool:
        """移除节点结果"""
        pass
    
    @abstractmethod
    def get_all_node_results(self) -> Dict[str, Any]:
        """获取所有节点结果"""
        pass
    
    @abstractmethod
    def clear_node_results(self) -> None:
        """清空所有节点结果"""
        pass
    
    # ========== 函数管理 ==========
    
    @abstractmethod
    def register_function(self, name: str, func: Callable) -> None:
        """注册函数"""
        pass
    
    @abstractmethod
    def register_functions(self, functions: Dict[str, Callable]) -> None:
        """批量注册函数"""
        pass
    
    @abstractmethod
    def get_function(self, name: str) -> Optional[Callable]:
        """获取函数"""
        pass
    
    @abstractmethod
    def has_function(self, name: str) -> bool:
        """检查函数是否存在"""
        pass
    
    @abstractmethod
    def remove_function(self, name: str) -> bool:
        """移除函数"""
        pass
    
    @abstractmethod
    def get_all_functions(self) -> Dict[str, Callable]:
        """获取所有函数"""
        pass
    
    @abstractmethod
    def clear_functions(self) -> None:
        """清空所有函数"""
        pass
    
    # ========== 字符串渲染 ==========
    
    @abstractmethod
    def render_string(self, template_str: str) -> str:
        """渲染字符串模板"""
        pass
    
    # ========== UI上下文管理 ==========
    
    @abstractmethod
    def set_ui_variable(self, key: str, value: Any) -> None:
        """设置UI变量"""
        pass
    
    @abstractmethod
    def get_ui_variable(self, key: str) -> Any:
        """获取UI变量"""
        pass
    
    @abstractmethod
    def get_ui_variables(self) -> Dict[str, Any]:
        """获取所有UI变量"""
        pass
    
    @abstractmethod
    def clear_ui_variables(self) -> None:
        """清空UI变量"""
        pass
    
    @abstractmethod
    def set_recording_state(self, state: Dict[str, Any]) -> None:
        """设置录制状态"""
        pass
    
    @abstractmethod
    def get_recording_state(self) -> Optional[Dict[str, Any]]:
        """获取录制状态"""
        pass
    
    @abstractmethod
    def add_screenshot(self, screenshot_info: Dict[str, Any]) -> None:
        """添加截图信息"""
        pass
    
    @abstractmethod
    def get_screenshots(self) -> List[Dict[str, Any]]:
        """获取所有截图信息"""
        pass
    
    @abstractmethod
    def add_network_request(self, request_info: Dict[str, Any]) -> None:
        """添加网络请求信息"""
        pass
    
    @abstractmethod
    def get_network_requests(self) -> List[Dict[str, Any]]:
        """获取所有网络请求"""
        pass
    
    @abstractmethod
    def set_performance_metrics(self, metrics: Dict[str, Any]) -> None:
        """设置性能指标"""
        pass
    
    @abstractmethod
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        pass
    
    @abstractmethod
    def set_accessibility_results(self, results: Dict[str, Any]) -> None:
        """设置可访问性测试结果"""
        pass
    
    @abstractmethod
    def get_accessibility_results(self) -> Dict[str, Any]:
        """获取可访问性测试结果"""
        pass
    
    @abstractmethod
    def set_session_info(self, info: Dict[str, Any]) -> None:
        """设置会话信息"""
        pass
    
    @abstractmethod
    def get_session_info(self) -> Dict[str, Any]:
        """获取会话信息"""
        pass
    
    @abstractmethod
    def get_ui_context_summary(self) -> Dict[str, Any]:
        """获取UI上下文摘要"""
        pass
    
    @abstractmethod
    def clear_ui_context(self) -> None:
        """清空所有UI上下文"""
        pass
    
    # ========== 上下文管理 ==========
    
    @abstractmethod
    def get_context_summary(self) -> Dict[str, Any]:
        """获取上下文摘要"""
        pass
    
    @abstractmethod
    def clear_all(self) -> None:
        """清空所有上下文"""
        pass
    
    @abstractmethod
    def clone(self) -> 'ContextInterface':
        """克隆上下文"""
        pass
    
    @abstractmethod
    def merge(self, other: 'ContextInterface') -> None:
        """合并另一个上下文"""
        pass
