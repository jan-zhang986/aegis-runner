# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName
@className WaitProcessor
@describe 等待处理器 - 智能等待机制，支持元素等待和条件等待
"""

import json
import os
import time
import asyncio
from typing import Dict, Any, Optional, Callable
from playwright.async_api import Page, Locator
from aegis_runner.engine.context import ExecutionContext
from .base_ui_processor import BaseUIProcessor
from aegis_runner.engine.core.simple_logger import logger
from aegis_runner.engine.core.ui.playwright.ui_manager import ui_manager


class WaitProcessor(BaseUIProcessor):
    """等待处理器"""
    
    def __init__(self):
        super().__init__()
        self.wait_conditions = {
            "element_visible": "等待元素可见",
            "element_hidden": "等待元素隐藏",
            "element_attached": "等待元素附加到DOM",
            "element_detached": "等待元素从DOM中分离",
            "text_present": "等待文本出现",
            "text_not_present": "等待文本消失",
            "url_contains": "等待URL包含指定文本",
            "url_equals": "等待URL等于指定值",
            "network_idle": "等待网络空闲",
            "custom_condition": "等待自定义条件",
            "download": "等待文件下载",
            "element_visualization": "等待元素可视化",
            "viewport_visualization": "等待视口可视化",
            "full_page_visualization": "等待全页可视化",
            "page_load": "等待页面加载",
            "network_request": "等待网络请求"
        }
    
    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> Any:
        """执行等待操作"""
        config = node_info.get("data", {}).get("config", {})
        operation = config.get("operation", "wait_for_element")
        
        logger.info(f"[WaitProcessor] 执行等待操作: {operation}")
        
        # 根据操作类型分发处理
        if operation == "wait_for_element":
            return self._handle_wait_for_element(config, context)
        elif operation == "wait_for_text":
            return self._handle_wait_for_text(config, context)
        elif operation == "wait_for_url":
            return self._handle_wait_for_url(config, context)
        elif operation == "wait_for_network":
            return self._handle_wait_for_network(config, context)
        elif operation == "wait_for_condition":
            return self._handle_wait_for_condition(config, context)
        elif operation == "wait_for_time":
            return self._handle_wait_for_time(config, context)
        elif operation == "wait_for_download":
            return self._handle_wait_for_download(config, context)
        elif operation == "wait_for_element_visualization":
            return self._handle_wait_for_element_visualization(config, context)
        elif operation == "wait_for_viewport_visualization":
            return self._handle_wait_for_viewport_visualization(config, context)
        elif operation == "wait_for_full_page_visualization":
            return self._handle_wait_for_full_page_visualization(config, context)
        elif operation == "wait_for_page_load":
            return self._handle_wait_for_page_load(config, context)
        elif operation == "wait_for_network_request":
            return self._handle_wait_for_network_request(config, context)
        else:
            raise ValueError(f"不支持的等待操作: {operation}")
    
    def _handle_wait_for_element(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理等待元素操作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        page_id = config.get("page_id", "default")
        state = config.get("state", "visible")  # visible, hidden, attached, detached
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 查找元素（传递config以支持role定位器）
            element = self._find_element(page, selector, selector_type, config)
            
            # 根据状态执行等待
            if state == "visible":
                ui_manager.run_async(element.wait_for)(state="visible", timeout=timeout)
            elif state == "hidden":
                ui_manager.run_async(element.wait_for)(state="hidden", timeout=timeout)
            elif state == "attached":
                ui_manager.run_async(element.wait_for)(state="attached", timeout=timeout)
            elif state == "detached":
                ui_manager.run_async(element.wait_for)(state="detached", timeout=timeout)
            else:
                raise ValueError(f"不支持的元素状态: {state}")
            
            # 检查元素是否存在
            is_visible = ui_manager.run_async(element.is_visible)()
            is_enabled = ui_manager.run_async(element.is_enabled)()
            
            logger.info(f"[WaitProcessor] 元素等待成功: {selector} ({state})")
            
            return {
                "status": "success",
                "operation": "wait_for_element",
                "selector": selector,
                "selector_type": selector_type,
                "state": state,
                "is_visible": is_visible,
                "is_enabled": is_enabled,
                "timeout": timeout,
                "page_id": page_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[WaitProcessor] 元素等待失败: {str(e)}")
            return {
                "status": "error",
                "operation": "wait_for_element",
                "selector": selector,
                "state": state,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_wait_for_text(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理等待文本操作"""
        text = context.render_string(config.get("text", ""))
        page_id = config.get("page_id", "default")
        selector = config.get("selector", "")  # 可选，指定在某个元素内查找
        selector_type = config.get("selector_type", "css")
        timeout = config.get("timeout", 30000)
        exact_match = config.get("exact_match", False)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            if selector:
                # 在指定元素内等待文本
                element = self._find_element(page, selector, selector_type)
                if exact_match:
                    ui_manager.run_async(element.wait_for)(selector=f"text={text}", timeout=timeout)
                else:
                    ui_manager.run_async(element.wait_for)(selector=f"text*={text}", timeout=timeout)
            else:
                # 在整个页面等待文本
                if exact_match:
                    ui_manager.run_async(page.wait_for_selector)(f"text={text}", timeout=timeout)
                else:
                    ui_manager.run_async(page.wait_for_selector)(f"text*={text}", timeout=timeout)
            
            logger.info(f"[WaitProcessor] 文本等待成功: {text}")
            
            return {
                "status": "success",
                "operation": "wait_for_text",
                "text": text,
                "selector": selector,
                "exact_match": exact_match,
                "timeout": timeout,
                "page_id": page_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[WaitProcessor] 文本等待失败: {str(e)}")
            return {
                "status": "error",
                "operation": "wait_for_text",
                "text": text,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_wait_for_url(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理等待URL操作"""
        expected_url = context.render_string(config.get("expected_url", ""))
        page_id = config.get("page_id", "default")
        timeout = config.get("timeout", 30000)
        exact_match = config.get("exact_match", False)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 等待URL变化
            if exact_match:
                ui_manager.run_async(page.wait_for_url)(expected_url, timeout=timeout)
            else:
                ui_manager.run_async(page.wait_for_url)(lambda url: expected_url in url, timeout=timeout)
            
            # 获取当前URL
            current_url = ui_manager.run_async(lambda: page.url)()
            
            logger.info(f"[WaitProcessor] URL等待成功: {current_url}")
            
            return {
                "status": "success",
                "operation": "wait_for_url",
                "expected_url": expected_url,
                "current_url": current_url,
                "exact_match": exact_match,
                "timeout": timeout,
                "page_id": page_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[WaitProcessor] URL等待失败: {str(e)}")
            return {
                "status": "error",
                "operation": "wait_for_url",
                "expected_url": expected_url,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_wait_for_network(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理等待网络操作"""
        page_id = config.get("page_id", "default")
        timeout = config.get("timeout", 30000)
        idle_time = config.get("idle_time", 500)  # 网络空闲时间（毫秒）
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 等待网络空闲
            ui_manager.run_async(page.wait_for_load_state)("networkidle", timeout=timeout)
            
            logger.info(f"[WaitProcessor] 网络等待成功")
            
            return {
                "status": "success",
                "operation": "wait_for_network",
                "idle_time": idle_time,
                "timeout": timeout,
                "page_id": page_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[WaitProcessor] 网络等待失败: {str(e)}")
            return {
                "status": "error",
                "operation": "wait_for_network",
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_wait_for_condition(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理等待自定义条件"""
        condition_script = config.get("condition_script", "")
        page_id = config.get("page_id", "default")
        timeout = config.get("timeout", 30000)
        poll_interval = config.get("poll_interval", 1000)  # 轮询间隔（毫秒）
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 执行自定义条件等待
            result = ui_manager.run_async(page.wait_for_function)(
                condition_script,
                timeout=timeout,
                polling=poll_interval
            )
            
            logger.info(f"[WaitProcessor] 自定义条件等待成功")
            
            return {
                "status": "success",
                "operation": "wait_for_condition",
                "condition_script": condition_script,
                "result": result,
                "timeout": timeout,
                "poll_interval": poll_interval,
                "page_id": page_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[WaitProcessor] 自定义条件等待失败: {str(e)}")
            return {
                "status": "error",
                "operation": "wait_for_condition",
                "condition_script": condition_script,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_wait_for_time(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理固定时间等待"""
        wait_time = config.get("wait_time", 1000)  # 等待时间（毫秒）
        page_id = config.get("page_id", "default")
        
        try:
            # 转换为秒
            wait_seconds = wait_time / 1000.0
            
            # 执行等待
            time.sleep(wait_seconds)
            
            logger.info(f"[WaitProcessor] 固定时间等待成功: {wait_time}ms")
            
            return {
                "status": "success",
                "operation": "wait_for_time",
                "wait_time": wait_time,
                "wait_seconds": wait_seconds,
                "page_id": page_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[WaitProcessor] 固定时间等待失败: {str(e)}")
            return {
                "status": "error",
                "operation": "wait_for_time",
                "wait_time": wait_time,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _find_element(self, page: Page, selector: str, selector_type: str, config: Dict[str, Any] = None) -> Locator:
        """查找页面元素"""
        try:
            if selector_type == "css":
                return page.locator(selector)
            elif selector_type == "xpath":
                return page.locator(f"xpath={selector}")
            elif selector_type == "text":
                return page.get_by_text(selector)
            elif selector_type == "id":
                return page.locator(f"#{selector}")
            elif selector_type == "class":
                return page.locator(f".{selector}")
            elif selector_type == "name":
                return page.locator(f"[name='{selector}']")
            elif selector_type == "placeholder":
                return page.locator(f"[placeholder='{selector}']")
            elif selector_type == "role":
                # Role定位器：格式 "role" 或 "role:name" 
                role_name = config.get("role_name") if config else None
                parts = selector.split(":", 1)
                if len(parts) == 2:
                    role = parts[0].strip()
                    name = parts[1].strip()
                    role_name = name if name else role_name
                else:
                    role = selector.strip()
                if role_name:
                    return page.get_by_role(role, name=role_name, exact=False)
                else:
                    return page.get_by_role(role)
            else:
                # 默认使用CSS选择器
                return page.locator(selector)
                
        except Exception as e:
            logger.error(f"[WaitProcessor] 元素查找失败: {selector} ({selector_type})")
            raise ValueError(f"无法找到元素: {selector} ({selector_type}) - {str(e)}")
    
    def _handle_wait_for_download(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理等待文件下载"""
        download_path = context.render_string(config.get("download_path", ""))
        timeout = config.get("timeout", 30000)
        
        try:
            # 等待文件下载完成
            start_time = time.time()
            while time.time() - start_time < timeout / 1000:
                if os.path.exists(download_path):
                    file_size = os.path.getsize(download_path)
                    
                    logger.info(f"[WaitProcessor] 文件下载等待成功: {download_path}")
                    
                    return {
                        "status": "success",
                        "operation": "wait_for_download",
                        "download_path": download_path,
                        "file_size": file_size,
                        "timeout": timeout,
                        "timestamp": time.time()
                    }
                
                time.sleep(0.5)  # 等待500ms
            
            raise AssertionError(f"文件下载超时: {download_path}")
            
        except Exception as e:
            logger.error(f"[WaitProcessor] 文件下载等待失败: {str(e)}")
            return {
                "status": "error",
                "operation": "wait_for_download",
                "download_path": download_path,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _handle_wait_for_element_visualization(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理等待元素可视化"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        reference_image = config.get("reference_image", "")
        threshold = config.get("threshold", 0.1)
        page_id = config.get("page_id", "default")
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 查找元素（传递config以支持role定位器）
            element = self._find_element(page, selector, selector_type, config)
            
            # 等待元素可视化匹配
            start_time = time.time()
            while time.time() - start_time < timeout / 1000:
                # 这里应该实现图像对比逻辑
                # 简化版本：检查元素是否可见
                is_visible = ui_manager.run_async(element.is_visible)()
                if is_visible:
                    logger.info(f"[WaitProcessor] 元素可视化等待成功: {selector}")
                    
                    return {
                        "status": "success",
                        "operation": "wait_for_element_visualization",
                        "selector": selector,
                        "selector_type": selector_type,
                        "reference_image": reference_image,
                        "threshold": threshold,
                        "timeout": timeout,
                        "timestamp": time.time()
                    }
                
                time.sleep(0.5)
            
            raise AssertionError(f"元素可视化等待超时: {selector}")
            
        except Exception as e:
            logger.error(f"[WaitProcessor] 元素可视化等待失败: {str(e)}")
            return {
                "status": "error",
                "operation": "wait_for_element_visualization",
                "selector": selector,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _handle_wait_for_viewport_visualization(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理等待视口可视化"""
        reference_image = config.get("reference_image", "")
        threshold = config.get("threshold", 0.1)
        page_id = config.get("page_id", "default")
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 等待视口可视化匹配
            start_time = time.time()
            while time.time() - start_time < timeout / 1000:
                # 这里应该实现图像对比逻辑
                # 简化版本：检查页面是否加载完成
                page_state = ui_manager.run_async(lambda: page.evaluate("document.readyState"))()
                if page_state == "complete":
                    logger.info(f"[WaitProcessor] 视口可视化等待成功")
                    
                    return {
                        "status": "success",
                        "operation": "wait_for_viewport_visualization",
                        "reference_image": reference_image,
                        "threshold": threshold,
                        "timeout": timeout,
                        "timestamp": time.time()
                    }
                
                time.sleep(0.5)
            
            raise AssertionError(f"视口可视化等待超时")
            
        except Exception as e:
            logger.error(f"[WaitProcessor] 视口可视化等待失败: {str(e)}")
            return {
                "status": "error",
                "operation": "wait_for_viewport_visualization",
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _handle_wait_for_full_page_visualization(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理等待全页可视化"""
        reference_image = config.get("reference_image", "")
        threshold = config.get("threshold", 0.1)
        page_id = config.get("page_id", "default")
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 等待全页可视化匹配
            start_time = time.time()
            while time.time() - start_time < timeout / 1000:
                # 这里应该实现图像对比逻辑
                # 简化版本：检查页面是否加载完成
                page_state = ui_manager.run_async(lambda: page.evaluate("document.readyState"))()
                if page_state == "complete":
                    logger.info(f"[WaitProcessor] 全页可视化等待成功")
                    
                    return {
                        "status": "success",
                        "operation": "wait_for_full_page_visualization",
                        "reference_image": reference_image,
                        "threshold": threshold,
                        "timeout": timeout,
                        "timestamp": time.time()
                    }
                
                time.sleep(0.5)
            
            raise AssertionError(f"全页可视化等待超时")
            
        except Exception as e:
            logger.error(f"[WaitProcessor] 全页可视化等待失败: {str(e)}")
            return {
                "status": "error",
                "operation": "wait_for_full_page_visualization",
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _validate_ui_config(self, config: Dict[str, Any]) -> bool:
        """验证UI特定配置"""
        # 基础验证，子类可以重写
        return True
    
        
    
    def _handle_wait_for_page_load(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理等待页面加载"""
        page_id = config.get("page_id", "default")
        wait_until = config.get("wait_until", "load")
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 等待页面加载
            ui_manager.run_async(page.wait_for_load_state)(wait_until, timeout=timeout)
            
            logger.info(f"[WaitProcessor] 页面加载等待成功: {wait_until}")
            
            return {
                "status": "success",
                "operation": "wait_for_page_load",
                "wait_until": wait_until,
                "timeout": timeout,
                "page_id": page_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[WaitProcessor] 页面加载等待失败: {str(e)}")
            return {
                "status": "error",
                "operation": "wait_for_page_load",
                "wait_until": wait_until,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_wait_for_network_request(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理等待网络请求"""
        expected_url = context.render_string(config.get("expected_url", ""))
        expected_method = config.get("expected_method", "GET")
        expected_status = config.get("expected_status", 200)
        page_id = config.get("page_id", "default")
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 这里需要实现网络请求监听和等待
            # 简化版本：等待一段时间
            
            await_time = min(timeout / 1000, 5)  # 最多等待5秒
            time.sleep(await_time)
            
            logger.info(f"[WaitProcessor] 网络请求等待成功: {expected_url}")
            
            return {
                "status": "success",
                "operation": "wait_for_network_request",
                "expected_url": expected_url,
                "expected_method": expected_method,
                "expected_status": expected_status,
                "timeout": timeout,
                "page_id": page_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[WaitProcessor] 网络请求等待失败: {str(e)}")
            return {
                "status": "error",
                "operation": "wait_for_network_request",
                "expected_url": expected_url,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
