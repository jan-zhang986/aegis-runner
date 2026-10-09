# -*- coding: utf-8 -*-
"""
Aegis 跨语言增量覆盖率 (Diff Coverage) 计算引擎
将测试覆盖率报告与 Git Diff 交叉比对，精确输出改动代码行的覆盖率与未触达代码清单。
"""
import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Set, Any, Optional
from dataclasses import dataclass, field


@dataclass
class UncoveredLine:
    file_path: str
    line_number: int
    code_content: Optional[str] = None
    risk_level: str = "MEDIUM"


@dataclass
class DiffCoverageReport:
    total_changed_lines: int = 0
    covered_changed_lines: int = 0
    diff_coverage_percent: float = 0.0
    passed_threshold: bool = True
    threshold: float = 80.0
    uncovered_lines: List[UncoveredLine] = field(default_factory=list)
    file_summary: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "totalChangedLines": self.total_changed_lines,
            "coveredChangedLines": self.covered_changed_lines,
            "diffCoveragePercent": round(self.diff_coverage_percent, 2),
            "passedThreshold": self.passed_threshold,
            "threshold": self.threshold,
            "uncoveredCount": len(self.uncovered_lines),
            "uncoveredLines": [
                {
                    "filePath": ul.file_path,
                    "lineNumber": ul.line_number,
                    "codeContent": ul.code_content,
                    "riskLevel": ul.risk_level,
                }
                for ul in self.uncovered_lines
            ],
            "fileSummary": self.file_summary,
        }


