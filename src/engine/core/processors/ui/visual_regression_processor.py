# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-30
@packageName src.core.processors.ui
@className VisualRegressionProcessor
@describe 视觉回归测试处理器 - 提供视觉对比和回归测试能力
"""

import os
import time
import json
import hashlib
from typing import Dict, Any, Optional, Tuple
from playwright.async_api import Page
from src.engine.context import ExecutionContext
from .base_ui_processor import BaseUIProcessor
from src.engine.core.simple_logger import logger
from src.engine.core.ui.playwright.ui_manager import ui_manager


class VisualRegressionProcessor(BaseUIProcessor):
    """视觉回归测试处理器"""
    
    def __init__(self):
        super().__init__()
        self.baseline_dir = "visual_baselines"
        self.diff_dir = "visual_diffs"
        self.threshold = 0.01  # 默认1%差异阈值
        self.comparison_results = []
        
        # 确保目录存在
        os.makedirs(self.baseline_dir, exist_ok=True)
        os.makedirs(self.diff_dir, exist_ok=True)
    
    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> Any:
        """执行视觉回归测试操作"""
        config = node_info.get("data", {}).get("config", {})
        operation = config.get("operation", "visual_compare")
        
        logger.info(f"[VisualRegressionProcessor] 执行视觉回归测试: {operation}")
        
        # 根据操作类型分发处理
        if operation == "capture_baseline":
            return self._handle_capture_baseline(config, context)
        elif operation == "visual_compare":
            return self._handle_visual_compare(config, context)
        elif operation == "update_baseline":
            return self._handle_update_baseline(config, context)
        elif operation == "element_compare":
            return self._handle_element_compare(config, context)
        elif operation == "full_page_compare":
            return self._handle_full_page_compare(config, context)
        elif operation == "get_comparison_report":
            return self._handle_get_comparison_report(config, context)
        else:
            raise ValueError(f"不支持的视觉回归测试操作: {operation}")
    
    def _handle_capture_baseline(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """捕获基线图像"""
        baseline_name = config.get("baseline_name", "")
        page_id = config.get("page_id", "default")
        selector = config.get("selector", None)  # 如果为None则截取整个页面
        full_page = config.get("full_page", True)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            baseline_path = os.path.join(self.baseline_dir, f"{baseline_name}.png")
            
            # 截图
            if selector:
                # 截取特定元素
                element = page.locator(selector)
                ui_manager.run_async(element.screenshot)(path=baseline_path)
            else:
                # 截取整个页面
                ui_manager.run_async(page.screenshot)(path=baseline_path, full_page=full_page)
            
            # 保存元数据
            metadata = {
                "baseline_name": baseline_name,
                "page_id": page_id,
                "url": page.url,
                "selector": selector,
                "full_page": full_page,
                "timestamp": time.time(),
                "checksum": self._calculate_image_checksum(baseline_path)
            }
            
            metadata_path = os.path.join(self.baseline_dir, f"{baseline_name}.json")
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"[VisualRegressionProcessor] 基线图像已保存: {baseline_path}")
            
            return {
                "status": "success",
                "operation": "capture_baseline",
                "baseline_name": baseline_name,
                "baseline_path": baseline_path,
                "metadata": metadata,
                "page_id": page_id,
                "message": "基线图像捕获成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[VisualRegressionProcessor] 捕获基线图像失败: {str(e)}")
            return {
                "status": "error",
                "operation": "capture_baseline",
                "baseline_name": baseline_name,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_visual_compare(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """视觉对比"""
        baseline_name = config.get("baseline_name", "")
        page_id = config.get("page_id", "default")
        selector = config.get("selector", None)
        full_page = config.get("full_page", True)
        threshold = config.get("threshold", self.threshold)
        save_diff = config.get("save_diff", True)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 基线图像路径
            baseline_path = os.path.join(self.baseline_dir, f"{baseline_name}.png")
            if not os.path.exists(baseline_path):
                raise FileNotFoundError(f"基线图像不存在: {baseline_path}")
            
            # 捕获当前图像
            current_path = os.path.join(self.diff_dir, f"{baseline_name}_current_{int(time.time())}.png")
            
            if selector:
                element = page.locator(selector)
                ui_manager.run_async(element.screenshot)(path=current_path)
            else:
                ui_manager.run_async(page.screenshot)(path=current_path, full_page=full_page)
            
            # 执行图像对比
            diff_percentage, diff_path = self._compare_images(baseline_path, current_path, baseline_name, save_diff)
            
            # 判断是否通过
            passed = diff_percentage <= threshold
            
            # 记录对比结果
            comparison_result = {
                "baseline_name": baseline_name,
                "baseline_path": baseline_path,
                "current_path": current_path,
                "diff_path": diff_path,
                "diff_percentage": diff_percentage,
                "threshold": threshold,
                "passed": passed,
                "timestamp": time.time()
            }
            self.comparison_results.append(comparison_result)
            
            logger.info(
                f"[VisualRegressionProcessor] 视觉对比完成: {baseline_name}, "
                f"差异: {diff_percentage:.2%}, 阈值: {threshold:.2%}, "
                f"结果: {'通过' if passed else '失败'}"
            )
            
            return {
                "status": "success" if passed else "warning",
                "operation": "visual_compare",
                "baseline_name": baseline_name,
                "diff_percentage": diff_percentage,
                "threshold": threshold,
                "passed": passed,
                "current_path": current_path,
                "diff_path": diff_path,
                "page_id": page_id,
                "message": f"视觉对比{'通过' if passed else '失败'}",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[VisualRegressionProcessor] 视觉对比失败: {str(e)}")
            return {
                "status": "error",
                "operation": "visual_compare",
                "baseline_name": baseline_name,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_update_baseline(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """更新基线图像"""
        baseline_name = config.get("baseline_name", "")
        page_id = config.get("page_id", "default")
        selector = config.get("selector", None)
        full_page = config.get("full_page", True)
        
        try:
            # 重新捕获基线
            result = self._handle_capture_baseline({
                "baseline_name": baseline_name,
                "page_id": page_id,
                "selector": selector,
                "full_page": full_page
            }, context)
            
            if result["status"] == "success":
                logger.info(f"[VisualRegressionProcessor] 基线图像已更新: {baseline_name}")
                result["message"] = "基线图像更新成功"
                result["operation"] = "update_baseline"
            
            return result
            
        except Exception as e:
            logger.error(f"[VisualRegressionProcessor] 更新基线图像失败: {str(e)}")
            return {
                "status": "error",
                "operation": "update_baseline",
                "baseline_name": baseline_name,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_element_compare(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """元素级视觉对比"""
        baseline_name = config.get("baseline_name", "")
        selector = config.get("selector", "")
        page_id = config.get("page_id", "default")
        threshold = config.get("threshold", self.threshold)
        
        try:
            # 使用selector进行对比
            result = self._handle_visual_compare({
                "baseline_name": baseline_name,
                "page_id": page_id,
                "selector": selector,
                "full_page": False,
                "threshold": threshold
            }, context)
            
            result["operation"] = "element_compare"
            return result
            
        except Exception as e:
            logger.error(f"[VisualRegressionProcessor] 元素视觉对比失败: {str(e)}")
            return {
                "status": "error",
                "operation": "element_compare",
                "baseline_name": baseline_name,
                "selector": selector,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_full_page_compare(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """全页面视觉对比"""
        baseline_name = config.get("baseline_name", "")
        page_id = config.get("page_id", "default")
        threshold = config.get("threshold", self.threshold)
        
        try:
            result = self._handle_visual_compare({
                "baseline_name": baseline_name,
                "page_id": page_id,
                "selector": None,
                "full_page": True,
                "threshold": threshold
            }, context)
            
            result["operation"] = "full_page_compare"
            return result
            
        except Exception as e:
            logger.error(f"[VisualRegressionProcessor] 全页面视觉对比失败: {str(e)}")
            return {
                "status": "error",
                "operation": "full_page_compare",
                "baseline_name": baseline_name,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_get_comparison_report(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """获取对比报告"""
        try:
            # 统计结果
            total_comparisons = len(self.comparison_results)
            passed_comparisons = sum(1 for result in self.comparison_results if result["passed"])
            failed_comparisons = total_comparisons - passed_comparisons
            
            # 计算平均差异
            avg_diff = 0
            if total_comparisons > 0:
                avg_diff = sum(r["diff_percentage"] for r in self.comparison_results) / total_comparisons
            
            report = {
                "total_comparisons": total_comparisons,
                "passed_comparisons": passed_comparisons,
                "failed_comparisons": failed_comparisons,
                "pass_rate": passed_comparisons / total_comparisons if total_comparisons > 0 else 0,
                "average_diff_percentage": avg_diff,
                "comparison_results": self.comparison_results,
                "timestamp": time.time()
            }
            
            # 保存报告
            report_path = os.path.join(self.diff_dir, f"comparison_report_{int(time.time())}.json")
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(
                f"[VisualRegressionProcessor] 对比报告: "
                f"总计 {total_comparisons}, 通过 {passed_comparisons}, 失败 {failed_comparisons}"
            )
            
            return {
                "status": "success",
                "operation": "get_comparison_report",
                "report": report,
                "report_path": report_path,
                "message": "对比报告生成成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[VisualRegressionProcessor] 生成对比报告失败: {str(e)}")
            return {
                "status": "error",
                "operation": "get_comparison_report",
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _compare_images(
        self, 
        baseline_path: str, 
        current_path: str, 
        name: str,
        save_diff: bool = True
    ) -> Tuple[float, Optional[str]]:
        """
        对比两个图像
        
        Returns:
            (差异百分比, 差异图像路径)
        """
        try:
            from PIL import Image, ImageChops, ImageDraw
            
            # 加载图像
            baseline_img = Image.open(baseline_path).convert('RGB')
            current_img = Image.open(current_path).convert('RGB')
            
            # 确保图像尺寸相同
            if baseline_img.size != current_img.size:
                logger.warning(
                    f"[VisualRegressionProcessor] 图像尺寸不同: "
                    f"基线={baseline_img.size}, 当前={current_img.size}"
                )
                # 调整当前图像大小
                current_img = current_img.resize(baseline_img.size, Image.LANCZOS)
            
            # 计算差异
            diff = ImageChops.difference(baseline_img, current_img)
            
            # 计算差异百分比
            diff_array = list(diff.getdata())
            total_pixels = len(diff_array)
            diff_pixels = sum(1 for pixel in diff_array if sum(pixel) > 30)  # 阈值30
            diff_percentage = diff_pixels / total_pixels if total_pixels > 0 else 0
            
            # 保存差异图像
            diff_path = None
            if save_diff:
                diff_path = os.path.join(self.diff_dir, f"{name}_diff_{int(time.time())}.png")
                
                # 创建彩色差异图像
                diff_colored = Image.new('RGB', baseline_img.size)
                for x in range(baseline_img.size[0]):
                    for y in range(baseline_img.size[1]):
                        base_pixel = baseline_img.getpixel((x, y))
                        curr_pixel = current_img.getpixel((x, y))
                        
                        # 如果像素不同，标记为红色
                        if abs(base_pixel[0] - curr_pixel[0]) > 10 or \
                           abs(base_pixel[1] - curr_pixel[1]) > 10 or \
                           abs(base_pixel[2] - curr_pixel[2]) > 10:
                            diff_colored.putpixel((x, y), (255, 0, 0))  # 红色
                        else:
                            diff_colored.putpixel((x, y), curr_pixel)
                
                diff_colored.save(diff_path)
                logger.info(f"[VisualRegressionProcessor] 差异图像已保存: {diff_path}")
            
            return diff_percentage, diff_path
            
        except ImportError:
            logger.warning("[VisualRegressionProcessor] PIL库未安装，使用简单的字节对比")
            return self._simple_image_compare(baseline_path, current_path)
        except Exception as e:
            logger.error(f"[VisualRegressionProcessor] 图像对比失败: {str(e)}")
            raise
    
    def _simple_image_compare(self, baseline_path: str, current_path: str) -> Tuple[float, None]:
        """简单的图像对比（基于文件字节）"""
        with open(baseline_path, 'rb') as f:
            baseline_bytes = f.read()
        
        with open(current_path, 'rb') as f:
            current_bytes = f.read()
        
        if len(baseline_bytes) != len(current_bytes):
            return 1.0, None  # 完全不同
        
        diff_bytes = sum(1 for b1, b2 in zip(baseline_bytes, current_bytes) if b1 != b2)
        diff_percentage = diff_bytes / len(baseline_bytes) if len(baseline_bytes) > 0 else 0
        
        return diff_percentage, None
    
    def _calculate_image_checksum(self, image_path: str) -> str:
        """计算图像的校验和"""
        try:
            with open(image_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.warning(f"[VisualRegressionProcessor] 计算校验和失败: {str(e)}")
            return ""
    
    def get_comparison_results(self) -> list:
        """获取所有对比结果"""
        return self.comparison_results
    
    def clear_comparison_results(self):
        """清除对比结果"""
        self.comparison_results.clear()
        logger.info("[VisualRegressionProcessor] 对比结果已清除")
    
    def _validate_ui_config(self, config: Dict[str, Any]) -> bool:
        """验证UI特定配置"""
        return True

