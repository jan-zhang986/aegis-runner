# -*- coding: utf-8 -*-
"""
Aegis Git Workspace Manager
负责测试工程代码仓的克隆、拉取、分支切换以及变更行 Diff 计算。
"""
import asyncio
import os
import shutil
from typing import Dict, List, Set, Optional, Tuple, Any


class GitWorkspaceManager:
    """Git 测试工作区管理器"""

    def __init__(self, base_workspace_dir: str = "/tmp/aegis-workspaces"):
        self.base_workspace_dir = base_workspace_dir
        os.makedirs(self.base_workspace_dir, exist_ok=True)

    def get_repo_dir(self, repo_url: str, branch: str = "main") -> str:
        """根据仓库地址与分支计算本地工作区目录"""
        safe_repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        safe_branch = branch.replace("/", "_")
        return os.path.join(self.base_workspace_dir, f"{safe_repo_name}_{safe_branch}")

    async def prepare_workspace(
        self,
        repo_url: Optional[str] = None,
        branch: str = "main",
        local_dir: Optional[str] = None
    ) -> str:
        """
        准备执行目录：若指定 local_dir 则直接使用本地工程；
        若指定 remote repo_url 则执行 git clone / pull。
        """
        if local_dir and os.path.isdir(local_dir):
            return local_dir

        if not repo_url:
            # 默认使用当前工作区目录
            return os.getcwd()

        target_dir = self.get_repo_dir(repo_url, branch)

        if os.path.exists(os.path.join(target_dir, ".git")):
            # 仓库已存在，执行 git fetch & checkout & pull
            await self._run_git(["checkout", branch], cwd=target_dir)
            await self._run_git(["pull", "origin", branch], cwd=target_dir)
        else:
            # 首次执行 clone
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
            await self._run_git(
                ["clone", "--depth", "50", "--branch", branch, repo_url, target_dir],
                cwd=self.base_workspace_dir
            )

        return target_dir

    async def get_changed_lines(
        self,
        cwd: str,
        base_branch: str = "origin/main"
    ) -> Dict[str, Set[int]]:
        """
        基于 git diff 计算相对于 base_branch 的变更文件及行号列表。
        返回值: { "relative/path/to/file.py": {12, 13, 14, 25} }
        """
        cmd = ["diff", "-U0", base_branch, "HEAD"]
        code, stdout, _ = await self._run_git(cmd, cwd=cwd)
        if code != 0:
            # 回退尝试直接对比 main
            code, stdout, _ = await self._run_git(["diff", "-U0", "main", "HEAD"], cwd=cwd)
            if code != 0:
                return {}

        return self._parse_diff_output(stdout)

    def _parse_diff_output(self, diff_text: str) -> Dict[str, Set[int]]:
        """解析 unified diff 文本提取变更行号"""
        changed_files: Dict[str, Set[int]] = {}
        current_file = None

        for line in diff_text.splitlines():
            if line.startswith("+++ b/"):
                current_file = line[6:].strip()
                if current_file not in changed_files:
                    changed_files[current_file] = set()
            elif line.startswith("@@ ") and current_file:
                # 形如: @@ -10,0 +15,3 @@ 或 @@ -5 +6 @@
                parts = line.split(" ")
                for p in parts:
                    if p.startswith("+"):
                        range_str = p[1:]
                        if "," in range_str:
                            start, count = map(int, range_str.split(","))
                        else:
                            start, count = int(range_str), 1
                        for line_num in range(start, start + count):
                            changed_files[current_file].add(line_num)

        return changed_files

    async def _run_git(self, args: List[str], cwd: str) -> Tuple[int, str, str]:
        cmd = ["git"] + args
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="ignore"),
            stderr.decode("utf-8", errors="ignore")
        )

    @classmethod
    def get_diff_changed_lines(cls, cwd: str, base_ref: str = "HEAD~1") -> Dict[str, Any]:
        """
        同步获取 Git Diff 变更行，供 CLI 与 HarnessEngine 直接调用。
        返回: {"changed_files": {"file.py": [1, 2, 3]}}
        """
        import subprocess
        mgr = cls()
        changed_files: Dict[str, List[int]] = {}

        # 尝试几种常见 diff 目标：指定的 base_ref、HEAD~1、HEAD、origin/main、main
        candidates = [
            ["diff", "-U0", base_ref, "HEAD"],
            ["diff", "-U0", "HEAD~1", "HEAD"],
            ["diff", "-U0", "HEAD"],
            ["diff", "-U0", "origin/main", "HEAD"],
            ["diff", "-U0", "main", "HEAD"],
        ]
        if base_ref:
            candidates.insert(0, ["diff", "-U0", base_ref])

        diff_output = ""
        for args in candidates:
            try:
                proc = subprocess.run(
                    ["git"] + args,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    diff_output = proc.stdout
                    break
            except Exception:
                continue

        parsed = mgr._parse_diff_output(diff_output) if diff_output else {}
        for f, lines in parsed.items():
            changed_files[f] = sorted(list(lines))

        return {"changed_files": changed_files}
