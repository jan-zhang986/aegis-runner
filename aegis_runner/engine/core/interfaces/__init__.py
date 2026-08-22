# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName src.core.interfaces
@className Interfaces Package
@describe 核心接口定义包
"""

from .processor_interface import ProcessorInterface
from .context_interface import ContextInterface

__all__ = [
    'ProcessorInterface',
    'ContextInterface'
]
