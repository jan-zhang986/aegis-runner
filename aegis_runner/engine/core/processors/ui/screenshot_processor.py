# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName
@className ScreenshotProcessor
@describe 截图处理器 - 处理页面和元素截图功能
"""

import json
import os
import time
from typing import Dict, Any, Optional
from playwright.async_api import Page, Locator
from aegis_runner.engine.context import ExecutionContext
from .base_ui_processor import BaseUIProcessor
from aegis_runner.engine.core.simple_logger import logger
from aegis_runner.engine.core.ui.playwright.ui_manager import ui_manager


class ScreenshotProcessor(BaseUIProcessor):
    """截图处理器"""
    
    def __init__(self):
        super().__init__()
        self.screenshot_types = {
            "page": "整页截图",
            "element": "元素截图",
            "viewport": "视口截图",
            "full_page": "完整页面截图"
        }
    
    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> Any:
        """执行截图操作"""
        config = node_info.get("data", {}).get("config", {})
        operation = config.get("operation", "page_screenshot")
        
        logger.info(f"[ScreenshotProcessor] 执行截图操作: {operation}")
        
        # 根据操作类型分发处理
        if operation == "page_screenshot":
            return self._handle_page_screenshot(config, context)
        elif operation == "element_screenshot":
            return self._handle_element_screenshot(config, context)
        elif operation == "viewport_screenshot":
            return self._handle_viewport_screenshot(config, context)
        elif operation == "full_page_screenshot":
            return self._handle_full_page_screenshot(config, context)
        else:
            raise ValueError(f"不支持的截图操作: {operation}")
    
    def _handle_page_screenshot(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理页面截图"""
        file_path = context.render_string(config.get("path", ""))
        page_id = config.get("page_id", "default")
        full_page = config.get("full_page", False)
        quality = config.get("quality", 90)
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 确保目录存在
            screenshot_dir = os.path.dirname(file_path)
            if screenshot_dir and not os.path.exists(screenshot_dir):
                os.makedirs(screenshot_dir, exist_ok=True)
            
            # 生成默认文件名
            if not file_path:
                timestamp = int(time.time())
                file_path = f"screenshots/page_screenshot_{timestamp}.png"
            
            # 执行截图
            ui_manager.run_async(page.screenshot)(
                path=file_path,
                full_page=full_page,
                quality=quality,
                timeout=timeout
            )
            
            # 获取文件信息
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            
            logger.info(f"[ScreenshotProcessor] 页面截图成功: {file_path}")
            
            return {
                "status": "success",
                "operation": "page_screenshot",
                "file_path": file_path,
                "full_page": full_page,
                "quality": quality,
                "file_size": file_size,
                "page_id": page_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ScreenshotProcessor] 页面截图失败: {str(e)}")
            return {
                "status": "error",
                "operation": "page_screenshot",
                "file_path": file_path,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_element_screenshot(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理元素截图"""
        file_path = context.render_string(config.get("path", ""))
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        page_id = config.get("page_id", "default")
        quality = config.get("quality", 90)
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 查找元素
            element = self._find_element(page, selector, selector_type)
            
            # 确保目录存在
            screenshot_dir = os.path.dirname(file_path) if file_path else ""
            if screenshot_dir and not os.path.exists(screenshot_dir):
                os.makedirs(screenshot_dir, exist_ok=True)
            
            # 生成默认文件名
            if not file_path:
                timestamp = int(time.time())
                safe_selector = selector.replace("/", "_").replace("\\", "_")[:20]
                file_path = f"screenshots/element_{safe_selector}_{timestamp}.png"
            
            # 执行元素截图
            ui_manager.run_async(element.screenshot)(
                path=file_path,
                quality=quality,
                timeout=timeout
            )
            
            # 获取文件信息
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            
            logger.info(f"[ScreenshotProcessor] 元素截图成功: {file_path}")
            
            return {
                "status": "success",
                "operation": "element_screenshot",
                "file_path": file_path,
                "selector": selector,
                "selector_type": selector_type,
                "quality": quality,
                "file_size": file_size,
                "page_id": page_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ScreenshotProcessor] 元素截图失败: {str(e)}")
            return {
                "status": "error",
                "operation": "element_screenshot",
                "file_path": file_path,
                "selector": selector,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_viewport_screenshot(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理视口截图（当前可见区域）"""
        file_path = context.render_string(config.get("path", ""))
        page_id = config.get("page_id", "default")
        quality = config.get("quality", 90)
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 确保目录存在
            screenshot_dir = os.path.dirname(file_path) if file_path else ""
            if screenshot_dir and not os.path.exists(screenshot_dir):
                os.makedirs(screenshot_dir, exist_ok=True)
            
            # 生成默认文件名
            if not file_path:
                timestamp = int(time.time())
                file_path = f"screenshots/viewport_{timestamp}.png"
            
            # 执行视口截图（full_page=False）
            ui_manager.run_async(page.screenshot)(
                path=file_path,
                full_page=False,  # 只截取当前视口
                quality=quality,
                timeout=timeout
            )
            
            # 获取文件信息
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            
            logger.info(f"[ScreenshotProcessor] 视口截图成功: {file_path}")
            
            return {
                "status": "success",
                "operation": "viewport_screenshot",
                "file_path": file_path,
                "full_page": False,
                "quality": quality,
                "file_size": file_size,
                "page_id": page_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ScreenshotProcessor] 视口截图失败: {str(e)}")
            return {
                "status": "error",
                "operation": "viewport_screenshot",
                "file_path": file_path,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _validate_ui_config(self, config: Dict[str, Any]) -> bool:
        """验证UI特定配置"""
        # 基础验证，子类可以重写
        return True
    
        
    
    def _handle_full_page_screenshot(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理完整页面截图"""
        file_path = context.render_string(config.get("path", ""))
        page_id = config.get("page_id", "default")
        quality = config.get("quality", 90)
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 确保目录存在
            screenshot_dir = os.path.dirname(file_path) if file_path else ""
            if screenshot_dir and not os.path.exists(screenshot_dir):
                os.makedirs(screenshot_dir, exist_ok=True)
            
            # 生成默认文件名
            if not file_path:
                timestamp = int(time.time())
                file_path = f"screenshots/full_page_{timestamp}.png"
            
            # 执行完整页面截图
            ui_manager.run_async(page.screenshot)(
                path=file_path,
                full_page=True,  # 完整页面截图
                quality=quality,
                timeout=timeout
            )
            
            # 获取文件信息
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            
            logger.info(f"[ScreenshotProcessor] 完整页面截图成功: {file_path}")
            
            return {
                "status": "success",
                "operation": "full_page_screenshot",
                "file_path": file_path,
                "full_page": True,
                "quality": quality,
                "file_size": file_size,
                "page_id": page_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ScreenshotProcessor] 完整页面截图失败: {str(e)}")
            return {
                "status": "error",
                "operation": "full_page_screenshot",
                "file_path": file_path,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _find_element(self, page: Page, selector: str, selector_type: str) -> Locator:
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
            else:
                # 默认使用CSS选择器
                return page.locator(selector)
                
        except Exception as e:
            logger.error(f"[ScreenshotProcessor] 元素查找失败: {selector} ({selector_type})")
            raise ValueError(f"无法找到元素: {selector} ({selector_type}) - {str(e)}")
