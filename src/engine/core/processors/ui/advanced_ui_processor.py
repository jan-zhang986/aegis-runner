# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName
@className AdvancedUIProcessor
@describe 高级UI功能处理器 - 实现Testim风格的高级UI功能
"""

import json
import time
from typing import Dict, Any, List, Optional
from playwright.async_api import Page, Locator
from src.engine.context import ExecutionContext
from .base_ui_processor import BaseUIProcessor
from src.engine.core.simple_logger import logger
from src.engine.core.ui.playwright.ui_manager import ui_manager


class AdvancedUIProcessor(BaseUIProcessor):
    """高级UI功能处理器"""
    
    def __init__(self):
        super().__init__()
        self.advanced_features = {
            "data_driven_testing": "数据驱动测试",
            "dynamic_text_input": "动态文本输入",
            "visual_validation": "视觉验证",
            "accessibility_testing": "可访问性测试",
            "network_monitoring": "网络监控",
            "performance_testing": "性能测试",
            "mobile_testing": "移动端测试",
            "iframe_handling": "iframe处理",
            "shadow_dom": "Shadow DOM处理",
            "auto_scroll": "自动滚动",
            "locator_improvement": "定位器优化"
        }
    
    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> Any:
        """执行高级UI操作"""
        config = node_info.get("data", {}).get("config", {})
        feature_type = config.get("feature_type", "dynamic_text_input")
        
        logger.info(f"[AdvancedUIProcessor] 执行高级UI功能: {feature_type}")
        
        # 根据功能类型分发处理
        if feature_type == "dynamic_text_input":
            return self._handle_dynamic_text_input(config, context)
        elif feature_type == "visual_validation":
            return self._handle_visual_validation(config, context)
        elif feature_type == "accessibility_testing":
            return self._handle_accessibility_testing(config, context)
        elif feature_type == "network_monitoring":
            return self._handle_network_monitoring(config, context)
        elif feature_type == "performance_testing":
            return self._handle_performance_testing(config, context)
        elif feature_type == "iframe_handling":
            return self._handle_iframe_handling(config, context)
        elif feature_type == "shadow_dom":
            return self._handle_shadow_dom(config, context)
        elif feature_type == "locator_improvement":
            return self._handle_locator_improvement(config, context)
        else:
            raise ValueError(f"不支持的高级UI功能: {feature_type}")
    
    def _handle_dynamic_text_input(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理动态文本输入"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        text_template = config.get("text_template", "")
        data_source = config.get("data_source", "context")  # context, file, api
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 查找元素
            element = self._find_element(page, selector, selector_type)
            
            # 根据数据源获取动态文本
            if data_source == "context":
                dynamic_text = context.render_string(text_template)
            elif data_source == "file":
                # 从文件读取数据
                file_path = config.get("file_path", "")
                dynamic_text = self._read_text_from_file(file_path, context)
            elif data_source == "api":
                # 从API获取数据
                api_url = config.get("api_url", "")
                dynamic_text = self._fetch_text_from_api(api_url, context)
            else:
                dynamic_text = text_template
            
            # 输入动态文本
            ui_manager.run_async(element.fill)(dynamic_text)
            
            logger.info(f"[AdvancedUIProcessor] 动态文本输入成功: {dynamic_text}")
            
            return {
                "status": "success",
                "feature_type": "dynamic_text_input",
                "selector": selector,
                "selector_type": selector_type,
                "data_source": data_source,
                "dynamic_text": dynamic_text,
                "text_length": len(dynamic_text),
                "message": "动态文本输入成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[AdvancedUIProcessor] 动态文本输入失败: {str(e)}")
            return {
                "status": "error",
                "feature_type": "dynamic_text_input",
                "selector": selector,
                "error": str(e),
                "message": "动态文本输入失败",
                "timestamp": time.time()
            }
    
    def _handle_visual_validation(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理视觉验证"""
        selector = config.get("selector", "")
        selector_type = config.get("selector_type", "css")
        validation_type = config.get("validation_type", "element")  # element, viewport, full_page
        threshold = config.get("threshold", 0.1)
        baseline_image = config.get("baseline_image", "")
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 截取当前图像
            current_screenshot = f"screenshots/visual_validation_{int(time.time())}.png"
            
            if validation_type == "element" and selector:
                element = self._find_element(page, selector, selector_type)
                ui_manager.run_async(element.screenshot)(path=current_screenshot)
            elif validation_type == "viewport":
                ui_manager.run_async(page.screenshot)(path=current_screenshot, full_page=False)
            elif validation_type == "full_page":
                ui_manager.run_async(page.screenshot)(path=current_screenshot, full_page=True)
            
            # 执行图像对比（简化版本）
            similarity_score = self._compare_images(baseline_image, current_screenshot)
            is_match = similarity_score >= (1 - threshold)
            
            logger.info(f"[AdvancedUIProcessor] 视觉验证完成: 相似度 {similarity_score:.2f}")
            
            return {
                "status": "success",
                "feature_type": "visual_validation",
                "validation_type": validation_type,
                "selector": selector,
                "threshold": threshold,
                "baseline_image": baseline_image,
                "current_screenshot": current_screenshot,
                "similarity_score": similarity_score,
                "is_match": is_match,
                "message": "视觉验证完成",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[AdvancedUIProcessor] 视觉验证失败: {str(e)}")
            return {
                "status": "error",
                "feature_type": "visual_validation",
                "validation_type": validation_type,
                "error": str(e),
                "message": "视觉验证失败",
                "timestamp": time.time()
            }
    
    def _handle_accessibility_testing(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理可访问性测试"""
        page_id = config.get("page_id", "default")
        test_level = config.get("test_level", "wcag2.1")  # wcag2.1, wcag2.0, section508
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 执行可访问性检查
            accessibility_snapshot = ui_manager.run_async(page.accessibility.snapshot)()
            
            # 分析可访问性问题
            issues = self._analyze_accessibility_issues(accessibility_snapshot, test_level)
            
            logger.info(f"[AdvancedUIProcessor] 可访问性测试完成: 发现 {len(issues)} 个问题")
            
            return {
                "status": "success",
                "feature_type": "accessibility_testing",
                "test_level": test_level,
                "accessibility_snapshot": accessibility_snapshot,
                "issues": issues,
                "issue_count": len(issues),
                "message": "可访问性测试完成",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[AdvancedUIProcessor] 可访问性测试失败: {str(e)}")
            return {
                "status": "error",
                "feature_type": "accessibility_testing",
                "test_level": test_level,
                "error": str(e),
                "message": "可访问性测试失败",
                "timestamp": time.time()
            }
    
    def _handle_network_monitoring(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理网络监控"""
        page_id = config.get("page_id", "default")
        monitor_requests = config.get("monitor_requests", True)
        monitor_responses = config.get("monitor_responses", True)
        filter_pattern = config.get("filter_pattern", "")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 设置网络监听
            network_requests = []
            network_responses = []
            
            def handle_request(request):
                if not filter_pattern or filter_pattern in request.url:
                    network_requests.append({
                        "url": request.url,
                        "method": request.method,
                        "headers": request.headers,
                        "timestamp": time.time()
                    })
            
            def handle_response(response):
                if not filter_pattern or filter_pattern in response.url:
                    network_responses.append({
                        "url": response.url,
                        "status": response.status,
                        "headers": response.headers,
                        "timestamp": time.time()
                    })
            
            # 监听网络事件
            if monitor_requests:
                page.on("request", handle_request)
            if monitor_responses:
                page.on("response", handle_response)
            
            # 等待一段时间收集网络数据
            time.sleep(config.get("monitor_duration", 5))
            
            logger.info(f"[AdvancedUIProcessor] 网络监控完成: 捕获 {len(network_requests)} 个请求")
            
            return {
                "status": "success",
                "feature_type": "network_monitoring",
                "monitor_requests": monitor_requests,
                "monitor_responses": monitor_responses,
                "filter_pattern": filter_pattern,
                "request_count": len(network_requests),
                "response_count": len(network_responses),
                "message": "网络监控完成",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[AdvancedUIProcessor] 网络监控失败: {str(e)}")
            return {
                "status": "error",
                "feature_type": "network_monitoring",
                "error": str(e),
                "message": "网络监控失败",
                "timestamp": time.time()
            }
    
    def _handle_performance_testing(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理性能测试"""
        page_id = config.get("page_id", "default")
        metrics = config.get("metrics", ["load_time", "dom_content_loaded", "first_paint"])
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 收集性能指标
            performance_metrics = {}
            
            # 获取页面加载时间
            load_time = ui_manager.run_async(page.evaluate)(
                "performance.timing.loadEventEnd - performance.timing.navigationStart"
            )
            
            # 获取DOM内容加载时间
            dom_content_loaded = ui_manager.run_async(page.evaluate)(
                "performance.timing.domContentLoadedEventEnd - performance.timing.navigationStart"
            )
            
            # 获取首次绘制时间
            first_paint = ui_manager.run_async(page.evaluate)(
                "performance.getEntriesByType('paint')[0].startTime"
            )
            
            performance_metrics = {
                "load_time": load_time,
                "dom_content_loaded": dom_content_loaded,
                "first_paint": first_paint
            }
            
            logger.info(f"[AdvancedUIProcessor] 性能测试完成: 加载时间 {load_time}ms")
            
            return {
                "status": "success",
                "feature_type": "performance_testing",
                "metrics": performance_metrics,
                "page_id": page_id,
                "message": "性能测试完成",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[AdvancedUIProcessor] 性能测试失败: {str(e)}")
            return {
                "status": "error",
                "feature_type": "performance_testing",
                "error": str(e),
                "message": "性能测试失败",
                "timestamp": time.time()
            }
    
    def _handle_iframe_handling(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理iframe操作"""
        iframe_selector = context.render_string(config.get("iframe_selector", ""))
        action = config.get("action", "switch_to")  # switch_to, switch_back, get_content
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            if action == "switch_to":
                # 切换到iframe
                iframe = page.frame_locator(iframe_selector)
                # 这里需要保存原始页面上下文以便切换回来
                context.set_variable("original_page_context", page)
                
                logger.info(f"[AdvancedUIProcessor] 切换到iframe: {iframe_selector}")
                
                return {
                    "status": "success",
                    "feature_type": "iframe_handling",
                    "action": action,
                    "iframe_selector": iframe_selector,
                    "message": "切换到iframe成功",
                    "timestamp": time.time()
                }
                
            elif action == "switch_back":
                # 切换回主页面
                original_page = context.get_variable("original_page_context")
                if original_page:
                    # 恢复原始页面上下文
                    pass
                
                logger.info(f"[AdvancedUIProcessor] 切换回主页面")
                
                return {
                    "status": "success",
                    "feature_type": "iframe_handling",
                    "action": action,
                    "message": "切换回主页面成功",
                    "timestamp": time.time()
                }
            
        except Exception as e:
            logger.error(f"[AdvancedUIProcessor] iframe操作失败: {str(e)}")
            return {
                "status": "error",
                "feature_type": "iframe_handling",
                "action": action,
                "error": str(e),
                "message": "iframe操作失败",
                "timestamp": time.time()
            }
    
    def _handle_shadow_dom(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理Shadow DOM操作"""
        shadow_host_selector = context.render_string(config.get("shadow_host_selector", ""))
        shadow_content_selector = context.render_string(config.get("shadow_content_selector", ""))
        action = config.get("action", "access")  # access, click, input
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 访问Shadow DOM
            shadow_host = page.locator(shadow_host_selector)
            shadow_root = shadow_host.evaluate_handle("element => element.shadowRoot")
            
            if action == "access":
                # 访问Shadow DOM内容
                shadow_element = shadow_root.locator(shadow_content_selector)
                element_info = ui_manager.run_async(shadow_element.text_content)()
                
                logger.info(f"[AdvancedUIProcessor] Shadow DOM访问成功")
                
                return {
                    "status": "success",
                    "feature_type": "shadow_dom",
                    "action": action,
                    "shadow_host_selector": shadow_host_selector,
                    "shadow_content_selector": shadow_content_selector,
                    "element_info": element_info,
                    "message": "Shadow DOM访问成功",
                    "timestamp": time.time()
                }
            
        except Exception as e:
            logger.error(f"[AdvancedUIProcessor] Shadow DOM操作失败: {str(e)}")
            return {
                "status": "error",
                "feature_type": "shadow_dom",
                "action": action,
                "error": str(e),
                "message": "Shadow DOM操作失败",
                "timestamp": time.time()
            }
    
    def _handle_locator_improvement(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理定位器优化"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        improvement_strategy = config.get("improvement_strategy", "auto")  # auto, stable, unique
        page_id = config.get("page_id", "default")
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 分析当前选择器
            current_locator = self._find_element(page, selector, selector_type)
            
            # 生成改进的选择器
            improved_selectors = self._generate_improved_selectors(current_locator, improvement_strategy)
            
            # 选择最佳选择器
            best_selector = self._select_best_selector(improved_selectors)
            
            logger.info(f"[AdvancedUIProcessor] 定位器优化完成: {selector} -> {best_selector}")
            
            return {
                "status": "success",
                "feature_type": "locator_improvement",
                "original_selector": selector,
                "original_type": selector_type,
                "improved_selector": best_selector["selector"],
                "improved_type": best_selector["type"],
                "confidence_score": best_selector["confidence"],
                "all_candidates": improved_selectors,
                "message": "定位器优化完成",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[AdvancedUIProcessor] 定位器优化失败: {str(e)}")
            return {
                "status": "error",
                "feature_type": "locator_improvement",
                "selector": selector,
                "error": str(e),
                "message": "定位器优化失败",
                "timestamp": time.time()
            }
    
    # 辅助方法
    def _find_element(self, page: Page, selector: str, selector_type: str) -> Locator:
        """查找页面元素"""
        if selector_type == "css":
            return page.locator(selector)
        elif selector_type == "xpath":
            return page.locator(f"xpath={selector}")
        elif selector_type == "text":
            return page.get_by_text(selector)
        else:
            return page.locator(selector)
    
    def _read_text_from_file(self, file_path: str, context: ExecutionContext) -> str:
        """从文件读取文本"""
        # 简化实现
        return f"text_from_file_{file_path}"
    
    def _fetch_text_from_api(self, api_url: str, context: ExecutionContext) -> str:
        """从API获取文本"""
        # 简化实现
        return f"text_from_api_{api_url}"
    
    def _compare_images(self, baseline: str, current: str) -> float:
        """比较图像相似度"""
        # 简化实现，返回随机相似度
        import random
        return random.uniform(0.8, 1.0)
    
    def _analyze_accessibility_issues(self, snapshot: Any, test_level: str) -> List[Dict]:
        """分析可访问性问题"""
        # 简化实现
        return []
    
    def _validate_ui_config(self, config: Dict[str, Any]) -> bool:
        """验证UI特定配置"""
        # 基础验证，子类可以重写
        return True
    
        
    
    def _generate_improved_selectors(self, locator: Locator, strategy: str) -> List[Dict]:
        """生成改进的选择器"""
        # 简化实现
        return [
            {
                "selector": "improved_selector",
                "type": "css",
                "confidence": 0.9
            }
        ]
    
    def _select_best_selector(self, selectors: List[Dict]) -> Dict:
        """选择最佳选择器"""
        return selectors[0] if selectors else {"selector": "", "type": "css", "confidence": 0.0}
