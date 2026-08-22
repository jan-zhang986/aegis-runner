# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-30
@packageName src.core.processors.ui
@className UIObservabilityProcessor
@describe UI可观测性处理器 - 提供诊断信息收集和监控能力
"""

import json
import time
import os
from typing import Dict, Any, List, Optional
from playwright.async_api import Page
from aegis_runner.engine.context import ExecutionContext
from .base_ui_processor import BaseUIProcessor
from aegis_runner.engine.core.simple_logger import logger
from aegis_runner.engine.core.ui.playwright.ui_manager import ui_manager


class UIObservabilityProcessor(BaseUIProcessor):
    """UI可观测性处理器"""
    
    def __init__(self):
        super().__init__()
        self.diagnostic_dir = "diagnostic_data"
        self.console_logs = []
        self.network_requests = []
        self.performance_metrics = []
        
        # 确保诊断目录存在
        os.makedirs(self.diagnostic_dir, exist_ok=True)
    
    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> Any:
        """执行可观测性操作"""
        config = node_info.get("data", {}).get("config", {})
        operation = config.get("operation", "capture_diagnostic")
        
        logger.info(f"[ObservabilityProcessor] 执行可观测性操作: {operation}")
        
        # 根据操作类型分发处理
        if operation == "capture_diagnostic":
            return self._handle_capture_diagnostic(config, context)
        elif operation == "start_monitoring":
            return self._handle_start_monitoring(config, context)
        elif operation == "stop_monitoring":
            return self._handle_stop_monitoring(config, context)
        elif operation == "get_console_logs":
            return self._handle_get_console_logs(config, context)
        elif operation == "get_network_requests":
            return self._handle_get_network_requests(config, context)
        elif operation == "get_performance_metrics":
            return self._handle_get_performance_metrics(config, context)
        elif operation == "save_diagnostic_report":
            return self._handle_save_diagnostic_report(config, context)
        else:
            raise ValueError(f"不支持的可观测性操作: {operation}")
    
    def _handle_capture_diagnostic(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """捕获完整的诊断信息"""
        page_id = config.get("page_id", "default")
        node_id = config.get("node_id", "unknown")
        capture_screenshot = config.get("capture_screenshot", True)
        capture_dom = config.get("capture_dom", True)
        capture_console = config.get("capture_console", True)
        capture_network = config.get("capture_network", True)
        capture_performance = config.get("capture_performance", True)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            diagnostic_info = {
                "node_id": node_id,
                "page_id": page_id,
                "timestamp": time.time(),
                "url": None,
                "title": None
            }
            
            # 基本页面信息
            diagnostic_info["url"] = page.url
            diagnostic_info["title"] = ui_manager.run_async(page.title)()
            
            # 截图
            if capture_screenshot:
                screenshot_path = f"{self.diagnostic_dir}/{node_id}_{int(time.time())}.png"
                ui_manager.run_async(page.screenshot)(path=screenshot_path, full_page=True)
                diagnostic_info["screenshot_path"] = screenshot_path
                logger.info(f"[ObservabilityProcessor] 截图已保存: {screenshot_path}")
            
            # DOM快照
            if capture_dom:
                dom_content = ui_manager.run_async(page.content)()
                dom_path = f"{self.diagnostic_dir}/{node_id}_{int(time.time())}.html"
                with open(dom_path, 'w', encoding='utf-8') as f:
                    f.write(dom_content)
                diagnostic_info["dom_path"] = dom_path
                diagnostic_info["dom_size"] = len(dom_content)
                logger.info(f"[ObservabilityProcessor] DOM已保存: {dom_path}")
            
            # 控制台日志
            if capture_console:
                console_logs = self._get_console_logs_sync(page)
                diagnostic_info["console_logs"] = console_logs
                diagnostic_info["console_log_count"] = len(console_logs)
            
            # 网络请求
            if capture_network:
                network_requests = self._get_network_requests_sync(page)
                diagnostic_info["network_requests"] = network_requests
                diagnostic_info["network_request_count"] = len(network_requests)
            
            # 性能指标
            if capture_performance:
                performance_metrics = self._get_performance_metrics_sync(page)
                diagnostic_info["performance_metrics"] = performance_metrics
            
            logger.info(f"[ObservabilityProcessor] 诊断信息捕获完成: {node_id}")
            
            return {
                "status": "success",
                "operation": "capture_diagnostic",
                "diagnostic_info": diagnostic_info,
                "message": "诊断信息捕获成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ObservabilityProcessor] 捕获诊断信息失败: {str(e)}")
            return {
                "status": "error",
                "operation": "capture_diagnostic",
                "node_id": node_id,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _handle_start_monitoring(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """开始监控"""
        page_id = config.get("page_id", "default")
        monitor_types = config.get("monitor_types", ["console", "network", "performance"])
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 设置监控
            if "console" in monitor_types:
                self._setup_console_monitoring(page)
            
            if "network" in monitor_types:
                self._setup_network_monitoring(page)
            
            if "performance" in monitor_types:
                self._setup_performance_monitoring(page)
            
            logger.info(f"[ObservabilityProcessor] 监控已启动: {monitor_types}")
            
            return {
                "status": "success",
                "operation": "start_monitoring",
                "monitor_types": monitor_types,
                "page_id": page_id,
                "message": "监控启动成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ObservabilityProcessor] 启动监控失败: {str(e)}")
            return {
                "status": "error",
                "operation": "start_monitoring",
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_stop_monitoring(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """停止监控"""
        page_id = config.get("page_id", "default")
        
        try:
            # 收集所有监控数据
            monitoring_summary = {
                "console_logs_count": len(self.console_logs),
                "network_requests_count": len(self.network_requests),
                "performance_metrics_count": len(self.performance_metrics)
            }
            
            logger.info(f"[ObservabilityProcessor] 监控已停止: {monitoring_summary}")
            
            return {
                "status": "success",
                "operation": "stop_monitoring",
                "monitoring_summary": monitoring_summary,
                "page_id": page_id,
                "message": "监控停止成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ObservabilityProcessor] 停止监控失败: {str(e)}")
            return {
                "status": "error",
                "operation": "stop_monitoring",
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _handle_get_console_logs(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """获取控制台日志"""
        page_id = config.get("page_id", "default")
        level_filter = config.get("level_filter", None)  # error, warning, info, log
        limit = config.get("limit", 100)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            console_logs = self._get_console_logs_sync(page)
            
            # 过滤日志级别
            if level_filter:
                console_logs = [log for log in console_logs if log.get("level") == level_filter]
            
            # 限制数量
            console_logs = console_logs[-limit:]
            
            logger.info(f"[ObservabilityProcessor] 获取控制台日志: {len(console_logs)}条")
            
            return {
                "status": "success",
                "operation": "get_console_logs",
                "console_logs": console_logs,
                "count": len(console_logs),
                "page_id": page_id,
                "message": "获取控制台日志成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ObservabilityProcessor] 获取控制台日志失败: {str(e)}")
            return {
                "status": "error",
                "operation": "get_console_logs",
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_get_network_requests(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """获取网络请求"""
        page_id = config.get("page_id", "default")
        status_filter = config.get("status_filter", None)  # 200, 404, 500, etc.
        method_filter = config.get("method_filter", None)  # GET, POST, etc.
        limit = config.get("limit", 100)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            network_requests = self._get_network_requests_sync(page)
            
            # 过滤状态码
            if status_filter:
                network_requests = [req for req in network_requests if req.get("status") == status_filter]
            
            # 过滤请求方法
            if method_filter:
                network_requests = [req for req in network_requests if req.get("method") == method_filter]
            
            # 限制数量
            network_requests = network_requests[-limit:]
            
            logger.info(f"[ObservabilityProcessor] 获取网络请求: {len(network_requests)}个")
            
            return {
                "status": "success",
                "operation": "get_network_requests",
                "network_requests": network_requests,
                "count": len(network_requests),
                "page_id": page_id,
                "message": "获取网络请求成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ObservabilityProcessor] 获取网络请求失败: {str(e)}")
            return {
                "status": "error",
                "operation": "get_network_requests",
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_get_performance_metrics(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """获取性能指标"""
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            performance_metrics = self._get_performance_metrics_sync(page)
            
            logger.info(f"[ObservabilityProcessor] 获取性能指标成功")
            
            return {
                "status": "success",
                "operation": "get_performance_metrics",
                "performance_metrics": performance_metrics,
                "page_id": page_id,
                "message": "获取性能指标成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ObservabilityProcessor] 获取性能指标失败: {str(e)}")
            return {
                "status": "error",
                "operation": "get_performance_metrics",
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_save_diagnostic_report(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """保存诊断报告"""
        report_name = config.get("report_name", f"diagnostic_report_{int(time.time())}")
        include_all = config.get("include_all", True)
        
        try:
            report_data = {
                "report_name": report_name,
                "timestamp": time.time(),
                "summary": {
                    "console_logs_count": len(self.console_logs),
                    "network_requests_count": len(self.network_requests),
                    "performance_metrics_count": len(self.performance_metrics)
                }
            }
            
            if include_all:
                report_data["console_logs"] = self.console_logs
                report_data["network_requests"] = self.network_requests
                report_data["performance_metrics"] = self.performance_metrics
            
            # 保存报告
            report_path = f"{self.diagnostic_dir}/{report_name}.json"
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[ObservabilityProcessor] 诊断报告已保存: {report_path}")
            
            return {
                "status": "success",
                "operation": "save_diagnostic_report",
                "report_path": report_path,
                "report_name": report_name,
                "summary": report_data["summary"],
                "message": "诊断报告保存成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ObservabilityProcessor] 保存诊断报告失败: {str(e)}")
            return {
                "status": "error",
                "operation": "save_diagnostic_report",
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _setup_console_monitoring(self, page: Page):
        """设置控制台监控"""
        def on_console(msg):
            console_log = {
                "type": msg.type,
                "text": msg.text,
                "timestamp": time.time()
            }
            self.console_logs.append(console_log)
            logger.debug(f"[Console] [{msg.type}] {msg.text}")
        
        page.on("console", on_console)
    
    def _setup_network_monitoring(self, page: Page):
        """设置网络监控"""
        def on_request(request):
            self.network_requests.append({
                "type": "request",
                "method": request.method,
                "url": request.url,
                "timestamp": time.time()
            })
        
        def on_response(response):
            self.network_requests.append({
                "type": "response",
                "method": response.request.method,
                "url": response.url,
                "status": response.status,
                "timestamp": time.time()
            })
        
        page.on("request", on_request)
        page.on("response", on_response)
    
    def _setup_performance_monitoring(self, page: Page):
        """设置性能监控"""
        # 性能监控通过定期采样实现
        pass
    
    def _get_console_logs_sync(self, page: Page) -> List[Dict[str, Any]]:
        """同步获取控制台日志"""
        try:
            # 从页面中提取控制台日志（如果浏览器支持）
            logs = ui_manager.run_async(page.evaluate)("""
                () => {
                    if (window.__console_logs__) {
                        return window.__console_logs__;
                    }
                    return [];
                }
            """)
            return logs or self.console_logs
        except:
            return self.console_logs
    
    def _get_network_requests_sync(self, page: Page) -> List[Dict[str, Any]]:
        """同步获取网络请求"""
        try:
            # 从页面中提取网络请求（如果浏览器支持）
            requests = ui_manager.run_async(page.evaluate)("""
                () => {
                    if (window.performance && window.performance.getEntriesByType) {
                        const entries = window.performance.getEntriesByType('resource');
                        return entries.map(entry => ({
                            name: entry.name,
                            type: entry.initiatorType,
                            duration: entry.duration,
                            size: entry.transferSize
                        }));
                    }
                    return [];
                }
            """)
            return requests or self.network_requests
        except:
            return self.network_requests
    
    def _get_performance_metrics_sync(self, page: Page) -> Dict[str, Any]:
        """同步获取性能指标"""
        try:
            metrics = ui_manager.run_async(page.evaluate)("""
                () => {
                    if (!window.performance || !window.performance.timing) {
                        return {};
                    }
                    
                    const timing = window.performance.timing;
                    const navigation = window.performance.navigation;
                    
                    return {
                        // 页面加载时间
                        dns_time: timing.domainLookupEnd - timing.domainLookupStart,
                        tcp_time: timing.connectEnd - timing.connectStart,
                        request_time: timing.responseStart - timing.requestStart,
                        response_time: timing.responseEnd - timing.responseStart,
                        dom_processing_time: timing.domComplete - timing.domLoading,
                        load_event_time: timing.loadEventEnd - timing.loadEventStart,
                        total_time: timing.loadEventEnd - timing.navigationStart,
                        
                        // 导航类型
                        navigation_type: navigation.type,
                        redirect_count: navigation.redirectCount,
                        
                        // 关键时间点
                        dom_interactive: timing.domInteractive - timing.navigationStart,
                        dom_content_loaded: timing.domContentLoadedEventEnd - timing.navigationStart,
                        dom_complete: timing.domComplete - timing.navigationStart,
                        load_complete: timing.loadEventEnd - timing.navigationStart
                    };
                }
            """)
            return metrics
        except Exception as e:
            logger.warning(f"[ObservabilityProcessor] 获取性能指标失败: {str(e)}")
            return {}
    
    def _validate_ui_config(self, config: Dict[str, Any]) -> bool:
        """验证UI特定配置"""
        return True

