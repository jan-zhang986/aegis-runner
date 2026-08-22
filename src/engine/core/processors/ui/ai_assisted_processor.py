# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-30
@packageName src.core.processors.ui
@className AIAssistedUIProcessor
@describe AI辅助UI处理器 - 提供AI增强的元素定位和自愈能力
"""

import time
import json
from typing import Dict, Any, Optional, List
from playwright.async_api import Page
from src.engine.context import ExecutionContext
from .base_ui_processor import BaseUIProcessor
from src.engine.core.simple_logger import logger
from src.engine.core.ui.playwright.ui_manager import ui_manager


class AIAssistedUIProcessor(BaseUIProcessor):
    """AI辅助UI处理器"""
    
    def __init__(self):
        super().__init__()
        self.ai_enabled = False
        self.ai_model = None
        self.selector_memory = {}  # 记忆成功的选择器
        self.healing_history = []  # 自愈历史
    
    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> Any:
        """执行AI辅助操作"""
        config = node_info.get("data", {}).get("config", {})
        operation = config.get("operation", "find_by_description")
        
        logger.info(f"[AIAssistedProcessor] 执行AI辅助操作: {operation}")
        
        # 根据操作类型分发处理
        if operation == "find_by_description":
            return self._handle_find_by_description(config, context)
        elif operation == "auto_heal_selector":
            return self._handle_auto_heal_selector(config, context)
        elif operation == "intelligent_wait":
            return self._handle_intelligent_wait(config, context)
        elif operation == "suggest_selectors":
            return self._handle_suggest_selectors(config, context)
        elif operation == "analyze_page_structure":
            return self._handle_analyze_page_structure(config, context)
        elif operation == "semantic_search":
            return self._handle_semantic_search(config, context)
        else:
            raise ValueError(f"不支持的AI辅助操作: {operation}")
    
    def _handle_find_by_description(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """通过自然语言描述查找元素"""
        description = context.render_string(config.get("description", ""))
        page_id = config.get("page_id", "default")
        use_ai = config.get("use_ai", True)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 获取页面DOM结构
            dom_info = ui_manager.run_async(self._extract_dom_info)(page)
            
            if use_ai and self.ai_enabled:
                # 使用AI模型查找
                selector = self._find_selector_with_ai(description, dom_info)
            else:
                # 使用启发式规则查找
                selector = self._find_selector_with_heuristics(description, dom_info)
            
            if not selector:
                raise ValueError(f"无法根据描述找到元素: {description}")
            
            # 验证选择器
            element = page.locator(selector)
            count = ui_manager.run_async(element.count)()
            
            if count == 0:
                raise ValueError(f"生成的选择器无效: {selector}")
            
            logger.info(f"[AIAssistedProcessor] 通过描述找到元素: {description} -> {selector}")
            
            # 记忆成功的选择器
            self.selector_memory[description] = selector
            
            return {
                "status": "success",
                "operation": "find_by_description",
                "description": description,
                "selector": selector,
                "element_count": count,
                "page_id": page_id,
                "message": "通过描述查找元素成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[AIAssistedProcessor] 通过描述查找元素失败: {str(e)}")
            return {
                "status": "error",
                "operation": "find_by_description",
                "description": description,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_auto_heal_selector(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """自动修复失败的选择器"""
        failed_selector = config.get("failed_selector", "")
        selector_type = config.get("selector_type", "css")
        page_id = config.get("page_id", "default")
        healing_strategy = config.get("healing_strategy", "auto")  # auto, ai, heuristic
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            logger.info(f"[AIAssistedProcessor] 尝试修复选择器: {failed_selector}")
            
            # 获取页面结构
            dom_info = ui_manager.run_async(self._extract_dom_info)(page)
            
            # 根据策略选择修复方法
            if healing_strategy == "ai" and self.ai_enabled:
                new_selector = self._heal_with_ai(failed_selector, dom_info)
            elif healing_strategy == "heuristic" or not self.ai_enabled:
                new_selector = self._heal_with_heuristics(failed_selector, dom_info)
            else:
                # 自动选择：先尝试AI，失败则用启发式
                new_selector = self._heal_with_ai(failed_selector, dom_info)
                if not new_selector:
                    new_selector = self._heal_with_heuristics(failed_selector, dom_info)
            
            if not new_selector:
                raise ValueError("无法修复选择器")
            
            # 验证新选择器
            element = page.locator(new_selector)
            count = ui_manager.run_async(element.count)()
            
            if count == 0:
                raise ValueError(f"修复后的选择器无效: {new_selector}")
            
            # 记录自愈历史
            healing_record = {
                "original_selector": failed_selector,
                "new_selector": new_selector,
                "strategy": healing_strategy,
                "timestamp": time.time(),
                "success": True
            }
            self.healing_history.append(healing_record)
            
            logger.info(f"[AIAssistedProcessor] 选择器修复成功: {failed_selector} -> {new_selector}")
            
            return {
                "status": "success",
                "operation": "auto_heal_selector",
                "original_selector": failed_selector,
                "new_selector": new_selector,
                "element_count": count,
                "healing_strategy": healing_strategy,
                "page_id": page_id,
                "message": "选择器修复成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[AIAssistedProcessor] 选择器修复失败: {str(e)}")
            
            # 记录失败的自愈尝试
            healing_record = {
                "original_selector": failed_selector,
                "strategy": healing_strategy,
                "timestamp": time.time(),
                "success": False,
                "error": str(e)
            }
            self.healing_history.append(healing_record)
            
            return {
                "status": "error",
                "operation": "auto_heal_selector",
                "original_selector": failed_selector,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_intelligent_wait(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """智能等待 - 根据目标自动判断等待条件"""
        goal = context.render_string(config.get("goal", ""))
        page_id = config.get("page_id", "default")
        timeout = config.get("timeout", 30000)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            logger.info(f"[AIAssistedProcessor] 智能等待目标: {goal}")
            
            # 分析目标，确定等待策略
            wait_strategy = self._analyze_wait_goal(goal)
            
            # 执行等待
            if wait_strategy == "element":
                # 等待元素出现
                selector = self._extract_selector_from_goal(goal)
                element = page.locator(selector)
                ui_manager.run_async(element.wait_for)(state="visible", timeout=timeout)
                
            elif wait_strategy == "navigation":
                # 等待导航完成
                ui_manager.run_async(page.wait_for_load_state)("networkidle", timeout=timeout)
                
            elif wait_strategy == "text":
                # 等待文本出现
                text = self._extract_text_from_goal(goal)
                ui_manager.run_async(page.wait_for_function)(
                    f"document.body.textContent.includes('{text}')",
                    timeout=timeout
                )
            
            else:
                # 默认等待网络空闲
                ui_manager.run_async(page.wait_for_load_state)("networkidle", timeout=timeout)
            
            logger.info(f"[AIAssistedProcessor] 智能等待完成: {goal}")
            
            return {
                "status": "success",
                "operation": "intelligent_wait",
                "goal": goal,
                "wait_strategy": wait_strategy,
                "timeout": timeout,
                "page_id": page_id,
                "message": "智能等待成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[AIAssistedProcessor] 智能等待失败: {str(e)}")
            return {
                "status": "error",
                "operation": "intelligent_wait",
                "goal": goal,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_suggest_selectors(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """为页面元素建议最佳选择器"""
        page_id = config.get("page_id", "default")
        element_description = context.render_string(config.get("element_description", ""))
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 获取页面结构
            dom_info = ui_manager.run_async(self._extract_dom_info)(page)
            
            # 生成建议的选择器
            suggested_selectors = self._generate_selector_suggestions(element_description, dom_info)
            
            logger.info(f"[AIAssistedProcessor] 生成了 {len(suggested_selectors)} 个选择器建议")
            
            return {
                "status": "success",
                "operation": "suggest_selectors",
                "element_description": element_description,
                "suggested_selectors": suggested_selectors,
                "count": len(suggested_selectors),
                "page_id": page_id,
                "message": "选择器建议生成成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[AIAssistedProcessor] 生成选择器建议失败: {str(e)}")
            return {
                "status": "error",
                "operation": "suggest_selectors",
                "element_description": element_description,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_analyze_page_structure(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """分析页面结构"""
        page_id = config.get("page_id", "default")
        analysis_depth = config.get("analysis_depth", "basic")  # basic, detailed, full
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 分析页面结构
            structure_analysis = ui_manager.run_async(self._analyze_page_structure_async)(page, analysis_depth)
            
            logger.info(f"[AIAssistedProcessor] 页面结构分析完成")
            
            return {
                "status": "success",
                "operation": "analyze_page_structure",
                "analysis_depth": analysis_depth,
                "structure_analysis": structure_analysis,
                "page_id": page_id,
                "message": "页面结构分析成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[AIAssistedProcessor] 页面结构分析失败: {str(e)}")
            return {
                "status": "error",
                "operation": "analyze_page_structure",
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    def _handle_semantic_search(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """语义搜索页面元素"""
        query = context.render_string(config.get("query", ""))
        page_id = config.get("page_id", "default")
        max_results = config.get("max_results", 10)
        
        try:
            page = ui_manager.get_page(page_id)
            if not page:
                raise ValueError(f"页面 {page_id} 不存在")
            
            # 执行语义搜索
            search_results = ui_manager.run_async(self._semantic_search_async)(page, query, max_results)
            
            logger.info(f"[AIAssistedProcessor] 语义搜索找到 {len(search_results)} 个结果")
            
            return {
                "status": "success",
                "operation": "semantic_search",
                "query": query,
                "search_results": search_results,
                "count": len(search_results),
                "page_id": page_id,
                "message": "语义搜索成功",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"[AIAssistedProcessor] 语义搜索失败: {str(e)}")
            return {
                "status": "error",
                "operation": "semantic_search",
                "query": query,
                "error": str(e),
                "page_id": page_id,
                "timestamp": time.time()
            }
    
    # ============= 辅助方法 =============
    
    async def _extract_dom_info(self, page: Page) -> Dict[str, Any]:
        """提取DOM信息"""
        return await page.evaluate("""
            () => {
                const getElementInfo = (element) => {
                    return {
                        tag: element.tagName.toLowerCase(),
                        id: element.id || null,
                        classes: Array.from(element.classList),
                        text: element.textContent?.trim().substring(0, 100) || null,
                        attributes: Array.from(element.attributes).map(attr => ({
                            name: attr.name,
                            value: attr.value
                        })),
                        visible: element.offsetParent !== null
                    };
                };
                
                // 获取所有可交互元素
                const interactiveElements = Array.from(
                    document.querySelectorAll('button, a, input, select, textarea, [role="button"], [onclick]')
                ).map(getElementInfo);
                
                // 获取所有带ID的元素
                const idElements = Array.from(
                    document.querySelectorAll('[id]')
                ).map(getElementInfo);
                
                // 获取所有带data-testid的元素
                const testIdElements = Array.from(
                    document.querySelectorAll('[data-testid], [data-test], [data-qa]')
                ).map(getElementInfo);
                
                return {
                    interactive_elements: interactiveElements,
                    id_elements: idElements,
                    test_id_elements: testIdElements,
                    total_elements: document.querySelectorAll('*').length
                };
            }
        """)
    
    def _find_selector_with_heuristics(self, description: str, dom_info: Dict[str, Any]) -> Optional[str]:
        """使用启发式规则查找选择器"""
        description_lower = description.lower()
        
        # 1. 搜索测试属性
        for elem in dom_info.get("test_id_elements", []):
            for attr in elem.get("attributes", []):
                if attr["name"] in ["data-testid", "data-test", "data-qa"]:
                    if description_lower in attr["value"].lower():
                        return f"[{attr['name']}='{attr['value']}']"
        
        # 2. 搜索ID
        for elem in dom_info.get("id_elements", []):
            if elem.get("id") and description_lower in elem["id"].lower():
                return f"#{elem['id']}"
        
        # 3. 搜索文本内容
        for elem in dom_info.get("interactive_elements", []):
            if elem.get("text") and description_lower in elem["text"].lower():
                # 尝试构建选择器
                if elem.get("id"):
                    return f"#{elem['id']}"
                elif elem.get("classes"):
                    return f"{elem['tag']}.{'.'.join(elem['classes'])}"
        
        return None
    
    def _find_selector_with_ai(self, description: str, dom_info: Dict[str, Any]) -> Optional[str]:
        """使用AI模型查找选择器（占位符）"""
        # TODO: 集成实际的AI模型（GPT, Claude等）
        logger.warning("[AIAssistedProcessor] AI模型未配置，使用启发式方法")
        return self._find_selector_with_heuristics(description, dom_info)
    
    def _heal_with_heuristics(self, failed_selector: str, dom_info: Dict[str, Any]) -> Optional[str]:
        """使用启发式规则修复选择器"""
        # 提取选择器特征
        import re
        
        # 1. 如果是ID选择器，尝试查找相似ID
        if failed_selector.startswith("#"):
            failed_id = failed_selector[1:]
            for elem in dom_info.get("id_elements", []):
                elem_id = elem.get("id", "")
                if elem_id and (
                    failed_id in elem_id or 
                    elem_id in failed_id or
                    self._similarity_score(failed_id, elem_id) > 0.6
                ):
                    return f"#{elem_id}"
        
        # 2. 如果是类选择器，尝试查找相似类名
        if "." in failed_selector:
            classes = re.findall(r'\.([a-zA-Z0-9_-]+)', failed_selector)
            if classes:
                for elem in dom_info.get("interactive_elements", []):
                    elem_classes = elem.get("classes", [])
                    match_count = sum(1 for c in classes if c in elem_classes)
                    if match_count >= len(classes) * 0.5:  # 至少匹配50%的类
                        if elem.get("id"):
                            return f"#{elem['id']}"
                        return f"{elem['tag']}.{'.'.join(elem_classes[:2])}"
        
        # 3. 尝试使用测试属性
        if dom_info.get("test_id_elements"):
            first_test_elem = dom_info["test_id_elements"][0]
            for attr in first_test_elem.get("attributes", []):
                if attr["name"] in ["data-testid", "data-test", "data-qa"]:
                    return f"[{attr['name']}='{attr['value']}']"
        
        return None
    
    def _heal_with_ai(self, failed_selector: str, dom_info: Dict[str, Any]) -> Optional[str]:
        """使用AI模型修复选择器（占位符）"""
        # TODO: 集成实际的AI模型
        logger.warning("[AIAssistedProcessor] AI模型未配置，使用启发式方法")
        return self._heal_with_heuristics(failed_selector, dom_info)
    
    def _similarity_score(self, str1: str, str2: str) -> float:
        """计算字符串相似度"""
        # 简单的Levenshtein距离实现
        if not str1 or not str2:
            return 0.0
        
        len1, len2 = len(str1), len(str2)
        max_len = max(len1, len2)
        
        # 计算编辑距离
        dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        
        for i in range(len1 + 1):
            dp[i][0] = i
        for j in range(len2 + 1):
            dp[0][j] = j
        
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                if str1[i-1] == str2[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1]) + 1
        
        distance = dp[len1][len2]
        similarity = 1 - (distance / max_len)
        
        return similarity
    
    def _analyze_wait_goal(self, goal: str) -> str:
        """分析等待目标，确定等待策略"""
        goal_lower = goal.lower()
        
        if any(keyword in goal_lower for keyword in ["element", "button", "input", "click"]):
            return "element"
        elif any(keyword in goal_lower for keyword in ["navigate", "load", "page"]):
            return "navigation"
        elif any(keyword in goal_lower for keyword in ["text", "content", "显示"]):
            return "text"
        else:
            return "default"
    
    def _extract_selector_from_goal(self, goal: str) -> str:
        """从目标描述中提取选择器"""
        # 简单的关键词提取
        import re
        
        # 查找带引号的文本
        quoted = re.findall(r'"([^"]+)"', goal)
        if quoted:
            return f'text="{quoted[0]}"'
        
        # 查找#id或.class
        id_match = re.search(r'#([a-zA-Z0-9_-]+)', goal)
        if id_match:
            return f"#{id_match.group(1)}"
        
        class_match = re.search(r'\.([a-zA-Z0-9_-]+)', goal)
        if class_match:
            return f".{class_match.group(1)}"
        
        return "body"  # 默认返回body
    
    def _extract_text_from_goal(self, goal: str) -> str:
        """从目标描述中提取文本"""
        import re
        quoted = re.findall(r'"([^"]+)"', goal)
        return quoted[0] if quoted else ""
    
    def _generate_selector_suggestions(
        self, 
        description: str, 
        dom_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """生成选择器建议"""
        suggestions = []
        
        # 基于测试属性的建议
        for elem in dom_info.get("test_id_elements", []):
            for attr in elem.get("attributes", []):
                if attr["name"] in ["data-testid", "data-test", "data-qa"]:
                    suggestions.append({
                        "selector": f"[{attr['name']}='{attr['value']}']",
                        "type": "test_attribute",
                        "priority": 10,
                        "description": f"测试属性选择器: {attr['value']}"
                    })
        
        # 基于ID的建议
        for elem in dom_info.get("id_elements", []):
            if elem.get("id"):
                suggestions.append({
                    "selector": f"#{elem['id']}",
                    "type": "id",
                    "priority": 9,
                    "description": f"ID选择器: {elem['id']}"
                })
        
        # 基于类名的建议
        for elem in dom_info.get("interactive_elements", []):
            if elem.get("classes"):
                selector = f"{elem['tag']}.{'.'.join(elem['classes'][:2])}"
                suggestions.append({
                    "selector": selector,
                    "type": "class",
                    "priority": 5,
                    "description": f"类选择器: {selector}"
                })
        
        # 按优先级排序
        suggestions.sort(key=lambda x: x["priority"], reverse=True)
        
        return suggestions[:10]  # 返回前10个建议
    
    async def _analyze_page_structure_async(
        self, 
        page: Page, 
        depth: str
    ) -> Dict[str, Any]:
        """异步分析页面结构"""
        analysis = await page.evaluate("""
            (depth) => {
                const analysis = {
                    basic: {
                        title: document.title,
                        url: window.location.href,
                        total_elements: document.querySelectorAll('*').length,
                        interactive_elements: document.querySelectorAll('button, a, input, select, textarea').length
                    }
                };
                
                if (depth === 'detailed' || depth === 'full') {
                    analysis.detailed = {
                        forms: document.querySelectorAll('form').length,
                        images: document.querySelectorAll('img').length,
                        scripts: document.querySelectorAll('script').length,
                        stylesheets: document.querySelectorAll('link[rel="stylesheet"]').length,
                        iframes: document.querySelectorAll('iframe').length
                    };
                }
                
                if (depth === 'full') {
                    analysis.full = {
                        headings: {
                            h1: document.querySelectorAll('h1').length,
                            h2: document.querySelectorAll('h2').length,
                            h3: document.querySelectorAll('h3').length
                        },
                        lists: document.querySelectorAll('ul, ol').length,
                        tables: document.querySelectorAll('table').length,
                        sections: document.querySelectorAll('section, article, aside').length
                    };
                }
                
                return analysis;
            }
        """, depth)
        
        return analysis
    
    async def _semantic_search_async(
        self, 
        page: Page, 
        query: str, 
        max_results: int
    ) -> List[Dict[str, Any]]:
        """异步语义搜索"""
        results = await page.evaluate("""
            (query, maxResults) => {
                const elements = Array.from(document.querySelectorAll('*'));
                const results = [];
                const queryLower = query.toLowerCase();
                
                for (const element of elements) {
                    let score = 0;
                    
                    // 检查文本内容
                    const text = element.textContent?.trim() || '';
                    if (text.toLowerCase().includes(queryLower)) {
                        score += 3;
                    }
                    
                    // 检查ID
                    if (element.id && element.id.toLowerCase().includes(queryLower)) {
                        score += 5;
                    }
                    
                    // 检查类名
                    if (element.className) {
                        const classes = Array.from(element.classList);
                        for (const cls of classes) {
                            if (cls.toLowerCase().includes(queryLower)) {
                                score += 2;
                            }
                        }
                    }
                    
                    // 检查属性
                    for (const attr of element.attributes) {
                        if (attr.value.toLowerCase().includes(queryLower)) {
                            score += 1;
                        }
                    }
                    
                    if (score > 0) {
                        results.push({
                            tag: element.tagName.toLowerCase(),
                            id: element.id || null,
                            classes: Array.from(element.classList),
                            text: text.substring(0, 100),
                            score: score
                        });
                    }
                }
                
                // 按分数排序
                results.sort((a, b) => b.score - a.score);
                return results.slice(0, maxResults);
            }
        """, query, max_results)
        
        return results
    
    def get_healing_history(self) -> List[Dict[str, Any]]:
        """获取自愈历史"""
        return self.healing_history
    
    def get_selector_memory(self) -> Dict[str, str]:
        """获取选择器记忆"""
        return self.selector_memory
    
    def _validate_ui_config(self, config: Dict[str, Any]) -> bool:
        """验证UI特定配置"""
        return True

