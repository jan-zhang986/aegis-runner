# -*- coding: utf-8 -*-
"""
Aegis Cloud Code Runner
云端代码测试调度器：负责在容器/Worker 节点克隆代码、驱动测试框架执行并调用覆盖率分析引擎。
"""
import asyncio
import os
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from src.runner.git_workspace import GitWorkspaceManager
from src.runner.coverage_analyzer import DiffCoverageAnalyzer, DiffCoverageReport


@dataclass
class CodeTask:
    task_id: str
    run_id: str
    runner_type: str = "pytest"  # "pytest" | "maven" | "go" | "playwright" | "shell"
    git_repo: Optional[str] = None
    git_branch: str = "main"
    test_target: str = ""        # 如: "tests/api/auth/test_sms.py"
    work_dir: Optional[str] = None
    base_branch: str = "origin/main"
    coverage_enabled: bool = True
    coverage_threshold: float = 80.0
    env: Dict[str, str] = field(default_factory=dict)
    command_override: Optional[str] = None


class CodeRunner:
    """原生测试代码执行引擎"""

    def __init__(self, workspace_manager: Optional[GitWorkspaceManager] = None):
        self.workspace_mgr = workspace_manager or GitWorkspaceManager()
        self.coverage_analyzer = DiffCoverageAnalyzer()

    async def execute(self, task: CodeTask) -> Dict[str, Any]:
        start_time = time.time()
        result = {
            "taskId": task.task_id,
            "runId": task.run_id,
            "runnerType": task.runner_type,
            "status": "RUNNING",
            "exitCode": -1,
            "durationMs": 0,
            "stdout": "",
            "stderr": "",
            "diffCoverage": None,
            "error": None,
        }

        try:
            # 1. 准备代码工作区
            cwd = await self.workspace_mgr.prepare_workspace(
                repo_url=task.git_repo,
                branch=task.git_branch,
                local_dir=task.work_dir
            )

            # 2. 计算 Git Diff 变更行 (在执行测试前预先分析出改动的代码行)
            changed_lines = {}
            if task.coverage_enabled:
                try:
                    changed_lines = await self.workspace_mgr.get_changed_lines(cwd, task.base_branch)
                except Exception:
                    pass

            # 3. 构造各测试语言的原生 CLI 命令与覆盖率产物路径
            cmd_args, cov_file = self._build_command(task, cwd)

            # 4. 执行测试子进程并捕获输出
            exec_env = os.environ.copy()
            exec_env["AEGIS_RUN_ID"] = task.run_id
            exec_env.update(task.env)

            proc = await asyncio.create_subprocess_exec(
                *cmd_args,
                cwd=cwd,
                env=exec_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout_bytes, stderr_bytes = await proc.communicate()
            exit_code = proc.returncode or 0

            result["exitCode"] = exit_code
            result["status"] = "PASSED" if exit_code == 0 else "FAILED"
            result["stdout"] = stdout_bytes.decode("utf-8", errors="ignore")
            result["stderr"] = stderr_bytes.decode("utf-8", errors="ignore")

            # 5. 分析增量覆盖率
            if task.coverage_enabled and cov_file:
                cov_full_path = os.path.join(cwd, cov_file)
                diff_report: DiffCoverageReport = self.coverage_analyzer.analyze(
                    changed_lines=changed_lines,
                    coverage_file_path=cov_full_path,
                    workspace_dir=cwd,
                    threshold=task.coverage_threshold
                )
                result["diffCoverage"] = diff_report.to_dict()

        except Exception as e:
            result["status"] = "ERROR"
            result["error"] = str(e)
        finally:
            result["durationMs"] = int((time.time() - start_time) * 1000)

        return result

    def _build_command(self, task: CodeTask, cwd: str) -> (List[str], Optional[str]):
        """根据 runner_type 构建支持覆盖率探针的命令"""
        if task.command_override:
            return task.command_override.split(), None

        rt = task.runner_type.lower()
        if rt == "pytest":
            cov_file = "coverage.xml"
            # 开启 pytest-cov 输出标准 Cobertura XML
            cmd = ["python3", "-m", "pytest"]
            if task.test_target:
                cmd.append(task.test_target)
            if task.coverage_enabled:
                cmd.extend(["--cov=.", f"--cov-report=xml:{cov_file}"])
            cmd.extend(["-v", "--tb=short"])
            return cmd, cov_file

        elif rt == "go":
            cov_file = "coverage.out"
            cmd = ["go", "test"]
            if task.coverage_enabled:
                cmd.append(f"-coverprofile={cov_file}")
            cmd.append("-v")
            cmd.append(task.test_target if task.test_target else "./...")
            return cmd, cov_file

        elif rt == "maven" or rt == "java":
            cov_file = "target/site/jacoco/jacoco.xml"
            cmd = ["mvn", "test"]
            if task.test_target:
                cmd.append(f"-Dtest={task.test_target}")
            if task.coverage_enabled:
                cmd.append("jacoco:report")
            return cmd, cov_file

        elif rt == "playwright":
            cmd = ["npx", "playwright", "test"]
            if task.test_target:
                cmd.append(task.test_target)
            cmd.append("--reporter=json")
            return cmd, None

        else:
            # 默认 shell 回退
            cmd = task.test_target.split() if task.test_target else ["echo", "No command specified"]
            return cmd, None
