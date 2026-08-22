# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-10-30
@packageName src.models
@className ProcessorResponse
@describe 处理器统一返回格式
"""

from typing import Any, Dict, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum


class ResponseStatus(Enum):
    """响应状态枚举"""
    SUCCESS = "success"
    FAILED = "failed"
    ERROR = "error"
    WARNING = "warning"


@dataclass
class ProcessorResponse:
    """
    处理器统一返回格式
    
    标准化所有处理器的返回结果，确保一致性和可观测性
    """
    
    # ========== 核心字段（必需） ==========
    status: ResponseStatus  # 执行状态：success/failed/error/warning
    processor_type: str  # 处理器类型：http_request/mysql/rocketmq等
    
    # ========== 数据字段 ==========
    body: Optional[Any] = None  # 处理器返回的主要数据
    message: Optional[str] = None  # 状态消息
    
    # ========== 状态码 ==========
    status_code: Optional[int] = None  # 状态码（如 HTTP 200, 500 等）
    
    # ========== 元数据字段 ==========
    metadata: Dict[str, Any] = field(default_factory=dict)  # 处理器特定的元数据
    variables: Optional[Dict[str, Any]] = None  # 上下文变量
    
    # ========== 错误信息 ==========
    error: Optional[str] = None  # 错误信息
    error_code: Optional[str] = None  # 错误代码
    error_details: Optional[Dict[str, Any]] = None  # 详细错误信息
    
    # ========== 性能指标 ==========
    duration: Optional[float] = None  # 执行耗时（秒）
    
    def to_dict(self, include_variables: bool = False) -> Dict[str, Any]:
        """
        转换为字典
        
        Args:
            include_variables: 是否包含 variables 字段（默认 False）
                              设置为 False 可以避免每个节点都携带所有变量导致内存溢出
        """
        result = {
            "status": self.status.value,
            "processor_type": self.processor_type,
        }
        
        if self.body is not None:
            result["body"] = self.body
        
        if self.message:
            result["message"] = self.message
        
        if self.status_code is not None:
            result["status_code"] = self.status_code
        
        if self.metadata:
            result["metadata"] = self.metadata
        
        # 默认不输出 variables，避免每个节点都携带所有变量导致数据量爆炸
        # 如果确实需要，可以通过 include_variables=True 参数显式启用
        if include_variables and self.variables is not None:
            result["variables"] = self.variables
        
        if self.error:
            result["error"] = self.error
        
        if self.error_code:
            result["error_code"] = self.error_code
        
        if self.error_details:
            result["error_details"] = self.error_details
        
        if self.duration is not None:
            result["duration"] = self.duration
        
        return result
    
    def is_success(self) -> bool:
        """判断是否成功"""
        return self.status == ResponseStatus.SUCCESS
    
    def is_failed(self) -> bool:
        """判断是否失败"""
        return self.status in [ResponseStatus.FAILED, ResponseStatus.ERROR]


class ResponseBuilder:
    """响应构建器，提供便捷的构建方法"""
    
    @staticmethod
    def success(
        processor_type: str,
        body: Any = None,
        message: str = None,
        status_code: int = None,
        metadata: Dict[str, Any] = None,
        duration: float = None,
        variables: Optional[Dict[str, Any]] = None
    ) -> ProcessorResponse:
        """
        构建成功响应
        
        Args:
            processor_type: 处理器类型
            body: 返回数据
            message: 成功消息
            status_code: 状态码（如 HTTP 200）
            metadata: 元数据
            duration: 执行耗时
            variables: 上下文变量
        
        Returns:
            ProcessorResponse: 标准响应对象
        """
        return ProcessorResponse(
            status=ResponseStatus.SUCCESS,
            processor_type=processor_type,
            body=body,
            message=message or "操作成功",
            status_code=status_code,
            metadata=metadata or {},
            duration=duration,
            variables=variables
        )
    
    @staticmethod
    def error(
        processor_type: str,
        error: str,
        error_code: str = None,
        status_code: int = None,
        error_details: Dict[str, Any] = None,
        body: Any = None,
        duration: float = None,
        variables: Optional[Dict[str, Any]] = None
    ) -> ProcessorResponse:
        """
        构建错误响应
        
        Args:
            processor_type: 处理器类型
            error: 错误信息
            error_code: 错误代码
            status_code: 状态码（如 HTTP 500）
            error_details: 详细错误信息
            body: 部分数据（如果有）
            duration: 执行耗时
            variables: 上下文变量
        
        Returns:
            ProcessorResponse: 标准响应对象
        """
        return ProcessorResponse(
            status=ResponseStatus.ERROR,
            processor_type=processor_type,
            error=error,
            error_code=error_code,
            status_code=status_code,
            error_details=error_details or {},
            body=body,
            message="操作失败",
            duration=duration,
            variables=variables
        )
    
    @staticmethod
    def failed(
        processor_type: str,
        message: str,
        body: Any = None,
        status_code: int = None,
        metadata: Dict[str, Any] = None,
        duration: float = None,
        variables: Optional[Dict[str, Any]] = None
    ) -> ProcessorResponse:
        """
        构建失败响应（业务失败，非系统错误）
        
        Args:
            processor_type: 处理器类型
            message: 失败消息
            body: 返回数据
            status_code: 状态码
            metadata: 元数据
            duration: 执行耗时
            variables: 上下文变量
        
        Returns:
            ProcessorResponse: 标准响应对象
        """
        return ProcessorResponse(
            status=ResponseStatus.FAILED,
            processor_type=processor_type,
            message=message,
            body=body,
            status_code=status_code,
            metadata=metadata or {},
            duration=duration,
            variables=variables
        )
    
    @staticmethod
    def from_http_response(
        status_code: int,
        headers: Dict[str, Any],
        body: Any,
        duration: float = None,
        request: Dict[str, Any] = None,
        variables: Optional[Dict[str, Any]] = None
    ) -> ProcessorResponse:
        """
        从HTTP响应构建标准响应
        
        Args:
            status_code: HTTP状态码
            headers: 响应头
            body: 响应体
            duration: 执行耗时
            request: 请求元数据（包含method, url, headers, params, cookies, json/data等）
            variables: 上下文变量
        
        Returns:
            ProcessorResponse: 标准响应对象
        """
        status = ResponseStatus.SUCCESS if 200 <= status_code < 300 else ResponseStatus.ERROR
        
        metadata = {
            "headers": headers
        }
        
        # 如果提供了请求元数据，添加到metadata中
        if request:
            metadata["request"] = request
        
        return ProcessorResponse(
            status=status,
            processor_type="http_request",
            body=body,
            message=f"HTTP {status_code}",
            status_code=status_code,
            variables=variables,
            metadata=metadata,
            duration=duration
        )
    
    @staticmethod
    def from_db_response(
        operation: str,
        body: Any,
        affected_rows: int = 0,
        duration: float = None,
        variables: Optional[Dict[str, Any]] = None
    ) -> ProcessorResponse:
        """
        从数据库响应构建标准响应
        
        Args:
            operation: 操作类型（select/insert/update/delete）
            body: 返回数据
            affected_rows: 影响行数
            duration: 执行耗时
            variables: 上下文变量
        
        Returns:
            ProcessorResponse: 标准响应对象
        """
        return ProcessorResponse(
            status=ResponseStatus.SUCCESS,
            processor_type="mysql",
            body=body,
            message=f"{operation.upper()} 操作成功",
            status_code=200,
            metadata={
                "operation": operation,
                "affected_rows": affected_rows
            },
            duration=duration,
            variables=variables
        )
    
    @staticmethod
    def from_mq_response(
        msg_id: str,
        topic: str,
        tag: str = None,
        key: str = None,
        duration: float = None,
        variables: Optional[Dict[str, Any]] = None
    ) -> ProcessorResponse:
        """
        从MQ响应构建标准响应
        
        Args:
            msg_id: 消息ID
            topic: 主题
            tag: 标签
            key: 键值
            duration: 执行耗时
            variables: 上下文变量
        
        Returns:
            ProcessorResponse: 标准响应对象
        """
        return ProcessorResponse(
            status=ResponseStatus.SUCCESS,
            processor_type="rocketmq",
            body={"msg_id": msg_id},
            message="消息发送成功",
            status_code=200,
            metadata={
                "topic": topic,
                "tag": tag or "*",
                "key": key or "*"
            },
            duration=duration,
            variables=variables
        )
    
    @staticmethod
    def from_loop_response(
        loop_type: str,
        iterations: int,
        results: list,
        duration: float = None,
        variables: Optional[Dict[str, Any]] = None
    ) -> ProcessorResponse:
        """
        从循环响应构建标准响应
        
        Args:
            loop_type: 循环类型
            iterations: 迭代次数
            results: 迭代结果列表
            duration: 执行耗时
            variables: 上下文变量
        
        Returns:
            ProcessorResponse: 标准响应对象
        """
        return ProcessorResponse(
            status=ResponseStatus.SUCCESS,
            processor_type="loop",
            body=results,
            message=f"循环执行完成：{iterations}次迭代",
            status_code=200,
            metadata={
                "loop_type": loop_type,
                "iterations": iterations,
                "items_count": len(results)
            },
            duration=duration,
            variables=variables
        )


# ========== 便捷函数 ==========

def success_response(processor_type: str, include_variables: bool = False, **kwargs) -> Dict[str, Any]:
    """快速创建成功响应字典"""
    return ResponseBuilder.success(processor_type, **kwargs).to_dict(include_variables=include_variables)


def error_response(processor_type: str, error: str, include_variables: bool = False, **kwargs) -> Dict[str, Any]:
    """快速创建错误响应字典"""
    return ResponseBuilder.error(processor_type, error, **kwargs).to_dict(include_variables=include_variables)


def failed_response(processor_type: str, message: str, include_variables: bool = False, **kwargs) -> Dict[str, Any]:
    """快速创建失败响应字典"""
    return ResponseBuilder.failed(processor_type, message, **kwargs).to_dict(include_variables=include_variables)

