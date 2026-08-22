# -*- coding: utf-8 -*-
"""
Aegis Runner Core Exceptions
"""

class AegisRunnerException(Exception):
    """Aegis Runner 基础异常类"""
    pass

class ConfigError(AegisRunnerException):
    """配置加载异常"""
    pass

class TaskExecutionError(AegisRunnerException):
    """任务执行异常"""
    pass

class EngineError(AegisRunnerException):
    """工作流引擎处理异常"""
    pass
