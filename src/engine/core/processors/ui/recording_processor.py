# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName
@className RecordingProcessor
@describe 自动录制步骤处理器
"""

import json
import time
from typing import Dict, Any, List, Optional
from playwright.async_api import Page, Locator
from src.engine.context import ExecutionContext
from .base_ui_processor import BaseUIProcessor
from src.engine.core.simple_logger import logger
from src.engine.core.ui.playwright.ui_manager import ui_manager


class RecordingProcessor(BaseUIProcessor):
    """自动录制步骤处理器"""
    
    def __init__(self):
        super().__init__()
        self.recorded_steps = []
        self.recording_types = {
            "click": "点击动作",
            "double_click": "双击动作",
            "right_click": "右键点击",
            "scroll": "滚动动作",
            "set_text": "设置文本",
            "file_upload": "文件上传",
            "file_drop": "文件拖拽",
            "key_press": "按键动作",
            "download": "下载验证"
        }
    
    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> Any:
        """执行录制操作"""
        config = node_info.get("data", {}).get("config", {})
        operation = config.get("operation", "start_recording")
        
        logger.info(f"[RecordingProcessor] 执行录制操作: {operation}")
        
        # 根据操作类型分发处理
        if operation == "start_recording":
            return self._handle_start_recording(config, context)
        elif operation == "stop_recording":
            return self._handle_stop_recording(config, context)
        elif operation == "pause_recording":
            return self._handle_pause_recording(config, context)
        elif operation == "resume_recording":
            return self._handle_resume_recording(config, context)
        elif operation == "record_click":
            return self._handle_record_click(config, context)
        elif operation == "record_double_click":
            return self._handle_record_double_click(config, context)
        elif operation == "record_right_click":
            return self._handle_record_right_click(config, context)
        elif operation == "record_scroll":
            return self._handle_record_scroll(config, context)
        elif operation == "record_set_text":
            return self._handle_record_set_text(config, context)
        elif operation == "record_file_upload":
            return self._handle_record_file_upload(config, context)
        elif operation == "record_file_drop":
            return self._handle_record_file_drop(config, context)
        elif operation == "record_key_press":
            return self._handle_record_key_press(config, context)
        elif operation == "record_download":
            return self._handle_record_download(config, context)
        elif operation == "get_recorded_steps":
            return self._handle_get_recorded_steps(config, context)
        else:
            raise ValueError(f"不支持的录制操作: {operation}")
    
    def _handle_start_recording(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理开始录制"""
        recording_name = config.get("recording_name", f"recording_{int(time.time())}")
        page_id = config.get("page_id", "default")
        
        try:
            # 初始化录制状态
            self.recorded_steps = []
            recording_state = {
                "recording_name": recording_name,
                "start_time": time.time(),
                "page_id": page_id,
                "status": "recording"
            }
            
            # 保存录制状态到上下文
            context.set_variable("recording_state", recording_state)
            
            logger.info(f"[RecordingProcessor] 开始录制: {recording_name}")
            
            return {
                "status": "success",
                "operation": "start_recording",
                "recording_name": recording_name,
                "page_id": page_id,
                "message": "开始录制成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[RecordingProcessor] 开始录制失败: {str(e)}")
            return {
                "status": "error",
                "operation": "start_recording",
                "recording_name": recording_name,
                "error": str(e),
                "message": "开始录制失败",
                "timestamp": time.time()
            }
    
    def _handle_stop_recording(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理停止录制"""
        save_to_file = config.get("save_to_file", True)
        file_path = config.get("file_path", "")
        
        try:
            # 获取录制状态
            recording_state = context.get_variable("recording_state")
            if not recording_state:
                raise ValueError("录制状态不存在，请先开始录制")
            
            # 更新录制状态
            recording_state["status"] = "stopped"
            recording_state["end_time"] = time.time()
            recording_state["total_steps"] = len(self.recorded_steps)
            
            # 构建录制结果
            recording_result = {
                "recording_state": recording_state,
                "recorded_steps": self.recorded_steps,
                "summary": {
                    "total_steps": len(self.recorded_steps),
                    "duration": recording_state["end_time"] - recording_state["start_time"],
                    "step_types": self._get_step_types_summary()
                }
            }
            
            # 保存到上下文
            context.set_variable("recording_result", recording_result)
            
            # 保存到文件
            if save_to_file:
                if not file_path:
                    file_path = f"recordings/{recording_state['recording_name']}.json"
                
                # 确保目录存在
                import os
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(recording_result, f, ensure_ascii=False, indent=2)
            
            logger.info(f"[RecordingProcessor] 停止录制成功: {len(self.recorded_steps)}个步骤")
            
            return {
                "status": "success",
                "operation": "stop_recording",
                "recording_result": recording_result,
                "file_path": file_path if save_to_file else None,
                "message": "停止录制成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[RecordingProcessor] 停止录制失败: {str(e)}")
            return {
                "status": "error",
                "operation": "stop_recording",
                "error": str(e),
                "message": "停止录制失败",
                "timestamp": time.time()
            }
    
    def _handle_pause_recording(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理暂停录制"""
        try:
            recording_state = context.get_variable("recording_state")
            if not recording_state:
                raise ValueError("录制状态不存在")
            
            recording_state["status"] = "paused"
            recording_state["pause_time"] = time.time()
            
            logger.info(f"[RecordingProcessor] 暂停录制成功")
            
            return {
                "status": "success",
                "operation": "pause_recording",
                "message": "暂停录制成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[RecordingProcessor] 暂停录制失败: {str(e)}")
            return {
                "status": "error",
                "operation": "pause_recording",
                "error": str(e),
                "message": "暂停录制失败",
                "timestamp": time.time()
            }
    
    def _handle_resume_recording(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理恢复录制"""
        try:
            recording_state = context.get_variable("recording_state")
            if not recording_state:
                raise ValueError("录制状态不存在")
            
            recording_state["status"] = "recording"
            if "pause_time" in recording_state:
                recording_state["pause_duration"] = time.time() - recording_state["pause_time"]
                del recording_state["pause_time"]
            
            logger.info(f"[RecordingProcessor] 恢复录制成功")
            
            return {
                "status": "success",
                "operation": "resume_recording",
                "message": "恢复录制成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[RecordingProcessor] 恢复录制失败: {str(e)}")
            return {
                "status": "error",
                "operation": "resume_recording",
                "error": str(e),
                "message": "恢复录制失败",
                "timestamp": time.time()
            }
    
    def _handle_record_click(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理录制点击动作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        page_id = config.get("page_id", "default")
        element_text = config.get("element_text", "")
        element_tag = config.get("element_tag", "")
        
        try:
            # 检查录制状态
            recording_state = context.get_variable("recording_state")
            if not recording_state or recording_state["status"] != "recording":
                raise ValueError("录制未激活")
            
            # 记录点击步骤
            click_step = {
                "step_id": f"click_{len(self.recorded_steps) + 1}",
                "step_type": "click",
                "selector": selector,
                "selector_type": selector_type,
                "element_text": element_text,
                "element_tag": element_tag,
                "timestamp": time.time(),
                "page_id": page_id,
                "description": f"点击元素: {element_text or selector}"
            }
            
            self.recorded_steps.append(click_step)
            
            logger.info(f"[RecordingProcessor] 录制点击动作: {selector}")
            
            return {
                "status": "success",
                "operation": "record_click",
                "step": click_step,
                "total_steps": len(self.recorded_steps),
                "message": "录制点击动作成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[RecordingProcessor] 录制点击动作失败: {str(e)}")
            return {
                "status": "error",
                "operation": "record_click",
                "selector": selector,
                "error": str(e),
                "message": "录制点击动作失败",
                "timestamp": time.time()
            }
    
    def _handle_record_double_click(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理录制双击动作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        page_id = config.get("page_id", "default")
        element_text = config.get("element_text", "")
        
        try:
            recording_state = context.get_variable("recording_state")
            if not recording_state or recording_state["status"] != "recording":
                raise ValueError("录制未激活")
            
            double_click_step = {
                "step_id": f"double_click_{len(self.recorded_steps) + 1}",
                "step_type": "double_click",
                "selector": selector,
                "selector_type": selector_type,
                "element_text": element_text,
                "timestamp": time.time(),
                "page_id": page_id,
                "description": f"双击元素: {element_text or selector}"
            }
            
            self.recorded_steps.append(double_click_step)
            
            logger.info(f"[RecordingProcessor] 录制双击动作: {selector}")
            
            return {
                "status": "success",
                "operation": "record_double_click",
                "step": double_click_step,
                "total_steps": len(self.recorded_steps),
                "message": "录制双击动作成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[RecordingProcessor] 录制双击动作失败: {str(e)}")
            return {
                "status": "error",
                "operation": "record_double_click",
                "selector": selector,
                "error": str(e),
                "message": "录制双击动作失败",
                "timestamp": time.time()
            }
    
    def _handle_record_right_click(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理录制右键点击动作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        page_id = config.get("page_id", "default")
        element_text = config.get("element_text", "")
        
        try:
            recording_state = context.get_variable("recording_state")
            if not recording_state or recording_state["status"] != "recording":
                raise ValueError("录制未激活")
            
            right_click_step = {
                "step_id": f"right_click_{len(self.recorded_steps) + 1}",
                "step_type": "right_click",
                "selector": selector,
                "selector_type": selector_type,
                "element_text": element_text,
                "timestamp": time.time(),
                "page_id": page_id,
                "description": f"右键点击元素: {element_text or selector}"
            }
            
            self.recorded_steps.append(right_click_step)
            
            logger.info(f"[RecordingProcessor] 录制右键点击动作: {selector}")
            
            return {
                "status": "success",
                "operation": "record_right_click",
                "step": right_click_step,
                "total_steps": len(self.recorded_steps),
                "message": "录制右键点击动作成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[RecordingProcessor] 录制右键点击动作失败: {str(e)}")
            return {
                "status": "error",
                "operation": "record_right_click",
                "selector": selector,
                "error": str(e),
                "message": "录制右键点击动作失败",
                "timestamp": time.time()
            }
    
    def _handle_record_scroll(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理录制滚动动作"""
        direction = config.get("direction", "down")
        amount = config.get("amount", 100)
        page_id = config.get("page_id", "default")
        target_selector = config.get("target_selector", "")
        
        try:
            recording_state = context.get_variable("recording_state")
            if not recording_state or recording_state["status"] != "recording":
                raise ValueError("录制未激活")
            
            scroll_step = {
                "step_id": f"scroll_{len(self.recorded_steps) + 1}",
                "step_type": "scroll",
                "direction": direction,
                "amount": amount,
                "target_selector": target_selector,
                "timestamp": time.time(),
                "page_id": page_id,
                "description": f"滚动页面: {direction} {amount}px"
            }
            
            self.recorded_steps.append(scroll_step)
            
            logger.info(f"[RecordingProcessor] 录制滚动动作: {direction} {amount}px")
            
            return {
                "status": "success",
                "operation": "record_scroll",
                "step": scroll_step,
                "total_steps": len(self.recorded_steps),
                "message": "录制滚动动作成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[RecordingProcessor] 录制滚动动作失败: {str(e)}")
            return {
                "status": "error",
                "operation": "record_scroll",
                "direction": direction,
                "error": str(e),
                "message": "录制滚动动作失败",
                "timestamp": time.time()
            }
    
    def _handle_record_set_text(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理录制设置文本动作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        text_value = context.render_string(config.get("text_value", ""))
        page_id = config.get("page_id", "default")
        field_name = config.get("field_name", "")
        
        try:
            recording_state = context.get_variable("recording_state")
            if not recording_state or recording_state["status"] != "recording":
                raise ValueError("录制未激活")
            
            set_text_step = {
                "step_id": f"set_text_{len(self.recorded_steps) + 1}",
                "step_type": "set_text",
                "selector": selector,
                "selector_type": selector_type,
                "text_value": text_value,
                "field_name": field_name,
                "timestamp": time.time(),
                "page_id": page_id,
                "description": f"设置文本: {field_name or selector} = {text_value}"
            }
            
            self.recorded_steps.append(set_text_step)
            
            logger.info(f"[RecordingProcessor] 录制设置文本动作: {selector}")
            
            return {
                "status": "success",
                "operation": "record_set_text",
                "step": set_text_step,
                "total_steps": len(self.recorded_steps),
                "message": "录制设置文本动作成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[RecordingProcessor] 录制设置文本动作失败: {str(e)}")
            return {
                "status": "error",
                "operation": "record_set_text",
                "selector": selector,
                "error": str(e),
                "message": "录制设置文本动作失败",
                "timestamp": time.time()
            }
    
    def _handle_record_file_upload(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理录制文件上传动作"""
        selector = context.render_string(config.get("selector", ""))
        selector_type = config.get("selector_type", "css")
        file_path = context.render_string(config.get("file_path", ""))
        page_id = config.get("page_id", "default")
        
        try:
            recording_state = context.get_variable("recording_state")
            if not recording_state or recording_state["status"] != "recording":
                raise ValueError("录制未激活")
            
            file_upload_step = {
                "step_id": f"file_upload_{len(self.recorded_steps) + 1}",
                "step_type": "file_upload",
                "selector": selector,
                "selector_type": selector_type,
                "file_path": file_path,
                "timestamp": time.time(),
                "page_id": page_id,
                "description": f"文件上传: {file_path}"
            }
            
            self.recorded_steps.append(file_upload_step)
            
            logger.info(f"[RecordingProcessor] 录制文件上传动作: {file_path}")
            
            return {
                "status": "success",
                "operation": "record_file_upload",
                "step": file_upload_step,
                "total_steps": len(self.recorded_steps),
                "message": "录制文件上传动作成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[RecordingProcessor] 录制文件上传动作失败: {str(e)}")
            return {
                "status": "error",
                "operation": "record_file_upload",
                "selector": selector,
                "error": str(e),
                "message": "录制文件上传动作失败",
                "timestamp": time.time()
            }
    
    def _handle_record_file_drop(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理录制文件拖拽动作"""
        source_file = context.render_string(config.get("source_file", ""))
        target_selector = context.render_string(config.get("target_selector", ""))
        target_selector_type = config.get("target_selector_type", "css")
        page_id = config.get("page_id", "default")
        
        try:
            recording_state = context.get_variable("recording_state")
            if not recording_state or recording_state["status"] != "recording":
                raise ValueError("录制未激活")
            
            file_drop_step = {
                "step_id": f"file_drop_{len(self.recorded_steps) + 1}",
                "step_type": "file_drop",
                "source_file": source_file,
                "target_selector": target_selector,
                "target_selector_type": target_selector_type,
                "timestamp": time.time(),
                "page_id": page_id,
                "description": f"文件拖拽: {source_file} -> {target_selector}"
            }
            
            self.recorded_steps.append(file_drop_step)
            
            logger.info(f"[RecordingProcessor] 录制文件拖拽动作: {source_file}")
            
            return {
                "status": "success",
                "operation": "record_file_drop",
                "step": file_drop_step,
                "total_steps": len(self.recorded_steps),
                "message": "录制文件拖拽动作成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[RecordingProcessor] 录制文件拖拽动作失败: {str(e)}")
            return {
                "status": "error",
                "operation": "record_file_drop",
                "source_file": source_file,
                "error": str(e),
                "message": "录制文件拖拽动作失败",
                "timestamp": time.time()
            }
    
    def _handle_record_key_press(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理录制按键动作"""
        key = config.get("key", "")
        selector = config.get("selector", "")
        selector_type = config.get("selector_type", "css")
        page_id = config.get("page_id", "default")
        
        try:
            recording_state = context.get_variable("recording_state")
            if not recording_state or recording_state["status"] != "recording":
                raise ValueError("录制未激活")
            
            key_press_step = {
                "step_id": f"key_press_{len(self.recorded_steps) + 1}",
                "step_type": "key_press",
                "key": key,
                "selector": selector,
                "selector_type": selector_type,
                "timestamp": time.time(),
                "page_id": page_id,
                "description": f"按键: {key}"
            }
            
            self.recorded_steps.append(key_press_step)
            
            logger.info(f"[RecordingProcessor] 录制按键动作: {key}")
            
            return {
                "status": "success",
                "operation": "record_key_press",
                "step": key_press_step,
                "total_steps": len(self.recorded_steps),
                "message": "录制按键动作成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[RecordingProcessor] 录制按键动作失败: {str(e)}")
            return {
                "status": "error",
                "operation": "record_key_press",
                "key": key,
                "error": str(e),
                "message": "录制按键动作失败",
                "timestamp": time.time()
            }
    
    def _handle_record_download(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理录制下载验证"""
        download_path = context.render_string(config.get("download_path", ""))
        expected_filename = config.get("expected_filename", "")
        page_id = config.get("page_id", "default")
        
        try:
            recording_state = context.get_variable("recording_state")
            if not recording_state or recording_state["status"] != "recording":
                raise ValueError("录制未激活")
            
            download_step = {
                "step_id": f"download_{len(self.recorded_steps) + 1}",
                "step_type": "download",
                "download_path": download_path,
                "expected_filename": expected_filename,
                "timestamp": time.time(),
                "page_id": page_id,
                "description": f"下载验证: {expected_filename or download_path}"
            }
            
            self.recorded_steps.append(download_step)
            
            logger.info(f"[RecordingProcessor] 录制下载验证: {download_path}")
            
            return {
                "status": "success",
                "operation": "record_download",
                "step": download_step,
                "total_steps": len(self.recorded_steps),
                "message": "录制下载验证成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[RecordingProcessor] 录制下载验证失败: {str(e)}")
            return {
                "status": "error",
                "operation": "record_download",
                "download_path": download_path,
                "error": str(e),
                "message": "录制下载验证失败",
                "timestamp": time.time()
            }
    
    def _validate_ui_config(self, config: Dict[str, Any]) -> bool:
        """验证UI特定配置"""
        # 基础验证，子类可以重写
        return True
    
        
    
    def _handle_get_recorded_steps(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """处理获取录制的步骤"""
        try:
            recording_result = context.get_variable("recording_result")
            if not recording_result:
                raise ValueError("录制结果不存在，请先完成录制")
            
            logger.info(f"[RecordingProcessor] 获取录制步骤: {len(self.recorded_steps)}个步骤")
            
            return {
                "status": "success",
                "operation": "get_recorded_steps",
                "recorded_steps": self.recorded_steps,
                "recording_result": recording_result,
                "total_steps": len(self.recorded_steps),
                "message": "获取录制步骤成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[RecordingProcessor] 获取录制步骤失败: {str(e)}")
            return {
                "status": "error",
                "operation": "get_recorded_steps",
                "error": str(e),
                "message": "获取录制步骤失败",
                "timestamp": time.time()
            }
    
    def _get_step_types_summary(self) -> Dict[str, int]:
        """获取步骤类型汇总"""
        summary = {}
        for step in self.recorded_steps:
            step_type = step.get("step_type", "unknown")
            summary[step_type] = summary.get(step_type, 0) + 1
        return summary
