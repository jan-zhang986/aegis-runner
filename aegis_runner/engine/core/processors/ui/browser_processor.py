# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName
@className BrowserProcessor
@describe 浏览器处理器 - 处理浏览器启动、关闭等生命周期操作
"""

import json
import time
from typing import Dict, Any
from aegis_runner.engine.context import ExecutionContext
from .base_ui_processor import BaseUIProcessor
from aegis_runner.engine.core.simple_logger import logger
from aegis_runner.engine.core.ui.playwright.ui_manager import ui_manager


class BrowserProcessor(BaseUIProcessor):
    """浏览器处理器"""
    
    def __init__(self):
        super().__init__()
        self.browser_operations = {
            "launch": "启动浏览器",
            "close": "关闭浏览器",
            "new_page": "创建新页面",
            "switch_page": "切换页面",
            "new_context": "创建新上下文（用于多网站隔离）",
            "switch_context": "切换上下文",
            "close_context": "关闭上下文",
            "list_contexts": "列出所有上下文"
        }
    
    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> Any:
        """执行浏览器操作"""
        config = node_info.get("data", {}).get("config", {})
        operation = config.get("operation", "launch")
        
        logger.info(f"[BrowserProcessor] 执行浏览器操作: {operation}")
        
        # 根据操作类型分发处理
        if operation == "launch":
            return self._handle_launch(config, context)
        elif operation == "close":
            return self._handle_close(config, context)
        elif operation == "new_page":
            return self._handle_new_page(config, context)
        elif operation == "switch_page":
            return self._handle_switch_page(config, context)
        elif operation == "new_context":
            return self._handle_new_context(config, context)
        elif operation == "switch_context":
            return self._handle_switch_context(config, context)
        elif operation == "close_context":
            return self._handle_close_context(config, context)
        elif operation == "list_contexts":
            return self._handle_list_contexts(config, context)
        else:
            raise ValueError(f"不支持的浏览器操作: {operation}")
    
    def _handle_launch(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理浏览器启动"""
        browser_type = config.get("browser_type", "chromium")
        headless = config.get("headless", False)
        viewport = config.get("viewport", {"width": 1920, "height": 1080})
        slow_mo = config.get("slow_mo", 0)
        args = config.get("args", [])
        
        try:
            # 调用UI管理器启动浏览器
            result = ui_manager.run_async(ui_manager.launch_browser)({
                "browser_type": browser_type,
                "headless": headless,
                "viewport": viewport,
                "slow_mo": slow_mo,
                "args": args
            })
            
            logger.info(f"[BrowserProcessor] 浏览器启动结果: {result['status']}")
            
            return {
                "status": result["status"],
                "operation": "launch",
                "browser_type": browser_type,
                "headless": headless,
                "viewport": viewport,
                "slow_mo": slow_mo,
                "args": args,
                "result": result,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[BrowserProcessor] 浏览器启动失败: {str(e)}")
            return {
                "status": "error",
                "operation": "launch",
                "browser_type": browser_type,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _handle_close(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理浏览器关闭"""
        try:
            # 调用UI管理器关闭浏览器
            result = ui_manager.run_async(ui_manager.close_browser)()
            
            logger.info(f"[BrowserProcessor] 浏览器关闭结果: {result['status']}")
            
            return {
                "status": result["status"],
                "operation": "close",
                "result": result,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[BrowserProcessor] 浏览器关闭失败: {str(e)}")
            return {
                "status": "error",
                "operation": "close",
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _validate_ui_config(self, config: Dict[str, Any]) -> bool:
        """验证UI特定配置"""
        # 基础验证，子类可以重写
        return True
    
        
    
    def _handle_new_page(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理创建新页面"""
        page_id = config.get("page_id")
        
        try:
            # 调用UI管理器创建新页面
            result = ui_manager.run_async(ui_manager.new_page)(page_id)
            
            logger.info(f"[BrowserProcessor] 创建新页面结果: {result['status']}")
            
            return {
                "status": result["status"],
                "operation": "new_page",
                "page_id": result.get("page_id"),
                "result": result,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[BrowserProcessor] 创建新页面失败: {str(e)}")
            return {
                "status": "error",
                "operation": "new_page",
                "page_id": page_id,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _handle_switch_page(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理切换页面"""
        page_id = config.get("page_id", "default")
        
        try:
            # 调用UI管理器切换页面
            result = ui_manager.switch_page(page_id)
            
            logger.info(f"[BrowserProcessor] 切换页面结果: {result['status']}")
            
            return {
                "status": result["status"],
                "operation": "switch_page",
                "page_id": page_id,
                "result": result,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[BrowserProcessor] 切换页面失败: {str(e)}")
            return {
                "status": "error",
                "operation": "switch_page",
                "page_id": page_id,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _handle_new_context(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理创建新上下文"""
        context_id = config.get("context_id")
        if not context_id:
            raise ValueError("创建上下文需要提供context_id")
        
        context_config = config.get("context_config", {})
        
        try:
            # 调用UI管理器创建新上下文
            result = ui_manager.run_async(ui_manager.new_context)(context_id, context_config)
            
            logger.info(f"[BrowserProcessor] 创建上下文结果: {result['status']}")
            
            return {
                "status": result["status"],
                "operation": "new_context",
                "context_id": context_id,
                "context_config": context_config,
                "result": result,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[BrowserProcessor] 创建上下文失败: {str(e)}")
            return {
                "status": "error",
                "operation": "new_context",
                "context_id": context_id,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _handle_switch_context(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理切换上下文"""
        context_id = config.get("context_id")
        if not context_id:
            raise ValueError("切换上下文需要提供context_id")
        
        try:
            # 调用UI管理器切换上下文
            result = ui_manager.switch_context(context_id)
            
            logger.info(f"[BrowserProcessor] 切换上下文结果: {result['status']}")
            
            return {
                "status": result["status"],
                "operation": "switch_context",
                "context_id": context_id,
                "result": result,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[BrowserProcessor] 切换上下文失败: {str(e)}")
            return {
                "status": "error",
                "operation": "switch_context",
                "context_id": context_id,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _handle_close_context(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理关闭上下文"""
        context_id = config.get("context_id")
        if not context_id:
            raise ValueError("关闭上下文需要提供context_id")
        
        try:
            # 调用UI管理器关闭上下文
            result = ui_manager.run_async(ui_manager.close_context)(context_id)
            
            logger.info(f"[BrowserProcessor] 关闭上下文结果: {result['status']}")
            
            return {
                "status": result["status"],
                "operation": "close_context",
                "context_id": context_id,
                "result": result,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[BrowserProcessor] 关闭上下文失败: {str(e)}")
            return {
                "status": "error",
                "operation": "close_context",
                "context_id": context_id,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _handle_list_contexts(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理列出所有上下文"""
        try:
            # 获取所有上下文ID
            context_ids = ui_manager.list_contexts()
            
            logger.info(f"[BrowserProcessor] 当前有 {len(context_ids)} 个上下文")
            
            return {
                "status": "success",
                "operation": "list_contexts",
                "context_ids": context_ids,
                "count": len(context_ids),
                "current_context_id": ui_manager.current_context_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[BrowserProcessor] 列出上下文失败: {str(e)}")
            return {
                "status": "error",
                "operation": "list_contexts",
                "error": str(e),
                "timestamp": time.time()
            }
