# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName
@className ElementProcessor
@describe 元素处理器 - 处理页面元素的各种操作
"""

import json
import time
from typing import Dict, Any, Optional, List
from playwright.async_api import Page, Locator
from aegis_runner.engine.context import ExecutionContext
from aegis_runner.engine.core.simple_logger import logger
from aegis_runner.engine.core.ui.playwright.ui_manager import ui_manager
from aegis_runner.engine.core.elegant_processor_registry import register_processor, ProcessorCategory
# 延迟导入以避免循环依赖
from .base_ui_processor import BaseUIProcessor


@register_processor(
    processor_type="ui_element",
    category=ProcessorCategory.UI,
    description="UI元素操作处理器，支持点击、输入、获取文本等操作",
    tags={"ui", "element", "interaction", "browser"},
    enabled=True,
    priority=80,
    version="1.0.0",
    author="Aegis Team"
)
class ElementProcessor(BaseUIProcessor):
    """元素处理器"""
    
    def __init__(self):
        super().__init__()
        self.selector_types = {
            "css": "css选择器",
            "xpath": "XPath表达式", 
            "text": "文本内容",
            "id": "元素ID",
            "class": "CSS类名",
            "name": "name属性",
            "placeholder": "placeholder属性",
            "role": "role定位器（推荐用于稳定性）"
        }
        self.required_config_keys = ["operation", "selector"]
        self.optional_config_keys = ["value", "timeout", "wait_for_visible"]
        self.supported_operations = [
            "click", "input", "get_text", "get_attribute", "hover", 
            "double_click", "right_click", "select_option", "upload_file"
        ]
    
    def _validate_ui_config(self, config: Dict[str, Any]) -> bool:
        """验证UI特定配置"""
        operation = config.get("operation")
        if operation not in self.supported_operations:
            logger.error(f"[ElementProcessor] 不支持的操作类型: {operation}")
            return False
        
        selector = config.get("selector")
        if not selector:
            logger.error(f"[ElementProcessor] 选择器不能为空")
            return False
        
        return True
    
    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> Any:
        """执行元素操作"""
        config = node_info.get("data", {}).get("config", {})
        operation = config.get("operation", "click")
        
        logger.info(f"[ElementProcessor] 执行元素操作: {operation}")
        
        # 根据操作类型分发处理
        if operation == "click":
            return self._handle_click(config, context)
        elif operation == "input":
            return self._handle_input(config, context)
        elif operation == "get_text":
            return self._handle_get_text(config, context)
        elif operation == "get_attribute":
            return self._handle_get_attribute(config, context)
        elif operation == "hover":
            return self._handle_hover(config, context)
        elif operation == "double_click":
            return self._handle_double_click(config, context)
        elif operation == "right_click":
            return self._handle_right_click(config, context)
        elif operation == "select_option":
            return self._handle_select_option(config, context)
        elif operation == "upload_file":
            return self._handle_upload_file(config, context)
        elif operation == "key_press":
            return self._handle_key_press(config, context)
        else:
            raise ValueError(f"不支持的元素操作: {operation}")
    
    def _handle_click(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理点击操作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        page_id = config.get("page_id", "default")
        wait_for_navigation = config.get("wait_for_navigation", False)
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 渲染选择器
            rendered_selector = self._render_selector(selector, selector_type, context)
            
            # 查找元素（传递config以支持role定位器）
            element = self._find_element(page, rendered_selector, selector_type, config)
            
            # 等待元素可见并滚动到视口
            try:
                ui_manager.run_async(element.wait_for)(state="visible", timeout=timeout)
                ui_manager.run_async(element.scroll_into_view_if_needed)()
            except Exception:
                # 如果等待失败，仍然尝试滚动
                try:
                    ui_manager.run_async(element.scroll_into_view_if_needed)()
                except Exception:
                    pass
            
            # 执行点击
            if wait_for_navigation:
                async def click_with_navigation():
                    async with page.expect_navigation(timeout=timeout):
                        await element.click()
                    return "点击完成并等待导航"
                
                result = ui_manager.run_async(click_with_navigation)()
            else:
                ui_manager.run_async(element.click)()
                result = "点击完成"
            
            logger.info(f"[ElementProcessor] 点击成功: {rendered_selector}")
            
            return {
                "status": "success",
                "operation": "click",
                "selector": rendered_selector,
                "selector_type": selector_type,
                "result": result,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ElementProcessor] 点击失败: {str(e)}")
            return {
                "status": "error",
                "operation": "click",
                "selector": selector,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _handle_input(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理输入操作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        value = context.render_string(config.get("value", ""))
        page_id = config.get("page_id", "default")
        clear_first = config.get("clear_first", True)
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 渲染选择器
            rendered_selector = self._render_selector(selector, selector_type, context)
            
            # 查找元素（传递config以支持role定位器）
            element = self._find_element(page, rendered_selector, selector_type, config)
            
            # 等待元素可见（如果需要）
            wait_for_visible = config.get("wait_for_visible", False)
            if wait_for_visible:
                try:
                    ui_manager.run_async(element.wait_for)(state="visible", timeout=timeout)
                except Exception:
                    # 如果等待失败，尝试滚动到元素
                    try:
                        ui_manager.run_async(element.scroll_into_view_if_needed)()
                    except Exception:
                        pass
            
            # 滚动元素到视口（确保元素可见）
            try:
                ui_manager.run_async(element.scroll_into_view_if_needed)()
            except Exception:
                pass
            
            # 执行输入
            if clear_first:
                ui_manager.run_async(element.clear)()
            
            ui_manager.run_async(element.fill)(value)
            
            logger.info(f"[ElementProcessor] 输入成功: {rendered_selector} = {value}")
            
            return {
                "status": "success",
                "operation": "input",
                "selector": rendered_selector,
                "selector_type": selector_type,
                "value": value,
                "clear_first": clear_first,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ElementProcessor] 输入失败: {str(e)}")
            return {
                "status": "error",
                "operation": "input",
                "selector": selector,
                "value": value,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _handle_get_text(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理获取文本操作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        page_id = config.get("page_id", "default")
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 渲染选择器
            rendered_selector = self._render_selector(selector, selector_type, context)
            
            # 查找元素（传递config以支持role定位器）
            element = self._find_element(page, rendered_selector, selector_type, config)
            
            # 获取文本
            text = ui_manager.run_async(element.text_content)()
            
            logger.info(f"[ElementProcessor] 获取文本成功: {rendered_selector} = {text}")
            
            return {
                "status": "success",
                "operation": "get_text",
                "selector": rendered_selector,
                "selector_type": selector_type,
                "text": text,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ElementProcessor] 获取文本失败: {str(e)}")
            return {
                "status": "error",
                "operation": "get_text",
                "selector": selector,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _handle_get_attribute(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理获取属性操作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        attribute = config.get("attribute", "")
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 渲染选择器
            rendered_selector = self._render_selector(selector, selector_type, context)
            
            # 查找元素（传递config以支持role定位器）
            element = self._find_element(page, rendered_selector, selector_type, config)
            
            # 获取属性
            attr_value = ui_manager.run_async(element.get_attribute)(attribute)
            
            logger.info(f"[ElementProcessor] 获取属性成功: {rendered_selector}.{attribute} = {attr_value}")
            
            return {
                "status": "success",
                "operation": "get_attribute",
                "selector": rendered_selector,
                "selector_type": selector_type,
                "attribute": attribute,
                "value": attr_value,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ElementProcessor] 获取属性失败: {str(e)}")
            return {
                "status": "error",
                "operation": "get_attribute",
                "selector": selector,
                "attribute": attribute,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _handle_hover(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理悬停操作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 渲染选择器
            rendered_selector = self._render_selector(selector, selector_type, context)
            
            # 查找元素（传递config以支持role定位器）
            element = self._find_element(page, rendered_selector, selector_type, config)
            
            # 执行悬停
            ui_manager.run_async(element.hover)()
            
            logger.info(f"[ElementProcessor] 悬停成功: {rendered_selector}")
            
            return {
                "status": "success",
                "operation": "hover",
                "selector": rendered_selector,
                "selector_type": selector_type,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ElementProcessor] 悬停失败: {str(e)}")
            return {
                "status": "error",
                "operation": "hover",
                "selector": selector,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _handle_double_click(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理双击操作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 渲染选择器
            rendered_selector = self._render_selector(selector, selector_type, context)
            
            # 查找元素（传递config以支持role定位器）
            element = self._find_element(page, rendered_selector, selector_type, config)
            
            # 执行双击
            ui_manager.run_async(element.dblclick)()
            
            logger.info(f"[ElementProcessor] 双击成功: {rendered_selector}")
            
            return {
                "status": "success",
                "operation": "double_click",
                "selector": rendered_selector,
                "selector_type": selector_type,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ElementProcessor] 双击失败: {str(e)}")
            return {
                "status": "error",
                "operation": "double_click",
                "selector": selector,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _handle_right_click(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理右键点击操作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 渲染选择器
            rendered_selector = self._render_selector(selector, selector_type, context)
            
            # 查找元素（传递config以支持role定位器）
            element = self._find_element(page, rendered_selector, selector_type, config)
            
            # 执行右键点击
            ui_manager.run_async(element.click)(button="right")
            
            logger.info(f"[ElementProcessor] 右键点击成功: {rendered_selector}")
            
            return {
                "status": "success",
                "operation": "right_click",
                "selector": rendered_selector,
                "selector_type": selector_type,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ElementProcessor] 右键点击失败: {str(e)}")
            return {
                "status": "error",
                "operation": "right_click",
                "selector": selector,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _handle_select_option(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理下拉选择操作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        option_value = context.render_string(config.get("option_value", ""))
        option_text = context.render_string(config.get("option_text", ""))
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 渲染选择器
            rendered_selector = self._render_selector(selector, selector_type, context)
            
            # 查找元素（传递config以支持role定位器）
            element = self._find_element(page, rendered_selector, selector_type, config)
            
            # 执行选择
            if option_value:
                ui_manager.run_async(element.select_option)(value=option_value)
                selected_value = option_value
            elif option_text:
                ui_manager.run_async(element.select_option)(label=option_text)
                selected_value = option_text
            else:
                raise ValueError("必须指定 option_value 或 option_text")
            
            logger.info(f"[ElementProcessor] 选择成功: {rendered_selector} = {selected_value}")
            
            return {
                "status": "success",
                "operation": "select_option",
                "selector": rendered_selector,
                "selector_type": selector_type,
                "selected_value": selected_value,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ElementProcessor] 选择失败: {str(e)}")
            return {
                "status": "error",
                "operation": "select_option",
                "selector": selector,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _handle_upload_file(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理文件上传操作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        file_path = context.render_string(config.get("file_path", ""))
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 渲染选择器
            rendered_selector = self._render_selector(selector, selector_type, context)
            
            # 查找元素（传递config以支持role定位器）
            element = self._find_element(page, rendered_selector, selector_type, config)
            
            # 执行文件上传
            ui_manager.run_async(element.set_input_files)(file_path)
            
            logger.info(f"[ElementProcessor] 文件上传成功: {rendered_selector} = {file_path}")
            
            return {
                "status": "success",
                "operation": "upload_file",
                "selector": rendered_selector,
                "selector_type": selector_type,
                "file_path": file_path,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ElementProcessor] 文件上传失败: {str(e)}")
            return {
                "status": "error",
                "operation": "upload_file",
                "selector": selector,
                "file_path": file_path,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _render_selector(self, selector: str, selector_type: str, context: ExecutionContext) -> str:
        """渲染选择器，支持变量替换"""
        try:
            # 使用上下文渲染选择器
            rendered = context.render_string(selector)
            
            # 根据选择器类型进行验证
            if selector_type == "css" and not rendered.startswith(("#", ".", "[", "*")):
                # CSS选择器通常以 #、.、[ 或 * 开头，如果不是，尝试添加 #
                if not rendered.startswith("#") and not rendered.startswith("."):
                    rendered = f"#{rendered}"
            
            return rendered
            
        except Exception as e:
            logger.warning(f"[ElementProcessor] 选择器渲染失败，使用原始值: {str(e)}")
            return selector
    
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
                # 例如: "textbox" 或 "textbox:搜索框" 或 "button:百度一下"
                # 也可以从配置的role_name获取name
                role_name = config.get("role_name") if config else None
                
                parts = selector.split(":", 1)
                if len(parts) == 2:
                    role = parts[0].strip()
                    name = parts[1].strip()
                    # 优先使用selector中的name
                    role_name = name if name else role_name
                else:
                    role = selector.strip()
                
                # 如果有name，使用name定位；否则只用role
                if role_name:
                    return page.get_by_role(role, name=role_name, exact=False)
                else:
                    return page.get_by_role(role)
            else:
                # 默认使用CSS选择器
                return page.locator(selector)
                
        except Exception as e:
            logger.error(f"[ElementProcessor] 元素查找失败: {selector} ({selector_type})")
            raise ValueError(f"无法找到元素: {selector} ({selector_type}) - {str(e)}")

    def _handle_key_press(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理按键操作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        key = config.get("key", "Enter")
        modifiers = config.get("modifiers", 0)
        page_id = config.get("page_id", "default")
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            element = self._find_element(page, selector, selector_type, config)
            
            # 等待元素可见
            ui_manager.run_async(element.wait_for)(state="visible", timeout=timeout)
            
            # 执行按键操作
            if modifiers > 0:
                # 处理修饰键
                element.press(key, modifiers=modifiers)
            else:
                element.press(key)
            
            logger.info(f"[ElementProcessor] 按键操作成功: {key}")
            
            return {
                "status": "success",
                "operation": "key_press",
                "selector": selector,
                "key": key,
                "modifiers": modifiers,
                "page_id": page_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ElementProcessor] 按键操作失败: {str(e)}")
            return {
                "status": "error",
                "operation": "key_press",
                "selector": selector,
                "key": key,
                "error": str(e),
                "timestamp": time.time()
            }
