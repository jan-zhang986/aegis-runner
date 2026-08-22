# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-10-30
@packageName src.core
@className SafeEval
@describe 安全的表达式求值器，替代 eval
"""

import re
import operator
from typing import Any, Dict


class SafeEval:
    """安全的表达式求值器
    
    支持的操作：
    - 比较运算: ==, !=, <, <=, >, >=
    - 逻辑运算: and, or, not
    - 算术运算: +, -, *, /, %
    - 成员运算: in, not in
    - 字符串操作: len(), str(), int(), float()
    - 布尔值: True, False
    """
    
    # 支持的操作符映射
    OPERATORS = {
        # 比较运算
        '==': operator.eq,
        '!=': operator.ne,
        '<': operator.lt,
        '<=': operator.le,
        '>': operator.gt,
        '>=': operator.ge,
        # 算术运算
        '+': operator.add,
        '-': operator.sub,
        '*': operator.mul,
        '/': operator.truediv,
        '%': operator.mod,
        # 成员运算
        'in': lambda x, y: x in y,
        'not in': lambda x, y: x not in y,
    }
    
    # 支持的安全函数
    SAFE_FUNCTIONS = {
        'len': len,
        'str': str,
        'int': int,
        'float': float,
        'bool': bool,
        'abs': abs,
        'min': min,
        'max': max,
        'sum': sum,
        'round': round,
    }
    
    def __init__(self, names: Dict[str, Any] = None):
        """初始化求值器
        
        Args:
            names: 允许访问的变量字典
        """
        self.names = names or {}
    
    def eval(self, expression: str) -> Any:
        """安全地求值表达式
        
        Args:
            expression: 要求值的表达式字符串
            
        Returns:
            表达式的结果
            
        Raises:
            ValueError: 不安全的表达式
        """
        if not expression or not isinstance(expression, str):
            return None
        
        expression = expression.strip()
        
        # 检查是否包含危险的关键字
        dangerous_keywords = [
            '__', 'import', 'exec', 'eval', 'compile', 'open', 'file',
            'input', 'raw_input', 'reload', '__import__', 'globals', 'locals',
            'vars', 'dir', 'getattr', 'setattr', 'delattr', 'hasattr'
        ]
        
        for keyword in dangerous_keywords:
            if keyword in expression:
                raise ValueError(f"不安全的表达式，包含禁止的关键字: {keyword}")
        
        # 简单的表达式求值
        try:
            # 处理布尔字面量
            if expression == 'True':
                return True
            if expression == 'False':
                return False
            if expression == 'None':
                return None
            
            # 处理数字字面量
            if re.match(r'^-?\d+$', expression):
                return int(expression)
            if re.match(r'^-?\d+\.\d+$', expression):
                return float(expression)
            
            # 处理字符串字面量
            if (expression.startswith("'") and expression.endswith("'")) or \
               (expression.startswith('"') and expression.endswith('"')):
                return expression[1:-1]
            
            # 处理简单的比较表达式
            for op_str, op_func in self.OPERATORS.items():
                if op_str in expression:
                    parts = expression.split(op_str, 1)
                    if len(parts) == 2:
                        left = self._eval_operand(parts[0].strip())
                        right = self._eval_operand(parts[1].strip())
                        return op_func(left, right)
            
            # 处理逻辑运算 and/or
            if ' and ' in expression:
                parts = expression.split(' and ')
                return all(self.eval(p.strip()) for p in parts)
            
            if ' or ' in expression:
                parts = expression.split(' or ')
                return any(self.eval(p.strip()) for p in parts)
            
            if expression.startswith('not '):
                return not self.eval(expression[4:].strip())
            
            # 处理函数调用
            func_match = re.match(r'(\w+)\((.*)\)$', expression)
            if func_match:
                func_name = func_match.group(1)
                args_str = func_match.group(2)
                
                if func_name in self.SAFE_FUNCTIONS:
                    if args_str:
                        args = [self._eval_operand(arg.strip()) for arg in args_str.split(',')]
                        return self.SAFE_FUNCTIONS[func_name](*args)
                    else:
                        return self.SAFE_FUNCTIONS[func_name]()
                else:
                    raise ValueError(f"不支持的函数: {func_name}")
            
            # 最后尝试作为变量名
            if expression in self.names:
                return self.names[expression]
            
            # 无法解析的表达式
            raise ValueError(f"无法解析的表达式: {expression}")
            
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"表达式求值失败: {str(e)}")
    
    def _eval_operand(self, operand: str) -> Any:
        """求值单个操作数
        
        Args:
            operand: 操作数字符串
            
        Returns:
            操作数的值
        """
        operand = operand.strip()
        
        # 布尔值
        if operand == 'True':
            return True
        if operand == 'False':
            return False
        if operand == 'None':
            return None
        
        # 数字
        if re.match(r'^-?\d+$', operand):
            return int(operand)
        if re.match(r'^-?\d+\.\d+$', operand):
            return float(operand)
        
        # 字符串字面量
        if (operand.startswith("'") and operand.endswith("'")) or \
           (operand.startswith('"') and operand.endswith('"')):
            return operand[1:-1]
        
        # 函数调用
        func_match = re.match(r'(\w+)\((.*)\)$', operand)
        if func_match:
            return self.eval(operand)
        
        # 变量名
        if operand in self.names:
            return self.names[operand]
        
        # 默认作为字符串处理
        return operand


def safe_eval(expression: str, names: Dict[str, Any] = None) -> Any:
    """安全地求值表达式的便捷函数
    
    Args:
        expression: 要求值的表达式字符串
        names: 允许访问的变量字典
        
    Returns:
        表达式的结果
    """
    evaluator = SafeEval(names)
    return evaluator.eval(expression)

