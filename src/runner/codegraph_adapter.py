# -*- coding: utf-8 -*-
"""
AegisOne CodeGraph 适配器 (codegraph_adapter.py)
无缝桥接 colbymchenry/codegraph (Tree-sitter 本地代码知识图谱)：
1. 自动探测本地是否已安装 codegraph CLI 或 npx @colbymchenry/codegraph；
2. 封装 init / sync / impact / callers / callees 命令；
3. 当本地未安装 codegraph 时，提供基于 AST 与正则的优雅降级 (Graceful Fallback)；
4. 输出标准结构化拓扑分析结果，供 DeepSeek Harness 与 HarnessEngine 进行爆炸半径与风控计算。
"""
import json
import os
import re
import shutil
import subprocess
from typing import Dict, List, Any, Optional, Set


class CodeGraphAdapter:
    """colbymchenry/codegraph 本地图谱适配器"""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = workspace_root or os.getcwd()
        self.cli_command = self._detect_codegraph_cli()

    def _detect_codegraph_cli(self) -> Optional[List[str]]:
        """探测本地环境中的 codegraph 命令形式"""
        # 1. 优先检查本地编译的 vendor/codegraph/dist/bin/codegraph.js
        vendor_bin = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../vendor/codegraph/dist/bin/codegraph.js"))
        if os.path.exists(vendor_bin) and shutil.which("node"):
            return ["node", vendor_bin]

        # 2. 检查全局 PATH 中的 codegraph 二进制
        if shutil.which("codegraph"):
            return ["codegraph"]
        return None

    def query_diff(self, base_ref: str = "HEAD~1") -> Optional[Dict[str, Any]]:
        """调用 CodeGraph 原生 diff 命令进行变动与测试覆盖深度分析"""
        if self.is_available():
            try:
                cmd = self.cli_command + ["diff", base_ref, "-p", self.workspace_root, "--json"]
                proc = subprocess.run(
                    cmd,
                    cwd=self.workspace_root,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    return json.loads(proc.stdout)
            except Exception:
                pass
        return None

    def is_available(self) -> bool:
        """检查 codegraph 是否可用"""
        return self.cli_command is not None

    def init_or_sync(self) -> bool:
        """初始化或增量同步代码图谱索引"""
        if not self.is_available():
            return False

        codegraph_dir = os.path.join(self.workspace_root, ".codegraph")
        subcmd = "sync" if os.path.exists(codegraph_dir) else "init"

        try:
            cmd = self.cli_command + [subcmd]
            proc = subprocess.run(
                cmd,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return proc.returncode == 0
        except Exception:
            return False

    def query_impact(self, symbol: str, depth: int = 3) -> Dict[str, Any]:
        """
        查询某个符号 (函数/类) 的爆炸半径 (Blast Radius) 与波及范围
        """
        if self.is_available():
            try:
                cmd = self.cli_command + ["impact", symbol, "--depth", str(depth), "--json"]
                proc = subprocess.run(
                    cmd,
                    cwd=self.workspace_root,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    return json.loads(proc.stdout)
            except Exception:
                pass

        # 降级模式 (Fallback): 基于本地源码 AST/文本分析直接推导引用
        return self._fallback_impact(symbol, depth)

    def query_callers(self, symbol: str) -> List[str]:
        """查询调用方列表"""
        if self.is_available():
            try:
                cmd = self.cli_command + ["callers", symbol, "--json"]
                proc = subprocess.run(
                    cmd,
                    cwd=self.workspace_root,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    data = json.loads(proc.stdout)
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict) and "callers" in data:
                        return data["callers"]
            except Exception:
                pass

        # 降级推导调用方
        return self._fallback_find_callers(symbol)

    def analyze_changed_symbols_impact(self, changed_files: Dict[str, List[int]]) -> Dict[str, Any]:
        """
        输入 Git 变动文件和行号，计算受波及的整体调用拓扑与最大爆炸半径
        """
        symbols_impacted = []
        max_depth = 1
        total_fan_in = 0

        for file_path, lines in changed_files.items():
            full_path = os.path.join(self.workspace_root, file_path) if not os.path.isabs(file_path) else file_path
            if not os.path.exists(full_path):
                continue

            extracted_symbols = self._extract_symbols_from_file_lines(full_path, lines)
            for sym in extracted_symbols:
                impact = self.query_impact(sym, depth=3)
                depth = impact.get("depth", 1)
                callers = impact.get("callers", [])
                max_depth = max(max_depth, depth)
                total_fan_in += len(callers)

                symbols_impacted.append({
                    "symbol": sym,
                    "file": file_path,
                    "depth": depth,
                    "callersCount": len(callers),
                    "callers": callers[:5],
                    "riskWeight": "HIGH" if len(callers) > 3 or depth >= 2 else "LOW",
                })

        return {
            "isNativeCodeGraph": self.is_available(),
            "symbolsImpacted": symbols_impacted,
            "maxCallDepth": max_depth,
            "totalFanIn": total_fan_in,
            "overallArchitecturalRisk": "CRITICAL" if total_fan_in > 10 or max_depth >= 3 else ("HIGH" if total_fan_in > 0 else "LOW"),
        }

    # =========================================================================
    # 优雅降级 (Graceful Fallback) 实现
    # =========================================================================
    def _fallback_impact(self, symbol: str, depth: int) -> Dict[str, Any]:
        callers = self._fallback_find_callers(symbol)
        return {
            "symbol": symbol,
            "depth": min(depth, 2 if callers else 1),
            "callers": callers,
            "impactedFiles": list(set(c.split(":")[0] for c in callers if ":" in c)),
            "isFallback": True,
        }

    def _fallback_find_callers(self, symbol: str) -> List[str]:
        """在工作区内搜索对 symbol 的引用行 (支持函数调用、JSX 组件引用、类型使用与 Hook)"""
        callers = []
        # 兼容: 1. 函数调用 symbol(  2. JSX 标签 <symbol  3. 类型声明 : symbol  4. import 导入
        call_pattern = re.compile(rf'(?:\b{re.escape(symbol)}\s*\(|<\s*{re.escape(symbol)}\b|:\s*{re.escape(symbol)}\b|\bimport\s+.*?\{{\s*.*?\b{re.escape(symbol)}\b)')

        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".venv", "target", "bin", "__pycache__", ".idea", "dist", "build")]
            for f in files:
                if f.endswith((".py", ".java", ".go", ".ts", ".tsx", ".js", ".jsx", ".vue")):
                    f_path = os.path.join(root, f)
                    rel_p = os.path.relpath(f_path, self.workspace_root)
                    try:
                        with open(f_path, "r", encoding="utf-8", errors="ignore") as fp:
                            for idx, line in enumerate(fp, 1):
                                if call_pattern.search(line):
                                    callers.append(f"{rel_p}:{idx}")
                                    if len(callers) >= 20:
                                        return callers
                    except Exception:
                        pass
        return callers

    def _extract_symbols_from_file_lines(self, full_path: str, lines: List[int]) -> List[str]:
        """根据变动行号，提取对应的函数名、组件名、类名或类型名"""
        symbols = []
        line_set = set(lines)

        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content_lines = f.readlines()

            for idx, line in enumerate(content_lines, 1):
                if idx in line_set:
                    # 1. 匹配 TypeScript / React: export const Xxx: React.FC, function Xxx, const useXxx =
                    ts_comp_m = re.search(r'(?:export\s+)?(?:const|let|var|function)\s+([A-Za-z0-9_]+)\s*(?:[:=]|\()', line)
                    if ts_comp_m and ts_comp_m.group(1) not in ("if", "for", "while", "return", "switch"):
                        symbols.append(ts_comp_m.group(1))
                        continue

                    # 2. 匹配 TypeScript interface / type: export type Xxx = / interface Xxx {
                    ts_type_m = re.search(r'(?:export\s+)?(?:type|interface)\s+([A-Za-z0-9_]+)', line)
                    if ts_type_m:
                        symbols.append(ts_type_m.group(1))
                        continue

                    # 3. 匹配 Python: def xxx( / class Xxx:
                    py_m = re.search(r'(?:def|class)\s+([A-Za-z0-9_]+)', line)
                    if py_m:
                        symbols.append(py_m.group(1))
                        continue

                    # 4. 匹配 Java: public ... void xxx( / class Xxx
                    java_m = re.search(r'(?:public|protected|private|static|\s)+\s+(?:[\w<>\[\]]+)\s+([A-Za-z0-9_]+)\s*\(', line)
                    if java_m and java_m.group(1) not in ("if", "for", "while", "switch"):
                        symbols.append(java_m.group(1))
                        continue

                    # 5. 匹配 Go: func Xxx( / func (r *Repo) Xxx(
                    go_m = re.search(r'func\s+(?:\([^)]+\)\s*)?([A-Za-z0-9_]+)\s*\(', line)
                    if go_m:
                        symbols.append(go_m.group(1))
                        continue
        except Exception:
            pass

        # 若未精确定位到声明行，提取文件名主词作为粗粒度符号
        if not symbols:
            base = os.path.splitext(os.path.basename(full_path))[0]
            if base:
                symbols.append(base)

        return list(set(symbols))
