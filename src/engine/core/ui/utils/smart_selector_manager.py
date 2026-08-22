# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-30
@packageName src.core.ui.utils
@className SmartSelectorManager
@describe 智能选择器管理器 - 提供稳定的选择器生成和自动修复能力
"""

import time
import json
from typing import Dict, Any, List, Optional, Tuple
from playwright.async_api import Page, Locator
from src.engine.core.simple_logger import logger


class SmartSelectorManager:
    """智能选择器管理器"""
    
    def __init__(self):
        self.selector_priority = [
            "data-testid",      # 优先级最高 - 测试专用属性
            "id",               # ID选择器
            "aria-label",       # 无障碍标签
            "name",             # name属性
            "data-test",        # 另一种测试属性
            "data-qa",          # QA测试属性
            "class",            # CSS类名
            "xpath"             # XPath - 优先级最低
        ]
        self.selector_cache: Dict[str, List[str]] = {}  # 缓存有效的选择器
        self.failed_selectors: Dict[str, int] = {}  # 记录失败次数
        
    def generate_robust_selectors(self, element_info: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        生成多个备用选择器
        
        Args:
            element_info: 元素信息字典
            
        Returns:
            选择器列表，每个选择器包含type和value
        """
        selectors = []
        
        # 1. data-testid 选择器
        if element_info.get("data-testid"):
            selectors.append({
                "type": "css",
                "value": f"[data-testid='{element_info['data-testid']}']",
                "priority": 10,
                "description": "测试专用属性选择器"
            })
        
        # 2. ID 选择器
        if element_info.get("id"):
            selectors.append({
                "type": "css",
                "value": f"#{element_info['id']}",
                "priority": 9,
                "description": "ID选择器"
            })
        
        # 3. aria-label 选择器
        if element_info.get("aria-label"):
            selectors.append({
                "type": "css",
                "value": f"[aria-label='{element_info['aria-label']}']",
                "priority": 8,
                "description": "ARIA标签选择器"
            })
        
        # 4. name 属性选择器
        if element_info.get("name"):
            selectors.append({
                "type": "css",
                "value": f"[name='{element_info['name']}']",
                "priority": 7,
                "description": "name属性选择器"
            })
        
        # 5. data-test/data-qa 选择器
        for attr in ["data-test", "data-qa"]:
            if element_info.get(attr):
                selectors.append({
                    "type": "css",
                    "value": f"[{attr}='{element_info[attr]}']",
                    "priority": 6,
                    "description": f"{attr}属性选择器"
                })
        
        # 6. 组合选择器（标签+类名）
        if element_info.get("tag") and element_info.get("class"):
            classes = element_info["class"].split()
            if classes:
                selectors.append({
                    "type": "css",
                    "value": f"{element_info['tag']}.{'.'.join(classes)}",
                    "priority": 5,
                    "description": "标签+类名组合选择器"
                })
        
        # 7. 类名选择器
        if element_info.get("class"):
            classes = element_info["class"].split()
            if classes:
                selectors.append({
                    "type": "css",
                    "value": f".{'.'.join(classes)}",
                    "priority": 4,
                    "description": "类名选择器"
                })
        
        # 8. 文本内容选择器
        if element_info.get("text"):
            text = element_info["text"].strip()
            if text:
                selectors.append({
                    "type": "text",
                    "value": text,
                    "priority": 3,
                    "description": "文本内容选择器"
                })
        
        # 9. XPath 选择器
        if element_info.get("xpath"):
            selectors.append({
                "type": "xpath",
                "value": element_info["xpath"],
                "priority": 2,
                "description": "XPath选择器"
            })
        
        # 按优先级排序
        selectors.sort(key=lambda x: x["priority"], reverse=True)
        
        return selectors
    
    async def find_element_with_fallback(
        self, 
        page: Page, 
        selectors: List[Dict[str, str]], 
        timeout: int = 30000
    ) -> Tuple[Optional[Locator], Optional[Dict[str, str]]]:
        """
        使用备用选择器查找元素
        
        Args:
            page: Playwright页面对象
            selectors: 选择器列表
            timeout: 超时时间（毫秒）
            
        Returns:
            (元素定位器, 成功的选择器) 或 (None, None)
        """
        for selector_info in selectors:
            selector_type = selector_info["type"]
            selector_value = selector_info["value"]
            
            # 检查是否在失败列表中
            cache_key = f"{selector_type}:{selector_value}"
            if self.failed_selectors.get(cache_key, 0) > 3:
                logger.warning(f"[SmartSelector] 跳过失败次数过多的选择器: {cache_key}")
                continue
            
            try:
                logger.info(f"[SmartSelector] 尝试选择器: {selector_info['description']} - {selector_value}")
                
                # 根据类型查找元素
                if selector_type == "css":
                    element = page.locator(selector_value)
                elif selector_type == "xpath":
                    element = page.locator(f"xpath={selector_value}")
                elif selector_type == "text":
                    element = page.get_by_text(selector_value)
                else:
                    element = page.locator(selector_value)
                
                # 等待元素出现
                await element.first.wait_for(state="attached", timeout=min(timeout, 5000))
                
                # 检查元素是否存在
                count = await element.count()
                if count > 0:
                    logger.info(f"[SmartSelector] 找到元素: {selector_info['description']} (共{count}个)")
                    
                    # 缓存成功的选择器
                    self.selector_cache[cache_key] = selector_info
                    
                    # 清除失败记录
                    if cache_key in self.failed_selectors:
                        del self.failed_selectors[cache_key]
                    
                    return element.first, selector_info
                    
            except Exception as e:
                logger.warning(f"[SmartSelector] 选择器失败: {selector_value} - {str(e)}")
                
                # 记录失败
                self.failed_selectors[cache_key] = self.failed_selectors.get(cache_key, 0) + 1
                continue
        
        logger.error("[SmartSelector] 所有选择器都失败了")
        return None, None
    
    async def extract_element_info(self, page: Page, selector: str, selector_type: str = "css") -> Dict[str, Any]:
        """
        提取元素的所有有用信息用于生成备用选择器
        
        Args:
            page: Playwright页面对象
            selector: 初始选择器
            selector_type: 选择器类型
            
        Returns:
            元素信息字典
        """
        try:
            # 查找元素
            if selector_type == "css":
                element = page.locator(selector)
            elif selector_type == "xpath":
                element = page.locator(f"xpath={selector}")
            else:
                element = page.locator(selector)
            
            # 提取元素信息
            element_info = await page.evaluate("""
                (selector) => {
                    const element = document.querySelector(selector);
                    if (!element) return null;
                    
                    return {
                        tag: element.tagName.toLowerCase(),
                        id: element.id || null,
                        class: element.className || null,
                        name: element.getAttribute('name') || null,
                        'data-testid': element.getAttribute('data-testid') || null,
                        'data-test': element.getAttribute('data-test') || null,
                        'data-qa': element.getAttribute('data-qa') || null,
                        'aria-label': element.getAttribute('aria-label') || null,
                        text: element.textContent?.trim() || null,
                        xpath: null  // XPath需要单独生成
                    };
                }
            """, selector)
            
            # 生成XPath
            if element_info:
                xpath = await self._generate_xpath(page, selector)
                element_info["xpath"] = xpath
            
            return element_info or {}
            
        except Exception as e:
            logger.error(f"[SmartSelector] 提取元素信息失败: {str(e)}")
            return {}
    
    async def _generate_xpath(self, page: Page, css_selector: str) -> Optional[str]:
        """生成元素的XPath"""
        try:
            xpath = await page.evaluate("""
                (selector) => {
                    const element = document.querySelector(selector);
                    if (!element) return null;
                    
                    function getXPath(element) {
                        if (element.id) {
                            return `//*[@id="${element.id}"]`;
                        }
                        if (element === document.body) {
                            return '/html/body';
                        }
                        
                        let ix = 0;
                        const siblings = element.parentNode.childNodes;
                        for (let i = 0; i < siblings.length; i++) {
                            const sibling = siblings[i];
                            if (sibling === element) {
                                return getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                            }
                            if (sibling.nodeType === 1 && sibling.tagName === element.tagName) {
                                ix++;
                            }
                        }
                    }
                    
                    return getXPath(element);
                }
            """, css_selector)
            
            return xpath
        except Exception as e:
            logger.warning(f"[SmartSelector] 生成XPath失败: {str(e)}")
            return None
    
    async def auto_heal_selector(
        self, 
        page: Page, 
        failed_selector: str, 
        selector_type: str = "css"
    ) -> Optional[Dict[str, str]]:
        """
        自动修复失败的选择器
        
        Args:
            page: Playwright页面对象
            failed_selector: 失败的选择器
            selector_type: 选择器类型
            
        Returns:
            新的选择器信息或None
        """
        logger.info(f"[SmartSelector] 尝试自动修复选择器: {failed_selector}")
        
        try:
            # 1. 尝试查找相似元素
            similar_elements = await self._find_similar_elements(page, failed_selector, selector_type)
            
            if similar_elements:
                logger.info(f"[SmartSelector] 找到 {len(similar_elements)} 个相似元素")
                
                # 2. 为第一个相似元素生成新选择器
                element_info = similar_elements[0]
                new_selectors = self.generate_robust_selectors(element_info)
                
                if new_selectors:
                    logger.info(f"[SmartSelector] 生成了 {len(new_selectors)} 个备用选择器")
                    return new_selectors[0]
            
            # 3. 如果找不到相似元素，尝试放宽条件
            logger.warning("[SmartSelector] 未找到相似元素，尝试放宽条件")
            relaxed_elements = await self._find_elements_by_relaxed_criteria(page, failed_selector)
            
            if relaxed_elements:
                element_info = relaxed_elements[0]
                new_selectors = self.generate_robust_selectors(element_info)
                if new_selectors:
                    return new_selectors[0]
            
            logger.error("[SmartSelector] 自动修复失败")
            return None
            
        except Exception as e:
            logger.error(f"[SmartSelector] 自动修复出错: {str(e)}")
            return None
    
    async def _find_similar_elements(
        self, 
        page: Page, 
        selector: str, 
        selector_type: str
    ) -> List[Dict[str, Any]]:
        """查找相似的元素"""
        try:
            # 提取选择器特征
            features = self._extract_selector_features(selector, selector_type)
            
            # 在页面中查找具有相似特征的元素
            similar_elements = await page.evaluate("""
                (features) => {
                    const elements = Array.from(document.querySelectorAll('*'));
                    const similar = [];
                    
                    for (const element of elements) {
                        let score = 0;
                        
                        // 比较标签名
                        if (features.tag && element.tagName.toLowerCase() === features.tag.toLowerCase()) {
                            score += 3;
                        }
                        
                        // 比较类名
                        if (features.classes) {
                            const elementClasses = Array.from(element.classList);
                            const matchedClasses = features.classes.filter(c => elementClasses.includes(c));
                            score += matchedClasses.length * 2;
                        }
                        
                        // 比较属性
                        if (features.attributes) {
                            for (const [key, value] of Object.entries(features.attributes)) {
                                if (element.getAttribute(key) === value) {
                                    score += 2;
                                }
                            }
                        }
                        
                        // 相似度足够高才加入结果
                        if (score >= 3) {
                            similar.push({
                                tag: element.tagName.toLowerCase(),
                                id: element.id || null,
                                class: element.className || null,
                                name: element.getAttribute('name') || null,
                                'data-testid': element.getAttribute('data-testid') || null,
                                'aria-label': element.getAttribute('aria-label') || null,
                                text: element.textContent?.trim().substring(0, 100) || null,
                                score: score
                            });
                        }
                    }
                    
                    // 按相似度排序
                    similar.sort((a, b) => b.score - a.score);
                    return similar.slice(0, 5);  // 返回前5个
                }
            """, features)
            
            return similar_elements
            
        except Exception as e:
            logger.error(f"[SmartSelector] 查找相似元素失败: {str(e)}")
            return []
    
    async def _find_elements_by_relaxed_criteria(
        self, 
        page: Page, 
        selector: str
    ) -> List[Dict[str, Any]]:
        """使用放宽的条件查找元素"""
        try:
            # 尝试只用标签名查找
            elements = await page.evaluate("""
                (selector) => {
                    // 提取标签名
                    const tagMatch = selector.match(/^([a-z]+)/i);
                    if (!tagMatch) return [];
                    
                    const tag = tagMatch[1];
                    const elements = Array.from(document.querySelectorAll(tag));
                    
                    return elements.slice(0, 10).map(element => ({
                        tag: element.tagName.toLowerCase(),
                        id: element.id || null,
                        class: element.className || null,
                        name: element.getAttribute('name') || null,
                        'data-testid': element.getAttribute('data-testid') || null,
                        text: element.textContent?.trim().substring(0, 100) || null
                    }));
                }
            """, selector)
            
            return elements
            
        except Exception as e:
            logger.error(f"[SmartSelector] 放宽条件查找失败: {str(e)}")
            return []
    
    def _extract_selector_features(self, selector: str, selector_type: str) -> Dict[str, Any]:
        """提取选择器特征"""
        features = {
            "tag": None,
            "classes": [],
            "attributes": {}
        }
        
        if selector_type == "css":
            # 解析CSS选择器
            # 提取标签名
            tag_match = selector.split('.')[0].split('#')[0].split('[')[0]
            if tag_match:
                features["tag"] = tag_match
            
            # 提取类名
            import re
            class_matches = re.findall(r'\.([a-zA-Z0-9_-]+)', selector)
            features["classes"] = class_matches
            
            # 提取属性
            attr_matches = re.findall(r'\[([a-zA-Z0-9_-]+)=["\']([^"\']+)["\']\]', selector)
            for attr, value in attr_matches:
                features["attributes"][attr] = value
        
        return features
    
    def get_selector_statistics(self) -> Dict[str, Any]:
        """获取选择器使用统计"""
        return {
            "cached_selectors": len(self.selector_cache),
            "failed_selectors": len(self.failed_selectors),
            "cache": dict(self.selector_cache),
            "failures": dict(self.failed_selectors)
        }
    
    def clear_cache(self):
        """清除选择器缓存"""
        self.selector_cache.clear()
        logger.info("[SmartSelector] 选择器缓存已清除")
    
    def clear_failures(self):
        """清除失败记录"""
        self.failed_selectors.clear()
        logger.info("[SmartSelector] 失败记录已清除")


# 全局智能选择器管理器实例
smart_selector_manager = SmartSelectorManager()

