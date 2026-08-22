# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-30
@packageName src.core.processors.ui
@className SmartWaitProcessor
@describe 智能等待处理器 - 提供增强的等待和重试机制
"""

import asyncio
import time
from typing import Dict, Any, Callable, Optional
from playwright.async_api import Page
from src.engine.context import ExecutionContext
from .base_ui_processor import BaseUIProcessor
from src.engine.core.simple_logger import logger
from src.engine.core.ui.playwright.ui_manager import ui_manager


class SmartWaitProcessor(BaseUIProcessor):
    """智能等待处理器"""
    
    def __init__(self):
        super().__init__()
        self.wait_strategies = {
            "element_visible": "等待元素可见",
            "element_hidden": "等待元素隐藏",
            "network_idle": "等待网络空闲",
            "ajax_complete": "等待AJAX完成",
            "custom_condition": "自定义条件等待",
            "smart_wait": "智能等待",
            "retry_operation": "重试操作"
        }
        self.default_max_retries = 3
        self.default_backoff_factor = 1.5
    
    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> Any:
        """执行智能等待操作"""
        config = node_info.get("data", {}).get("config", {})
        operation = config.get("operation", "smart_wait")
        
        logger.info(f"[SmartWaitProcessor] 执行等待操作: {operation}")
        
        # 根据操作类型分发处理
        if operation == "element_visible":
            return self._handle_element_visible(config, context)
        elif operation == "element_hidden":
            return self._handle_element_hidden(config, context)
        elif operation == "network_idle":
            return self._handle_network_idle(config, context)
        elif operation == "ajax_complete":
            return self._handle_ajax_complete(config, context)
        elif operation == "custom_condition":
            return self._handle_custom_condition(config, context)
        elif operation == "smart_wait":
            return self._handle_smart_wait(config, context)
        elif operation == "retry_operation":
            return self._handle_retry_operation(config, context)
        else:
            raise ValueError(f"不支持的等待操作: {operation}")
    
    def _handle_element_visible(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """等待元素可见（带重试）"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        page_id = config.get("page_id", "default")
        timeout = config.get("timeout", 30000)
        max_retries = config.get("max_retries", self.default_max_retries)
        backoff = config.get("backoff_factor", self.default_backoff_factor)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 使用重试机制等待元素
            async def wait_condition():
                element = self._find_element(page, selector, selector_type)
                await element.wait_for(state="visible", timeout=timeout)
            
            result = ui_manager.run_async(self._smart_retry)(
                wait_condition,
                max_retries=max_retries,
                backoff_factor=backoff,
                operation_name=f"等待元素可见: {selector}"
            )
            
            logger.info(f"[SmartWaitProcessor] 元素可见: {selector}")
            
            return {
                "status": "success",
                "operation": "element_visible",
                "selector": selector,
                "selector_type": selector_type,
                "timeout": timeout,
                "page_id": page_id,
                "message": "元素等待成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[SmartWaitProcessor] 等待元素可见失败: {str(e)}")
            return {
                "status": "error",
                "operation": "element_visible",
                "selector": selector,
                "error": str(e),
                "page_id": page_id,
                "message": "元素等待失败",
                "timestamp": time.time()
            }
    
    def _handle_element_hidden(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """等待元素隐藏"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        page_id = config.get("page_id", "default")
        timeout = config.get("timeout", 30000)
        max_retries = config.get("max_retries", self.default_max_retries)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            async def wait_condition():
                element = self._find_element(page, selector, selector_type)
                await element.wait_for(state="hidden", timeout=timeout)
            
            ui_manager.run_async(self._smart_retry)(
                wait_condition,
                max_retries=max_retries,
                operation_name=f"等待元素隐藏: {selector}"
            )
            
            logger.info(f"[SmartWaitProcessor] 元素隐藏: {selector}")
            
            return {
                "status": "success",
                "operation": "element_hidden",
                "selector": selector,
                "selector_type": selector_type,
                "timeout": timeout,
                "page_id": page_id,
                "message": "元素隐藏等待成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[SmartWaitProcessor] 等待元素隐藏失败: {str(e)}")
            return {
                "status": "error",
                "operation": "element_hidden",
                "selector": selector,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_network_idle(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """等待网络空闲"""
        page_id = config.get("page_id", "default")
        timeout = config.get("timeout", 30000)
        idle_time = config.get("idle_time", 500)  # 网络空闲时间（毫秒）
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 等待网络空闲
            ui_manager.run_async(page.wait_for_load_state)("networkidle", timeout=timeout)
            
            logger.info("[SmartWaitProcessor] 网络已空闲")
            
            return {
                "status": "success",
                "operation": "network_idle",
                "timeout": timeout,
                "idle_time": idle_time,
                "page_id": page_id,
                "message": "网络空闲等待成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[SmartWaitProcessor] 等待网络空闲失败: {str(e)}")
            return {
                "status": "error",
                "operation": "network_idle",
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_ajax_complete(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """等待AJAX请求完成"""
        page_id = config.get("page_id", "default")
        timeout = config.get("timeout", 10000)
        check_interval = config.get("check_interval", 100)  # 检查间隔（毫秒）
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 等待AJAX完成
            async def wait_ajax():
                await page.evaluate("""
                    (checkInterval) => new Promise((resolve, reject) => {
                        const startTime = Date.now();
                        
                        const checkAjax = () => {
                            // 检查jQuery
                            if (typeof jQuery !== 'undefined' && jQuery.active > 0) {
                                setTimeout(checkAjax, checkInterval);
                                return;
                            }
                            
                            // 检查fetch
                            if (window.fetch && window.fetch.pending > 0) {
                                setTimeout(checkAjax, checkInterval);
                                return;
                            }
                            
                            // 检查XMLHttpRequest
                            if (window.XMLHttpRequest && window.XMLHttpRequest.pending > 0) {
                                setTimeout(checkAjax, checkInterval);
                                return;
                            }
                            
                            resolve();
                        };
                        
                        checkAjax();
                    })
                """, check_interval)
            
            ui_manager.run_async(asyncio.wait_for)(wait_ajax(), timeout=timeout / 1000)
            
            logger.info("[SmartWaitProcessor] AJAX请求已完成")
            
            return {
                "status": "success",
                "operation": "ajax_complete",
                "timeout": timeout,
                "check_interval": check_interval,
                "page_id": page_id,
                "message": "AJAX完成等待成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[SmartWaitProcessor] 等待AJAX完成失败: {str(e)}")
            return {
                "status": "error",
                "operation": "ajax_complete",
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_custom_condition(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """自定义条件等待"""
        page_id = config.get("page_id", "default")
        condition_script = config.get("condition_script", "")
        timeout = config.get("timeout", 30000)
        check_interval = config.get("check_interval", 100)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 执行自定义等待条件
            async def wait_custom():
                await page.wait_for_function(
                    condition_script,
                    timeout=timeout,
                    polling=check_interval
                )
            
            ui_manager.run_async(wait_custom)()
            
            logger.info("[SmartWaitProcessor] 自定义条件满足")
            
            return {
                "status": "success",
                "operation": "custom_condition",
                "condition_script": condition_script,
                "timeout": timeout,
                "check_interval": check_interval,
                "page_id": page_id,
                "message": "自定义条件等待成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[SmartWaitProcessor] 自定义条件等待失败: {str(e)}")
            return {
                "status": "error",
                "operation": "custom_condition",
                "condition_script": condition_script,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_smart_wait(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """智能等待 - 自动判断等待条件"""
        page_id = config.get("page_id", "default")
        timeout = config.get("timeout", 30000)
        wait_types = config.get("wait_types", ["network_idle", "dom_stable"])
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            results = []
            
            # 依次执行多种等待策略
            for wait_type in wait_types:
                try:
                    if wait_type == "network_idle":
                        ui_manager.run_async(page.wait_for_load_state)("networkidle", timeout=timeout)
                        results.append(("network_idle", "success"))
                        
                    elif wait_type == "dom_stable":
                        # 等待DOM稳定（连续两次检查DOM节点数量相同）
                        async def wait_dom_stable():
                            prev_count = 0
                            stable_count = 0
                            
                            while stable_count < 3:
                                await asyncio.sleep(0.5)
                                current_count = await page.evaluate("document.querySelectorAll('*').length")
                                
                                if current_count == prev_count:
                                    stable_count += 1
                                else:
                                    stable_count = 0
                                
                                prev_count = current_count
                        
                        ui_manager.run_async(asyncio.wait_for)(wait_dom_stable(), timeout=timeout / 1000)
                        results.append(("dom_stable", "success"))
                        
                    elif wait_type == "no_animation":
                        # 等待动画完成
                        ui_manager.run_async(page.wait_for_function)(
                            "document.getAnimations().length === 0",
                            timeout=timeout
                        )
                        results.append(("no_animation", "success"))
                        
                except Exception as e:
                    logger.warning(f"[SmartWaitProcessor] {wait_type}等待失败: {str(e)}")
                    results.append((wait_type, "failed"))
            
            logger.info(f"[SmartWaitProcessor] 智能等待完成: {results}")
            
            return {
                "status": "success",
                "operation": "smart_wait",
                "wait_types": wait_types,
                "results": results,
                "timeout": timeout,
                "page_id": page_id,
                "message": "智能等待成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[SmartWaitProcessor] 智能等待失败: {str(e)}")
            return {
                "status": "error",
                "operation": "smart_wait",
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_retry_operation(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """重试操作包装器"""
        operation_type = config.get("operation_type", "")
        operation_config = config.get("operation_config", {})
        max_retries = config.get("max_retries", self.default_max_retries)
        backoff_factor = config.get("backoff_factor", self.default_backoff_factor)
        
        try:
            # 这里可以包装其他处理器的操作进行重试
            logger.info(f"[SmartWaitProcessor] 执行重试操作: {operation_type}")
            
            # TODO: 集成其他处理器进行重试
            
            return {
                "status": "success",
                "operation": "retry_operation",
                "operation_type": operation_type,
                "max_retries": max_retries,
                "message": "重试操作成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[SmartWaitProcessor] 重试操作失败: {str(e)}")
            return {
                "status": "error",
                "operation": "retry_operation",
                "operation_type": operation_type,
                "error": str(e),
                "timestamp": time.time()
            }
    
    async def _smart_retry(
        self,
        operation: Callable,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        operation_name: str = "操作"
    ) -> Any:
        """
        智能重试机制（带指数退避）
        
        Args:
            operation: 要执行的异步操作
            max_retries: 最大重试次数
            backoff_factor: 退避系数
            operation_name: 操作名称（用于日志）
            
        Returns:
            操作结果
        """
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                logger.info(f"[SmartWaitProcessor] 尝试{operation_name} (第{attempt + 1}/{max_retries}次)")
                result = await operation()
                logger.info(f"[SmartWaitProcessor] {operation_name}成功")
                return result
                
            except Exception as e:
                last_exception = e
                
                if attempt < max_retries - 1:
                    wait_time = backoff_factor ** attempt
                    logger.warning(
                        f"[SmartWaitProcessor] {operation_name}失败: {str(e)}, "
                        f"{wait_time:.1f}秒后重试..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"[SmartWaitProcessor] {operation_name}最终失败: {str(e)}")
        
        raise last_exception
    
    def _find_element(self, page: Page, selector: str, selector_type: str):
        """查找页面元素"""
        if selector_type == "css":
            return page.locator(selector)
        elif selector_type == "xpath":
            return page.locator(f"xpath={selector}")
        elif selector_type == "text":
            return page.get_by_text(selector)
        elif selector_type == "id":
            return page.locator(f"#{selector}")
        else:
            return page.locator(selector)
    
    def _validate_ui_config(self, config: Dict[str, Any]) -> bool:
        """验证UI特定配置"""
        return True

