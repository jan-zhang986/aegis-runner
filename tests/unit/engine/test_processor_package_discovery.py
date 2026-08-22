# -*- coding: utf-8 -*-
"""
processor_package_discovery：行为测试（不依赖真实 processors 包）。
tests/conftest 已将 packages/engine 加入 path，此处仅追加 fixtures 根目录。
"""

from __future__ import annotations

import pathlib
import sys
from types import ModuleType

_ROOT = pathlib.Path(__file__).resolve().parents[3]
_FIXTURE_PKG_ROOT = _ROOT / "tests" / "fixtures"
if str(_FIXTURE_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_FIXTURE_PKG_ROOT))

from aegis_runner.engine.core.processor_discovery_paths import DEFAULT_PROCESSOR_DISCOVERY_PACKAGES
from aegis_runner.engine.core.processor_package_discovery import (
    for_each_direct_submodule,
    preload_processor_packages,
)


def test_for_each_direct_submodule_calls_visitor_for_importable_modules():
    seen: list[str] = []

    def visitor(module: ModuleType, module_name: str) -> None:
        seen.append(module_name)

    for_each_direct_submodule(
        "pd_fixture_pkg",
        visitor,
        log_tag="[test-pd]",
        module_import_error_level="debug",
    )
    assert "pd_fixture_pkg.mod_ok" in seen
    assert "pd_fixture_pkg.mod_bad" not in seen


def test_for_each_direct_submodule_missing_package_does_not_raise():
    def _noop(_module: ModuleType, _module_name: str) -> None:
        return None

    for_each_direct_submodule(
        "pd_fixture_pkg_nonexistent_xyz",
        _noop,
        log_tag="[test-pd]",
        module_import_error_level="warning",
    )


def test_preload_processor_packages_does_not_raise():
    preload_processor_packages(("pd_fixture_pkg",), log_tag="[test-pd]")


def test_default_discovery_packages_non_empty_and_stable_entries():
    names = set(DEFAULT_PROCESSOR_DISCOVERY_PACKAGES)
    assert "packages.engine.src.core.processors.base" in names
    assert "packages.engine.src.core.processors.job" in names
