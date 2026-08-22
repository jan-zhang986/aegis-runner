# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName
@className ActionProcessor
@describe 动作步骤处理器
"""

import json
import time
import os
import random
import string
from typing import Dict, Any, List, Optional
from playwright.async_api import Page, Locator
from aegis_runner.engine.context import ExecutionContext
from .base_ui_processor import BaseUIProcessor
from aegis_runner.engine.core.simple_logger import logger
from aegis_runner.engine.core.ui.playwright.ui_manager import ui_manager


class ActionProcessor(BaseUIProcessor):
    """动作步骤处理器"""
    
    def __init__(self):
        super().__init__()
        self.action_types = {
            "hover": "悬停动作",
            "extract_value": "提取值动作",
            "generate_email": "生成邮件地址",
            "set_cookie": "设置Cookie",
            "get_cookie": "获取Cookie",
            "navigation": "导航动作",
            "custom_action": "自定义动作",
            "cli_action": "CLI动作",
            "api_action": "API动作",
            "refresh": "刷新页面",
            "generate_random": "生成随机值",
            "generate_date": "生成日期",
            "drag_drop": "拖拽动作",
            "scroll": "滚动动作",
            "key_press": "按键动作",
            "file_upload": "文件上传动作",
            "auto_scroll": "自动滚动",
            "keyboard_shortcut": "键盘快捷键"
        }
    
    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> Any:
        """执行动作操作"""
        config = node_info.get("data", {}).get("config", {})
        action_type = config.get("action_type", "hover")
        
        logger.info(f"[ActionProcessor] 执行动作: {action_type}")
        
        # 根据动作类型分发处理
        if action_type == "hover":
            return self._handle_hover(config, context)
        elif action_type == "extract_value":
            return self._handle_extract_value(config, context)
        elif action_type == "generate_email":
            return self._handle_generate_email(config, context)
        elif action_type == "set_cookie":
            return self._handle_set_cookie(config, context)
        elif action_type == "get_cookie":
            return self._handle_get_cookie(config, context)
        elif action_type == "navigation":
            return self._handle_navigation(config, context)
        elif action_type == "custom_action":
            return self._handle_custom_action(config, context)
        elif action_type == "cli_action":
            return self._handle_cli_action(config, context)
        elif action_type == "api_action":
            return self._handle_api_action(config, context)
        elif action_type == "refresh":
            return self._handle_refresh(config, context)
        elif action_type == "generate_random":
            return self._handle_generate_random(config, context)
        elif action_type == "generate_date":
            return self._handle_generate_date(config, context)
        elif action_type == "drag_drop":
            return self._handle_drag_drop(config, context)
        elif action_type == "scroll":
            return self._handle_scroll(config, context)
        elif action_type == "key_press":
            return self._handle_key_press(config, context)
        elif action_type == "file_upload":
            return self._handle_file_upload(config, context)
        elif action_type == "auto_scroll":
            return self._handle_auto_scroll(config, context)
        elif action_type == "keyboard_shortcut":
            return self._handle_keyboard_shortcut(config, context)
        else:
            raise ValueError(f"不支持的动作类型: {action_type}")
    
    def _handle_hover(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理悬停动作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 查找元素
            element = self._find_element(page, selector, selector_type)
            
            # 执行悬停
            ui_manager.run_async(element.hover)()
            
            logger.info(f"[ActionProcessor] 悬停动作成功: {selector}")
            
            return {
                "status": "success",
                "action_type": "hover",
                "selector": selector,
                "selector_type": selector_type,
                "message": "悬停动作成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ActionProcessor] 悬停动作失败: {str(e)}")
            return {
                "status": "error",
                "action_type": "hover",
                "selector": selector,
                "error": str(e),
                "message": "悬停动作失败",
                "timestamp": time.time()
            }
    
    def _handle_extract_value(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理提取值动作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        extract_type = config.get("extract_type", "text")  # text, attribute, value
        attribute_name = config.get("attribute_name", "")
        variable_name = config.get("variable_name", "extracted_value")
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 查找元素
            element = self._find_element(page, selector, selector_type)
            
            # 根据提取类型获取值
            if extract_type == "text":
                extracted_value = ui_manager.run_async(element.text_content)()
            elif extract_type == "attribute":
                extracted_value = ui_manager.run_async(element.get_attribute)(attribute_name)
            elif extract_type == "value":
                extracted_value = ui_manager.run_async(element.input_value)()
            else:
                raise ValueError(f"不支持的提取类型: {extract_type}")
            
            # 将提取的值保存到上下文变量
            context.set_variable(variable_name, extracted_value)
            
            logger.info(f"[ActionProcessor] 提取值成功: {selector} -> {variable_name} = {extracted_value}")
            
            return {
                "status": "success",
                "action_type": "extract_value",
                "selector": selector,
                "selector_type": selector_type,
                "extract_type": extract_type,
                "attribute_name": attribute_name,
                "variable_name": variable_name,
                "extracted_value": extracted_value,
                "message": "提取值成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ActionProcessor] 提取值失败: {str(e)}")
            return {
                "status": "error",
                "action_type": "extract_value",
                "selector": selector,
                "error": str(e),
                "message": "提取值失败",
                "timestamp": time.time()
            }
    
    def _handle_generate_email(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理生成邮件地址动作"""
        domain = config.get("domain", "example.com")
        variable_name = config.get("variable_name", "generated_email")
        prefix = config.get("prefix", "test")
        
        try:
            # 生成随机邮件地址
            random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            generated_email = f"{prefix}_{random_string}@{domain}"
            
            # 保存到上下文变量
            context.set_variable(variable_name, generated_email)
            
            logger.info(f"[ActionProcessor] 生成邮件地址成功: {generated_email}")
            
            return {
                "status": "success",
                "action_type": "generate_email",
                "domain": domain,
                "prefix": prefix,
                "variable_name": variable_name,
                "generated_email": generated_email,
                "message": "生成邮件地址成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ActionProcessor] 生成邮件地址失败: {str(e)}")
            return {
                "status": "error",
                "action_type": "generate_email",
                "error": str(e),
                "message": "生成邮件地址失败",
                "timestamp": time.time()
            }
    
    def _handle_set_cookie(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理设置Cookie动作"""
        name = context.render_string(config.get("name", ""))
        value = context.render_string(config.get("value", ""))
        domain = config.get("domain", "")
        path = config.get("path", "/")
        expires = config.get("expires")  # 秒数
        http_only = config.get("http_only", False)
        secure = config.get("secure", False)
        same_site = config.get("same_site", "Lax")  # Strict, Lax, None
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 构建Cookie对象
            cookie_data = {
                "name": name,
                "value": value,
                "domain": domain,
                "path": path,
                "httpOnly": http_only,
                "secure": secure,
                "sameSite": same_site
            }
            
            if expires:
                cookie_data["expires"] = expires
            
            # 设置Cookie
            ui_manager.run_async(page.context.add_cookies)([cookie_data])
            
            logger.info(f"[ActionProcessor] 设置Cookie成功: {name}={value}")
            
            return {
                "status": "success",
                "action_type": "set_cookie",
                "name": name,
                "value": value,
                "domain": domain,
                "path": path,
                "expires": expires,
                "http_only": http_only,
                "secure": secure,
                "same_site": same_site,
                "message": "设置Cookie成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ActionProcessor] 设置Cookie失败: {str(e)}")
            return {
                "status": "error",
                "action_type": "set_cookie",
                "name": name,
                "error": str(e),
                "message": "设置Cookie失败",
                "timestamp": time.time()
            }
    
    def _handle_get_cookie(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理获取Cookie动作"""
        name = context.render_string(config.get("name", ""))
        variable_name = config.get("variable_name", "cookie_value")
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 获取Cookie
            cookies = ui_manager.run_async(page.context.cookies)()
            
            # 查找指定名称的Cookie
            cookie_value = None
            if name:
                for cookie in cookies:
                    if cookie["name"] == name:
                        cookie_value = cookie["value"]
                        break
            else:
                # 如果没有指定名称，返回所有Cookie
                cookie_value = cookies
            
            # 保存到上下文变量
            context.set_variable(variable_name, cookie_value)
            
            logger.info(f"[ActionProcessor] 获取Cookie成功: {name}")
            
            return {
                "status": "success",
                "action_type": "get_cookie",
                "name": name,
                "variable_name": variable_name,
                "cookie_value": cookie_value,
                "message": "获取Cookie成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ActionProcessor] 获取Cookie失败: {str(e)}")
            return {
                "status": "error",
                "action_type": "get_cookie",
                "name": name,
                "error": str(e),
                "message": "获取Cookie失败",
                "timestamp": time.time()
            }
    
    def _handle_navigation(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理导航动作"""
        url = context.render_string(config.get("url", ""))
        page_id = config.get("page_id", "default")
        wait_until = config.get("wait_until", "networkidle")
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 执行导航
            ui_manager.run_async(page.goto)(url, wait_until=wait_until, timeout=timeout)
            
            # 获取导航后的页面信息
            current_url = ui_manager.run_async(lambda: page.url)()
            title = ui_manager.run_async(lambda: page.title)()
            
            logger.info(f"[ActionProcessor] 导航动作成功: {url}")
            
            return {
                "status": "success",
                "action_type": "navigation",
                "url": url,
                "current_url": current_url,
                "title": title,
                "wait_until": wait_until,
                "timeout": timeout,
                "page_id": page_id,
                "message": "导航动作成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ActionProcessor] 导航动作失败: {str(e)}")
            return {
                "status": "error",
                "action_type": "navigation",
                "url": url,
                "error": str(e),
                "message": "导航动作失败",
                "timestamp": time.time()
            }
    
    def _handle_custom_action(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理自定义动作"""
        custom_script = config.get("custom_script", "")
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 执行自定义脚本
            result = ui_manager.run_async(page.evaluate)(custom_script)
            
            logger.info(f"[ActionProcessor] 自定义动作成功")
            
            return {
                "status": "success",
                "action_type": "custom_action",
                "custom_script": custom_script,
                "result": result,
                "message": "自定义动作成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ActionProcessor] 自定义动作失败: {str(e)}")
            return {
                "status": "error",
                "action_type": "custom_action",
                "custom_script": custom_script,
                "error": str(e),
                "message": "自定义动作失败",
                "timestamp": time.time()
            }
    
    def _handle_cli_action(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理CLI动作"""
        command = context.render_string(config.get("command", ""))
        working_directory = config.get("working_directory", "")
        timeout = config.get("timeout", 30000)
        variable_name = config.get("variable_name", "cli_output")
        
        try:
            import subprocess
            import os
            
            # 设置工作目录
            if working_directory:
                os.chdir(working_directory)
            
            # 执行命令
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout / 1000
            )
            
            # 保存输出到上下文变量
            output = {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "command": command
            }
            context.set_variable(variable_name, output)
            
            logger.info(f"[ActionProcessor] CLI动作成功: {command}")
            
            return {
                "status": "success",
                "action_type": "cli_action",
                "command": command,
                "working_directory": working_directory,
                "variable_name": variable_name,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "message": "CLI动作成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ActionProcessor] CLI动作失败: {str(e)}")
            return {
                "status": "error",
                "action_type": "cli_action",
                "command": command,
                "error": str(e),
                "message": "CLI动作失败",
                "timestamp": time.time()
            }
    
    def _handle_api_action(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理API动作"""
        url = context.render_string(config.get("url", ""))
        method = config.get("method", "GET")
        headers = config.get("headers", {})
        body = config.get("body", {})
        timeout = config.get("timeout", 30000)
        variable_name = config.get("variable_name", "api_response")
        
        try:
            import requests
            
            # 渲染请求头和请求体
            rendered_headers = {k: context.render_string(v) for k, v in headers.items()}
            rendered_body = context.render_string(json.dumps(body)) if body else None
            
            # 发送API请求
            response = requests.request(
                method=method,
                url=url,
                headers=rendered_headers,
                data=rendered_body,
                timeout=timeout / 1000
            )
            
            # 构建响应数据
            response_data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text,
                "url": response.url
            }
            
            # 保存到上下文变量
            context.set_variable(variable_name, response_data)
            
            logger.info(f"[ActionProcessor] API动作成功: {method} {url}")
            
            return {
                "status": "success",
                "action_type": "api_action",
                "url": url,
                "method": method,
                "headers": rendered_headers,
                "body": rendered_body,
                "variable_name": variable_name,
                "response": response_data,
                "message": "API动作成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ActionProcessor] API动作失败: {str(e)}")
            return {
                "status": "error",
                "action_type": "api_action",
                "url": url,
                "method": method,
                "error": str(e),
                "message": "API动作失败",
                "timestamp": time.time()
            }
    
    def _handle_refresh(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理刷新页面动作"""
        page_id = config.get("page_id", "default")
        wait_until = config.get("wait_until", "networkidle")
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 执行页面刷新
            ui_manager.run_async(page.reload)(wait_until=wait_until, timeout=timeout)
            
            # 获取刷新后的页面信息
            current_url = ui_manager.run_async(lambda: page.url)()
            title = ui_manager.run_async(lambda: page.title)()
            
            logger.info(f"[ActionProcessor] 刷新页面成功")
            
            return {
                "status": "success",
                "action_type": "refresh",
                "current_url": current_url,
                "title": title,
                "wait_until": wait_until,
                "timeout": timeout,
                "page_id": page_id,
                "message": "刷新页面成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ActionProcessor] 刷新页面失败: {str(e)}")
            return {
                "status": "error",
                "action_type": "refresh",
                "error": str(e),
                "message": "刷新页面失败",
                "timestamp": time.time()
            }
    
    def _handle_generate_random(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理生成随机值动作"""
        value_type = config.get("value_type", "string")  # string, number, email, uuid
        length = config.get("length", 10)
        min_value = config.get("min_value", 1)
        max_value = config.get("max_value", 100)
        variable_name = config.get("variable_name", "random_value")
        
        try:
            if value_type == "string":
                generated_value = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
            elif value_type == "number":
                generated_value = random.randint(min_value, max_value)
            elif value_type == "email":
                random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
                generated_value = f"test_{random_string}@example.com"
            elif value_type == "uuid":
                import uuid
                generated_value = str(uuid.uuid4())
            else:
                raise ValueError(f"不支持的随机值类型: {value_type}")
            
            # 保存到上下文变量
            context.set_variable(variable_name, generated_value)
            
            logger.info(f"[ActionProcessor] 生成随机值成功: {generated_value}")
            
            return {
                "status": "success",
                "action_type": "generate_random",
                "value_type": value_type,
                "length": length,
                "min_value": min_value,
                "max_value": max_value,
                "variable_name": variable_name,
                "generated_value": generated_value,
                "message": "生成随机值成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ActionProcessor] 生成随机值失败: {str(e)}")
            return {
                "status": "error",
                "action_type": "generate_random",
                "value_type": value_type,
                "error": str(e),
                "message": "生成随机值失败",
                "timestamp": time.time()
            }
    
    def _handle_generate_date(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理生成日期动作"""
        from datetime import datetime, timedelta
        
        date_type = config.get("date_type", "current")  # current, future, past, specific
        days_offset = config.get("days_offset", 0)
        format_string = config.get("format", "%Y-%m-%d")
        variable_name = config.get("variable_name", "generated_date")
        
        try:
            if date_type == "current":
                generated_date = datetime.now()
            elif date_type == "future":
                generated_date = datetime.now() + timedelta(days=days_offset)
            elif date_type == "past":
                generated_date = datetime.now() - timedelta(days=days_offset)
            elif date_type == "specific":
                specific_date = config.get("specific_date", "")
                generated_date = datetime.strptime(specific_date, format_string)
            else:
                raise ValueError(f"不支持的日期类型: {date_type}")
            
            # 格式化日期
            formatted_date = generated_date.strftime(format_string)
            
            # 保存到上下文变量
            context.set_variable(variable_name, formatted_date)
            
            logger.info(f"[ActionProcessor] 生成日期成功: {formatted_date}")
            
            return {
                "status": "success",
                "action_type": "generate_date",
                "date_type": date_type,
                "days_offset": days_offset,
                "format": format_string,
                "variable_name": variable_name,
                "generated_date": formatted_date,
                "message": "生成日期成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ActionProcessor] 生成日期失败: {str(e)}")
            return {
                "status": "error",
                "action_type": "generate_date",
                "date_type": date_type,
                "error": str(e),
                "message": "生成日期失败",
                "timestamp": time.time()
            }
    
    def _handle_drag_drop(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理拖拽动作"""
        source_selector = context.render_string(config.get("source_selector", ""))
        target_selector = context.render_string(config.get("target_selector", ""))
        source_selector_type = config.get("source_selector_type", "css")
        target_selector_type = config.get("target_selector_type", "css")
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 查找源元素和目标元素
            source_element = self._find_element(page, source_selector, source_selector_type)
            target_element = self._find_element(page, target_selector, target_selector_type)
            
            # 执行拖拽
            ui_manager.run_async(source_element.drag_to)(target_element)
            
            logger.info(f"[ActionProcessor] 拖拽动作成功: {source_selector} -> {target_selector}")
            
            return {
                "status": "success",
                "action_type": "drag_drop",
                "source_selector": source_selector,
                "target_selector": target_selector,
                "source_selector_type": source_selector_type,
                "target_selector_type": target_selector_type,
                "message": "拖拽动作成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ActionProcessor] 拖拽动作失败: {str(e)}")
            return {
                "status": "error",
                "action_type": "drag_drop",
                "source_selector": source_selector,
                "target_selector": target_selector,
                "error": str(e),
                "message": "拖拽动作失败",
                "timestamp": time.time()
            }
    
    def _handle_scroll(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理滚动动作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        direction = config.get("direction", "down")  # down, up, left, right
        amount = config.get("amount", 100)  # 像素数
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            if selector:
                # 滚动到指定元素
                element = self._find_element(page, selector, selector_type)
                ui_manager.run_async(element.scroll_into_view_if_needed)()
            else:
                # 滚动页面
                if direction == "down":
                    ui_manager.run_async(page.evaluate)(f"window.scrollBy(0, {amount})")
                elif direction == "up":
                    ui_manager.run_async(page.evaluate)(f"window.scrollBy(0, -{amount})")
                elif direction == "left":
                    ui_manager.run_async(page.evaluate)(f"window.scrollBy(-{amount}, 0)")
                elif direction == "right":
                    ui_manager.run_async(page.evaluate)(f"window.scrollBy({amount}, 0)")
            
            logger.info(f"[ActionProcessor] 滚动动作成功: {direction} {amount}px")
            
            return {
                "status": "success",
                "action_type": "scroll",
                "selector": selector,
                "selector_type": selector_type,
                "direction": direction,
                "amount": amount,
                "message": "滚动动作成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ActionProcessor] 滚动动作失败: {str(e)}")
            return {
                "status": "error",
                "action_type": "scroll",
                "selector": selector,
                "direction": direction,
                "error": str(e),
                "message": "滚动动作失败",
                "timestamp": time.time()
            }
    
    def _handle_key_press(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理按键动作"""
        key = config.get("key", "")  # Enter, Tab, Escape, ArrowUp, ArrowDown, etc.
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            if selector:
                # 在指定元素上按键
                element = self._find_element(page, selector, selector_type)
                ui_manager.run_async(element.press)(key)
            else:
                # 在页面上按键
                ui_manager.run_async(page.keyboard.press)(key)
            
            logger.info(f"[ActionProcessor] 按键动作成功: {key}")
            
            return {
                "status": "success",
                "action_type": "key_press",
                "key": key,
                "selector": selector,
                "selector_type": selector_type,
                "message": "按键动作成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ActionProcessor] 按键动作失败: {str(e)}")
            return {
                "status": "error",
                "action_type": "key_press",
                "key": key,
                "selector": selector,
                "error": str(e),
                "message": "按键动作失败",
                "timestamp": time.time()
            }
    
    def _handle_file_upload(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理文件上传动作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        file_path = context.render_string(config.get("file_path", ""))
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 查找文件上传元素
            element = self._find_element(page, selector, selector_type)
            
            # 执行文件上传
            ui_manager.run_async(element.set_input_files)(file_path)
            
            logger.info(f"[ActionProcessor] 文件上传成功: {file_path}")
            
            return {
                "status": "success",
                "action_type": "file_upload",
                "selector": selector,
                "selector_type": selector_type,
                "file_path": file_path,
                "message": "文件上传成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ActionProcessor] 文件上传失败: {str(e)}")
            return {
                "status": "error",
                "action_type": "file_upload",
                "selector": selector,
                "file_path": file_path,
                "error": str(e),
                "message": "文件上传失败",
                "timestamp": time.time()
            }
    
    def _handle_auto_scroll(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理自动滚动动作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            if selector:
                # 滚动到指定元素
                element = self._find_element(page, selector, selector_type)
                ui_manager.run_async(element.scroll_into_view_if_needed)()
            else:
                # 滚动到页面底部
                ui_manager.run_async(page.evaluate)("window.scrollTo(0, document.body.scrollHeight)")
            
            logger.info(f"[ActionProcessor] 自动滚动成功")
            
            return {
                "status": "success",
                "action_type": "auto_scroll",
                "selector": selector,
                "selector_type": selector_type,
                "message": "自动滚动成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ActionProcessor] 自动滚动失败: {str(e)}")
            return {
                "status": "error",
                "action_type": "auto_scroll",
                "selector": selector,
                "error": str(e),
                "message": "自动滚动失败",
                "timestamp": time.time()
            }
    
    def _validate_ui_config(self, config: Dict[str, Any]) -> bool:
        """验证UI特定配置"""
        # 基础验证，子类可以重写
        return True
    
    
    
    def _handle_keyboard_shortcut(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理键盘快捷键动作"""
        shortcut = config.get("shortcut", "")  # Ctrl+C, Ctrl+V, Ctrl+A, etc.
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 执行键盘快捷键
            ui_manager.run_async(page.keyboard.press)(shortcut)
            
            logger.info(f"[ActionProcessor] 键盘快捷键成功: {shortcut}")
            
            return {
                "status": "success",
                "action_type": "keyboard_shortcut",
                "shortcut": shortcut,
                "message": "键盘快捷键成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ActionProcessor] 键盘快捷键失败: {str(e)}")
            return {
                "status": "error",
                "action_type": "keyboard_shortcut",
                "shortcut": shortcut,
                "error": str(e),
                "message": "键盘快捷键失败",
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
                return page.locator(selector)
                
        except Exception as e:
            logger.error(f"[ActionProcessor] 元素查找失败: {selector} ({selector_type})")
            raise ValueError(f"无法找到元素: {selector} ({selector_type}) - {str(e)}")
