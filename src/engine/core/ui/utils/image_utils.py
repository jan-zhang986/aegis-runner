# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName src.ui.utils
@className ImageUtils
@describe 图像工具类 - 提供图像处理相关的工具方法
"""

import os
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from src.engine.core.simple_logger import logger


class ImageUtils:
    """图像工具类"""
    
    @staticmethod
    def calculate_image_hash(image_path: str) -> Optional[str]:
        """计算图像文件的哈希值"""
        try:
            if not os.path.exists(image_path):
                return None
            
            with open(image_path, 'rb') as f:
                image_data = f.read()
                return hashlib.md5(image_data).hexdigest()
        except Exception as e:
            logger.error(f"[ImageUtils] 计算图像哈希失败: {str(e)}")
            return None
    
    @staticmethod
    def compare_images_simple(image1_path: str, image2_path: str) -> float:
        """简单的图像比较（基于文件大小和哈希）"""
        try:
            if not os.path.exists(image1_path) or not os.path.exists(image2_path):
                return 0.0
            
            # 获取文件大小
            size1 = os.path.getsize(image1_path)
            size2 = os.path.getsize(image2_path)
            
            # 如果大小差异很大，相似度较低
            size_diff = abs(size1 - size2) / max(size1, size2)
            if size_diff > 0.5:  # 大小差异超过50%
                return 0.3
            
            # 计算哈希值
            hash1 = ImageUtils.calculate_image_hash(image1_path)
            hash2 = ImageUtils.calculate_image_hash(image2_path)
            
            if hash1 == hash2:
                return 1.0  # 完全相同
            elif hash1 and hash2:
                # 计算哈希相似度（简化版本）
                similarity = sum(c1 == c2 for c1, c2 in zip(hash1, hash2)) / len(hash1)
                return similarity
            else:
                return 0.5  # 无法比较时的默认值
        
        except Exception as e:
            logger.error(f"[ImageUtils] 图像比较失败: {str(e)}")
            return 0.0
    
    @staticmethod
    def ensure_directory_exists(file_path: str) -> bool:
        """确保目录存在"""
        try:
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                logger.debug(f"[ImageUtils] 创建目录: {directory}")
            return True
        except Exception as e:
            logger.error(f"[ImageUtils] 创建目录失败: {str(e)}")
            return False
    
    @staticmethod
    def get_image_info(image_path: str) -> Dict[str, Any]:
        """获取图像信息"""
        try:
            if not os.path.exists(image_path):
                return {"exists": False}
            
            file_size = os.path.getsize(image_path)
            file_hash = ImageUtils.calculate_image_hash(image_path)
            
            return {
                "exists": True,
                "path": image_path,
                "size": file_size,
                "hash": file_hash,
                "size_formatted": ImageUtils.format_file_size(file_size)
            }
        except Exception as e:
            logger.error(f"[ImageUtils] 获取图像信息失败: {str(e)}")
            return {"exists": False, "error": str(e)}
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
    
    @staticmethod
    def generate_baseline_path(test_name: str, element_selector: str = None) -> str:
        """生成基线图像路径"""
        if element_selector:
            # 清理选择器字符串，用作文件名
            safe_selector = "".join(c for c in element_selector if c.isalnum() or c in ('-', '_', '.'))
            filename = f"{test_name}_{safe_selector}.png"
        else:
            filename = f"{test_name}.png"
        
        return os.path.join("baselines", filename)
    
    @staticmethod
    def generate_screenshot_path(test_name: str, timestamp: str = None) -> str:
        """生成截图路径"""
        if not timestamp:
            import time
            timestamp = str(int(time.time()))
        
        filename = f"{test_name}_{timestamp}.png"
        return os.path.join("screenshots", filename)
    
    @staticmethod
    def cleanup_old_screenshots(directory: str, max_age_days: int = 7) -> int:
        """清理旧的截图文件"""
        try:
            if not os.path.exists(directory):
                return 0
            
            import time
            current_time = time.time()
            max_age_seconds = max_age_days * 24 * 60 * 60
            cleaned_count = 0
            
            for filename in os.listdir(directory):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    file_path = os.path.join(directory, filename)
                    file_age = current_time - os.path.getmtime(file_path)
                    
                    if file_age > max_age_seconds:
                        try:
                            os.remove(file_path)
                            cleaned_count += 1
                            logger.debug(f"[ImageUtils] 删除旧截图: {filename}")
                        except Exception as e:
                            logger.error(f"[ImageUtils] 删除文件失败: {filename}, {str(e)}")
            
            if cleaned_count > 0:
                logger.info(f"[ImageUtils] 清理了 {cleaned_count} 个旧截图文件")
            
            return cleaned_count
        
        except Exception as e:
            logger.error(f"[ImageUtils] 清理截图失败: {str(e)}")
            return 0
    
    @staticmethod
    def validate_image_format(file_path: str) -> bool:
        """验证图像格式"""
        try:
            if not os.path.exists(file_path):
                return False
            
            # 检查文件扩展名
            valid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp']
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext not in valid_extensions:
                return False
            
            # 检查文件头（简单的魔术字节检查）
            with open(file_path, 'rb') as f:
                header = f.read(8)
                
                # PNG: 89 50 4E 47 0D 0A 1A 0A
                if header.startswith(b'\x89PNG\r\n\x1a\n'):
                    return True
                
                # JPEG: FF D8 FF
                if header.startswith(b'\xff\xd8\xff'):
                    return True
                
                # GIF: 47 49 46 38
                if header.startswith(b'GIF8'):
                    return True
                
                # BMP: 42 4D
                if header.startswith(b'BM'):
                    return True
            
            return False
        
        except Exception as e:
            logger.error(f"[ImageUtils] 验证图像格式失败: {str(e)}")
            return False
    
    @staticmethod
    def get_image_comparison_report(baseline_path: str, current_path: str, threshold: float = 0.1) -> Dict[str, Any]:
        """生成图像比较报告"""
        try:
            baseline_info = ImageUtils.get_image_info(baseline_path)
            current_info = ImageUtils.get_image_info(current_path)
            
            if not baseline_info.get("exists"):
                return {
                    "status": "error",
                    "message": "基线图像不存在",
                    "baseline_path": baseline_path
                }
            
            if not current_info.get("exists"):
                return {
                    "status": "error", 
                    "message": "当前图像不存在",
                    "current_path": current_path
                }
            
            similarity = ImageUtils.compare_images_simple(baseline_path, current_path)
            is_match = similarity >= (1 - threshold)
            
            return {
                "status": "success",
                "similarity": similarity,
                "threshold": threshold,
                "is_match": is_match,
                "baseline_info": baseline_info,
                "current_info": current_info,
                "message": "图像比较完成"
            }
        
        except Exception as e:
            logger.error(f"[ImageUtils] 生成比较报告失败: {str(e)}")
            return {
                "status": "error",
                "message": f"比较报告生成失败: {str(e)}"
            }
