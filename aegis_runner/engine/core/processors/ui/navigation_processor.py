# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-10-13
@packageName
@className NavigationProcessor
@describe 页面导航处理器 - 处理页面导航、跳转和等待
"""

import json
import time
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
from playwright.async_api import Page
from aegis_runner.engine.context import ExecutionContext
from .base_ui_processor import BaseUIProcessor
from aegis_runner.engine.core.simple_logger import logger
from aegis_runner.engine.core.ui.playwright.ui_manager import ui_manager


class NavigationProcessor(BaseUIProcessor):
    """页面导航处理器"""
    
    def __init__(self):
        super().__init__()
        self.wait_conditions = {
            "load": "等待页面load事件",
            "domcontentloaded": "等待DOMContentLoaded事件", 
            "networkidle": "等待网络空闲",
            "commit": "等待导航提交"
        }
    
    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> Any:
        """执行导航操作"""
        config = node_info.get("data", {}).get("config", {})
        operation = config.get("operation", "navigate")
        
        logger.info(f"[NavigationProcessor] 执行导航操作: {operation}")
        
        # 根据操作类型分发处理
        if operation == "navigate":
            return self._handle_navigate(config, context)
        elif operation == "go_back":
            return self._handle_go_back(config, context)
        elif operation == "go_forward":
            return self._handle_go_forward(config, context)
        elif operation == "refresh":
            return self._handle_refresh(config, context)
        elif operation == "wait_for_url":
            return self._handle_wait_for_url(config, context)
        elif operation == "wait_for_load":
            return self._handle_wait_for_load(config, context)
        else:
            raise ValueError(f"不支持的导航操作: {operation}")
    
    def _handle_navigate(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理页面导航"""
        url = context.render_string(config.get("url", ""))
        page_id = config.get("page_id", "default")
        context_id = config.get("context_id")  # 上下文ID（用于多网站隔离）
        auto_create_context = config.get("auto_create_context", True)  # 是否自动创建上下文
        wait_until = config.get("wait_until", "networkidle")
        timeout = config.get("timeout", 30000)
        
        # 鉴权配置
        credential_id = config.get("credential_id")  # 使用凭证ID
        cookies = config.get("cookies", [])  # 直接配置Cookie
        headers = config.get("headers", {})  # 直接配置请求头
        local_storage = config.get("local_storage", {})  # localStorage
        session_storage = config.get("session_storage", {})  # sessionStorage
        
        try:
            # 处理上下文切换或创建
            target_context = None
            if context_id:
                # 方式1: 使用指定的context_id
                target_context = ui_manager.get_context(context_id)
                if not target_context and auto_create_context:
                    # 创建新上下文
                    result = ui_manager.run_async(ui_manager.new_context)(context_id)
                    if result["status"] == "success":
                        target_context = ui_manager.get_context(context_id)
                        logger.info(f"[NavigationProcessor] 已创建上下文: {context_id}")
                elif not target_context:
                    raise ValueError(f"上下文 {context_id} 不存在且auto_create_context为False")
                else:
                    # 切换到指定上下文
                    ui_manager.switch_context(context_id)
            elif auto_create_context:
                # 方式2: 根据URL自动获取或创建上下文
                target_context = ui_manager.run_async(ui_manager.get_or_create_context_for_url)(url)
                if target_context:
                    # 获取context_id
                    for ctx_id, ctx in ui_manager.contexts.items():
                        if ctx == target_context:
                            context_id = ctx_id
                            ui_manager.switch_context(ctx_id)
                            break
            
            # 获取页面（如果指定了page_id，使用指定页面；否则使用当前上下文默认页面）
            page = None
            actual_page_id = page_id
            
            # 如果切换了上下文，尝试获取该上下文的默认页面
            if context_id and context_id != "default":
                # 查找该上下文对应的页面（上下文创建时会生成 {context_id}_page）
                context_page_id = f"{context_id}_page"
                page = ui_manager.get_page(context_page_id)
                if page:
                    actual_page_id = context_page_id
                    ui_manager.current_page_id = context_page_id
                    logger.info(f"[NavigationProcessor] 使用上下文默认页面: {context_page_id}")
            
            # 如果还没找到页面，使用指定的page_id
            if not page:
                page = ui_manager.get_page(page_id)
            
            # 如果页面还不存在，在当前上下文中创建新页面
            if not page:
                if context_id:
                    result = ui_manager.run_async(ui_manager.new_page)(page_id, context_id)
                else:
                    result = ui_manager.run_async(ui_manager.new_page)(page_id)
                page = ui_manager.get_page(page_id)
                if page:
                    actual_page_id = page_id
            
            if not page:
                # 最后尝试：使用当前上下文的第一个页面
                current_context = ui_manager.get_context(context_id) if context_id else ui_manager.context
                if current_context:
                    pages_in_context = current_context.pages
                    if pages_in_context:
                        page = pages_in_context[0]
                        logger.info(f"[NavigationProcessor] 使用上下文中的第一个页面")
            
            if not page:
                raise ValueError(f"页面 {page_id} 不存在且创建失败 (上下文: {context_id})")
            
            # 在导航前注入鉴权信息
            self._inject_auth_info(page, context, {
                "credential_id": credential_id,
                "cookies": cookies,
                "headers": headers,
                "local_storage": local_storage,
                "session_storage": session_storage,
                "url": url
            })
            
            # 执行导航
            logger.info(f"[NavigationProcessor] 准备导航到: {url} (页面ID: {actual_page_id}, 上下文: {context_id})")
            
            # 确保页面已经准备好
            if page.url == "about:blank":
                logger.info(f"[NavigationProcessor] 页面当前为about:blank，开始导航")
            
            ui_manager.run_async(page.goto)(url, wait_until=wait_until, timeout=timeout)
            
            # 获取导航后的页面信息  
            # page.url是属性，不是async方法
            current_url = page.url
            # page.title()是async方法
            title = ui_manager.run_async(page.title)()
            
            logger.info(f"[NavigationProcessor] 导航成功: {url} -> {current_url} (标题: {title})")
            
            # 验证导航是否成功
            if current_url == "about:blank":
                logger.warning(f"[NavigationProcessor] 页面仍为about:blank，可能导航未成功")
                # 尝试再次导航
                ui_manager.run_async(page.goto)(url, wait_until=wait_until, timeout=timeout)
                current_url = page.url
                title = ui_manager.run_async(page.title)()
                logger.info(f"[NavigationProcessor] 重试后URL: {current_url}")
            
            return {
                "status": "success",
                "operation": "navigate",
                "target_url": url,
                "current_url": current_url,
                "page_title": title,
                "wait_until": wait_until,
                "timeout": timeout,
                "page_id": actual_page_id,
                "context_id": context_id or ui_manager.current_context_id,  # 返回使用的上下文ID
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[NavigationProcessor] 导航失败: {str(e)}")
            return {
                "status": "error",
                "operation": "navigate",
                "target_url": url,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_go_back(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理后退操作"""
        page_id = config.get("page_id", "default")
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 执行后退
            ui_manager.run_async(page.go_back)(timeout=timeout)
            
            # 获取后退后的页面信息
            current_url = page.url
            title = ui_manager.run_async(page.title)()
            
            logger.info(f"[NavigationProcessor] 后退成功: {current_url}")
            
            return {
                "status": "success",
                "operation": "go_back",
                "current_url": current_url,
                "page_title": title,
                "timeout": timeout,
                "page_id": page_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[NavigationProcessor] 后退失败: {str(e)}")
            return {
                "status": "error",
                "operation": "go_back",
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_go_forward(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理前进操作"""
        page_id = config.get("page_id", "default")
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 执行前进
            ui_manager.run_async(page.go_forward)(timeout=timeout)
            
            # 获取前进后的页面信息
            current_url = page.url
            title = ui_manager.run_async(page.title)()
            
            logger.info(f"[NavigationProcessor] 前进成功: {current_url}")
            
            return {
                "status": "success",
                "operation": "go_forward",
                "current_url": current_url,
                "page_title": title,
                "timeout": timeout,
                "page_id": page_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[NavigationProcessor] 前进失败: {str(e)}")
            return {
                "status": "error",
                "operation": "go_forward",
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_refresh(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理页面刷新"""
        page_id = config.get("page_id", "default")
        wait_until = config.get("wait_until", "networkidle")
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 执行刷新
            ui_manager.run_async(page.reload)(wait_until=wait_until, timeout=timeout)
            
            # 获取刷新后的页面信息
            current_url = page.url
            title = ui_manager.run_async(page.title)()
            
            logger.info(f"[NavigationProcessor] 刷新成功: {current_url}")
            
            return {
                "status": "success",
                "operation": "refresh",
                "current_url": current_url,
                "page_title": title,
                "wait_until": wait_until,
                "timeout": timeout,
                "page_id": page_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[NavigationProcessor] 刷新失败: {str(e)}")
            return {
                "status": "error",
                "operation": "refresh",
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _validate_ui_config(self, config: Dict[str, Any]) -> bool:
        """验证UI特定配置"""
        # 基础验证，子类可以重写
        return True
    
    
    
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
                # 使用 lambda 函数需要特殊处理
                async def wait_url_with_condition():
                    await page.wait_for_url(lambda url: expected_url in url, timeout=timeout)
                ui_manager.run_async(wait_url_with_condition)()
            
            # 获取当前URL
            current_url = page.url
            
            logger.info(f"[NavigationProcessor] URL等待成功: {current_url}")
            
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
            logger.error(f"[NavigationProcessor] URL等待失败: {str(e)}")
            return {
                "status": "error",
                "operation": "wait_for_url",
                "expected_url": expected_url,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_wait_for_load(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理等待页面加载"""
        page_id = config.get("page_id", "default")
        wait_until = config.get("wait_until", "networkidle")
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 等待页面加载
            ui_manager.run_async(page.wait_for_load_state)(wait_until, timeout=timeout)
            
            # 获取页面状态
            current_url = page.url
            title = ui_manager.run_async(page.title)()
            
            logger.info(f"[NavigationProcessor] 页面加载等待成功: {current_url}")
            
            return {
                "status": "success",
                "operation": "wait_for_load",
                "wait_until": wait_until,
                "current_url": current_url,
                "page_title": title,
                "timeout": timeout,
                "page_id": page_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[NavigationProcessor] 页面加载等待失败: {str(e)}")
            return {
                "status": "error",
                "operation": "wait_for_load",
                "wait_until": wait_until,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _inject_auth_info(self, page: Page, context: ExecutionContext, auth_config: Dict[str, Any]):
        """
        注入鉴权信息到页面
        
        Args:
            page: Playwright页面对象
            context: 执行上下文
            auth_config: 鉴权配置，包含：
                - credential_id: 凭证ID（优先使用）
                - cookies: Cookie列表
                - headers: 请求头字典
                - local_storage: localStorage键值对
                - session_storage: sessionStorage键值对
                - url: 目标URL（用于确定domain）
        """
        try:
            credential_id = auth_config.get("credential_id")
            
            # 方法1: 使用凭证管理器（推荐）
            applied_credential = False
            if credential_id:
                self._apply_credential(page, context, credential_id, auth_config.get("url"))
                logger.info(f"[NavigationProcessor] 已应用凭证: {credential_id}")
                applied_credential = True
            
            # 方法2: 直接配置Cookie（补充凭证中的Cookie）
            # 参考: https://playwright.dev/python/docs/api/class-browsercontext#browser-context-add-cookies
            cookies = auth_config.get("cookies", [])
            if cookies:
                if isinstance(cookies, list):
                    rendered_cookies = []
                    for cookie in cookies:
                        if isinstance(cookie, dict):
                            # 渲染cookie值中的变量
                            rendered_cookie = {}
                            for key, value in cookie.items():
                                if isinstance(value, str):
                                    rendered_cookie[key] = context.render_string(value)
                                else:
                                    rendered_cookie[key] = value
                            
                            # 确保必需的字段存在（根据Playwright API要求）
                            # 必需: name, value, domain, path
                            if "name" not in rendered_cookie or "value" not in rendered_cookie:
                                logger.warning(f"[NavigationProcessor] Cookie缺少必需字段(name/value)，跳过: {rendered_cookie}")
                                continue
                            
                            # 如果没有domain，从URL中提取
                            if "domain" not in rendered_cookie:
                                if auth_config.get("url"):
                                    parsed_url = urlparse(auth_config["url"])
                                    rendered_cookie["domain"] = parsed_url.netloc
                                else:
                                    logger.warning(f"[NavigationProcessor] Cookie缺少domain且无法从URL提取，跳过: {rendered_cookie.get('name')}")
                                    continue
                            
                            # 设置默认path
                            if "path" not in rendered_cookie:
                                rendered_cookie["path"] = "/"
                            
                            rendered_cookies.append(rendered_cookie)
                    
                    if rendered_cookies:
                        # 使用BrowserContext.add_cookies API（Playwright标准方法）
                        ui_manager.run_async(page.context.add_cookies)(rendered_cookies)
                        logger.info(f"[NavigationProcessor] 已注入 {len(rendered_cookies)} 个Cookie到浏览器上下文")
            
            # 方法3: 设置请求头
            headers = auth_config.get("headers", {})
            if headers:
                rendered_headers = {}
                for key, value in headers.items():
                    if isinstance(value, str):
                        rendered_headers[key] = context.render_string(value)
                    else:
                        rendered_headers[key] = value
                
                ui_manager.run_async(page.set_extra_http_headers)(rendered_headers)
                logger.info(f"[NavigationProcessor] 已注入请求头: {list(rendered_headers.keys())}")
            
            # 方法4: 设置localStorage（使用add_init_script，Playwright推荐方式）
            # 参考: https://playwright.dev/python/docs/api/class-browsercontext#browser-context-add-init-script
            local_storage = auth_config.get("local_storage", {})
            if local_storage:
                # 构建localStorage初始化脚本
                storage_items = []
                for key, value in local_storage.items():
                    rendered_key = context.render_string(key) if isinstance(key, str) else str(key)
                    rendered_value = context.render_string(value) if isinstance(value, str) else str(value)
                    # 使用JSON序列化确保安全
                    key_json = json.dumps(rendered_key)
                    value_json = json.dumps(rendered_value)
                    storage_items.append(f"localStorage.setItem({key_json}, {value_json});")
                
                if storage_items:
                    init_script = "".join(storage_items)
                    # 使用BrowserContext.add_init_script（在页面加载前执行）
                    ui_manager.run_async(page.context.add_init_script)(init_script)
                    logger.info(f"[NavigationProcessor] 已注入localStorage初始化脚本({len(local_storage)}项)")
            
            # 方法5: 设置sessionStorage（使用add_init_script）
            session_storage = auth_config.get("session_storage", {})
            if session_storage:
                # 构建sessionStorage初始化脚本
                storage_items = []
                for key, value in session_storage.items():
                    rendered_key = context.render_string(key) if isinstance(key, str) else str(key)
                    rendered_value = context.render_string(value) if isinstance(value, str) else str(value)
                    # 使用JSON序列化确保安全
                    key_json = json.dumps(rendered_key)
                    value_json = json.dumps(rendered_value)
                    storage_items.append(f"sessionStorage.setItem({key_json}, {value_json});")
                
                if storage_items:
                    init_script = "".join(storage_items)
                    # 使用BrowserContext.add_init_script（在页面加载前执行）
                    ui_manager.run_async(page.context.add_init_script)(init_script)
                    logger.info(f"[NavigationProcessor] 已注入sessionStorage初始化脚本({len(session_storage)}项)")
                
        except Exception as e:
            logger.warning(f"[NavigationProcessor] 注入鉴权信息失败: {str(e)}，继续执行导航")
    
    def _apply_credential(self, page: Page, context: ExecutionContext, credential_id: str, url: str = None):
        """
        应用凭证到页面
        
        Args:
            page: Playwright页面对象
            context: 执行上下文
            credential_id: 凭证ID
            url: 目标URL（用于确定domain）
        """
        try:
            from aegis_runner.engine.core.credential_store import credential_store
            
            # 获取凭证配置
            credential_config = credential_store.get_credential_config(credential_id)
            if not credential_config:
                logger.warning(f"[NavigationProcessor] 凭证 {credential_id} 不存在")
                return
            
            # 获取凭证对象
            credential = credential_store.get_credential(credential_id)
            if not credential:
                logger.warning(f"[NavigationProcessor] 无法获取凭证对象: {credential_id}")
                return
            
            # 应用凭证信息
            auth_config = {
                "cookies": [],
                "headers": {},
                "local_storage": {},
                "session_storage": {}
            }
            
            # 从凭证配置中提取信息
            # 1. 生成HTTP鉴权头
            auth_headers = credential_store.get_auth_headers(credential_id, context)
            auth_config["headers"].update(auth_headers)
            
            # 2. 提取Cookie（如果配置中有）
            if "cookies" in credential_config:
                cookies = credential_config["cookies"]
                if isinstance(cookies, list):
                    # 渲染变量并设置domain
                    rendered_cookies = []
                    for cookie in cookies:
                        if isinstance(cookie, dict):
                            rendered_cookie = {}
                            for key, value in cookie.items():
                                if isinstance(value, str):
                                    rendered_cookie[key] = context.render_string(value)
                                else:
                                    rendered_cookie[key] = value
                            
                            # 如果没有domain且有URL，从URL提取
                            if "domain" not in rendered_cookie:
                                if url:
                                    parsed_url = urlparse(url)
                                    rendered_cookie["domain"] = parsed_url.netloc
                                else:
                                    logger.warning(f"[NavigationProcessor] Cookie缺少domain且无法从URL提取，跳过: {rendered_cookie.get('name')}")
                                    continue
                            
                            # 设置默认path（Playwright API要求）
                            if "path" not in rendered_cookie:
                                rendered_cookie["path"] = "/"
                            
                            rendered_cookies.append(rendered_cookie)
                    auth_config["cookies"] = rendered_cookies
            
            # 3. 提取localStorage和sessionStorage
            if "local_storage" in credential_config:
                auth_config["local_storage"] = credential_config["local_storage"]
            if "session_storage" in credential_config:
                auth_config["session_storage"] = credential_config["session_storage"]
            
            # 直接应用凭证信息（避免递归调用）
            # 应用Cookie（使用BrowserContext.add_cookies）
            if auth_config["cookies"]:
                ui_manager.run_async(page.context.add_cookies)(auth_config["cookies"])
                logger.info(f"[NavigationProcessor] 已从凭证注入 {len(auth_config['cookies'])} 个Cookie到浏览器上下文")
            
            # 应用Header
            if auth_config["headers"]:
                ui_manager.run_async(page.set_extra_http_headers)(auth_config["headers"])
                logger.info(f"[NavigationProcessor] 已从凭证注入请求头: {list(auth_config['headers'].keys())}")
            
            # 应用localStorage（使用BrowserContext.add_init_script）
            if auth_config["local_storage"]:
                storage_items = []
                for key, value in auth_config["local_storage"].items():
                    rendered_key = context.render_string(key) if isinstance(key, str) else str(key)
                    rendered_value = context.render_string(value) if isinstance(value, str) else str(value)
                    key_json = json.dumps(rendered_key)
                    value_json = json.dumps(rendered_value)
                    storage_items.append(f"localStorage.setItem({key_json}, {value_json});")
                
                if storage_items:
                    init_script = "".join(storage_items)
                    ui_manager.run_async(page.context.add_init_script)(init_script)
                    logger.info(f"[NavigationProcessor] 已从凭证注入localStorage初始化脚本({len(auth_config['local_storage'])}项)")
            
            # 应用sessionStorage（使用BrowserContext.add_init_script）
            if auth_config["session_storage"]:
                storage_items = []
                for key, value in auth_config["session_storage"].items():
                    rendered_key = context.render_string(key) if isinstance(key, str) else str(key)
                    rendered_value = context.render_string(value) if isinstance(value, str) else str(value)
                    key_json = json.dumps(rendered_key)
                    value_json = json.dumps(rendered_value)
                    storage_items.append(f"sessionStorage.setItem({key_json}, {value_json});")
                
                if storage_items:
                    init_script = "".join(storage_items)
                    ui_manager.run_async(page.context.add_init_script)(init_script)
                    logger.info(f"[NavigationProcessor] 已从凭证注入sessionStorage初始化脚本({len(auth_config['session_storage'])}项)")
            
        except Exception as e:
            logger.error(f"[NavigationProcessor] 应用凭证失败: {str(e)}")
            raise
