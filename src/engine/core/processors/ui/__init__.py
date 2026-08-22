# -*- coding: utf-8 -*-
"""
UI处理器包
"""

# 注意：为了避免循环导入，这里不直接导入处理器类
# 处理器类会在需要时动态导入

__all__ = [
    # 基础处理器
    'ElementProcessor',
    'NavigationProcessor',
    'ScreenshotProcessor',
    'WaitProcessor',
    'BrowserProcessor',
    'ValidationProcessor',
    'ActionProcessor',
    'RecordingProcessor',
    'AdvancedUIProcessor',
    
    # 增强处理器（2025-01-30新增）
    'SmartWaitProcessor',           # 智能等待处理器
    'UIObservabilityProcessor',     # 可观测性处理器
    'AIAssistedUIProcessor',        # AI辅助处理器
    'VisualRegressionProcessor',    # 视觉回归测试处理器
    'UIPerformanceProcessor',       # 性能监控处理器
    'ResponsiveUIProcessor',        # 响应式测试处理器
]