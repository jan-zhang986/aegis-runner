# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-10-03
@packageName src.ui.core
@className UIManager
@describe UI自动化管理器 - 负责浏览器和页面的生命周期管理
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from src.engine.core.simple_logger import logger


class UIManager:
    """UI自动化管理器"""
    
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.contexts: Dict[str, BrowserContext] = {}  # 支持多上下文管理（每个网站独立）
        self.pages: Dict[str, Page] = {}  # 页面管理：{page_id: Page}
        self.page_to_context: Dict[str, str] = {}  # 页面到上下文的映射：{page_id: context_id}
        self.context = None  # 当前上下文（向后兼容）
        self.current_page_id = "default"
        self.current_context_id = "default"  # 当前上下文ID
        self.is_initialized = False
    
    async def initialize(self, config: Dict[str, Any] = None):
        """初始化Playwright"""
        if self.is_initialized:
            return
        
        try:
            self.playwright = await async_playwright().start()
            logger.info("[UIManager] Playwright初始化成功")
            self.is_initialized = True
        except Exception as e:
            logger.error(f"[UIManager] Playwright初始化失败: {str(e)}")
            raise
    
    async def launch_browser(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        启动浏览器
        
        Args:
            config: 浏览器配置
                {
                    "browser_type": "chromium",  # chromium, firefox, webkit
                    "headless": False,
                    "viewport": {"width": 1920, "height": 1080},
                    "slow_mo": 0,
                    "args": ["--disable-web-security"]
                }
        
        Returns:
            启动结果信息
        """
        if not self.is_initialized:
            await self.initialize()
        
        config = config or {}
        browser_type = config.get("browser_type", "chromium").lower()
        headless = config.get("headless", False)
        viewport = config.get("viewport", {"width": 1920, "height": 1080})
        slow_mo = config.get("slow_mo", 0)
        args = config.get("args", [])
        
        try:
            # 选择浏览器类型
            if browser_type == "chromium":
                browser_launcher = self.playwright.chromium
            elif browser_type == "firefox":
                browser_launcher = self.playwright.firefox
            elif browser_type == "webkit":
                browser_launcher = self.playwright.webkit
            else:
                raise ValueError(f"不支持的浏览器类型: {browser_type}")
            
            # 启动浏览器
            self.browser = await browser_launcher.launch(
                headless=headless,
                slow_mo=slow_mo,
                args=args
            )
            
            # 创建默认浏览器上下文
            default_context = await self.browser.new_context(
                viewport=viewport,
                ignore_https_errors=True,
                accept_downloads=True
            )
            self.contexts["default"] = default_context
            self.context = default_context  # 向后兼容
            self.current_context_id = "default"
            
            # 创建默认页面
            default_page = await default_context.new_page()
            self.pages["default"] = default_page
            self.page_to_context["default"] = "default"
            self.current_page_id = "default"
            
            logger.info(f"[UIManager] 浏览器启动成功: {browser_type}, headless={headless}")
            
            return {
                "status": "success",
                "browser_type": browser_type,
                "headless": headless,
                "viewport": viewport,
                "page_id": "default",
                "message": "浏览器启动成功"
            }
            
        except Exception as e:
            logger.error(f"[UIManager] 浏览器启动失败: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "浏览器启动失败"
            }
    
    async def close_browser(self) -> Dict[str, Any]:
        """关闭浏览器（关闭所有上下文）"""
        try:
            if self.browser:
                # 关闭所有上下文
                for context_id, context in self.contexts.items():
                    try:
                        await context.close()
                        logger.debug(f"[UIManager] 已关闭上下文: {context_id}")
                    except Exception as e:
                        logger.warning(f"[UIManager] 关闭上下文失败 {context_id}: {str(e)}")
                
                await self.browser.close()
                self.browser = None
                self.contexts.clear()
                self.context = None
                self.pages.clear()
                self.page_to_context.clear()
                self.current_page_id = "default"
                self.current_context_id = "default"
                logger.info("[UIManager] 浏览器关闭成功")
                
                return {
                    "status": "success",
                    "message": "浏览器关闭成功"
                }
            else:
                return {
                    "status": "warning",
                    "message": "浏览器未启动"
                }
        except Exception as e:
            logger.error(f"[UIManager] 浏览器关闭失败: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "浏览器关闭失败"
            }
    
    async def new_page(self, page_id: str = None, context_id: str = None) -> Dict[str, Any]:
        """
        创建新页面
        
        Args:
            page_id: 页面ID（可选，自动生成）
            context_id: 上下文ID（可选，使用当前上下文）
        """
        if not self.browser:
            return {
                "status": "error",
                "error": "浏览器未启动",
                "message": "请先启动浏览器"
            }
        
        try:
            # 获取或使用指定的上下文
            target_context_id = context_id or self.current_context_id
            target_context = self.contexts.get(target_context_id)
            
            if not target_context:
                # 如果上下文不存在，使用默认上下文
                target_context_id = "default"
                target_context = self.contexts.get("default")
                if not target_context:
                    return {
                        "status": "error",
                        "error": "浏览器上下文不存在",
                        "message": "请先启动浏览器"
                    }
            
            page_id = page_id or f"page_{int(time.time())}"
            page = await target_context.new_page()
            self.pages[page_id] = page
            self.page_to_context[page_id] = target_context_id
            
            logger.info(f"[UIManager] 创建新页面: {page_id} (上下文: {target_context_id})")
            
            return {
                "status": "success",
                "page_id": page_id,
                "context_id": target_context_id,
                "message": f"页面 {page_id} 创建成功"
            }
        except Exception as e:
            logger.error(f"[UIManager] 创建页面失败: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "创建页面失败"
            }
    
    def switch_page(self, page_id: str) -> Dict[str, Any]:
        """切换当前页面"""
        if page_id in self.pages:
            self.current_page_id = page_id
            logger.info(f"[UIManager] 切换到页面: {page_id}")
            return {
                "status": "success",
                "page_id": page_id,
                "message": f"已切换到页面 {page_id}"
            }
        else:
            return {
                "status": "error",
                "error": f"页面 {page_id} 不存在",
                "message": "页面切换失败"
            }
    
    def get_current_page(self) -> Optional[Page]:
        """获取当前页面"""
        return self.pages.get(self.current_page_id)
    
    def get_page(self, page_id: str) -> Optional[Page]:
        """获取指定页面"""
        return self.pages.get(page_id)
    
    async def new_context(self, context_id: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        创建新的浏览器上下文（用于隔离不同网站）
        
        Args:
            context_id: 上下文ID（例如：网站域名或自定义名称）
            config: 上下文配置
                {
                    "viewport": {"width": 1920, "height": 1080},
                    "user_agent": "custom user agent",
                    "locale": "zh-CN",
                    "timezone_id": "Asia/Shanghai"
                }
        
        Returns:
            创建结果信息
        """
        if not self.browser:
            return {
                "status": "error",
                "error": "浏览器未启动",
                "message": "请先启动浏览器"
            }
        
        if context_id in self.contexts:
            logger.warning(f"[UIManager] 上下文 {context_id} 已存在，返回现有上下文")
            return {
                "status": "success",
                "context_id": context_id,
                "message": f"上下文 {context_id} 已存在",
                "existing": True
            }
        
        try:
            config = config or {}
            viewport = config.get("viewport", {"width": 1920, "height": 1080})
            user_agent = config.get("user_agent")
            locale = config.get("locale", "zh-CN")
            timezone_id = config.get("timezone_id")
            
            context_options = {
                "viewport": viewport,
                "ignore_https_errors": True,
                "accept_downloads": True,
                "locale": locale
            }
            
            if user_agent:
                context_options["user_agent"] = user_agent
            if timezone_id:
                context_options["timezone_id"] = timezone_id
            
            # 创建新上下文
            new_context = await self.browser.new_context(**context_options)
            self.contexts[context_id] = new_context
            
            # 创建默认页面
            default_page = await new_context.new_page()
            page_id = f"{context_id}_page"
            self.pages[page_id] = default_page
            self.page_to_context[page_id] = context_id
            
            logger.info(f"[UIManager] 创建新上下文: {context_id}")
            
            return {
                "status": "success",
                "context_id": context_id,
                "page_id": page_id,
                "message": f"上下文 {context_id} 创建成功"
            }
        except Exception as e:
            logger.error(f"[UIManager] 创建上下文失败: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "创建上下文失败"
            }
    
    def switch_context(self, context_id: str) -> Dict[str, Any]:
        """
        切换到指定的浏览器上下文
        
        Args:
            context_id: 上下文ID
        
        Returns:
            切换结果信息
        """
        if context_id not in self.contexts:
            return {
                "status": "error",
                "error": f"上下文 {context_id} 不存在",
                "message": "上下文切换失败"
            }
        
        self.current_context_id = context_id
        self.context = self.contexts[context_id]
        
        # 切换到该上下文的第一个页面
        for page_id, ctx_id in self.page_to_context.items():
            if ctx_id == context_id:
                self.current_page_id = page_id
                break
        
        logger.info(f"[UIManager] 切换到上下文: {context_id}")
        
        return {
            "status": "success",
            "context_id": context_id,
            "page_id": self.current_page_id,
            "message": f"已切换到上下文 {context_id}"
        }
    
    def get_context(self, context_id: str = None) -> Optional[BrowserContext]:
        """
        获取指定的浏览器上下文
        
        Args:
            context_id: 上下文ID（可选，默认当前上下文）
        
        Returns:
            浏览器上下文对象
        """
        target_context_id = context_id or self.current_context_id
        return self.contexts.get(target_context_id)
    
    def get_context_by_url(self, url: str) -> Optional[BrowserContext]:
        """
        根据URL自动获取或创建上下文
        
        Args:
            url: 目标URL
        
        Returns:
            浏览器上下文对象
        """
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace("www.", "").split(":")[0]
        
        # 使用域名作为上下文ID（简化版，可以改进）
        context_id = domain.replace(".", "_")
        
        # 如果上下文不存在，返回None（由调用者决定是否创建）
        return self.contexts.get(context_id)
    
    async def get_or_create_context_for_url(self, url: str, config: Dict[str, Any] = None) -> BrowserContext:
        """
        根据URL获取或创建上下文
        
        Args:
            url: 目标URL
            config: 上下文配置
        
        Returns:
            浏览器上下文对象
        """
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace("www.", "").split(":")[0]
        context_id = domain.replace(".", "_")
        
        # 如果上下文已存在，直接返回
        if context_id in self.contexts:
            logger.debug(f"[UIManager] 使用现有上下文: {context_id}")
            return self.contexts[context_id]
        
        # 创建新上下文
        result = await self.new_context(context_id, config)
        if result["status"] == "success":
            return self.contexts[context_id]
        else:
            # 创建失败，返回默认上下文
            logger.warning(f"[UIManager] 创建上下文失败，使用默认上下文: {result.get('error')}")
            return self.contexts.get("default")
    
    def list_contexts(self) -> List[str]:
        """列出所有上下文ID"""
        return list(self.contexts.keys())
    
    async def close_context(self, context_id: str) -> Dict[str, Any]:
        """
        关闭指定的浏览器上下文
        
        Args:
            context_id: 上下文ID
        
        Returns:
            关闭结果信息
        """
        if context_id not in self.contexts:
            return {
                "status": "error",
                "error": f"上下文 {context_id} 不存在",
                "message": "上下文关闭失败"
            }
        
        if context_id == "default":
            return {
                "status": "error",
                "error": "不能关闭默认上下文",
                "message": "请使用close_browser关闭所有上下文"
            }
        
        try:
            context = self.contexts[context_id]
            await context.close()
            del self.contexts[context_id]
            
            # 清理相关页面
            pages_to_remove = [page_id for page_id, ctx_id in self.page_to_context.items() if ctx_id == context_id]
            for page_id in pages_to_remove:
                del self.pages[page_id]
                del self.page_to_context[page_id]
            
            # 如果关闭的是当前上下文，切换到默认上下文
            if self.current_context_id == context_id:
                self.switch_context("default")
            
            logger.info(f"[UIManager] 上下文 {context_id} 已关闭")
            
            return {
                "status": "success",
                "context_id": context_id,
                "message": f"上下文 {context_id} 关闭成功"
            }
        except Exception as e:
            logger.error(f"[UIManager] 关闭上下文失败: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "上下文关闭失败"
            }
    
    async def cleanup(self):
        """清理资源"""
        try:
            if self.browser:
                await self.close_browser()
            if self.playwright:
                await self.playwright.stop()
            logger.info("[UIManager] 资源清理完成")
        except Exception as e:
            logger.error(f"[UIManager] 资源清理失败: {str(e)}")


# 全局UI管理器实例
ui_manager = UIManager()


def run_async(func):
    """运行异步函数的装饰器"""
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，使用线程池执行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(func(*args, **kwargs)))
                    return future.result()
            else:
                return loop.run_until_complete(func(*args, **kwargs))
        except RuntimeError:
            return asyncio.run(func(*args, **kwargs))
    return wrapper


# 为UIManager添加run_async方法
UIManager.run_async = staticmethod(run_async)
