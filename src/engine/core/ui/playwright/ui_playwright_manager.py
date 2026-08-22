# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName src.ui
@className UIPlaywrightManager
@describe UI包管理器 - 统一管理UI自动化功能
"""

import time
from typing import Dict, Any, List, Optional
from src.engine.core.simple_logger import logger
from .ui_manager import ui_manager
from src.engine.core.processors.ui.element_processor import ElementProcessor
from src.engine.core.processors.ui.navigation_processor import NavigationProcessor
from src.engine.core.processors.ui.screenshot_processor import ScreenshotProcessor
from src.engine.core.processors.ui.wait_processor import WaitProcessor
from src.engine.core.processors.ui.browser_processor import BrowserProcessor
from src.engine.core.processors.ui.validation_processor import ValidationProcessor
from src.engine.core.processors.ui.action_processor import ActionProcessor
from src.engine.core.processors.ui.recording_processor import RecordingProcessor
from src.engine.core.processors.ui.advanced_ui_processor import AdvancedUIProcessor
from ..utils import UIUtils, SelectorUtils, ImageUtils


class UIPlaywrightManager:
    """UI包管理器"""
    
    def __init__(self):
        self.processors = {}
        self.is_initialized = False
        
        # 注册所有处理器
        self._register_processors()
    
    def _register_processors(self):
        """注册所有UI处理器"""
        self.processors = {
            # 基础处理器
            "element": ElementProcessor(),
            "navigation": NavigationProcessor(),
            "screenshot": ScreenshotProcessor(),
            "wait": WaitProcessor(),
            "browser": BrowserProcessor(),
            

            "validation": ValidationProcessor(),
            "action": ActionProcessor(),
            "recording": RecordingProcessor(),
            "advanced_ui": AdvancedUIProcessor()
        }
        
        logger.info(f"[UIPackageManager] 注册了 {len(self.processors)} 个UI处理器")
    
    async def initialize(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """初始化UI包"""
        try:
            if self.is_initialized:
                return {"status": "success", "message": "UI包已初始化"}
            
            # 初始化UI管理器
            await ui_manager.initialize(config)
            
            # 设置会话信息
            session_info = {
                "start_time": time.time(),
                "version": "1.0.0",
                "config": config or {}
            }
            self.ui_context.set_session_info(session_info)
            
            self.is_initialized = True
            logger.info("[UIPackageManager] UI包初始化成功")
            
            return {
                "status": "success",
                "message": "UI包初始化成功",
                "processors_count": len(self.processors),
                "session_info": session_info
            }
            
        except Exception as e:
            logger.error(f"[UIPackageManager] UI包初始化失败: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "UI包初始化失败"
            }
    
    def get_processor(self, processor_type: str):
        """获取指定类型的处理器"""
        if not self.is_initialized:
            raise RuntimeError("UI包未初始化，请先调用initialize()")
        
        processor = self.processors.get(processor_type)
        if not processor:
            raise ValueError(f"未找到处理器类型: {processor_type}")
        
        return processor
    
    def get_available_processors(self) -> List[str]:
        """获取可用的处理器类型列表"""
        return list(self.processors.keys())
    
    def get_ui_context(self, execution_context):
        """获取UI上下文（返回执行上下文本身）"""
        return execution_context
    
    def get_ui_manager(self):
        """获取UI管理器"""
        return ui_manager
    
    def get_ui_utils(self):
        """获取UI工具类"""
        return UIUtils
    
    def get_selector_utils(self):
        """获取选择器工具类"""
        return SelectorUtils
    
    def get_image_utils(self):
        """获取图像工具类"""
        return ImageUtils
    
    def execute_ui_operation(self, operation_type: str, processor_type: str, config: Dict[str, Any], context) -> Any:
        """执行UI操作"""
        try:
            if not self.is_initialized:
                raise RuntimeError("UI包未初始化")
            
            processor = self.get_processor(processor_type)
            
            # 构建节点信息
            node_info = {
                "id": f"ui_operation_{int(time.time())}",
                "type": operation_type,
                "data": {"config": config}
            }
            
            # 执行操作
            result = processor.execute(node_info, context, {})
            
            # 更新UI上下文（通过ExecutionContext）
            if operation_type.startswith("recording_"):
                context.set_recording_state(config)
            elif operation_type.startswith("screenshot"):
                if isinstance(result, dict) and "screenshot_path" in result:
                    context.add_screenshot(result)
            
            return result
            
        except Exception as e:
            logger.error(f"[UIPackageManager] UI操作执行失败: {str(e)}")
            raise
    
    def get_package_status(self) -> Dict[str, Any]:
        """获取包状态"""
        return {
            "is_initialized": self.is_initialized,
            "processors_count": len(self.processors),
            "available_processors": self.get_available_processors(),
            "ui_context_summary": self.ui_context.get_context_summary(),
            "ui_manager_status": {
                "is_initialized": ui_manager.is_initialized,
                "browser_active": ui_manager.browser is not None,
                "pages_count": len(ui_manager.pages),
                "current_page_id": ui_manager.current_page_id
            }
        }
    
    async def cleanup(self) -> Dict[str, Any]:
        """清理UI包资源"""
        try:
            # 清理UI上下文
            self.ui_context.clear_all()
            
            # 清理UI管理器
            await ui_manager.cleanup()
            
            # 清理处理器
            self.processors.clear()
            
            self.is_initialized = False
            logger.info("[UIPackageManager] UI包资源清理完成")
            
            return {
                "status": "success",
                "message": "UI包资源清理完成"
            }
            
        except Exception as e:
            logger.error(f"[UIPackageManager] UI包资源清理失败: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "UI包资源清理失败"
            }
    
    def export_configuration(self) -> Dict[str, Any]:
        """导出UI包配置"""
        return {
            "version": "1.0.0",
            "processors": list(self.processors.keys()),
            "ui_context": self.ui_context.get_context_summary(),
            "timestamp": time.time()
        }
    
    def import_configuration(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """导入UI包配置"""
        try:
            # 验证配置格式
            if "version" not in config:
                raise ValueError("配置格式无效：缺少版本信息")
            
            # 应用配置
            if "ui_context" in config:
                # 这里可以根据需要恢复UI上下文状态
                pass
            
            logger.info("[UIPackageManager] UI包配置导入成功")
            
            return {
                "status": "success",
                "message": "UI包配置导入成功",
                "imported_config": config
            }
            
        except Exception as e:
            logger.error(f"[UIPackageManager] UI包配置导入失败: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "UI包配置导入失败"
            }


# 全局UI包管理器实例
ui_playwright_manager = UIPlaywrightManager()
