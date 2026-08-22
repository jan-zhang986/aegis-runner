# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-10-30
@packageName src.clients
@className OssClient
@describe OSS 客户端 - 封装阿里云 OSS 操作能力

提供统一的 OSS 上传、下载、删除功能
"""

import os
from typing import Optional, Dict, Any, Union
from pathlib import Path

try:
    import oss2
    OSS_AVAILABLE = True
except ImportError:
    OSS_AVAILABLE = False
    print("Warning: oss2 库未安装，OSS 功能将不可用。请执行: pip install oss2")

from src.engine.core.simple_logger import logger


def progress_callback(consumed_bytes: int, total_bytes: int):
    """
    OSS 操作进度回调函数
    
    Args:
        consumed_bytes: 已处理的字节数
        total_bytes: 总字节数
    """
    if total_bytes:
        percentage = int(100 * (float(consumed_bytes) / float(total_bytes)))
        logger.info(f"Progress: {consumed_bytes} / {total_bytes} bytes ({percentage}%)")
    else:
        logger.info(f"Progress: {consumed_bytes} bytes")


class OssClient:
    """
    阿里云 OSS 客户端
    
    封装 OSS 上传、下载、删除操作
    参考 aegis-runner 的 AiliBabaOss 类实现
    
    使用示例:
        client = OssClient(
            access_key_id="your-key",
            access_key_secret="your-secret",
            endpoint="https://oss-cn-hangzhou.aliyuncs.com",
            bucket="my-bucket"
        )
        
        # 上传文件
        result = client.upload_file("/path/to/local.txt", "remote/path.txt")
        
        # 下载文件
        result = client.download_file("remote/path.txt", "/path/to/save.txt")
        
        # 删除文件
        result = client.delete_file("remote/path.txt")
    """
    
    def __init__(
        self,
        access_key_id: str,
        access_key_secret: str,
        endpoint: str,
        bucket: str,
        enable_progress: bool = True
    ):
        """
        初始化 OSS 客户端
        
        Args:
            access_key_id: OSS Access Key ID
            access_key_secret: OSS Access Key Secret
            endpoint: OSS Endpoint (如: https://oss-cn-hangzhou.aliyuncs.com)
            bucket: Bucket 名称
            enable_progress: 是否启用进度回调
        
        Raises:
            ImportError: 如果 oss2 库未安装
            Exception: 如果连接失败
        """
        if not OSS_AVAILABLE:
            raise ImportError("oss2 库未安装，请执行: pip install oss2")
        
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.endpoint = endpoint
        self.bucket_name = bucket
        self.enable_progress = enable_progress
        
        # 创建认证对象
        self.auth = oss2.Auth(access_key_id, access_key_secret)
        
        # 创建 Bucket 对象
        self.bucket = oss2.Bucket(self.auth, endpoint, bucket)
        
        logger.info(f"[OssClient] 已初始化 OSS 客户端: endpoint={endpoint}, bucket={bucket}")
    
    def upload_file(
        self,
        local_path: str,
        oss_path: str,
        check_exists: bool = True
    ) -> Dict[str, Any]:
        """
        上传本地文件到 OSS
        
        Args:
            local_path: 本地文件路径
            oss_path: OSS 目标路径
            check_exists: 是否检查本地文件存在
        
        Returns:
            上传结果字典
            {
                "success": bool,
                "oss_path": str,
                "local_path": str,
                "etag": str,
                "request_id": str,
                "status_code": int
            }
        
        Raises:
            FileNotFoundError: 本地文件不存在
            Exception: 上传失败
        """
        # 检查本地文件
        if check_exists and not os.path.exists(local_path):
            raise FileNotFoundError(f"本地文件不存在: {local_path}")
        
        logger.info(f"[OssClient] 开始上传: {local_path} -> oss://{self.bucket_name}/{oss_path}")
        
        try:
            # 上传文件
            with open(local_path, 'rb') as f:
                result = self.bucket.put_object(oss_path, f)
            
            if result.status == 200:
                logger.info(f"[OssClient] ✅ 上传成功: {oss_path} (ETag: {result.etag})")
                
                return {
                    "success": True,
                    "oss_path": oss_path,
                    "local_path": local_path,
                    "etag": result.etag,
                    "request_id": result.request_id,
                    "status_code": result.status
                }
            else:
                raise Exception(f"上传失败，状态码: {result.status}")
        
        except Exception as e:
            logger.error(f"[OssClient] ❌ 上传失败: {str(e)}")
            raise
    
    def upload_stream(
        self,
        content: Union[str, bytes],
        oss_path: str
    ) -> Dict[str, Any]:
        """
        上传文件流到 OSS
        
        Args:
            content: 文件内容（字符串或字节）
            oss_path: OSS 目标路径
        
        Returns:
            上传结果字典
            {
                "success": bool,
                "oss_path": str,
                "content_length": int,
                "etag": str,
                "request_id": str,
                "status_code": int
            }
        
        Raises:
            Exception: 上传失败
        """
        logger.info(f"[OssClient] 开始上传文件流到: oss://{self.bucket_name}/{oss_path}")
        
        try:
            # 转换字符串为字节
            if isinstance(content, str):
                content = content.encode('utf-8')
            
            # 上传文件流
            result = self.bucket.put_object(oss_path, content)
            
            if result.status == 200:
                logger.info(f"[OssClient] ✅ 文件流上传成功: {oss_path} (Size: {len(content)} bytes)")
                
                return {
                    "success": True,
                    "oss_path": oss_path,
                    "content_length": len(content),
                    "etag": result.etag,
                    "request_id": result.request_id,
                    "status_code": result.status
                }
            else:
                raise Exception(f"上传失败，状态码: {result.status}")
        
        except Exception as e:
            logger.error(f"[OssClient] ❌ 文件流上传失败: {str(e)}")
            raise
    
    def download_file(
        self,
        oss_path: str,
        local_path: str,
        create_dirs: bool = True
    ) -> Dict[str, Any]:
        """
        从 OSS 下载文件到本地
        
        Args:
            oss_path: OSS 文件路径
            local_path: 本地保存路径
            create_dirs: 是否自动创建目录
        
        Returns:
            下载结果字典
            {
                "success": bool,
                "oss_path": str,
                "local_path": str,
                "file_size": int,
                "request_id": str,
                "status_code": int
            }
        
        Raises:
            Exception: 下载失败
        """
        # 确保本地目录存在
        if create_dirs:
            local_dir = os.path.dirname(local_path)
            if local_dir and not os.path.exists(local_dir):
                os.makedirs(local_dir, exist_ok=True)
                logger.info(f"[OssClient] 创建目录: {local_dir}")
        
        logger.info(f"[OssClient] 开始下载: oss://{self.bucket_name}/{oss_path} -> {local_path}")
        
        try:
            # 下载文件（带进度回调）
            if self.enable_progress:
                result = self.bucket.get_object_to_file(
                    oss_path,
                    local_path,
                    progress_callback=progress_callback
                )
            else:
                result = self.bucket.get_object_to_file(oss_path, local_path)
            
            if result.status == 200:
                # 获取文件大小
                file_size = os.path.getsize(local_path)
                
                logger.info(f"[OssClient] ✅ 下载成功: {local_path} (Size: {file_size} bytes)")
                
                return {
                    "success": True,
                    "oss_path": oss_path,
                    "local_path": local_path,
                    "file_size": file_size,
                    "request_id": result.request_id,
                    "status_code": result.status
                }
            else:
                raise Exception(f"下载失败，状态码: {result.status}")
        
        except Exception as e:
            logger.error(f"[OssClient] ❌ 下载失败: {str(e)}")
            raise
    
    def get_file_stream(
        self,
        oss_path: str
    ) -> Dict[str, Any]:
        """
        获取 OSS 文件流（不保存到本地）
        
        Args:
            oss_path: OSS 文件路径
        
        Returns:
            文件流结果字典
            {
                "success": bool,
                "oss_path": str,
                "content": bytes,
                "content_length": int,
                "request_id": str,
                "status_code": int
            }
        
        Raises:
            Exception: 获取失败
        """
        logger.info(f"[OssClient] 开始获取文件流: oss://{self.bucket_name}/{oss_path}")
        
        try:
            # 获取文件流
            if self.enable_progress:
                result = self.bucket.get_object(oss_path, progress_callback=progress_callback)
            else:
                result = self.bucket.get_object(oss_path)
            
            if result.status == 200:
                content = result.read()
                
                logger.info(f"[OssClient] ✅ 获取文件流成功: {oss_path} (Size: {len(content)} bytes)")
                
                return {
                    "success": True,
                    "oss_path": oss_path,
                    "content": content,
                    "content_length": len(content),
                    "request_id": result.request_id,
                    "status_code": result.status
                }
            else:
                raise Exception(f"获取文件流失败，状态码: {result.status}")
        
        except Exception as e:
            logger.error(f"[OssClient] ❌ 获取文件流失败: {str(e)}")
            raise
    
    def delete_file(
        self,
        oss_path: str
    ) -> Dict[str, Any]:
        """
        删除 OSS 文件
        
        Args:
            oss_path: OSS 文件路径
        
        Returns:
            删除结果字典
            {
                "success": bool,
                "oss_path": str,
                "request_id": str,
                "status_code": int
            }
        
        Raises:
            Exception: 删除失败
        """
        logger.info(f"[OssClient] 开始删除: oss://{self.bucket_name}/{oss_path}")
        
        try:
            # 删除文件
            result = self.bucket.delete_object(oss_path)
            
            # 删除成功返回 204
            if result.status == 204:
                logger.info(f"[OssClient] ✅ 删除成功: {oss_path}")
                
                return {
                    "success": True,
                    "oss_path": oss_path,
                    "request_id": result.request_id,
                    "status_code": result.status
                }
            else:
                raise Exception(f"删除失败，状态码: {result.status}")
        
        except Exception as e:
            logger.error(f"[OssClient] ❌ 删除失败: {str(e)}")
            raise
    
    def file_exists(
        self,
        oss_path: str
    ) -> bool:
        """
        检查 OSS 文件是否存在
        
        Args:
            oss_path: OSS 文件路径
        
        Returns:
            文件是否存在
        """
        try:
            return self.bucket.object_exists(oss_path)
        except Exception as e:
            logger.error(f"[OssClient] 检查文件存在失败: {str(e)}")
            return False
    
    def get_file_meta(
        self,
        oss_path: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取 OSS 文件元信息
        
        Args:
            oss_path: OSS 文件路径
        
        Returns:
            文件元信息字典，如果获取失败返回 None
        """
        try:
            meta = self.bucket.get_object_meta(oss_path)
            
            return {
                "content_length": meta.headers.get('Content-Length'),
                "content_type": meta.headers.get('Content-Type'),
                "etag": meta.headers.get('ETag'),
                "last_modified": meta.headers.get('Last-Modified'),
            }
        except Exception as e:
            logger.error(f"[OssClient] 获取文件元信息失败: {str(e)}")
            return None
    
    def list_files(
        self,
        prefix: str = "",
        max_keys: int = 100
    ) -> Dict[str, Any]:
        """
        列出 OSS 文件
        
        Args:
            prefix: 文件路径前缀
            max_keys: 最大返回数量
        
        Returns:
            文件列表字典
            {
                "success": bool,
                "files": List[Dict],
                "count": int
            }
        """
        try:
            result = self.bucket.list_objects(prefix=prefix, max_keys=max_keys)
            
            files = []
            for obj in result.object_list:
                files.append({
                    "key": obj.key,
                    "size": obj.size,
                    "last_modified": str(obj.last_modified),
                    "etag": obj.etag
                })
            
            logger.info(f"[OssClient] 列出文件成功: prefix={prefix}, count={len(files)}")
            
            return {
                "success": True,
                "files": files,
                "count": len(files)
            }
        
        except Exception as e:
            logger.error(f"[OssClient] 列出文件失败: {str(e)}")
            raise
    
    def close(self):
        """关闭客户端（oss2 不需要显式关闭）"""
        logger.info(f"[OssClient] OSS 客户端关闭")


# 便捷函数
def create_oss_client(
    access_key_id: str,
    access_key_secret: str,
    endpoint: str,
    bucket: str,
    enable_progress: bool = True
) -> OssClient:
    """
    创建 OSS 客户端（工厂函数）
    
    Args:
        access_key_id: OSS Access Key ID
        access_key_secret: OSS Access Key Secret
        endpoint: OSS Endpoint
        bucket: Bucket 名称
        enable_progress: 是否启用进度回调
    
    Returns:
        OssClient 实例
    """
    return OssClient(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        endpoint=endpoint,
        bucket=bucket,
        enable_progress=enable_progress
    )


if __name__ == '__main__':
    # 使用示例
    client = OssClient(
        access_key_id="your-access-key-id",
        access_key_secret="your-secret-key",
        endpoint="https://oss-cn-hangzhou.aliyuncs.com",
        bucket="test-bucket"
    )
    
    # 上传文件
    # result = client.upload_file("/path/to/local.txt", "remote/file.txt")
    
    # 下载文件
    # result = client.download_file("remote/file.txt", "/path/to/save.txt")
    
    # 删除文件
    # result = client.delete_file("remote/file.txt")