class DiffCoverageAnalyzer:
    """增量覆盖率交叉分析器"""

    def __init__(self, default_threshold: float = 80.0):
        self.default_threshold = default_threshold

    def analyze(
        self,
        changed_lines: Dict[str, Set[int]],
        coverage_file_path: str,
        workspace_dir: str,
        threshold: Optional[float] = None
    ) -> DiffCoverageReport:
        """
        核心交叉分析入口：
        :param changed_lines: Git Diff 得出的变更行集合
        :param coverage_file_path: Cobertura XML 或 Go coverage.out 路径
        :param workspace_dir: 源码根目录
        :param threshold: 门禁合格阈值百分比 (如 85.0)
        """
        th = threshold if threshold is not None else self.default_threshold
        report = DiffCoverageReport(threshold=th)

        if not changed_lines:
            # 本次 PR 无代码行改动
            report.diff_coverage_percent = 100.0
            report.passed_threshold = True
            return report

        # 解析覆盖率文件中每个文件的命中行信息
        covered_map = self._parse_coverage_file(coverage_file_path, workspace_dir)

        total_lines = 0
        covered_lines = 0

        for file_rel_path, lines in changed_lines.items():
            if not lines:
                continue

            # 标准化路径匹配
            matched_key = self._find_matching_file_key(file_rel_path, covered_map)
            file_hits = covered_map.get(matched_key, {})

            file_total = len(lines)
            file_covered = 0
            file_uncovered = []

            for line_no in sorted(lines):
                # hit_count > 0 代表被测试执行覆盖到
                hits = file_hits.get(line_no, 0)
                if hits > 0:
                    file_covered += 1
                else:
                    code_snippet = self._read_source_line(workspace_dir, file_rel_path, line_no)
                    risk_level = self._evaluate_line_risk(code_snippet)
                    uncovered_item = UncoveredLine(
                        file_path=file_rel_path,
                        line_number=line_no,
                        code_content=code_snippet,
                        risk_level=risk_level
                    )
                    file_uncovered.append(uncovered_item)
                    report.uncovered_lines.append(uncovered_item)

            total_lines += file_total
            covered_lines += file_covered

            file_percent = (file_covered / file_total * 100.0) if file_total > 0 else 100.0
            report.file_summary[file_rel_path] = {
                "total": file_total,
                "covered": file_covered,
                "percent": round(file_percent, 2),
                "uncoveredLines": [u.line_number for u in file_uncovered],
            }

        report.total_changed_lines = total_lines
        report.covered_changed_lines = covered_lines
        if total_lines > 0:
            report.diff_coverage_percent = (covered_lines / total_lines) * 100.0
        else:
            report.diff_coverage_percent = 100.0

        report.passed_threshold = report.diff_coverage_percent >= th
        return report

    def _parse_coverage_file(self, coverage_path: str, workspace_dir: str) -> Dict[str, Dict[int, int]]:
        """
        自动探测并解析不同语言的覆盖率格式：
        返回格式: { "file_path": { line_no: hit_count } }
        """
        if not os.path.isfile(coverage_path):
            return {}

        # 1. 尝试作为 Cobertura XML 解析 (Python / Java Jacoco / c8 / gocov-xml)
        try:
            tree = ET.parse(coverage_path)
            root = tree.getroot()
            if root.tag in ("coverage", "report"):
                return self._parse_cobertura_xml(root)
        except Exception:
            pass

        # 2. 尝试作为 Go coverage.out 解析
        try:
            return self._parse_go_coverage_out(coverage_path)
        except Exception:
            pass

        return {}

    def _parse_cobertura_xml(self, root: ET.Element) -> Dict[str, Dict[int, int]]:
        """解析标准 Cobertura XML"""
        file_map: Dict[str, Dict[int, int]] = {}

        for cls_elem in root.iter("class"):
            filename = cls_elem.get("filename", "")
            if not filename:
                continue

            if filename not in file_map:
                file_map[filename] = {}

            lines_elem = cls_elem.find("lines")
            if lines_elem is not None:
                for line in lines_elem.findall("line"):
                    try:
                        num = int(line.get("number", "0"))
                        hits = int(line.get("hits", "0"))
                        file_map[filename][num] = hits
                    except (ValueError, TypeError):
                        continue

        return file_map

    def _parse_go_coverage_out(self, file_path: str) -> Dict[str, Dict[int, int]]:
        """解析 Go 格式 coverage.out (如: mode: set\npkg/file.go:10.2,15.3 1 1)"""
        file_map: Dict[str, Dict[int, int]] = {}

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("mode:") or not line:
                    continue

                parts = line.split(":")
                if len(parts) != 2:
                    continue

                file_name = parts[0]
                rest = parts[1].split(" ")
                if len(rest) < 3:
                    continue

                range_part = rest[0]
                count = int(rest[2])

                # range_part: startLine.col,endLine.col
                if "," in range_part:
                    start_str, end_str = range_part.split(",")
                    start_line = int(start_str.split(".")[0])
                    end_line = int(end_str.split(".")[0])
                else:
                    start_line = int(range_part.split(".")[0])
                    end_line = start_line

                if file_name not in file_map:
                    file_map[file_name] = {}

                for l_no in range(start_line, end_line + 1):
                    file_map[file_name][l_no] = count

        return file_map

    def _find_matching_file_key(self, rel_path: str, covered_map: Dict[str, Any]) -> str:
        """支持相对路径与全路径后置匹配"""
        if rel_path in covered_map:
            return rel_path

        norm_rel = rel_path.replace("\\", "/")
        for k in covered_map.keys():
            norm_k = k.replace("\\", "/")
            if norm_k.endswith(norm_rel) or norm_rel.endswith(norm_k):
                return k
        return rel_path

    def _read_source_line(self, workspace_dir: str, rel_path: str, line_no: int) -> Optional[str]:
        full_path = os.path.join(workspace_dir, rel_path)
        if not os.path.isfile(full_path):
            return None
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                for idx, line in enumerate(f, 1):
                    if idx == line_no:
                        return line.strip()
        except Exception:
            return None
        return None

    def _evaluate_line_risk(self, code_snippet: Optional[str]) -> str:
        """轻量业务风险评分规则"""
        if not code_snippet:
            return "MEDIUM"
        
        low = code_snippet.lower()
        # 涉及金额、支付、库存、状态机变更、抛出异常等定义为高危
        if any(k in low for k in ("pay", "amount", "price", "stock", "refund", "balance", "money", "rollback", "raise", "throw")):
            return "HIGH"
        if any(k in low for k in ("if", "else", "switch", "case", "catch", "except", "retry")):
            return "MEDIUM"
        return "LOW"
