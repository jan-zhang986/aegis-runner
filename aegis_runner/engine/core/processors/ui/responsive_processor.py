# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-30
@packageName src.core.processors.ui
@className ResponsiveUIProcessor
@describe 响应式UI测试处理器 - 提供多设备和响应式布局测试能力
"""

import time
import json
import os
from typing import Dict, Any, List, Optional
from playwright.async_api import Page
from aegis_runner.engine.context import ExecutionContext
from .base_ui_processor import BaseUIProcessor
from aegis_runner.engine.core.simple_logger import logger
from aegis_runner.engine.core.ui.playwright.ui_manager import ui_manager


class ResponsiveUIProcessor(BaseUIProcessor):
    """响应式UI测试处理器"""
    
    def __init__(self):
        super().__init__()
        self.responsive_dir = "responsive_test_data"
        
        # 设备预设配置
        self.DEVICE_PRESETS = {
            # 移动设备
            "iphone_se": {
                "width": 375, "height": 667, 
                "device_scale_factor": 2,
                "is_mobile": True,
                "has_touch": True,
                "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15"
            },
            "iphone_13": {
                "width": 390, "height": 844,
                "device_scale_factor": 3,
                "is_mobile": True,
                "has_touch": True,
                "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15"
            },
            "iphone_13_pro_max": {
                "width": 428, "height": 926,
                "device_scale_factor": 3,
                "is_mobile": True,
                "has_touch": True,
                "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15"
            },
            "samsung_galaxy_s21": {
                "width": 360, "height": 800,
                "device_scale_factor": 3,
                "is_mobile": True,
                "has_touch": True,
                "user_agent": "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36"
            },
            
            # 平板设备
            "ipad_mini": {
                "width": 768, "height": 1024,
                "device_scale_factor": 2,
                "is_mobile": True,
                "has_touch": True,
                "user_agent": "Mozilla/5.0 (iPad; CPU OS 15_0 like Mac OS X) AppleWebKit/605.1.15"
            },
            "ipad_pro": {
                "width": 1024, "height": 1366,
                "device_scale_factor": 2,
                "is_mobile": True,
                "has_touch": True,
                "user_agent": "Mozilla/5.0 (iPad; CPU OS 15_0 like Mac OS X) AppleWebKit/605.1.15"
            },
            
            # 桌面设备
            "desktop_hd": {
                "width": 1280, "height": 720,
                "device_scale_factor": 1,
                "is_mobile": False,
                "has_touch": False,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            "desktop_fhd": {
                "width": 1920, "height": 1080,
                "device_scale_factor": 1,
                "is_mobile": False,
                "has_touch": False,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            "desktop_4k": {
                "width": 3840, "height": 2160,
                "device_scale_factor": 2,
                "is_mobile": False,
                "has_touch": False,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        }
        
        # 确保目录存在
        os.makedirs(self.responsive_dir, exist_ok=True)
    
    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> Any:
        """执行响应式测试操作"""
        config = node_info.get("data", {}).get("config", {})
        operation = config.get("operation", "test_responsive_layout")
        
        logger.info(f"[ResponsiveProcessor] 执行响应式测试: {operation}")
        
        # 根据操作类型分发处理
        if operation == "test_responsive_layout":
            return self._handle_test_responsive_layout(config, context)
        elif operation == "set_viewport":
            return self._handle_set_viewport(config, context)
        elif operation == "test_device":
            return self._handle_test_device(config, context)
        elif operation == "capture_multi_device":
            return self._handle_capture_multi_device(config, context)
        elif operation == "test_orientation":
            return self._handle_test_orientation(config, context)
        elif operation == "test_breakpoints":
            return self._handle_test_breakpoints(config, context)
        else:
            raise ValueError(f"不支持的响应式测试操作: {operation}")
    
    def _handle_test_responsive_layout(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """测试响应式布局"""
        url = context.render_string(config.get("url", ""))
        page_id = config.get("page_id", "default")
        devices = config.get("devices", ["iphone_13", "ipad_pro", "desktop_fhd"])
        capture_screenshots = config.get("capture_screenshots", True)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            results = {}
            
            for device_name in devices:
                if device_name not in self.DEVICE_PRESETS:
                    logger.warning(f"[ResponsiveProcessor] 未知设备: {device_name}，跳过")
                    continue
                
                device_config = self.DEVICE_PRESETS[device_name]
                
                logger.info(f"[ResponsiveProcessor] 测试设备: {device_name} ({device_config['width']}x{device_config['height']})")
                
                # 设置视口
                ui_manager.run_async(page.set_viewport_size)({
                    "width": device_config["width"],
                    "height": device_config["height"]
                })
                
                # 设置User-Agent（如果需要）
                if device_config.get("user_agent"):
                    ui_manager.run_async(page.context.set_extra_http_headers)({
                        "User-Agent": device_config["user_agent"]
                    })
                
                # 导航到页面
                ui_manager.run_async(page.goto)(url, wait_until="networkidle")
                
                # 等待渲染
                ui_manager.run_async(page.wait_for_load_state)("networkidle")
                
                # 捕获截图
                screenshot_path = None
                if capture_screenshots:
                    screenshot_path = os.path.join(
                        self.responsive_dir, 
                        f"{device_name}_{int(time.time())}.png"
                    )
                    ui_manager.run_async(page.screenshot)(path=screenshot_path, full_page=True)
                
                # 分析布局
                layout_analysis = ui_manager.run_async(self._analyze_layout)(page, device_config)
                
                results[device_name] = {
                    "device_config": device_config,
                    "screenshot_path": screenshot_path,
                    "layout_analysis": layout_analysis,
                    "timestamp": time.time()
                }
            
            logger.info(f"[ResponsiveProcessor] 响应式布局测试完成: 测试了 {len(results)} 个设备")
            
            return {
                "status": "success",
                "operation": "test_responsive_layout",
                "url": url,
                "results": results,
                "page_id": page_id,
                "message": "响应式布局测试成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ResponsiveProcessor] 响应式布局测试失败: {str(e)}")
            return {
                "status": "error",
                "operation": "test_responsive_layout",
                "url": url,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_set_viewport(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """设置视口大小"""
        width = config.get("width", 1920)
        height = config.get("height", 1080)
        page_id = config.get("page_id", "default")
        device_scale_factor = config.get("device_scale_factor", 1)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 设置视口
            ui_manager.run_async(page.set_viewport_size)({
                "width": width,
                "height": height
            })
            
            logger.info(f"[ResponsiveProcessor] 视口已设置: {width}x{height}")
            
            return {
                "status": "success",
                "operation": "set_viewport",
                "width": width,
                "height": height,
                "device_scale_factor": device_scale_factor,
                "page_id": page_id,
                "message": "视口设置成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ResponsiveProcessor] 设置视口失败: {str(e)}")
            return {
                "status": "error",
                "operation": "set_viewport",
                "width": width,
                "height": height,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_test_device(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """测试特定设备"""
        device_name = config.get("device_name", "iphone_13")
        url = context.render_string(config.get("url", ""))
        page_id = config.get("page_id", "default")
        
        try:
            if device_name not in self.DEVICE_PRESETS:
                raise ValueError(f"未知设备: {device_name}")
            
            result = self._handle_test_responsive_layout({
                "url": url,
                "page_id": page_id,
                "devices": [device_name],
                "capture_screenshots": True
            }, context)
            
            result["operation"] = "test_device"
            result["device_name"] = device_name
            
            return result
            
        except Exception as e:
            logger.error(f"[ResponsiveProcessor] 测试设备失败: {str(e)}")
            return {
                "status": "error",
                "operation": "test_device",
                "device_name": device_name,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_capture_multi_device(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """捕获多设备截图"""
        url = context.render_string(config.get("url", ""))
        page_id = config.get("page_id", "default")
        devices = config.get("devices", list(self.DEVICE_PRESETS.keys()))
        
        try:
            result = self._handle_test_responsive_layout({
                "url": url,
                "page_id": page_id,
                "devices": devices,
                "capture_screenshots": True
            }, context)
            
            result["operation"] = "capture_multi_device"
            
            # 提取截图路径
            screenshots = {}
            for device, data in result.get("results", {}).items():
                if data.get("screenshot_path"):
                    screenshots[device] = data["screenshot_path"]
            
            result["screenshots"] = screenshots
            
            return result
            
        except Exception as e:
            logger.error(f"[ResponsiveProcessor] 捕获多设备截图失败: {str(e)}")
            return {
                "status": "error",
                "operation": "capture_multi_device",
                "url": url,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_test_orientation(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """测试设备方向（横屏/竖屏）"""
        device_name = config.get("device_name", "iphone_13")
        url = context.render_string(config.get("url", ""))
        page_id = config.get("page_id", "default")
        
        try:
            if device_name not in self.DEVICE_PRESETS:
                raise ValueError(f"未知设备: {device_name}")
            
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            device_config = self.DEVICE_PRESETS[device_name]
            results = {}
            
            # 测试竖屏（Portrait）
            logger.info(f"[ResponsiveProcessor] 测试竖屏: {device_name}")
            ui_manager.run_async(page.set_viewport_size)({
                "width": device_config["width"],
                "height": device_config["height"]
            })
            ui_manager.run_async(page.goto)(url, wait_until="networkidle")
            
            portrait_screenshot = os.path.join(
                self.responsive_dir, 
                f"{device_name}_portrait_{int(time.time())}.png"
            )
            ui_manager.run_async(page.screenshot)(path=portrait_screenshot, full_page=True)
            
            results["portrait"] = {
                "width": device_config["width"],
                "height": device_config["height"],
                "screenshot_path": portrait_screenshot,
                "layout_analysis": ui_manager.run_async(self._analyze_layout)(page, device_config)
            }
            
            # 测试横屏（Landscape）
            logger.info(f"[ResponsiveProcessor] 测试横屏: {device_name}")
            ui_manager.run_async(page.set_viewport_size)({
                "width": device_config["height"],  # 宽高互换
                "height": device_config["width"]
            })
            ui_manager.run_async(page.reload)()
            
            landscape_screenshot = os.path.join(
                self.responsive_dir, 
                f"{device_name}_landscape_{int(time.time())}.png"
            )
            ui_manager.run_async(page.screenshot)(path=landscape_screenshot, full_page=True)
            
            results["landscape"] = {
                "width": device_config["height"],
                "height": device_config["width"],
                "screenshot_path": landscape_screenshot,
                "layout_analysis": ui_manager.run_async(self._analyze_layout)(page, {
                    **device_config,
                    "width": device_config["height"],
                    "height": device_config["width"]
                })
            }
            
            logger.info(f"[ResponsiveProcessor] 方向测试完成: {device_name}")
            
            return {
                "status": "success",
                "operation": "test_orientation",
                "device_name": device_name,
                "url": url,
                "results": results,
                "page_id": page_id,
                "message": "方向测试成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ResponsiveProcessor] 方向测试失败: {str(e)}")
            return {
                "status": "error",
                "operation": "test_orientation",
                "device_name": device_name,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_test_breakpoints(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """测试响应式断点"""
        url = context.render_string(config.get("url", ""))
        page_id = config.get("page_id", "default")
        breakpoints = config.get("breakpoints", [
            {"name": "mobile", "width": 375},
            {"name": "tablet", "width": 768},
            {"name": "desktop", "width": 1024},
            {"name": "wide", "width": 1440}
        ])
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            results = {}
            
            for breakpoint in breakpoints:
                name = breakpoint["name"]
                width = breakpoint["width"]
                height = breakpoint.get("height", 900)
                
                logger.info(f"[ResponsiveProcessor] 测试断点: {name} ({width}x{height})")
                
                # 设置视口
                ui_manager.run_async(page.set_viewport_size)({
                    "width": width,
                    "height": height
                })
                
                # 导航或刷新
                if not results:
                    ui_manager.run_async(page.goto)(url, wait_until="networkidle")
                else:
                    ui_manager.run_async(page.reload)()
                
                # 截图
                screenshot_path = os.path.join(
                    self.responsive_dir, 
                    f"breakpoint_{name}_{int(time.time())}.png"
                )
                ui_manager.run_async(page.screenshot)(path=screenshot_path, full_page=True)
                
                # 分析布局
                layout_analysis = ui_manager.run_async(self._analyze_layout)(page, {
                    "width": width,
                    "height": height,
                    "is_mobile": width < 768
                })
                
                results[name] = {
                    "width": width,
                    "height": height,
                    "screenshot_path": screenshot_path,
                    "layout_analysis": layout_analysis,
                    "timestamp": time.time()
                }
            
            logger.info(f"[ResponsiveProcessor] 断点测试完成: 测试了 {len(results)} 个断点")
            
            return {
                "status": "success",
                "operation": "test_breakpoints",
                "url": url,
                "results": results,
                "page_id": page_id,
                "message": "断点测试成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[ResponsiveProcessor] 断点测试失败: {str(e)}")
            return {
                "status": "error",
                "operation": "test_breakpoints",
                "url": url,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    async def _analyze_layout(self, page: Page, device_config: Dict[str, Any]) -> Dict[str, Any]:
        """分析页面布局"""
        analysis = await page.evaluate("""
            (deviceConfig) => {
                const analysis = {
                    viewport: {
                        width: window.innerWidth,
                        height: window.innerHeight
                    },
                    scroll: {
                        height: document.documentElement.scrollHeight,
                        width: document.documentElement.scrollWidth
                    },
                    elements: {
                        visible: 0,
                        hidden: 0,
                        total: 0
                    },
                    overflow: {
                        horizontal: false,
                        vertical: false
                    },
                    responsive_issues: []
                };
                
                // 检查所有元素
                const elements = document.querySelectorAll('*');
                analysis.elements.total = elements.length;
                
                elements.forEach(el => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    
                    // 统计可见/隐藏元素
                    if (style.display === 'none' || style.visibility === 'hidden') {
                        analysis.elements.hidden++;
                    } else {
                        analysis.elements.visible++;
                    }
                    
                    // 检查溢出
                    if (rect.right > window.innerWidth) {
                        analysis.overflow.horizontal = true;
                    }
                    if (rect.bottom > window.innerHeight && rect.top < 0) {
                        analysis.overflow.vertical = true;
                    }
                    
                    // 检查响应式问题
                    // 1. 固定宽度可能导致移动端问题
                    if (deviceConfig.is_mobile && parseInt(style.width) > deviceConfig.width) {
                        analysis.responsive_issues.push({
                            type: 'fixed_width_too_large',
                            element: el.tagName.toLowerCase(),
                            width: parseInt(style.width)
                        });
                    }
                    
                    // 2. 文本太小
                    const fontSize = parseInt(style.fontSize);
                    if (fontSize < 12 && deviceConfig.is_mobile) {
                        analysis.responsive_issues.push({
                            type: 'font_too_small',
                            element: el.tagName.toLowerCase(),
                            fontSize: fontSize
                        });
                    }
                });
                
                // 去重响应式问题（只保留前10个）
                analysis.responsive_issues = analysis.responsive_issues.slice(0, 10);
                
                return analysis;
            }
        """, device_config)
        
        return analysis
    
    def get_device_presets(self) -> Dict[str, Dict[str, Any]]:
        """获取所有设备预设"""
        return self.DEVICE_PRESETS
    
    def add_device_preset(self, name: str, config: Dict[str, Any]):
        """添加自定义设备预设"""
        self.DEVICE_PRESETS[name] = config
        logger.info(f"[ResponsiveProcessor] 添加设备预设: {name}")
    
    def _validate_ui_config(self, config: Dict[str, Any]) -> bool:
        """验证UI特定配置"""
        return True

