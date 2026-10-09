# -*- coding: utf-8 -*-
"""
验证 CodeRunner 与 DiffCoverageAnalyzer 增量覆盖率分析引擎
"""
import asyncio
import os
import sys
from pathlib import Path

# 将 aegis-runner 加入路径
runner_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(runner_root))

from src.runner.git_workspace import GitWorkspaceManager
from src.runner.coverage_analyzer import DiffCoverageAnalyzer, DiffCoverageReport
from src.runner.code_runner import CodeRunner, CodeTask


def test_git_diff_parsing():
    """测试统一 Diff 文本解析"""
    mgr = GitWorkspaceManager()
    sample_diff = """--- a/src/services/order_service.py
+++ b/src/services/order_service.py
@@ -10,0 +11,3 @@
+    def calculate_amount():
+        pay_amount = total - discount
+        return pay_amount
@@ -25,2 +28,1 @@
-    old_call()
+    new_call()
"""
    changed = mgr._parse_diff_output(sample_diff)
    print("Parsed Changed Lines:", changed)
    assert "src/services/order_service.py" in changed
    lines = changed["src/services/order_service.py"]
    assert 11 in lines and 12 in lines and 13 in lines
    assert 28 in lines
    print("✅ Git Diff 解析校验通过！")


def test_cobertura_diff_coverage():
    """测试 Cobertura XML 覆盖率与 Diff 交叉分析"""
    analyzer = DiffCoverageAnalyzer(default_threshold=80.0)

    # 模拟变更行：改动了 10, 11, 12, 13 行
    changed_lines = {
        "services/order.py": {10, 11, 12, 13}
    }

    # 模拟 Cobertura XML 内容：其中 10, 11, 12 被覆盖(hits=1)，13 未被覆盖(hits=0)
    cobertura_xml = """<?xml version="1.0" ?>
<coverage version="7.0">
  <packages>
    <package name="services">
      <classes>
        <class filename="services/order.py" name="order.py">
          <lines>
            <line number="10" hits="1"/>
            <line number="11" hits="2"/>
            <line number="12" hits="1"/>
            <line number="13" hits="0"/>
          </lines>
        </class>
      </classes>
    </package>
  </packages>
</coverage>"""

    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as f:
        f.write(cobertura_xml)
        tmp_cov_path = f.name

    try:
        report = analyzer.analyze(
            changed_lines=changed_lines,
            coverage_file_path=tmp_cov_path,
            workspace_dir="/tmp",
            threshold=70.0
        )
        print("Diff Coverage Report:", report.to_dict())
        assert report.total_changed_lines == 4
        assert report.covered_changed_lines == 3
        assert report.diff_coverage_percent == 75.0
        assert report.passed_threshold is True  # 75% >= 70%
        assert len(report.uncovered_lines) == 1
        assert report.uncovered_lines[0].line_number == 13
        print("✅ Cobertura 增量覆盖率计算与未覆盖代码检测 100% 通过！")
    finally:
        os.unlink(tmp_cov_path)


def test_go_coverage_out_analysis():
    """测试 Go coverage.out 格式解析与比对"""
    analyzer = DiffCoverageAnalyzer(default_threshold=80.0)

    changed_lines = {
        "auth/login.go": {15, 16, 20}
    }

    go_cov = """mode: set
github.com/test/auth/login.go:10.1,18.2 2 1
github.com/test/auth/login.go:19.1,25.2 3 0
"""
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".out", delete=False) as f:
        f.write(go_cov)
        tmp_cov_path = f.name

    try:
        report = analyzer.analyze(
            changed_lines=changed_lines,
            coverage_file_path=tmp_cov_path,
            workspace_dir="/tmp",
            threshold=60.0
        )
        # 行 15, 16 命中 (count=1), 行 20 未命中 (count=0)
        assert report.total_changed_lines == 3
        assert report.covered_changed_lines == 2
        assert round(report.diff_coverage_percent, 1) == 66.7
        assert len(report.uncovered_lines) == 1
        assert report.uncovered_lines[0].line_number == 20
        print("✅ Go 原生 coverage.out 增量比对 100% 通过！")
    finally:
        os.unlink(tmp_cov_path)


async def test_code_runner_execution():
    """测试 CodeRunner 驱动真实测试执行"""
    runner = CodeRunner()
    task = CodeTask(
        task_id="TASK-001",
        run_id="RUN-LOCAL-001",
        runner_type="go",
        work_dir=str(runner_root / "packages" / "aegis-sdk-go"),
        test_target="./...",
        coverage_enabled=True,
    )
    result = await runner.execute(task)
    print("CodeRunner Result Status:", result["status"])
    print("Execution Duration:", result["durationMs"], "ms")
    assert result["status"] == "PASSED"
    assert result["exitCode"] == 0
    assert "PASS" in result["stdout"]
    print("✅ CodeRunner 真实驱动 Go SDK 测试跑通！")


if __name__ == "__main__":
    test_git_diff_parsing()
    test_cobertura_diff_coverage()
    test_go_coverage_out_analysis()
    asyncio.run(test_code_runner_execution())
    print("\n🎉 Phase 2: Code Runner 与 Diff Coverage 引擎全部单元验证通过！")
