# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName src.core
@className ErrorManager
@describe 统一的异常管理器
"""

import time
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import threading
from collections import defaultdict, deque

from src.engine.core.exceptions import (
    WorkflowError, ErrorCategory, ErrorSeverity, ErrorContext,
    ValidationError, ExecutionError, ConnectionError, TimeoutError,
    SecurityError, DataError, SystemError, NetworkError, DatabaseError
)
from src.engine.core.simple_logger import logger


class RetryStrategy(Enum):
    """重试策略"""
    NONE = "none"                    # 不重试
    IMMEDIATE = "immediate"          # 立即重试
    LINEAR_BACKOFF = "linear_backoff" # 线性退避
    EXPONENTIAL_BACKOFF = "exponential_backoff" # 指数退避
    FIXED_DELAY = "fixed_delay"      # 固定延迟


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True


@dataclass
class ErrorPolicy:
    """错误处理策略"""
    retry_config: RetryConfig = field(default_factory=RetryConfig)
    continue_on_error: bool = False
    fallback_action: Optional[str] = None
    notify_on_error: bool = True
    log_error: bool = True


@dataclass
class ErrorMetrics:
    """错误指标"""
    total_errors: int = 0
    errors_by_category: Dict[str, int] = field(default_factory=dict)
    errors_by_severity: Dict[str, int] = field(default_factory=dict)
    retry_success_count: int = 0
    retry_failure_count: int = 0
    last_error_time: Optional[float] = None
    error_rate: float = 0.0


class ErrorManager:
    """统一的异常管理器"""
    
    def __init__(self):
        self._error_policies: Dict[str, ErrorPolicy] = {}
        self._error_metrics = ErrorMetrics()
        self._error_history: deque = deque(maxlen=1000)  # 保留最近1000个错误
        self._retry_cache: Dict[str, List[float]] = {}  # 重试时间缓存
        self._lock = threading.Lock()
        self._error_handlers: Dict[ErrorCategory, List[Callable]] = defaultdict(list)
        
        # 初始化默认错误策略
        self._initialize_default_policies()
    
    def _initialize_default_policies(self):
        """初始化默认错误策略"""
        # 验证错误策略
        self._error_policies[ErrorCategory.VALIDATION.value] = ErrorPolicy(
            retry_config=RetryConfig(max_attempts=0),  # 不重试
            continue_on_error=False,
            notify_on_error=True
        )
        
        # 执行错误策略
        self._error_policies[ErrorCategory.EXECUTION.value] = ErrorPolicy(
            retry_config=RetryConfig(max_attempts=3, strategy=RetryStrategy.EXPONENTIAL_BACKOFF),
            continue_on_error=False,
            notify_on_error=True
        )
        
        # 连接错误策略
        self._error_policies[ErrorCategory.CONNECTION.value] = ErrorPolicy(
            retry_config=RetryConfig(max_attempts=5, strategy=RetryStrategy.EXPONENTIAL_BACKOFF),
            continue_on_error=False,
            notify_on_error=True
        )
        
        # 超时错误策略
        self._error_policies[ErrorCategory.TIMEOUT.value] = ErrorPolicy(
            retry_config=RetryConfig(max_attempts=3, strategy=RetryStrategy.LINEAR_BACKOFF),
            continue_on_error=False,
            notify_on_error=True
        )
        
        # 安全错误策略
        self._error_policies[ErrorCategory.SECURITY.value] = ErrorPolicy(
            retry_config=RetryConfig(max_attempts=0),  # 不重试
            continue_on_error=False,
            notify_on_error=True
        )
        
        # 数据错误策略
        self._error_policies[ErrorCategory.DATA.value] = ErrorPolicy(
            retry_config=RetryConfig(max_attempts=0),  # 不重试
            continue_on_error=True,
            notify_on_error=True
        )
        
        # 系统错误策略
        self._error_policies[ErrorCategory.SYSTEM.value] = ErrorPolicy(
            retry_config=RetryConfig(max_attempts=0),  # 不重试
            continue_on_error=False,
            notify_on_error=True
        )
        
        # 网络错误策略
        self._error_policies[ErrorCategory.NETWORK.value] = ErrorPolicy(
            retry_config=RetryConfig(max_attempts=5, strategy=RetryStrategy.EXPONENTIAL_BACKOFF),
            continue_on_error=False,
            notify_on_error=True
        )
        
        # 数据库错误策略
        self._error_policies[ErrorCategory.DATABASE.value] = ErrorPolicy(
            retry_config=RetryConfig(max_attempts=3, strategy=RetryStrategy.EXPONENTIAL_BACKOFF),
            continue_on_error=False,
            notify_on_error=True
        )
    
    def set_error_policy(self, category: ErrorCategory, policy: ErrorPolicy):
        """设置错误处理策略"""
        self._error_policies[category.value] = policy
        logger.info(f"[ErrorManager] 设置错误策略: {category.value}")
    
    def get_error_policy(self, category: ErrorCategory) -> ErrorPolicy:
        """获取错误处理策略"""
        return self._error_policies.get(category.value, ErrorPolicy())
    
    def register_error_handler(self, category: ErrorCategory, handler: Callable):
        """注册错误处理器"""
        self._error_handlers[category].append(handler)
        logger.debug(f"[ErrorManager] 注册错误处理器: {category.value}")
    
    def handle_error(self, error: WorkflowError, context: Optional[ErrorContext] = None) -> Dict[str, Any]:
        """处理错误"""
        with self._lock:
            # 更新错误指标
            self._update_error_metrics(error)
            
            # 添加到错误历史
            self._error_history.append(error.to_dict())
            
            # 获取错误策略
            policy = self.get_error_policy(error.category)
            
            # 调用错误处理器
            self._call_error_handlers(error)
            
            # 决定是否需要重试
            if error.retryable and policy.retry_config.max_attempts > 0:
                return self._handle_retry(error, policy.retry_config, context)
            
            # 返回错误处理结果
            return {
                "handled": True,
                "retry": False,
                "continue": policy.continue_on_error,
                "error": error.to_dict(),
                "policy": {
                    "continue_on_error": policy.continue_on_error,
                    "fallback_action": policy.fallback_action
                }
            }
    
    def _update_error_metrics(self, error: WorkflowError):
        """更新错误指标"""
        self._error_metrics.total_errors += 1
        self._error_metrics.last_error_time = time.time()
        
        # 按类别统计
        category = error.category.value
        self._error_metrics.errors_by_category[category] = \
            self._error_metrics.errors_by_category.get(category, 0) + 1
        
        # 按严重程度统计
        severity = error.severity.value
        self._error_metrics.errors_by_severity[severity] = \
            self._error_metrics.errors_by_severity.get(severity, 0) + 1
    
    def _call_error_handlers(self, error: WorkflowError):
        """调用错误处理器"""
        handlers = self._error_handlers.get(error.category, [])
        for handler in handlers:
            try:
                handler(error)
            except Exception as e:
                logger.error(f"[ErrorManager] 错误处理器执行失败: {str(e)}")
    
    def _handle_retry(self, error: WorkflowError, retry_config: RetryConfig, context: Optional[ErrorContext]) -> Dict[str, Any]:
        """处理重试逻辑"""
        if not context:
            context = ErrorContext()
        
        # 检查重试次数
        if context.retry_count >= retry_config.max_attempts:
            self._error_metrics.retry_failure_count += 1
            logger.warning(f"[ErrorManager] 达到最大重试次数: {retry_config.max_attempts}")
            return {
                "handled": True,
                "retry": False,
                "continue": False,
                "error": error.to_dict(),
                "retry_exhausted": True
            }
        
        # 计算重试延迟
        delay = self._calculate_retry_delay(error, retry_config, context)
        
        # 更新重试计数
        context.retry_count += 1
        
        logger.info(f"[ErrorManager] 将在 {delay:.2f}s 后重试 (第 {context.retry_count} 次)")
        
        return {
            "handled": True,
            "retry": True,
            "retry_delay": delay,
            "retry_count": context.retry_count,
            "max_attempts": retry_config.max_attempts,
            "error": error.to_dict()
        }
    
    def _calculate_retry_delay(self, error: WorkflowError, retry_config: RetryConfig, context: ErrorContext) -> float:
        """计算重试延迟"""
        base_delay = retry_config.base_delay
        retry_count = context.retry_count
        
        if retry_config.strategy == RetryStrategy.NONE:
            return 0.0
        elif retry_config.strategy == RetryStrategy.IMMEDIATE:
            return 0.0
        elif retry_config.strategy == RetryStrategy.FIXED_DELAY:
            delay = base_delay
        elif retry_config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = base_delay * retry_count
        elif retry_config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = base_delay * (retry_config.backoff_multiplier ** retry_count)
        else:
            delay = base_delay
        
        # 添加抖动
        if retry_config.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)  # 50%-100% 的随机抖动
        
        # 限制最大延迟
        delay = min(delay, retry_config.max_delay)
        
        return delay
    
    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """执行函数并自动重试"""
        max_attempts = 3
        retry_config = RetryConfig(max_attempts=max_attempts)
        
        last_error = None
        
        for attempt in range(max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except WorkflowError as e:
                last_error = e
                if not e.retryable or attempt >= max_attempts:
                    break
                
                # 计算延迟
                context = ErrorContext(retry_count=attempt)
                delay = self._calculate_retry_delay(e, retry_config, context)
                
                if delay > 0:
                    time.sleep(delay)
                
                logger.info(f"[ErrorManager] 重试执行 (第 {attempt + 1} 次)")
        
        # 所有重试都失败了
        if last_error:
            raise last_error
        else:
            raise SystemError("执行失败，未知错误")
    
    def get_error_metrics(self) -> Dict[str, Any]:
        """获取错误指标"""
        with self._lock:
            return {
                "total_errors": self._error_metrics.total_errors,
                "errors_by_category": dict(self._error_metrics.errors_by_category),
                "errors_by_severity": dict(self._error_metrics.errors_by_severity),
                "retry_success_count": self._error_metrics.retry_success_count,
                "retry_failure_count": self._error_metrics.retry_failure_count,
                "last_error_time": self._error_metrics.last_error_time,
                "error_rate": self._error_metrics.error_rate,
                "recent_errors": list(self._error_history)[-10:]  # 最近10个错误
            }
    
    def get_error_summary(self) -> Dict[str, Any]:
        """获取错误摘要"""
        metrics = self.get_error_metrics()
        
        return {
            "summary": {
                "total_errors": metrics["total_errors"],
                "critical_errors": metrics["errors_by_severity"].get("critical", 0),
                "high_errors": metrics["errors_by_severity"].get("high", 0),
                "retry_success_rate": (
                    metrics["retry_success_count"] / 
                    (metrics["retry_success_count"] + metrics["retry_failure_count"])
                    if (metrics["retry_success_count"] + metrics["retry_failure_count"]) > 0
                    else 0
                )
            },
            "top_error_categories": sorted(
                metrics["errors_by_category"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
            "recent_errors": metrics["recent_errors"]
        }
    
    def clear_error_history(self):
        """清空错误历史"""
        with self._lock:
            self._error_history.clear()
            self._retry_cache.clear()
            logger.info("[ErrorManager] 错误历史已清空")
    
    def reset_metrics(self):
        """重置错误指标"""
        with self._lock:
            self._error_metrics = ErrorMetrics()
            logger.info("[ErrorManager] 错误指标已重置")


# 全局错误管理器实例
error_manager = ErrorManager()
