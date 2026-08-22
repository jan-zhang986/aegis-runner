# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName src.ui.utils
@className SelectorUtils
@describe 选择器工具类 - 提供选择器相关的工具方法
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from src.engine.core.simple_logger import logger


class SelectorUtils:
    """选择器工具类"""
    
    @staticmethod
    def generate_css_selector(element_info: Dict[str, Any]) -> List[str]:
        """生成CSS选择器候选列表"""
        selectors = []
        
        # ID选择器
        if element_info.get("id"):
            selectors.append(f"#{element_info['id']}")
        
        # 类名选择器
        if element_info.get("class"):
            classes = element_info["class"].split()
            for cls in classes:
                if cls.strip():
                    selectors.append(f".{cls.strip()}")
        
        # 属性选择器
        if element_info.get("name"):
            selectors.append(f"[name='{element_info['name']}']")
        
        if element_info.get("type"):
            selectors.append(f"[type='{element_info['type']}']")
        
        if element_info.get("placeholder"):
            selectors.append(f"[placeholder='{element_info['placeholder']}']")
        
        # 文本内容选择器
        if element_info.get("text"):
            text = element_info["text"].strip()
            if len(text) <= 50:  # 避免过长的文本
                selectors.append(f":contains('{text}')")
        
        # 标签选择器
        if element_info.get("tag"):
            tag = element_info["tag"].lower()
            if tag not in ["div", "span", "p"]:  # 避免过于通用的标签
                selectors.append(tag)
        
        return selectors
    
    @staticmethod
    def generate_xpath_selector(element_info: Dict[str, Any]) -> List[str]:
        """生成XPath选择器候选列表"""
        selectors = []
        
        # 基于ID的XPath
        if element_info.get("id"):
            selectors.append(f"//*[@id='{element_info['id']}']")
        
        # 基于属性的XPath
        if element_info.get("name"):
            selectors.append(f"//*[@name='{element_info['name']}']")
        
        if element_info.get("type"):
            selectors.append(f"//*[@type='{element_info['type']}']")
        
        # 基于文本的XPath
        if element_info.get("text"):
            text = element_info["text"].strip()
            if len(text) <= 50:
                selectors.append(f"//*[text()='{text}']")
                selectors.append(f"//*[contains(text(), '{text}')]")
        
        # 基于标签和属性的组合
        if element_info.get("tag") and element_info.get("class"):
            tag = element_info["tag"].lower()
            classes = element_info["class"].split()
            for cls in classes:
                if cls.strip():
                    selectors.append(f"//{tag}[@class='{cls.strip()}']")
        
        return selectors
    
    @staticmethod
    def validate_css_selector(selector: str) -> bool:
        """验证CSS选择器"""
        if not selector or not selector.strip():
            return False
        
        # 基本的CSS选择器语法检查
        try:
            # 检查是否包含非法字符
            if re.search(r'[<>"\'\\]', selector):
                return False
            
            # 检查基本语法
            if selector.startswith("//"):
                return False  # 这是XPath语法
            
            return True
        except Exception:
            return False
    
    @staticmethod
    def validate_xpath_selector(selector: str) -> bool:
        """验证XPath选择器"""
        if not selector or not selector.strip():
            return False
        
        # 基本的XPath语法检查
        try:
            # 检查是否以//或/开头
            if not (selector.startswith("//") or selector.startswith("/")):
                return False
            
            # 检查基本语法
            if selector.startswith("#") or selector.startswith("."):
                return False  # 这是CSS语法
            
            return True
        except Exception:
            return False
    
    @staticmethod
    def optimize_selector(selector: str, selector_type: str) -> str:
        """优化选择器"""
        if not selector:
            return ""
        
        selector = selector.strip()
        
        if selector_type == "css":
            # CSS选择器优化
            # 移除多余的空格
            selector = re.sub(r'\s+', ' ', selector)
            
            # 简化复杂的选择器
            if selector.count(" ") > 3:  # 如果层级太深，尝试简化
                parts = selector.split()
                if len(parts) > 4:
                    selector = " ".join(parts[-3:])  # 只保留最后3层
            
        elif selector_type == "xpath":
            # XPath选择器优化
            # 移除多余的空格
            selector = re.sub(r'\s+', ' ', selector)
            
            # 简化复杂的XPath
            if selector.count("/") > 5:  # 如果路径太深，尝试简化
                # 尝试使用更直接的选择器
                if "//*[" in selector:
                    # 提取属性选择器部分
                    match = re.search(r'//\*\[([^\]]+)\]', selector)
                    if match:
                        selector = f"//*[{match.group(1)}]"
        
        return selector
    
    @staticmethod
    def get_selector_priority(selector: str, selector_type: str) -> int:
        """获取选择器优先级（数字越小优先级越高）"""
        if selector_type == "css":
            if selector.startswith("#"):
                return 1  # ID选择器优先级最高
            elif selector.startswith("."):
                return 2  # 类选择器
            elif selector.startswith("["):
                return 3  # 属性选择器
            elif " " not in selector:
                return 4  # 简单标签选择器
            else:
                return 5  # 复杂选择器
        
        elif selector_type == "xpath":
            if selector.startswith("//*[@id="):
                return 1  # 基于ID的XPath
            elif selector.startswith("//*[@name="):
                return 2  # 基于name的XPath
            elif selector.startswith("//*[@type="):
                return 3  # 基于type的XPath
            elif selector.startswith("//*[text()="):
                return 4  # 基于文本的XPath
            else:
                return 5  # 其他XPath
        
        return 10  # 默认优先级
    
    @staticmethod
    def rank_selectors(selectors: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """对选择器进行排序（按优先级）"""
        def sort_key(item):
            selector, selector_type = item
            return SelectorUtils.get_selector_priority(selector, selector_type)
        
        return sorted(selectors, key=sort_key)
    
    @staticmethod
    def extract_element_attributes(html_content: str, tag_name: str = None) -> List[Dict[str, Any]]:
        """从HTML内容中提取元素属性"""
        elements = []
        
        # 简化的HTML解析（实际项目中应使用BeautifulSoup等库）
        pattern = r'<(\w+)([^>]*)>'
        matches = re.findall(pattern, html_content, re.IGNORECASE)
        
        for tag, attributes in matches:
            if tag_name and tag.lower() != tag_name.lower():
                continue
            
            element = {"tag": tag.lower()}
            
            # 解析属性
            attr_pattern = r'(\w+)=["\']([^"\']*)["\']'
            attr_matches = re.findall(attr_pattern, attributes)
            
            for attr_name, attr_value in attr_matches:
                element[attr_name.lower()] = attr_value
            
            elements.append(element)
        
        return elements
    
    @staticmethod
    def suggest_alternative_selectors(original_selector: str, selector_type: str, element_info: Dict[str, Any]) -> List[str]:
        """建议替代选择器"""
        alternatives = []
        
        if selector_type == "css":
            # 如果原选择器是ID，建议类选择器
            if original_selector.startswith("#") and element_info.get("class"):
                classes = element_info["class"].split()
                for cls in classes:
                    if cls.strip():
                        alternatives.append(f".{cls.strip()}")
            
            # 如果原选择器是类，建议ID选择器
            elif original_selector.startswith(".") and element_info.get("id"):
                alternatives.append(f"#{element_info['id']}")
            
            # 建议属性选择器
            if element_info.get("name"):
                alternatives.append(f"[name='{element_info['name']}']")
            
            if element_info.get("type"):
                alternatives.append(f"[type='{element_info['type']}']")
        
        elif selector_type == "xpath":
            # 生成CSS替代选择器
            css_alternatives = SelectorUtils.generate_css_selector(element_info)
            alternatives.extend(css_alternatives)
        
        return alternatives
