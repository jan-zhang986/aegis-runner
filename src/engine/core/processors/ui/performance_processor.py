# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-30
@packageName src.core.processors.ui
@className UIPerformanceProcessor
@describe UI性能监控处理器 - 提供页面性能分析和监控能力
"""

import time
import json
import os
from typing import Dict, Any, List, Optional
from playwright.async_api import Page
from src.engine.context import ExecutionContext
from .base_ui_processor import BaseUIProcessor
from src.engine.core.simple_logger import logger
from src.engine.core.ui.playwright.ui_manager import ui_manager


class UIPerformanceProcessor(BaseUIProcessor):
    """UI性能监控处理器"""
    
    def __init__(self):
        super().__init__()
        self.performance_dir = "performance_data"
        self.performance_reports = []
        
        # 性能阈值（毫秒）
        self.thresholds = {
            "page_load": 3000,      # 页面加载时间
            "first_paint": 1000,    # 首次渲染
            "dom_ready": 2000,      # DOM就绪
            "fully_loaded": 5000    # 完全加载
        }
        
        # 确保目录存在
        os.makedirs(self.performance_dir, exist_ok=True)
    
    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> Any:
        """执行性能监控操作"""
        config = node_info.get("data", {}).get("config", {})
        operation = config.get("operation", "measure_page_load")
        
        logger.info(f"[PerformanceProcessor] 执行性能监控: {operation}")
        
        # 根据操作类型分发处理
        if operation == "measure_page_load":
            return self._handle_measure_page_load(config, context)
        elif operation == "get_performance_metrics":
            return self._handle_get_performance_metrics(config, context)
        elif operation == "monitor_network_timing":
            return self._handle_monitor_network_timing(config, context)
        elif operation == "analyze_resource_loading":
            return self._handle_analyze_resource_loading(config, context)
        elif operation == "measure_interaction_time":
            return self._handle_measure_interaction_time(config, context)
        elif operation == "get_lighthouse_metrics":
            return self._handle_get_lighthouse_metrics(config, context)
        elif operation == "generate_performance_report":
            return self._handle_generate_performance_report(config, context)
        else:
            raise ValueError(f"不支持的性能监控操作: {operation}")
    
    def _handle_measure_page_load(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """测量页面加载性能"""
        url = context.render_string(config.get("url", ""))
        page_id = config.get("page_id", "default")
        wait_until = config.get("wait_until", "networkidle")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 记录开始时间
            start_time = time.time()
            
            # 导航到页面
            ui_manager.run_async(page.goto)(url, wait_until=wait_until)
            
            # 记录结束时间
            end_time = time.time()
            navigation_time = (end_time - start_time) * 1000  # 转换为毫秒
            
            # 获取性能指标
            performance_metrics = ui_manager.run_async(page.evaluate)("""
                () => {
                    if (!window.performance || !window.performance.timing) {
                        return null;
                    }
                    
                    const timing = window.performance.timing;
                    const navigationStart = timing.navigationStart;
                    
                    return {
                        // DNS查询时间
                        dns_time: timing.domainLookupEnd - timing.domainLookupStart,
                        
                        // TCP连接时间
                        tcp_time: timing.connectEnd - timing.connectStart,
                        
                        // SSL握手时间
                        ssl_time: timing.secureConnectionStart > 0 ? 
                            timing.connectEnd - timing.secureConnectionStart : 0,
                        
                        // 请求时间
                        request_time: timing.responseStart - timing.requestStart,
                        
                        // 响应时间
                        response_time: timing.responseEnd - timing.responseStart,
                        
                        // DOM处理时间
                        dom_processing_time: timing.domComplete - timing.domLoading,
                        
                        // 页面加载事件时间
                        load_event_time: timing.loadEventEnd - timing.loadEventStart,
                        
                        // 总时间
                        total_time: timing.loadEventEnd - navigationStart,
                        
                        // 关键时间点
                        first_paint: timing.responseEnd - navigationStart,
                        dom_interactive: timing.domInteractive - navigationStart,
                        dom_content_loaded: timing.domContentLoadedEventEnd - navigationStart,
                        dom_complete: timing.domComplete - navigationStart,
                        load_complete: timing.loadEventEnd - navigationStart
                    };
                }
            """)
            
            # 检查是否超过阈值
            warnings = []
            if performance_metrics:
                if performance_metrics.get("total_time", 0) > self.thresholds["page_load"]:
                    warnings.append(f"页面加载时间超过阈值: {performance_metrics['total_time']}ms > {self.thresholds['page_load']}ms")
                
                if performance_metrics.get("first_paint", 0) > self.thresholds["first_paint"]:
                    warnings.append(f"首次渲染时间超过阈值: {performance_metrics['first_paint']}ms > {self.thresholds['first_paint']}ms")
                
                if performance_metrics.get("dom_content_loaded", 0) > self.thresholds["dom_ready"]:
                    warnings.append(f"DOM就绪时间超过阈值: {performance_metrics['dom_content_loaded']}ms > {self.thresholds['dom_ready']}ms")
            
            # 记录性能报告
            performance_report = {
                "url": url,
                "navigation_time": navigation_time,
                "performance_metrics": performance_metrics,
                "warnings": warnings,
                "timestamp": time.time()
            }
            self.performance_reports.append(performance_report)
            
            logger.info(
                f"[PerformanceProcessor] 页面加载性能: {url}, "
                f"总时间: {performance_metrics.get('total_time', navigation_time):.2f}ms"
            )
            
            return {
                "status": "success" if not warnings else "warning",
                "operation": "measure_page_load",
                "url": url,
                "navigation_time": navigation_time,
                "performance_metrics": performance_metrics,
                "warnings": warnings,
                "page_id": page_id,
                "message": "页面加载性能测量成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[PerformanceProcessor] 页面加载性能测量失败: {str(e)}")
            return {
                "status": "error",
                "operation": "measure_page_load",
                "url": url,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_get_performance_metrics(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """获取详细的性能指标"""
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 获取性能指标
            metrics = ui_manager.run_async(page.evaluate)("""
                () => {
                    const result = {
                        navigation: {},
                        resources: [],
                        memory: null,
                        paint: []
                    };
                    
                    // 导航时间
                    if (window.performance && window.performance.timing) {
                        const timing = window.performance.timing;
                        const navigationStart = timing.navigationStart;
                        
                        result.navigation = {
                            redirect: timing.redirectEnd - timing.redirectStart,
                            app_cache: timing.domainLookupStart - timing.fetchStart,
                            dns: timing.domainLookupEnd - timing.domainLookupStart,
                            tcp: timing.connectEnd - timing.connectStart,
                            request: timing.responseStart - timing.requestStart,
                            response: timing.responseEnd - timing.responseStart,
                            dom_processing: timing.domComplete - timing.domLoading,
                            load_event: timing.loadEventEnd - timing.loadEventStart,
                            total: timing.loadEventEnd - navigationStart
                        };
                    }
                    
                    // 资源时间
                    if (window.performance && window.performance.getEntriesByType) {
                        const resources = window.performance.getEntriesByType('resource');
                        result.resources = resources.map(r => ({
                            name: r.name,
                            type: r.initiatorType,
                            duration: r.duration,
                            size: r.transferSize || 0,
                            cached: r.transferSize === 0
                        }));
                    }
                    
                    // 内存使用（如果可用）
                    if (window.performance && window.performance.memory) {
                        result.memory = {
                            used: window.performance.memory.usedJSHeapSize,
                            total: window.performance.memory.totalJSHeapSize,
                            limit: window.performance.memory.jsHeapSizeLimit
                        };
                    }
                    
                    // Paint时间
                    if (window.performance && window.performance.getEntriesByType) {
                        const paints = window.performance.getEntriesByType('paint');
                        result.paint = paints.map(p => ({
                            name: p.name,
                            start_time: p.startTime
                        }));
                    }
                    
                    return result;
                }
            """)
            
            logger.info(f"[PerformanceProcessor] 性能指标获取成功")
            
            return {
                "status": "success",
                "operation": "get_performance_metrics",
                "metrics": metrics,
                "page_id": page_id,
                "message": "性能指标获取成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[PerformanceProcessor] 获取性能指标失败: {str(e)}")
            return {
                "status": "error",
                "operation": "get_performance_metrics",
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_monitor_network_timing(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """监控网络时间"""
        page_id = config.get("page_id", "default")
        url_pattern = config.get("url_pattern", "")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 获取网络时间
            network_timing = ui_manager.run_async(page.evaluate)("""
                (urlPattern) => {
                    if (!window.performance || !window.performance.getEntriesByType) {
                        return [];
                    }
                    
                    const entries = window.performance.getEntriesByType('resource');
                    const filtered = urlPattern ? 
                        entries.filter(e => e.name.includes(urlPattern)) : 
                        entries;
                    
                    return filtered.map(entry => ({
                        name: entry.name,
                        type: entry.initiatorType,
                        start_time: entry.startTime,
                        duration: entry.duration,
                        size: entry.transferSize || 0,
                        timing: {
                            dns: entry.domainLookupEnd - entry.domainLookupStart,
                            tcp: entry.connectEnd - entry.connectStart,
                            request: entry.responseStart - entry.requestStart,
                            response: entry.responseEnd - entry.responseStart
                        }
                    }));
                }
            """, url_pattern)
            
            logger.info(f"[PerformanceProcessor] 网络时间监控完成: {len(network_timing)}个请求")
            
            return {
                "status": "success",
                "operation": "monitor_network_timing",
                "network_timing": network_timing,
                "count": len(network_timing),
                "page_id": page_id,
                "message": "网络时间监控成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[PerformanceProcessor] 网络时间监控失败: {str(e)}")
            return {
                "status": "error",
                "operation": "monitor_network_timing",
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_analyze_resource_loading(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """分析资源加载"""
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 分析资源加载
            resource_analysis = ui_manager.run_async(page.evaluate)("""
                () => {
                    if (!window.performance || !window.performance.getEntriesByType) {
                        return {};
                    }
                    
                    const resources = window.performance.getEntriesByType('resource');
                    
                    // 按类型分组
                    const byType = {};
                    resources.forEach(r => {
                        const type = r.initiatorType || 'other';
                        if (!byType[type]) {
                            byType[type] = {
                                count: 0,
                                total_size: 0,
                                total_duration: 0,
                                cached_count: 0
                            };
                        }
                        byType[type].count++;
                        byType[type].total_size += r.transferSize || 0;
                        byType[type].total_duration += r.duration;
                        if (r.transferSize === 0) {
                            byType[type].cached_count++;
                        }
                    });
                    
                    // 找出最慢的资源
                    const slowest = resources
                        .sort((a, b) => b.duration - a.duration)
                        .slice(0, 10)
                        .map(r => ({
                            name: r.name,
                            type: r.initiatorType,
                            duration: r.duration,
                            size: r.transferSize || 0
                        }));
                    
                    // 找出最大的资源
                    const largest = resources
                        .sort((a, b) => (b.transferSize || 0) - (a.transferSize || 0))
                        .slice(0, 10)
                        .map(r => ({
                            name: r.name,
                            type: r.initiatorType,
                            duration: r.duration,
                            size: r.transferSize || 0
                        }));
                    
                    return {
                        by_type: byType,
                        slowest_resources: slowest,
                        largest_resources: largest,
                        total_resources: resources.length,
                        total_size: resources.reduce((sum, r) => sum + (r.transferSize || 0), 0),
                        total_duration: resources.reduce((sum, r) => sum + r.duration, 0)
                    };
                }
            """)
            
            logger.info(f"[PerformanceProcessor] 资源加载分析完成")
            
            return {
                "status": "success",
                "operation": "analyze_resource_loading",
                "resource_analysis": resource_analysis,
                "page_id": page_id,
                "message": "资源加载分析成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[PerformanceProcessor] 资源加载分析失败: {str(e)}")
            return {
                "status": "error",
                "operation": "analyze_resource_loading",
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_measure_interaction_time(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """测量交互时间"""
        action_type = config.get("action_type", "click")
        selector = context.render_string(config.get("selector", ""))
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 记录开始时间
            start_time = time.time()
            
            # 执行操作
            element = page.locator(selector)
            if action_type == "click":
                ui_manager.run_async(element.click)()
            elif action_type == "input":
                value = config.get("value", "test")
                ui_manager.run_async(element.fill)(value)
            
            # 等待页面稳定
            ui_manager.run_async(page.wait_for_load_state)("domcontentloaded")
            
            # 记录结束时间
            end_time = time.time()
            interaction_time = (end_time - start_time) * 1000  # 转换为毫秒
            
            logger.info(f"[PerformanceProcessor] 交互时间: {action_type} on {selector} = {interaction_time:.2f}ms")
            
            return {
                "status": "success",
                "operation": "measure_interaction_time",
                "action_type": action_type,
                "selector": selector,
                "interaction_time": interaction_time,
                "page_id": page_id,
                "message": "交互时间测量成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[PerformanceProcessor] 交互时间测量失败: {str(e)}")
            return {
                "status": "error",
                "operation": "measure_interaction_time",
                "action_type": action_type,
                "selector": selector,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_get_lighthouse_metrics(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """获取Lighthouse性能指标（模拟）"""
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 获取核心Web指标
            web_vitals = ui_manager.run_async(page.evaluate)("""
                () => {
                    return new Promise((resolve) => {
                        const vitals = {
                            fcp: 0,  // First Contentful Paint
                            lcp: 0,  // Largest Contentful Paint
                            fid: 0,  // First Input Delay
                            cls: 0,  // Cumulative Layout Shift
                            ttfb: 0  // Time to First Byte
                        };
                        
                        // FCP
                        const fcpEntry = performance.getEntriesByName('first-contentful-paint')[0];
                        if (fcpEntry) {
                            vitals.fcp = fcpEntry.startTime;
                        }
                        
                        // TTFB
                        if (performance.timing) {
                            vitals.ttfb = performance.timing.responseStart - performance.timing.navigationStart;
                        }
                        
                        // LCP（需要使用PerformanceObserver，这里简化处理）
                        const navigationEntry = performance.getEntriesByType('navigation')[0];
                        if (navigationEntry) {
                            vitals.lcp = navigationEntry.loadEventEnd;
                        }
                        
                        resolve(vitals);
                    });
                }
            """)
            
            logger.info(f"[PerformanceProcessor] Lighthouse指标获取成功")
            
            return {
                "status": "success",
                "operation": "get_lighthouse_metrics",
                "web_vitals": web_vitals,
                "page_id": page_id,
                "message": "Lighthouse指标获取成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[PerformanceProcessor] Lighthouse指标获取失败: {str(e)}")
            return {
                "status": "error",
                "operation": "get_lighthouse_metrics",
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_generate_performance_report(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """生成性能报告"""
        report_name = config.get("report_name", f"performance_report_{int(time.time())}")
        
        try:
            # 汇总所有性能数据
            report = {
                "report_name": report_name,
                "timestamp": time.time(),
                "summary": {
                    "total_measurements": len(self.performance_reports),
                    "average_page_load": 0,
                    "slowest_page": None,
                    "fastest_page": None
                },
                "performance_reports": self.performance_reports,
                "thresholds": self.thresholds
            }
            
            # 计算平均值和极值
            if self.performance_reports:
                load_times = [
                    r.get("performance_metrics", {}).get("total_time", 0)
                    for r in self.performance_reports
                    if r.get("performance_metrics")
                ]
                
                if load_times:
                    report["summary"]["average_page_load"] = sum(load_times) / len(load_times)
                    
                    slowest_idx = load_times.index(max(load_times))
                    fastest_idx = load_times.index(min(load_times))
                    
                    report["summary"]["slowest_page"] = self.performance_reports[slowest_idx]
                    report["summary"]["fastest_page"] = self.performance_reports[fastest_idx]
            
            # 保存报告
            report_path = os.path.join(self.performance_dir, f"{report_name}.json")
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[PerformanceProcessor] 性能报告已生成: {report_path}")
            
            return {
                "status": "success",
                "operation": "generate_performance_report",
                "report": report,
                "report_path": report_path,
                "message": "性能报告生成成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[PerformanceProcessor] 生成性能报告失败: {str(e)}")
            return {
                "status": "error",
                "operation": "generate_performance_report",
                "error": str(e),
                "timestamp": time.time()
            }
    
    def set_thresholds(self, thresholds: Dict[str, int]):
        """设置性能阈值"""
        self.thresholds.update(thresholds)
        logger.info(f"[PerformanceProcessor] 性能阈值已更新: {self.thresholds}")
    
    def get_performance_reports(self) -> List[Dict[str, Any]]:
        """获取所有性能报告"""
        return self.performance_reports
    
    def clear_performance_reports(self):
        """清除性能报告"""
        self.performance_reports.clear()
        logger.info("[PerformanceProcessor] 性能报告已清除")
    
    def _validate_ui_config(self, config: Dict[str, Any]) -> bool:
        """验证UI特定配置"""
        return True

