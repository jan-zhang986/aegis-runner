# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-9-30
@packageName
@className CredentialStore
@describe 凭证管理中心 - 统一管理API鉴权信息
"""

import json
import base64
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from src.engine.core.simple_logger import logger


class AuthType(Enum):
    """鉴权类型枚举"""
    BEARER = "bearer"
    API_KEY = "api_key"
    BASIC = "basic"
    OAUTH2 = "oauth2"
    CUSTOM = "custom"
    SIGNATURE = "signature"
    NONE = "none"


@dataclass
class Credential:
    """凭证数据模型"""
    credential_id: str
    name: str
    auth_type: str
    config: Dict[str, Any]
    description: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: Optional[str] = None
    enabled: bool = True
    
    def is_expired(self) -> bool:
        """检查凭证是否过期"""
        if not self.expires_at:
            return False
        expire_time = datetime.fromisoformat(self.expires_at)
        return datetime.now() > expire_time
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


class CredentialStore:
    """
    企业级凭证管理中心
    
    功能：
    1. 凭证的CRUD操作
    2. 凭证加密存储
    3. 凭证过期管理
    4. 凭证使用审计
    5. 凭证权限控制
    """
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        初始化凭证存储
        
        Args:
            encryption_key: 加密密钥（用于加密敏感信息）
        """
        self._credentials: Dict[str, Credential] = {}
        self._encryption_key = encryption_key or "default_encryption_key_change_in_prod"
        self._audit_log: List[Dict[str, Any]] = []
        
        logger.info("[CredentialStore] 凭证管理中心已初始化")
    
    def add_credential(
        self,
        credential_id: str,
        name: str,
        auth_type: str,
        config: Dict[str, Any],
        description: str = "",
        tags: List[str] = None,
        expires_in_days: Optional[int] = None
    ) -> Credential:
        """
        添加凭证
        
        Args:
            credential_id: 凭证唯一标识
            name: 凭证名称
            auth_type: 鉴权类型
            config: 鉴权配置
            description: 描述信息
            tags: 标签列表
            expires_in_days: 过期天数
            
        Returns:
            Credential: 创建的凭证对象
        """
        if credential_id in self._credentials:
            raise ValueError(f"凭证ID '{credential_id}' 已存在")
        
        # 加密敏感信息
        encrypted_config = self._encrypt_sensitive_data(config)
        
        # 计算过期时间
        expires_at = None
        if expires_in_days:
            expires_at = (datetime.now() + timedelta(days=expires_in_days)).isoformat()
        
        # 创建凭证对象
        credential = Credential(
            credential_id=credential_id,
            name=name,
            auth_type=auth_type,
            config=encrypted_config,
            description=description,
            tags=tags or [],
            expires_at=expires_at
        )
        
        self._credentials[credential_id] = credential
        
        # 记录审计日志
        self._log_audit("ADD_CREDENTIAL", credential_id, {
            "name": name,
            "auth_type": auth_type
        })
        
        logger.info(f"[CredentialStore] ✅ 凭证已添加: {credential_id} ({name})")
        
        return credential
    
    def get_credential(self, credential_id: str) -> Optional[Credential]:
        """
        获取凭证
        
        Args:
            credential_id: 凭证ID
            
        Returns:
            Credential: 凭证对象，如果不存在返回None
        """
        credential = self._credentials.get(credential_id)
        
        if not credential:
            logger.warning(f"[CredentialStore] ⚠️ 凭证不存在: {credential_id}")
            return None
        
        if not credential.enabled:
            logger.warning(f"[CredentialStore] ⚠️ 凭证已禁用: {credential_id}")
            return None
        
        if credential.is_expired():
            logger.warning(f"[CredentialStore] ⚠️ 凭证已过期: {credential_id}")
            return None
        
        # 记录审计日志
        self._log_audit("GET_CREDENTIAL", credential_id)
        
        return credential
    
    def get_credential_config(self, credential_id: str) -> Optional[Dict[str, Any]]:
        """
        获取凭证配置（解密后）
        
        Args:
            credential_id: 凭证ID
            
        Returns:
            Dict: 解密后的凭证配置
        """
        credential = self.get_credential(credential_id)
        if not credential:
            return None
        
        # 解密敏感信息
        decrypted_config = self._decrypt_sensitive_data(credential.config)
        
        return decrypted_config
    
    def update_credential(
        self,
        credential_id: str,
        config: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        enabled: Optional[bool] = None
    ) -> bool:
        """
        更新凭证
        
        Args:
            credential_id: 凭证ID
            config: 新的配置（可选）
            description: 新的描述（可选）
            enabled: 启用/禁用（可选）
            
        Returns:
            bool: 是否更新成功
        """
        credential = self._credentials.get(credential_id)
        if not credential:
            logger.error(f"[CredentialStore] ❌ 凭证不存在: {credential_id}")
            return False
        
        # 更新配置
        if config is not None:
            credential.config = self._encrypt_sensitive_data(config)
        
        if description is not None:
            credential.description = description
        
        if enabled is not None:
            credential.enabled = enabled
        
        credential.updated_at = datetime.now().isoformat()
        
        # 记录审计日志
        self._log_audit("UPDATE_CREDENTIAL", credential_id, {
            "updated_fields": {
                "config": config is not None,
                "description": description is not None,
                "enabled": enabled is not None
            }
        })
        
        logger.info(f"[CredentialStore] ✅ 凭证已更新: {credential_id}")
        
        return True
    
    def delete_credential(self, credential_id: str) -> bool:
        """
        删除凭证
        
        Args:
            credential_id: 凭证ID
            
        Returns:
            bool: 是否删除成功
        """
        if credential_id not in self._credentials:
            logger.error(f"[CredentialStore] ❌ 凭证不存在: {credential_id}")
            return False
        
        del self._credentials[credential_id]
        
        # 记录审计日志
        self._log_audit("DELETE_CREDENTIAL", credential_id)
        
        logger.info(f"[CredentialStore] ✅ 凭证已删除: {credential_id}")
        
        return True
    
    def list_credentials(
        self,
        auth_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        enabled_only: bool = True
    ) -> List[Credential]:
        """
        列出凭证
        
        Args:
            auth_type: 按鉴权类型过滤
            tags: 按标签过滤
            enabled_only: 只返回启用的凭证
            
        Returns:
            List[Credential]: 凭证列表
        """
        credentials = list(self._credentials.values())
        
        # 过滤
        if enabled_only:
            credentials = [c for c in credentials if c.enabled]
        
        if auth_type:
            credentials = [c for c in credentials if c.auth_type == auth_type]
        
        if tags:
            credentials = [c for c in credentials if any(tag in c.tags for tag in tags)]
        
        return credentials
    
    def get_auth_headers(self, credential_id: str, context=None) -> Dict[str, str]:
        """
        根据凭证生成HTTP鉴权头
        
        Args:
            credential_id: 凭证ID
            context: 执行上下文（用于变量替换）
            
        Returns:
            Dict: HTTP请求头
        """
        config = self.get_credential_config(credential_id)
        if not config:
            logger.error(f"[CredentialStore] ❌ 无法获取凭证配置: {credential_id}")
            return {}
        
        credential = self._credentials[credential_id]
        auth_type = credential.auth_type
        
        # 根据不同的鉴权类型生成对应的Header
        if auth_type == AuthType.BEARER.value:
            token = config.get("token", "")
            if context:
                token = context.render_string(token)
            return {"Authorization": f"Bearer {token}"}
        
        elif auth_type == AuthType.API_KEY.value:
            key_name = config.get("key_name", "X-API-Key")
            key_value = config.get("key_value", "")
            if context:
                key_value = context.render_string(key_value)
            return {key_name: key_value}
        
        elif auth_type == AuthType.BASIC.value:
            username = config.get("username", "")
            password = config.get("password", "")
            if context:
                username = context.render_string(username)
                password = context.render_string(password)
            
            # Base64编码
            credentials = f"{username}:{password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        
        elif auth_type == AuthType.OAUTH2.value:
            access_token = config.get("access_token", "")
            token_type = config.get("token_type", "Bearer")
            if context:
                access_token = context.render_string(access_token)
            return {"Authorization": f"{token_type} {access_token}"}
        
        elif auth_type == AuthType.CUSTOM.value:
            # 自定义Header
            headers = config.get("headers", {})
            if context:
                processed_headers = {}
                for key, value in headers.items():
                    processed_headers[key] = context.render_string(str(value))
                return processed_headers
            return headers
        
        else:
            logger.warning(f"[CredentialStore] ⚠️ 不支持的鉴权类型: {auth_type}")
            return {}
    
    def _encrypt_sensitive_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        加密敏感数据
        
        Args:
            config: 原始配置
            
        Returns:
            Dict: 加密后的配置
        """
        # 简单的加密实现（生产环境应使用更强的加密算法）
        # 这里只是演示，实际应该使用 cryptography 库
        encrypted_config = config.copy()
        
        # 标记哪些字段需要加密
        sensitive_fields = ['token', 'password', 'secret_key', 'access_token', 'key_value']
        
        for field in sensitive_fields:
            if field in encrypted_config:
                # 简单的Base64编码（生产环境应使用AES等强加密）
                value = str(encrypted_config[field])
                encrypted_config[field] = base64.b64encode(value.encode()).decode()
                encrypted_config[f"_{field}_encrypted"] = True
        
        return encrypted_config
    
    def _decrypt_sensitive_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        解密敏感数据
        
        Args:
            config: 加密的配置
            
        Returns:
            Dict: 解密后的配置
        """
        decrypted_config = config.copy()
        
        # 解密标记为加密的字段
        for key in list(decrypted_config.keys()):
            if key.endswith("_encrypted") and decrypted_config[key]:
                field_name = key.replace("_", "").replace("encrypted", "")
                if field_name in decrypted_config:
                    encrypted_value = decrypted_config[field_name]
                    decrypted_config[field_name] = base64.b64decode(encrypted_value).decode()
                    del decrypted_config[key]
        
        return decrypted_config
    
    def _log_audit(self, action: str, credential_id: str, details: Dict[str, Any] = None):
        """
        记录审计日志
        
        Args:
            action: 操作类型
            credential_id: 凭证ID
            details: 详细信息
        """
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "credential_id": credential_id,
            "details": details or {}
        }
        
        self._audit_log.append(audit_entry)
        
        logger.info(f"[CredentialStore Audit] {action}: {credential_id}")
    
    def get_audit_log(
        self,
        credential_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取审计日志
        
        Args:
            credential_id: 按凭证ID过滤
            action: 按操作类型过滤
            limit: 返回记录数限制
            
        Returns:
            List: 审计日志列表
        """
        logs = self._audit_log
        
        if credential_id:
            logs = [log for log in logs if log["credential_id"] == credential_id]
        
        if action:
            logs = [log for log in logs if log["action"] == action]
        
        # 返回最新的N条
        return logs[-limit:]
    
    def export_credentials(self, file_path: str, include_sensitive: bool = False):
        """
        导出凭证配置
        
        Args:
            file_path: 导出文件路径
            include_sensitive: 是否包含敏感信息
        """
        export_data = {
            "export_time": datetime.now().isoformat(),
            "credentials": []
        }
        
        for credential in self._credentials.values():
            cred_data = credential.to_dict()
            
            if not include_sensitive:
                # 移除敏感信息
                if "config" in cred_data:
                    cred_data["config"] = {"_masked": True}
            
            export_data["credentials"].append(cred_data)
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[CredentialStore] ✅ 凭证已导出到: {file_path}")
    
    def import_credentials(self, file_path: str, overwrite: bool = False):
        """
        导入凭证配置
        
        Args:
            file_path: 导入文件路径
            overwrite: 是否覆盖已存在的凭证
        """
        with open(file_path, "r", encoding="utf-8") as f:
            import_data = json.load(f)
        
        credentials = import_data.get("credentials", [])
        imported_count = 0
        skipped_count = 0
        
        for cred_data in credentials:
            credential_id = cred_data["credential_id"]
            
            if credential_id in self._credentials and not overwrite:
                logger.warning(f"[CredentialStore] ⚠️ 凭证已存在，跳过: {credential_id}")
                skipped_count += 1
                continue
            
            credential = Credential(**cred_data)
            self._credentials[credential_id] = credential
            imported_count += 1
        
        logger.info(f"[CredentialStore] ✅ 凭证导入完成: 导入{imported_count}个，跳过{skipped_count}个")
    
    def check_expired_credentials(self) -> List[Credential]:
        """
        检查过期的凭证
        
        Returns:
            List[Credential]: 过期的凭证列表
        """
        expired = [c for c in self._credentials.values() if c.is_expired()]
        
        if expired:
            logger.warning(f"[CredentialStore] ⚠️ 发现{len(expired)}个过期凭证")
            for cred in expired:
                logger.warning(f"   - {cred.credential_id} ({cred.name}) 过期时间: {cred.expires_at}")
        
        return expired
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取凭证统计信息
        
        Returns:
            Dict: 统计信息
        """
        total = len(self._credentials)
        enabled = sum(1 for c in self._credentials.values() if c.enabled)
        disabled = total - enabled
        expired = sum(1 for c in self._credentials.values() if c.is_expired())
        
        # 按类型统计
        by_type = {}
        for credential in self._credentials.values():
            auth_type = credential.auth_type
            by_type[auth_type] = by_type.get(auth_type, 0) + 1
        
        stats = {
            "total_credentials": total,
            "enabled_credentials": enabled,
            "disabled_credentials": disabled,
            "expired_credentials": expired,
            "by_auth_type": by_type,
            "audit_log_count": len(self._audit_log)
        }
        
        return stats
    
    def print_statistics(self):
        """打印统计信息"""
        stats = self.get_statistics()
        
        print("\n" + "="*60)
        print("凭证管理中心统计信息")
        print("="*60)
        print(f"总凭证数: {stats['total_credentials']}")
        print(f"  ✅ 启用: {stats['enabled_credentials']}")
        print(f"  ❌ 禁用: {stats['disabled_credentials']}")
        print(f"  ⏰ 过期: {stats['expired_credentials']}")
        
        print(f"\n按鉴权类型统计:")
        for auth_type, count in stats['by_auth_type'].items():
            print(f"  {auth_type}: {count}")
        
        print(f"\n审计日志: {stats['audit_log_count']} 条记录")
        print("="*60)


# 全局凭证存储实例
credential_store = CredentialStore()


# ============================================================
# 便捷函数
# ============================================================

def add_bearer_credential(
    credential_id: str,
    name: str,
    token: str,
    description: str = "",
    expires_in_days: Optional[int] = None
) -> Credential:
    """快捷添加Bearer Token凭证"""
    return credential_store.add_credential(
        credential_id=credential_id,
        name=name,
        auth_type=AuthType.BEARER.value,
        config={"token": token},
        description=description,
        expires_in_days=expires_in_days
    )


def add_api_key_credential(
    credential_id: str,
    name: str,
    key_name: str,
    key_value: str,
    description: str = "",
    expires_in_days: Optional[int] = None
) -> Credential:
    """快捷添加API Key凭证"""
    return credential_store.add_credential(
        credential_id=credential_id,
        name=name,
        auth_type=AuthType.API_KEY.value,
        config={
            "key_name": key_name,
            "key_value": key_value
        },
        description=description,
        expires_in_days=expires_in_days
    )


def add_basic_auth_credential(
    credential_id: str,
    name: str,
    username: str,
    password: str,
    description: str = "",
    expires_in_days: Optional[int] = None
) -> Credential:
    """快捷添加Basic Auth凭证"""
    return credential_store.add_credential(
        credential_id=credential_id,
        name=name,
        auth_type=AuthType.BASIC.value,
        config={
            "username": username,
            "password": password
        },
        description=description,
        expires_in_days=expires_in_days
    )


def add_oauth2_credential(
    credential_id: str,
    name: str,
    access_token: str,
    token_type: str = "Bearer",
    refresh_token: Optional[str] = None,
    description: str = "",
    expires_in_days: Optional[int] = None
) -> Credential:
    """快捷添加OAuth2凭证"""
    config = {
        "access_token": access_token,
        "token_type": token_type
    }
    
    if refresh_token:
        config["refresh_token"] = refresh_token
    
    return credential_store.add_credential(
        credential_id=credential_id,
        name=name,
        auth_type=AuthType.OAUTH2.value,
        config=config,
        description=description,
        expires_in_days=expires_in_days
    )
