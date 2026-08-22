#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的日志系统 - 直接使用loguru，支持动态日志控制
"""

import os
import sys
from loguru import logger

# 移除默认处理器
logger.remove()

# 从环境变量获取日志级别配置
LOG_LEVEL = os.getenv("WORKFLOW_LOG_LEVEL", "INFO")  # 恢复INFO级别
ENABLE_CONSOLE_LOG = os.getenv("ENABLE_CONSOLE_LOG", "true").lower() == "true"  # 启用控制台日志
ENABLE_FILE_LOG = os.getenv("ENABLE_FILE_LOG", "false").lower() == "true"  # 禁用文件日志

# 日志处理器ID（用于后续动态控制）
_console_handler_id = None
_file_handler_id = None
_error_handler_id = None

# 控制台输出配置
if ENABLE_CONSOLE_LOG:
    _console_handler_id = logger.add(
        sys.stdout,
        level=LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> | <level>{message}</level>",
        colorize=True
    )

# 文件输出配置
if ENABLE_FILE_LOG:
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # 主日志文件
    _file_handler_id = logger.add(
        os.path.join(log_dir, "workflow_{time:YYYY-MM-DD}.log"),
        level=LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name} | {message}",
        rotation="1 day",
        retention="30 days",
        compression="zip"
    )
    
    # 错误日志文件
    _error_handler_id = logger.add(
        os.path.join(log_dir, "error_{time:YYYY-MM-DD}.log"),
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name} | {message}",
        rotation="1 day",
        retention="30 days",
        compression="zip"
    )


# ============================================================
# 日志控制函数
# ============================================================

def set_log_level(level: str):
    """
    动态设置日志级别
    
    Args:
        level: 日志级别（DEBUG/INFO/WARNING/ERROR）
    """
    global _console_handler_id, _file_handler_id
    
    # 移除旧的处理器
    if _console_handler_id is not None:
        logger.remove(_console_handler_id)
    if _file_handler_id is not None:
        logger.remove(_file_handler_id)
    
    # 重新添加处理器
    _console_handler_id = logger.add(
        sys.stdout,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> | <level>{message}</level>",
        colorize=True
    )
    
    if ENABLE_FILE_LOG:
        log_dir = "logs"
        _file_handler_id = logger.add(
            os.path.join(log_dir, "workflow_{time:YYYY-MM-DD}.log"),
            level=level,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name} | {message}",
            rotation="1 day",
            retention="30 days",
            compression="zip"
        )
    
    logger.info(f"[Logger] 日志级别已设置为: {level}")


def disable_console_log():
    """禁用控制台日志输出"""
    global _console_handler_id
    
    if _console_handler_id is not None:
        logger.remove(_console_handler_id)
        _console_handler_id = None
        print("✅ 控制台日志已禁用")


def enable_console_log(level: str = "INFO"):
    """启用控制台日志输出"""
    global _console_handler_id
    
    if _console_handler_id is not None:
        logger.remove(_console_handler_id)
    
    _console_handler_id = logger.add(
        sys.stdout,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> | <level>{message}</level>",
        colorize=True
    )
    
    logger.info(f"[Logger] 控制台日志已启用，级别: {level}")


def disable_file_log():
    """禁用文件日志输出"""
    global _file_handler_id, _error_handler_id
    
    if _file_handler_id is not None:
        logger.remove(_file_handler_id)
        _file_handler_id = None
    
    if _error_handler_id is not None:
        logger.remove(_error_handler_id)
        _error_handler_id = None
    
    print("✅ 文件日志已禁用")


def disable_all_logs():
    """禁用所有日志输出"""
    logger.remove()
    print("✅ 所有日志已禁用")


def get_log_config():
    """获取当前日志配置"""
    return {
        "level": LOG_LEVEL,
        "console_enabled": _console_handler_id is not None,
        "file_enabled": _file_handler_id is not None,
        "error_file_enabled": _error_handler_id is not None
    }


# 导出logger和控制函数
__all__ = [
    'logger',
    'set_log_level',
    'disable_console_log',
    'enable_console_log',
    'disable_file_log',
    'disable_all_logs',
    'get_log_config'
]
