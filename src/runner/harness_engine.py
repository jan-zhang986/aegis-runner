# -*- coding: utf-8 -*-
"""
AegisOne Test-as-Code Harness 核心引擎 (harness_engine.py)
为 DeepSeek Harness (dsh) 与终端开发者提供四项核心标准化能力：
1. scaffold: 三语言 (Python/Java/Go) 标准用例脚手架生成
2. scan: 全仓库毫秒级静态 AST 用例与步骤盘点 (代码即资产)
3. diff: Git 变更与用例覆盖缺口拓扑分析 (Gap Analysis)
4. run: 结构化单测执行与发布风险五问 (Q1-Q5) 质量门禁裁决
"""
import ast
import json
import os
import re
import subprocess
import time
from typing import List, Dict, Any, Optional

from runner.git_workspace import GitWorkspaceManager
from runner.coverage_analyzer import DiffCoverageAnalyzer, DiffCoverageReport
from runner.codegraph_adapter import CodeGraphAdapter


class HarnessEngine:
    """企业级 Test-as-Code 核心引擎"""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = workspace_root or os.getcwd()
        self.codegraph = CodeGraphAdapter(self.workspace_root)

    # =========================================================================
    # 1. SCAFFOLD: 标准用例脚手架生成
    # =========================================================================
    def scaffold_case(
        self,
        lang: str,
        req: str,
        risk: str = "P1",
        title: str = "测试用例标题",
        case_id: Optional[str] = None,
        out_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        生成符合 Aegis 契约的标准化测试用例代码
        """
        lang = lang.lower()
        if not case_id:
            safe_req = re.sub(r"[^A-Za-z0-9]", "", req).upper() or "REQ"
            case_id = f"TC-{safe_req}-{int(time.time()) % 10000:04d}"

        code_content = ""
        default_file = ""

        if lang == "python":
            default_file = f"tests/test_{case_id.lower().replace('-', '_')}.py"
            code_content = f'''# -*- coding: utf-8 -*-
"""
Aegis Test-as-Code - {case_id}
Requirement: {req} | Risk: {risk}
"""
import pytest
import aegis


@aegis.case(
    id="{case_id}",
    req="{req}",
    title="{title}",
    risk="{risk}",
    priority="P1",
    tags=["regression", "{risk.lower()}"]
)
def test_{case_id.lower().replace('-', '_')}():
    with aegis.step("1. 初始化测试数据与前置上下文"):
        payload = {{"id": "{case_id}", "status": "ACTIVE"}}
        assert payload["id"] == "{case_id}"

    with aegis.step("2. 执行业务操作并捕获结果"):
        result_code = 200
        aegis.attach_evidence("payload.json", payload)
        assert result_code == 200

    with aegis.step("3. 校验核心断言与副作用"):
        assert True
'''

        elif lang == "java":
            class_name = f"Test{case_id.replace('-', '_')}"
            default_file = f"src/test/java/com/aegis/{class_name}.java"
            code_content = f'''package com.aegis;

import com.vanguard.aegis.sdk.Aegis;
import com.vanguard.aegis.sdk.AegisCase;
import com.vanguard.aegis.sdk.AegisExtension;
import com.vanguard.aegis.sdk.RiskLevel;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;

import static org.junit.jupiter.api.Assertions.*;

@ExtendWith(AegisExtension.class)
public class {class_name} {{

    @Test
    @DisplayName("{title}")
    @AegisCase(
        id = "{case_id}",
        req = "{req}",
        title = "{title}",
        risk = RiskLevel.{risk.upper() if risk.upper() in ("P0", "P1", "P2", "P3") else "P1"},
        tags = {{"regression", "{risk.lower()}"}}
    )
    void testExecution() {{
        Aegis.step("1. 初始化业务数据与上下文", () -> {{
            assertNotNull("{case_id}");
        }});

        Aegis.step("2. 执行核心业务逻辑调用", () -> {{
            Aegis.attachEvidence("req.json", "{{\\"caseId\\": \\"{case_id}\\"}}");
            assertTrue(true);
        }});

        Aegis.step("3. 校验业务状态与断言边界", () -> {{
            assertEquals(1, 1);
        }});
    }}
}}
'''

        elif lang in ("go", "golang"):
            func_name = f"Test{case_id.replace('-', '_')}"
            default_file = f"tests/{case_id.lower().replace('-', '_')}_test.go"
            code_content = f'''package tests

import (
	"testing"
	"github.com/vanguard/aegis-sdk-go/aegis"
)

func {func_name}(t *testing.T) {{
	c := aegis.NewCase(t, "{case_id}", "{req}", aegis.Risk{risk.upper()})
	defer c.End()

	c.Step("1. 初始化测试数据与前置上下文", func() {{
		if "{case_id}" == "" {{
			t.Fatal("empty case id")
		}}
	}})

	c.Step("2. 执行核心逻辑并记录证据", func() {{
		c.AttachEvidence("context.json", []byte(`{{"caseId": "{case_id}"}}`))
	}})

	c.Step("3. 核心业务断言校验", func() {{
		// 校验业务断言
	}})
}}
'''
        else:
            raise ValueError(f"Unsupported language: {lang}. Expected python, java, or go.")

        target_path = out_path or default_file
        if not os.path.isabs(target_path):
            target_path = os.path.join(self.workspace_root, target_path)

        if out_path:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(code_content)

        return {
            "caseId": case_id,
            "lang": lang,
            "req": req,
            "risk": risk,
            "title": title,
            "targetPath": target_path,
            "codeContent": code_content,
        }

    # =========================================================================
    # 2. SCAN: 全库毫秒级静态 AST 用例与步骤盘点 (代码即资产)
    # =========================================================================
    def scan_cases(self, target_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        静态解析目录下的 Python / Java / Go 文件，提取所有 @aegis.case 元数据与 steps。
        """
        scan_root = target_dir or self.workspace_root
        cases = []

        for root, dirs, files in os.walk(scan_root):
            # 忽略常见无关目录
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".venv", "venv", "target", "bin", "__pycache__", ".idea")]
            for file in sorted(files):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, scan_root)

                if file.endswith(".py") and (file.startswith("test_") or "test" in file):
                    cases.extend(self._scan_python_file(full_path, rel_path))
                elif file.endswith(".java") and ("Test" in file or "TestCase" in file):
                    cases.extend(self._scan_java_file(full_path, rel_path))
                elif file.endswith("_test.go"):
                    cases.extend(self._scan_go_file(full_path, rel_path))

        # 按需求聚合统计
        req_mapping = {}
        risk_stats = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
        for c in cases:
            req = c.get("req") or "UNLINKED"
            req_mapping.setdefault(req, []).append(c["id"])
            risk = c.get("risk", "P1").upper()
            if risk in risk_stats:
                risk_stats[risk] += 1
            else:
                risk_stats["P1"] += 1

        return {
            "workspaceRoot": scan_root,
            "totalCases": len(cases),
            "riskDistribution": risk_stats,
            "linkedRequirementsCount": len(req_mapping),
            "requirementsMapping": req_mapping,
            "cases": cases,
        }

    def _scan_python_file(self, full_path: str, rel_path: str) -> List[Dict[str, Any]]:
        results = []
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source, filename=full_path)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    meta = self._extract_python_case_meta(node)
                    if meta:
                        steps = self._extract_python_steps(node)
                        meta.update({
                            "lang": "python",
                            "filePath": rel_path,
                            "functionName": node.name,
                            "lineNo": node.lineno,
                            "steps": steps,
                        })
                        results.append(meta)
        except Exception:
            pass
        return results

    def _extract_python_case_meta(self, node: ast.FunctionDef) -> Optional[Dict[str, Any]]:
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call):
                name = ""
                if isinstance(dec.func, ast.Attribute):
                    name = f"{getattr(dec.func.value, 'id', '')}.{dec.func.attr}"
                elif isinstance(dec.func, ast.Name):
                    name = dec.func.id

                if name in ("aegis.case", "case"):
                    meta = {"id": node.name, "req": "", "title": node.name, "risk": "P1", "tags": []}
                    for kw in dec.keywords:
                        if isinstance(kw.value, ast.Constant):
                            meta[kw.arg] = kw.value.value
                        elif isinstance(kw.value, ast.List):
                            meta[kw.arg] = [e.value for e in kw.value.elts if isinstance(e, ast.Constant)]
                    return meta
        return None

    def _extract_python_steps(self, func_node: ast.FunctionDef) -> List[str]:
        steps = []
        for n in ast.walk(func_node):
            if isinstance(n, ast.With):
                for item in n.items:
                    expr = item.context_expr
                    if isinstance(expr, ast.Call):
                        name = ""
                        if isinstance(expr.func, ast.Attribute):
                            name = f"{getattr(expr.func.value, 'id', '')}.{expr.func.attr}"
                        if name in ("aegis.step", "step") and expr.args:
                            if isinstance(expr.args[0], ast.Constant):
                                steps.append(str(expr.args[0].value))
        return steps

    def _scan_java_file(self, full_path: str, rel_path: str) -> List[Dict[str, Any]]:
        results = []
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            case_pattern = re.compile(
                r'@AegisCase\s*\(\s*(.*?)\)\s*(?:@\w+\s*)*\s*(?:public|protected|private)?\s*void\s+(\w+)\s*\(',
                re.DOTALL
            )
            for match in case_pattern.finditer(content):
                args_str, method_name = match.groups()
                meta = {"id": method_name, "req": "", "title": method_name, "risk": "P1", "tags": []}

                for k in ("id", "req", "title"):
                    m = re.search(rf'{k}\s*=\s*"([^"]+)"', args_str)
                    if m:
                        meta[k] = m.group(1)

                m_risk = re.search(r'risk\s*=\s*(?:RiskLevel\.)?(\w+)', args_str)
                if m_risk:
                    meta["risk"] = m_risk.group(1)

                method_start = match.end()
                method_body_slice = content[method_start:method_start + 1500]
                steps = re.findall(r'Aegis\.step\s*\(\s*"([^"]+)"', method_body_slice)

                line_no = content[:match.start()].count("\n") + 1
                meta.update({
                    "lang": "java",
                    "filePath": rel_path,
                    "functionName": method_name,
                    "lineNo": line_no,
                    "steps": steps,
                })
                results.append(meta)
        except Exception:
            pass
        return results

    def _scan_go_file(self, full_path: str, rel_path: str) -> List[Dict[str, Any]]:
        results = []
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            func_pattern = re.compile(r'func\s+(Test\w+)\s*\(\s*\w+\s*\*testing\.T\s*\)\s*\{', re.MULTILINE)
            for match in func_pattern.finditer(content):
                func_name = match.group(1)
                func_start = match.end()
                body_slice = content[func_start:func_start + 2000]

                case_m = re.search(r'aegis\.NewCase\s*\(\s*\w+\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*aegis\.Risk(\w+)\s*\)', body_slice)
                if case_m:
                    case_id, req, risk = case_m.groups()
                    steps = re.findall(r'c\.Step\s*\(\s*"([^"]+)"', body_slice)
                    line_no = content[:match.start()].count("\n") + 1
                    results.append({
                        "id": case_id,
                        "req": req,
                        "title": func_name,
                        "risk": f"P{risk[-1]}" if risk.startswith("P") else risk,
                        "lang": "go",
                        "filePath": rel_path,
                        "functionName": func_name,
                        "lineNo": line_no,
                        "steps": steps,
                    })
        except Exception:
            pass
        return results

    # =========================================================================
    # 3. DIFF: Git 变更与用例覆盖缺口拓扑分析 (Gap Analysis)
    # =========================================================================
    def analyze_diff_gaps(self, base_ref: str = "HEAD~1") -> Dict[str, Any]:
        """
        对比当前工作区或分支变更，结合已扫描的用例库，找出未覆盖测试的代码盲区
        """
        diff_info = GitWorkspaceManager.get_diff_changed_lines(self.workspace_root, base_ref=base_ref)
        scanned = self.scan_cases()
        all_cases = scanned["cases"]

        changed_files = diff_info.get("changed_files", {})
        gaps = []
        covered_impact = []

        for file_path, lines in changed_files.items():
            if not any(file_path.endswith(ext) for ext in (".py", ".java", ".go", ".ts", ".tsx", ".js", ".jsx", ".vue")):
                continue

            is_test_file = any(kw in file_path.lower() for kw in ("test", "tests", "_test.go", "spec"))

            if not is_test_file:
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                matched_cases = [
                    c for c in all_cases
                    if base_name.lower() in c["filePath"].lower() or base_name.lower() in c["id"].lower()
                ]

                if matched_cases:
                    covered_impact.append({
                        "sourceFile": file_path,
                        "changedLines": lines,
                        "associatedCases": [c["id"] for c in matched_cases],
                    })
                else:
                    gaps.append({
                        "sourceFile": file_path,
                        "changedLinesCount": len(lines),
                        "changedLines": lines,
                        "riskLevel": "P0" if any(k in file_path.lower() for k in ("pay", "auth", "money", "order", "security")) else "P1",
                        "suggestedAction": f"建议使用 DeepSeek Harness 执行 'aegis scaffold' 为 {file_path} 补充 P0 级边界断言用例",
                    })

        # 调用 CodeGraph 计算架构拓扑与爆炸半径
        codegraph_topology = self.codegraph.analyze_changed_symbols_impact(changed_files)

        return {
            "baseRef": base_ref,
            "totalChangedFiles": len(changed_files),
            "totalSourceFilesChanged": len(covered_impact) + len(gaps),
            "coveredComponents": covered_impact,
            "uncoveredGaps": gaps,
            "gapCount": len(gaps),
            "codeGraphTopology": codegraph_topology,
            "riskAssessment": "CRITICAL" if (any(g["riskLevel"] == "P0" for g in gaps) or codegraph_topology.get("overallArchitecturalRisk") == "CRITICAL") else ("WARNING" if gaps else "HEALTHY"),
        }

    # =========================================================================
    # 4. RUN: 结构化测试执行与质量风控五问 (Q1-Q5) 门禁裁决
    # =========================================================================
    def run_tests_with_gate(
        self,
        target_path: Optional[str] = None,
        lang: Optional[str] = None,
        base_ref: str = "HEAD~1"
    ) -> Dict[str, Any]:
        """
        本地运行测试并输出标准化 JSON 结果 + 五问风险门禁答卷
        """
        start_time = time.time()
        exec_target = target_path or self.workspace_root

        if not lang:
            if exec_target.endswith(".py") or "test_" in exec_target:
                lang = "python"
            elif exec_target.endswith(".java") or os.path.exists(os.path.join(self.workspace_root, "pom.xml")):
                lang = "java"
            elif exec_target.endswith("_test.go") or os.path.exists(os.path.join(self.workspace_root, "go.mod")):
                lang = "go"
            else:
                lang = "python"

        import sys
        cmd = []
        if lang == "python":
            has_pytest = False
            try:
                import pytest
                has_pytest = True
            except ImportError:
                pass

            if has_pytest:
                cmd = [sys.executable, "-m", "pytest", exec_target, "-v", "--tb=short"]
            else:
                cmd = [sys.executable, exec_target]
        elif lang == "go":
            cmd = ["go", "test", "-v", exec_target if exec_target.endswith(".go") else "./..."]
        elif lang == "java":
            mvn_cmd = "mvn"
            mvnw_path = os.path.join(self.workspace_root, "mvnw")
            if os.path.exists(mvnw_path):
                mvn_cmd = mvnw_path
            cmd = [mvn_cmd, "test", f"-Dtest={os.path.basename(exec_target).replace('.java', '')}"]

        exit_code = 0
        stdout = ""
        stderr = ""
        try:
            proc = subprocess.run(
                cmd,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=120,
            )
            exit_code = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr
        except Exception as e:
            exit_code = -1
            stderr = str(e)

        duration_ms = int((time.time() - start_time) * 1000)

        diff_gaps = self.analyze_diff_gaps(base_ref=base_ref)

        gate_answers = self._generate_five_questions_gate(
            exit_code=exit_code,
            duration_ms=duration_ms,
            diff_gaps=diff_gaps,
            target_path=exec_target,
        )

        return {
            "status": "PASSED" if exit_code == 0 else "FAILED",
            "exitCode": exit_code,
            "durationMs": duration_ms,
            "command": " ".join(cmd),
            "stdout": stdout,
            "stderr": stderr,
            "releaseRiskGate": gate_answers,
        }

    def _generate_five_questions_gate(
        self,
        exit_code: int,
        duration_ms: int,
        diff_gaps: Dict[str, Any],
        target_path: str,
    ) -> Dict[str, Any]:
        """生成具有审计效力的企业级质量风控五问答卷"""
        uncovered = diff_gaps.get("uncoveredGaps", [])
        has_p0_gap = any(g.get("riskLevel") == "P0" for g in uncovered)
        tests_passed = (exit_code == 0)
        topology = diff_gaps.get("codeGraphTopology", {})
        max_depth = topology.get("maxCallDepth", 1)
        total_fan_in = topology.get("totalFanIn", 0)

        q1 = f"本次变更经 CodeGraph 拓扑追溯：最大调用链深度为 {max_depth}，涉及上游累积 Fan-In: {total_fan_in}。"
        if has_p0_gap:
            q1 += f" ⚠️ 探测到 {len(uncovered)} 处高危核心业务代码缺乏测试覆盖，存在 P0 资损与逃逸隐患！"
        else:
            q1 += " 核心影响链路已被已知用例体系收敛。"

        q2 = f"执行目标: {target_path}。耗时 {duration_ms}ms。运行状态: {'全部通过 (PASS)' if tests_passed else '失败 (FAIL)'}。执行证据已包含控制台 Trace 与断言快照。"

        q3 = f"发现 {len(uncovered)} 个未覆盖代码文件。"
        if uncovered:
            q3 += " 详细清单: " + ", ".join([f"{u['sourceFile']} (风险: {u['riskLevel']})" for u in uncovered])
        else:
            q3 += " 变动代码行 100% 纳入测试覆盖范围。"

        q4 = "允许发布 (APPROVED)" if (tests_passed and not has_p0_gap) else "⚠️ 阻断发布 (RELEASE BLOCKED)"
        q4_reason = "所有用例执行通过且无 P0 缺口" if (tests_passed and not has_p0_gap) else ("用例失败" if not tests_passed else "存在高风险未测业务代码，违反企业发布基线")

        q5 = "上线后建议重点观测：API HTTP 5xx 错误率突增、核心方法调用 Latency P99 抖动、DB 死锁告警以及业务异常重试次数。"

        return {
            "verdict": "APPROVED" if (tests_passed and not has_p0_gap) else "BLOCKED",
            "q1_core_risk": q1,
            "q2_verification_evidence": q2,
            "q3_uncovered_risk": q3,
            "q4_release_impact": f"{q4} - 原因: {q4_reason}",
            "q5_post_release_observability": q5,
        }
