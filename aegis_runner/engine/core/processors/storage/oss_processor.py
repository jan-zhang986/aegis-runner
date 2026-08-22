# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-10-30
@packageName src.core.processors.storage
@className OssProcessor
@describe OSS 对象存储处理器

支持功能：
1. 上传文件到 OSS
2. 从 OSS 下载文件到本地
3. 删除 OSS 文件
4. 下载的文件可供 HTTP 处理器使用

参考 aegis-runner 的 FileManager.py 实现
使用独立的 OssClient 封装 OSS 操作
"""

import time
from typing import Any, Dict

from aegis_runner.engine.core.processors import BaseProcessor, render_recursive
from aegis_runner.engine.core.simple_logger import logger
from aegis_runner.engine.core.elegant_processor_registry import register_processor, ProcessorCategory
from aegis_runner.engine.models.response import ResponseBuilder
from aegis_runner.engine.clients.oss_client import OssClient, OSS_AVAILABLE


@register_processor(
    processor_type="oss",
    category=ProcessorCategory.DATA,
    description="阿里云 OSS 对象存储处理器，支持上传、下载、删除文件",
    tags={"oss", "storage", "alibaba", "upload", "download"},
    enabled=True,
    priority=100,
    version="1.0.0",
    author="Aegis Team"
)
class OssProcessor(BaseProcessor):
    """
    OSS 处理器
    
    配置示例：
    {
        "operation": "upload",  # 操作类型: upload, download, delete
        "access_key_id": "${OSS_ACCESS_KEY}",
        "access_key_secret": "${OSS_SECRET_KEY}",
        "endpoint": "https://oss-cn-hangzhou.aliyuncs.com",
        "bucket": "my-bucket",
        
        // 上传操作
        "local_path": "/path/to/local/file.txt",  // 本地文件路径
        "oss_path": "folder/file.txt",  // OSS 路径
        
        // 下载操作
        "oss_path": "folder/file.txt",  // OSS 文件路径
        "local_path": "/path/to/save/file.txt",  // 保存路径
        
        // 删除操作
        "oss_path": "folder/file.txt"  // 要删除的文件路径
    }
    """
    
    def __init__(self):
        super().__init__()
        self.processor_type = "oss"
        self.processor_name = "OSS对象存储处理器"
        self.processor_description = "支持阿里云OSS上传、下载、删除操作"
    
    def _get_config_schema_name(self) -> str:
        """获取配置模式名称"""
        return "oss"
    
    def _validate_specific_config(self, config: Dict[str, Any]) -> bool:
        """OSS特定的配置验证"""
        operation = config.get("operation")
        if not operation:
            logger.error("[OssProcessor] operation 不能为空")
            return False
        
        if operation not in ['upload', 'download', 'delete', 'upload_stream']:
            logger.error(f"[OssProcessor] 不支持的操作类型: {operation}")
            return False
        
        # 检查必需字段
        if not config.get("access_key_id"):
            logger.error("[OssProcessor] access_key_id 不能为空")
            return False
        
        if not config.get("access_key_secret"):
            logger.error("[OssProcessor] access_key_secret 不能为空")
            return False
        
        if not config.get("endpoint"):
            logger.error("[OssProcessor] endpoint 不能为空")
            return False
        
        if not config.get("bucket"):
            logger.error("[OssProcessor] bucket 不能为空")
            return False
        
        return True
    
    def execute(self, node_info: dict, context: Any, predecessor_results: dict) -> Dict[str, Any]:
        """
        执行 OSS 操作
        
        Args:
            node_info: 节点信息
            context: 执行上下文
            predecessor_results: 前置节点结果
            
        Returns:
            执行结果
        """
        if not OSS_AVAILABLE:
            return ResponseBuilder.error(
                processor_type="oss",
                error="oss2 库未安装，请执行: pip install oss2",
                error_code="OSS_NOT_AVAILABLE",
                status_code=500
            ).to_dict()
        
        start_time = time.time()
        oss_client = None
        
        try:
            # 获取配置
            config = node_info.get("data", {}).get("config", {})
            
            # 渲染配置中的变量
            config = render_recursive(config, context)
            
            # 验证配置
            if not self._validate_specific_config(config):
                return ResponseBuilder.error(
                    processor_type="oss",
                    error="配置验证失败",
                    error_code="INVALID_CONFIG",
                    status_code=400,
                    duration=time.time() - start_time
                ).to_dict()
            
            # 创建 OSS 客户端
            oss_client = self._create_oss_client(config)
            
            # 执行操作
            operation = config.get("operation")
            
            if operation == "upload":
                result = self._upload_file(oss_client, config, context)
            elif operation == "upload_stream":
                result = self._upload_stream(oss_client, config, context)
            elif operation == "download":
                result = self._download_file(oss_client, config, context)
            elif operation == "delete":
                result = self._delete_file(oss_client, config)
            else:
                return ResponseBuilder.error(
                    processor_type="oss",
                    error=f"不支持的操作类型: {operation}",
                    error_code="UNSUPPORTED_OPERATION",
                    status_code=400,
                    duration=time.time() - start_time
                ).to_dict()
            
            duration = time.time() - start_time
            
            # 返回标准响应
            return ResponseBuilder.success(
                processor_type="oss",
                body=result,
                message=f"OSS {operation} 操作成功",
                status_code=200,
                metadata={
                    "operation": operation,
                    "bucket": config.get("bucket"),
                    "oss_path": config.get("oss_path", "")
                },
                duration=duration
            ).to_dict()
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"[OssProcessor] OSS 操作失败: {str(e)}")
            return ResponseBuilder.error(
                processor_type="oss",
                error=f"OSS 操作失败: {str(e)}",
                error_code="OSS_ERROR",
                status_code=500,
                duration=duration
            ).to_dict()
        
        finally:
            # 关闭客户端
            if oss_client:
                oss_client.close()
    
    def _create_oss_client(self, config: Dict[str, Any]) -> OssClient:
        """
        创建 OSS 客户端
        
        Args:
            config: 配置信息
            
        Returns:
            OssClient 实例
        """
        access_key_id = config.get("access_key_id")
        access_key_secret = config.get("access_key_secret")
        endpoint = config.get("endpoint")
        bucket = config.get("bucket")
        
        # 创建 OSS 客户端
        return OssClient(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            endpoint=endpoint,
            bucket=bucket,
            enable_progress=True
        )
    
    def _upload_file(self, oss_client: OssClient, config: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """
        上传文件到 OSS
        
        Args:
            oss_client: OSS 客户端
            config: 配置信息
            context: 执行上下文
            
        Returns:
            上传结果
        """
        local_path = config.get("local_path")
        oss_path = config.get("oss_path")
        
        if not local_path:
            raise ValueError("local_path 不能为空")
        if not oss_path:
            raise ValueError("oss_path 不能为空")
        
        # 使用客户端上传文件
        result = oss_client.upload_file(local_path, oss_path)
        
        # 保存上传后的路径到上下文变量
        output_variable = config.get("output_variable", "oss_upload_path")
        if context and hasattr(context, 'set_variable'):
            context.set_variable(output_variable, oss_path)
        
        return {
            "status": "success",
            "oss_path": result["oss_path"],
            "local_path": result["local_path"],
            "etag": result["etag"],
            "request_id": result["request_id"]
        }
    
    def _upload_stream(self, oss_client: OssClient, config: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """
        上传文件流到 OSS
        
        Args:
            oss_client: OSS 客户端
            config: 配置信息
            context: 执行上下文
            
        Returns:
            上传结果
        """
        content = config.get("content")
        oss_path = config.get("oss_path")
        
        if content is None:
            raise ValueError("content 不能为空")
        if not oss_path:
            raise ValueError("oss_path 不能为空")
        
        # 使用客户端上传文件流
        result = oss_client.upload_stream(content, oss_path)
        
        # 保存上传后的路径到上下文变量
        output_variable = config.get("output_variable", "oss_upload_path")
        if context and hasattr(context, 'set_variable'):
            context.set_variable(output_variable, oss_path)
        
        return {
            "status": "success",
            "oss_path": result["oss_path"],
            "content_length": result["content_length"],
            "etag": result["etag"],
            "request_id": result["request_id"]
        }
    
    def _download_file(self, oss_client: OssClient, config: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """
        从 OSS 下载文件到本地
        
        Args:
            oss_client: OSS 客户端
            config: 配置信息
            context: 执行上下文
            
        Returns:
            下载结果
        """
        oss_path = config.get("oss_path")
        local_path = config.get("local_path")
        
        if not oss_path:
            raise ValueError("oss_path 不能为空")
        if not local_path:
            raise ValueError("local_path 不能为空")
        
        # 使用客户端下载文件
        result = oss_client.download_file(oss_path, local_path)
        
        # 保存下载后的本地路径到上下文变量
        output_variable = config.get("output_variable", "oss_download_path")
        if context and hasattr(context, 'set_variable'):
            context.set_variable(output_variable, local_path)
        
        return {
            "status": "success",
            "oss_path": result["oss_path"],
            "local_path": result["local_path"],
            "file_size": result["file_size"],
            "request_id": result["request_id"]
        }
    
    def _delete_file(self, oss_client: OssClient, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        删除 OSS 文件
        
        Args:
            oss_client: OSS 客户端
            config: 配置信息
            
        Returns:
            删除结果
        """
        oss_path = config.get("oss_path")
        
        if not oss_path:
            raise ValueError("oss_path 不能为空")
        
        # 使用客户端删除文件
        result = oss_client.delete_file(oss_path)
        
        return {
            "status": "success",
            "oss_path": result["oss_path"],
            "request_id": result["request_id"]
        }
    
    def get_processor_type(self) -> str:
        """获取处理器类型"""
        return self.processor_type
    
    def get_processor_name(self) -> str:
        """获取处理器名称"""
        return self.processor_name
    
    def get_processor_description(self) -> str:
        """获取处理器描述"""
        return self.processor_description
    
    def get_required_config_keys(self) -> list:
        """获取必需的配置键"""
        return ['operation', 'access_key_id', 'access_key_secret', 'endpoint', 'bucket']
    
    def get_optional_config_keys(self) -> list:
        """获取可选的配置键"""
        return ['local_path', 'oss_path', 'content', 'output_variable']

