# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-10-07
@packageName src.modules.ui
@className UI Module
@describe UI功能模块
"""

__version__ = "1.0.0"
__author__ = "Jan"
__description__ = "UI功能模块，提供UI自动化相关的功能实现"

from .playwright.ui_playwright_manager import ui_playwright_manager
from .config.ui_context_adapter import UIContextAdapter

__all__ = [
    'ui_playwright_manager',
    'UIContextAdapter',
]
