# -*- coding: utf-8 -*-
"""
Aegis AST 静态解析器
在不执行、不导入测试脚本的前提下，通过 Python AST 静态提取测试文件中的
@aegis.case, @aegis.feature, @aegis.epic 元数据，用于 PageIndex 覆盖率分析与 IDE 大纲渲染。
"""
import ast
import os
from typing import List, Dict, Any, Optional


class AegisAstVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.cases: List[Dict[str, Any]] = []
        self._current_feature: Optional[str] = None
        self._current_epic: Optional[str] = None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        case_info = self._parse_case_decorators(node)
        if case_info:
            case_info["filePath"] = self.file_path
            case_info["functionName"] = node.name
            case_info["lineNo"] = node.lineno
            case_info["docstring"] = ast.get_docstring(node) or ""
            self.cases.append(case_info)
        self.generic_visit(node)

    def _parse_case_decorators(self, node: ast.FunctionDef) -> Optional[Dict[str, Any]]:
        case_meta = None
        feature = self._current_feature
        epic = self._current_epic

        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue

            # 匹配 @aegis.case(...) 或 @case(...)
            func_name = self._get_decorator_name(decorator.func)

            if func_name in ("aegis.case", "case"):
                case_meta = self._extract_call_kwargs(decorator)
            elif func_name in ("aegis.feature", "feature"):
                if decorator.args and isinstance(decorator.args[0], ast.Constant):
                    feature = decorator.args[0].value
            elif func_name in ("aegis.epic", "epic"):
                if decorator.args and isinstance(decorator.args[0], ast.Constant):
                    epic = decorator.args[0].value

        if case_meta is not None:
            if "feature" not in case_meta and feature:
                case_meta["feature"] = feature
            if "epic" not in case_meta and epic:
                case_meta["epic"] = epic

        return case_meta

    def _get_decorator_name(self, node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            val = self._get_decorator_name(node.value)
            return f"{val}.{node.attr}" if val else node.attr
        return ""

    def _extract_call_kwargs(self, call_node: ast.Call) -> Dict[str, Any]:
        meta = {
            "id": "",
            "req": "",
            "title": "",
            "risk": "",
            "priority": "P1",
            "tags": [],
        }

        for keyword in call_node.keywords:
            k = keyword.arg
            if isinstance(keyword.value, ast.Constant):
                meta[k] = keyword.value.value
            elif isinstance(keyword.value, ast.List):
                meta[k] = [
                    elt.value
                    for elt in keyword.value.elts
                    if isinstance(elt, ast.Constant)
                ]

        return meta


def parse_test_file(file_path: str) -> List[Dict[str, Any]]:
    """解析单个 Python 测试文件，提取所有 @aegis.case 元数据"""
    if not os.path.isfile(file_path) or not file_path.endswith(".py"):
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content, filename=file_path)
        visitor = AegisAstVisitor(file_path)
        visitor.visit(tree)
        return visitor.cases
    except Exception:
        return []


def scan_test_directory(directory_path: str) -> List[Dict[str, Any]]:
    """递归扫描测试目录下的所有 .py 文件"""
    all_cases = []
    for root, _, files in os.walk(directory_path):
        for f in sorted(files):
            if f.startswith("test_") and f.endswith(".py"):
                full_path = os.path.join(root, f)
                all_cases.extend(parse_test_file(full_path))
    return all_cases
