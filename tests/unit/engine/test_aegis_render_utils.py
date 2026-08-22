# -*- coding: utf-8 -*-
"""engine: packages.engine.src.core.processors.render_utils"""

from src.engine.core.processors.render_utils import get_config_value, render_recursive


class _Ctx:
    def __init__(self, variables):
        self._variables = variables

    def get_variable(self, name):
        return self._variables.get(name)

    def render_string(self, s):
        return f"rendered:{s}"


def test_render_recursive_dollar_var():
    ctx = _Ctx({"port": 3306})
    assert render_recursive("$port", ctx) == 3306


def test_render_recursive_brace_var():
    ctx = _Ctx({"host": "db.local"})
    assert render_recursive("${host}", ctx) == "db.local"


def test_render_recursive_dict_nested():
    ctx = _Ctx({"a": 1})
    out = render_recursive({"x": "$a", "y": {"z": 2}}, ctx)
    assert out == {"x": 1, "y": {"z": 2}}


def test_get_config_value_dict_and_object():
    assert get_config_value({"k": 1}, "k", 0) == 1
    assert get_config_value({"k": 1}, "missing", 9) == 9

    class O:
        k = 3

    assert get_config_value(O(), "k", 0) == 3
