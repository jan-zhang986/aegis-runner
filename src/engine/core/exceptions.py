# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName src.core
@className Exceptions
@describe 统一的错误处理和异常管理
"""

from typing import Any, Dict, List, Optional, Union
from enum import Enum
import traceback
import time
from dataclasses import dataclass
from src.engine.core.simple_logger import logger


class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"          # 低严重程度，可以继续执行
    MEDIUM = "medium"    # 中等严重程度，需要警告
    HIGH = "high"        # 高严重程度，可能影响功能
    CRITICAL = "critical" # 严重错误，必须停止执行


class ErrorCategory(Enum):
    """错误分类"""
    VALIDATION = "validation"      # 配置验证错误
    EXECUTION = "execution"        # 执行错误
    CONNECTION = "connection"      # 连接错误
    TIMEOUT = "timeout"           # 超时错误
    SECURITY = "security"         # 安全错误
    DATA = "data"                 # 数据错误
    SYSTEM = "system"             # 系统错误
    NETWORK = "network"           # 网络错误
    DATABASE = "database"         # 数据库错误
    UNKNOWN = "unknown"           # 未知错误


@dataclass
class ErrorContext:
    """错误上下文信息"""
    node_id: Optional[str] = None
    processor_type: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    input_data: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None
    retry_count: int = 0
    execution_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class WorkflowError(Exception):
    """工作流基础异常类"""
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.HIGH,
        context: Optional[ErrorContext] = None,
        original_error: Optional[Exception] = None,
        retryable: bool = False
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.context = context or ErrorContext()
        self.original_error = original_error
        self.retryable = retryable
        self.timestamp = self.context.timestamp
        self.error_id = self._generate_error_id()
        
        # 记录错误
        self._log_error()
    
    def _generate_error_id(self) -> str:
        """生成错误ID"""
        import hashlib
        error_data = f"{self.message}{self.category.value}{self.timestamp}"
        return hashlib.md5(error_data.encode()).hexdigest()[:8]
    
    def _log_error(self):
        """记录错误日志"""
        log_level = "ERROR" if self.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL] else "WARNING"
        log_message = f"[{self.error_id}] {self.category.value.upper()} Error: {self.message}"
        
        if self.context.node_id:
            log_message += f" (Node: {self.context.node_id})"
        
        if self.context.processor_type:
            log_message += f" (Processor: {self.context.processor_type})"
        
        logger.log(log_level, log_message)
        
        if self.original_error:
            logger.error(f"[{self.error_id}] Original Error: {str(self.original_error)}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_id": self.error_id,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "retryable": self.retryable,
            "timestamp": self.timestamp,
            "context": {
                "node_id": self.context.node_id,
                "processor_type": self.context.processor_type,
                "retry_count": self.context.retry_count,
                "execution_id": self.context.execution_id
            },
            "original_error": str(self.original_error) if self.original_error else None,
            "traceback": traceback.format_exc() if self.original_error else None
        }


class ValidationError(WorkflowError):
    """配置验证错误"""
    
    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        field_value: Optional[Any] = None,
        validation_rule: Optional[str] = None,
        context: Optional[ErrorContext] = None
    ):
        self.field_name = field_name
        self.field_value = field_value
        self.validation_rule = validation_rule
        
        error_message = message
        if field_name:
            error_message = f"配置验证失败 [{field_name}]: {message}"
        
        super().__init__(
            message=error_message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            context=context,
            retryable=False
        )


class ExecutionError(WorkflowError):
    """执行错误"""
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        original_error: Optional[Exception] = None,
        retryable: bool = True
    ):
        self.operation = operation
        
        error_message = message
        if operation:
            error_message = f"执行失败 [{operation}]: {message}"
        
        super().__init__(
            message=error_message,
            category=ErrorCategory.EXECUTION,
            severity=ErrorSeverity.HIGH,
            context=context,
            original_error=original_error,
            retryable=retryable
        )


class ConnectionError(WorkflowError):
    """连接错误"""
    
    def __init__(
        self,
        message: str,
        connection_type: Optional[str] = None,
        endpoint: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        original_error: Optional[Exception] = None,
        retryable: bool = True
    ):
        self.connection_type = connection_type
        self.endpoint = endpoint
        
        error_message = message
        if connection_type:
            error_message = f"连接失败 [{connection_type}]: {message}"
        
        super().__init__(
            message=error_message,
            category=ErrorCategory.CONNECTION,
            severity=ErrorSeverity.HIGH,
            context=context,
            original_error=original_error,
            retryable=retryable
        )


class TimeoutError(WorkflowError):
    """超时错误"""
    
    def __init__(
        self,
        message: str,
        timeout_duration: Optional[float] = None,
        operation: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        retryable: bool = True
    ):
        self.timeout_duration = timeout_duration
        self.operation = operation
        
        error_message = message
        if timeout_duration:
            error_message = f"操作超时 ({timeout_duration}s): {message}"
        
        super().__init__(
            message=error_message,
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.HIGH,
            context=context,
            retryable=retryable
        )


class SecurityError(WorkflowError):
    """安全错误"""
    
    def __init__(
        self,
        message: str,
        security_rule: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        original_error: Optional[Exception] = None,
        retryable: bool = False
    ):
        self.security_rule = security_rule
        
        error_message = message
        if security_rule:
            error_message = f"安全违规 [{security_rule}]: {message}"
        
        super().__init__(
            message=error_message,
            category=ErrorCategory.SECURITY,
            severity=ErrorSeverity.CRITICAL,
            context=context,
            original_error=original_error,
            retryable=retryable
        )


class DataError(WorkflowError):
    """数据错误"""
    
    def __init__(
        self,
        message: str,
        data_type: Optional[str] = None,
        data_source: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        original_error: Optional[Exception] = None,
        retryable: bool = False
    ):
        self.data_type = data_type
        self.data_source = data_source
        
        error_message = message
        if data_type:
            error_message = f"数据错误 [{data_type}]: {message}"
        
        super().__init__(
            message=error_message,
            category=ErrorCategory.DATA,
            severity=ErrorSeverity.MEDIUM,
            context=context,
            original_error=original_error,
            retryable=retryable
        )


class SystemError(WorkflowError):
    """系统错误"""
    
    def __init__(
        self,
        message: str,
        system_component: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        original_error: Optional[Exception] = None,
        retryable: bool = False
    ):
        self.system_component = system_component
        
        error_message = message
        if system_component:
            error_message = f"系统错误 [{system_component}]: {message}"
        
        super().__init__(
            message=error_message,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.CRITICAL,
            context=context,
            original_error=original_error,
            retryable=retryable
        )


class NetworkError(WorkflowError):
    """网络错误"""
    
    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        status_code: Optional[int] = None,
        context: Optional[ErrorContext] = None,
        original_error: Optional[Exception] = None,
        retryable: bool = True
    ):
        self.url = url
        self.status_code = status_code
        
        error_message = message
        if url:
            error_message = f"网络错误 [{url}]: {message}"
        if status_code:
            error_message += f" (状态码: {status_code})"
        
        super().__init__(
            message=error_message,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.HIGH,
            context=context,
            original_error=original_error,
            retryable=retryable
        )


class DatabaseError(WorkflowError):
    """数据库错误"""
    
    def __init__(
        self,
        message: str,
        sql: Optional[str] = None,
        database_type: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        original_error: Optional[Exception] = None,
        retryable: bool = True
    ):
        self.sql = sql
        self.database_type = database_type
        
        error_message = message
        if database_type:
            error_message = f"数据库错误 [{database_type}]: {message}"
        
        super().__init__(
            message=error_message,
            category=ErrorCategory.DATABASE,
            severity=ErrorSeverity.HIGH,
            context=context,
            original_error=original_error,
            retryable=retryable
        )


class VariableNotFoundError(ExecutionError):
    """变量未找到错误"""
    
    def __init__(
        self,
        variable_name: str,
        template_str: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        original_error: Optional[Exception] = None,
        retryable: bool = False
    ):
        self.variable_name = variable_name
        self.template_str = template_str
        
        error_message = f"变量 '{variable_name}' 未找到"
        if template_str:
            error_message += f"（在模板: {template_str[:100]}...）" if len(template_str) > 100 else f"（在模板: {template_str}）"
        
        super().__init__(
            message=error_message,
            operation="variable_rendering",
            context=context,
            original_error=original_error,
            retryable=retryable
        )


# 错误处理装饰器
def handle_errors(
    category: ErrorCategory = ErrorCategory.UNKNOWN,
    severity: ErrorSeverity = ErrorSeverity.HIGH,
    retryable: bool = False,
    processor_type: Optional[str] = None
):
    """错误处理装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except WorkflowError:
                # 重新抛出工作流错误
                raise
            except Exception as e:
                # 包装其他异常为工作流错误
                context = ErrorContext(
                    processor_type=processor_type or func.__name__
                )
                
                if category == ErrorCategory.VALIDATION:
                    raise ValidationError(
                        message=str(e),
                        context=context,
                        original_error=e
                    )
                elif category == ErrorCategory.EXECUTION:
                    raise ExecutionError(
                        message=str(e),
                        context=context,
                        original_error=e,
                        retryable=retryable
                    )
                elif category == ErrorCategory.CONNECTION:
                    raise ConnectionError(
                        message=str(e),
                        context=context,
                        original_error=e,
                        retryable=retryable
                    )
                elif category == ErrorCategory.TIMEOUT:
                    raise TimeoutError(
                        message=str(e),
                        context=context,
                        original_error=e,
                        retryable=retryable
                    )
                elif category == ErrorCategory.SECURITY:
                    raise SecurityError(
                        message=str(e),
                        context=context,
                        original_error=e
                    )
                elif category == ErrorCategory.DATA:
                    raise DataError(
                        message=str(e),
                        context=context,
                        original_error=e
                    )
                elif category == ErrorCategory.SYSTEM:
                    raise SystemError(
                        message=str(e),
                        context=context,
                        original_error=e
                    )
                elif category == ErrorCategory.NETWORK:
                    raise NetworkError(
                        message=str(e),
                        context=context,
                        original_error=e,
                        retryable=retryable
                    )
                elif category == ErrorCategory.DATABASE:
                    raise DatabaseError(
                        message=str(e),
                        context=context,
                        original_error=e,
                        retryable=retryable
                    )
                else:
                    raise WorkflowError(
                        message=str(e),
                        category=category,
                        severity=severity,
                        context=context,
                        original_error=e,
                        retryable=retryable
                    )
        
        return wrapper
    return decorator


# 错误分类函数
def classify_error(error: Exception) -> ErrorCategory:
    """根据异常类型自动分类错误"""
    if isinstance(error, ValidationError):
        return ErrorCategory.VALIDATION
    elif isinstance(error, ExecutionError):
        return ErrorCategory.EXECUTION
    elif isinstance(error, ConnectionError):
        return ErrorCategory.CONNECTION
    elif isinstance(error, TimeoutError):
        return ErrorCategory.TIMEOUT
    elif isinstance(error, SecurityError):
        return ErrorCategory.SECURITY
    elif isinstance(error, DataError):
        return ErrorCategory.DATA
    elif isinstance(error, SystemError):
        return ErrorCategory.SYSTEM
    elif isinstance(error, NetworkError):
        return ErrorCategory.NETWORK
    elif isinstance(error, DatabaseError):
        return ErrorCategory.DATABASE
    else:
        return ErrorCategory.UNKNOWN
