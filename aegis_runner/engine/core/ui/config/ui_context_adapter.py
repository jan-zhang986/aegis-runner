# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName src.ui.core
@className UIContextAdapter
@describe UI上下文适配器 - 提供向后兼容性（新代码应直接使用ExecutionContext）
"""

from typing import Dict, Any, Optional, List
from aegis_runner.engine.core.simple_logger import logger


class UIContextAdapter:
    """
    UI上下文适配器
    
    这个类提供了向后兼容性，让现有的UI代码可以继续使用UIContext接口
    实际上内部委托给统一的ExecutionContext
    """
    
    def __init__(self, execution_context):
        """
        初始化适配器
        
        Args:
            execution_context: 统一的执行上下文实例
        """
        self._context = execution_context
        logger.debug("[UIContextAdapter] 初始化UI上下文适配器")
    
    def set_ui_variable(self, key: str, value: Any) -> None:
        """设置UI变量"""
        self._context.set_ui_variable(key, value)
    
    def get_ui_variable(self, key: str) -> Any:
        """获取UI变量"""
        return self._context.get_ui_variable(key)
    
    def get_ui_variables(self) -> Dict[str, Any]:
        """获取所有UI变量"""
        return self._context.get_ui_variables()
    
    def clear_ui_variables(self) -> None:
        """清空UI变量"""
        self._context.clear_ui_variables()
    
    def set_recording_state(self, state: Dict[str, Any]) -> None:
        """设置录制状态"""
        self._context.set_recording_state(state)
    
    def get_recording_state(self) -> Optional[Dict[str, Any]]:
        """获取录制状态"""
        return self._context.get_recording_state()
    
    def add_screenshot(self, screenshot_info: Dict[str, Any]) -> None:
        """添加截图信息"""
        self._context.add_screenshot(screenshot_info)
    
    def get_screenshots(self) -> List[Dict[str, Any]]:
        """获取所有截图信息"""
        return self._context.get_screenshots()
    
    def add_network_request(self, request_info: Dict[str, Any]) -> None:
        """添加网络请求信息"""
        self._context.add_network_request(request_info)
    
    def get_network_requests(self) -> List[Dict[str, Any]]:
        """获取所有网络请求"""
        return self._context.get_network_requests()
    
    def set_performance_metrics(self, metrics: Dict[str, Any]) -> None:
        """设置性能指标"""
        self._context.set_performance_metrics(metrics)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return self._context.get_performance_metrics()
    
    def set_accessibility_results(self, results: Dict[str, Any]) -> None:
        """设置可访问性测试结果"""
        self._context.set_accessibility_results(results)
    
    def get_accessibility_results(self) -> Dict[str, Any]:
        """获取可访问性测试结果"""
        return self._context.get_accessibility_results()
    
    def set_session_info(self, info: Dict[str, Any]) -> None:
        """设置会话信息"""
        self._context.set_session_info(info)
    
    def get_session_info(self) -> Dict[str, Any]:
        """获取会话信息"""
        return self._context.get_session_info()
    
    def get_context_summary(self) -> Dict[str, Any]:
        """获取上下文摘要"""
        return self._context.get_ui_context_summary()
    
    def clear_all(self) -> None:
        """清空所有上下文"""
        self._context.clear_ui_context()
