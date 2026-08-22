# -*- coding: utf-8 -*-
import sys
from pathlib import Path

from src.engine.workflow_engine import WorkflowExecutor


def test_hook_loading_restores_sys_path_and_registers_functions(tmp_path):
    helper_file = tmp_path / "helper_module.py"
    helper_file.write_text(
        "def helper_value():\n"
        "    return 42\n",
        encoding="utf-8",
    )

    hook_file = tmp_path / "custom_hooks.py"
    hook_file.write_text(
        "from helper_module import helper_value\n\n"
        "def exposed_hook():\n"
        "    return helper_value()\n",
        encoding="utf-8",
    )

    workflow = {"nodes": [], "edges": [], "work_id": "hook-test"}
    original_sys_path = list(sys.path)

    executor = WorkflowExecutor(workflow, hook_file=str(hook_file))

    assert list(sys.path) == original_sys_path
    assert executor.context.has_function("exposed_hook")
    assert executor.context.get_function("exposed_hook")() == 42
