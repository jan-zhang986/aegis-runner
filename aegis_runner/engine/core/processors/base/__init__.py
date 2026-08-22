# -*- coding: utf-8 -*-
"""
基础处理器包
"""

# 注意：为了避免循环导入，这里不直接导入处理器类
# 处理器类会在需要时动态导入

__all__ = [
    'ScriptProcessor',
    'ConditionProcessor',
    'LogMessageProcessor',
    'VariableExtractorProcessor',
    'AssertionProcessor',
]