# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-09-25
@packageName
@className TokenManager
@describe Token管理器 - 预加载和缓存Token，避免重复登录
"""

import json
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from src.engine.core.simple_logger import logger


@dataclass
class TokenInfo:
    """Token信息"""
    token_name: str
    token_value: str
    token_type: str = "Bearer"
    description: str = ""
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    refresh_token: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """检查Token是否过期"""
        if not self.expires_at:
            return False
        return time.time() > self.expires_at
    
    def get_remaining_seconds(self) -> Optional[int]:
        """获取剩余有效时间（秒）"""
        if not self.expires_at:
            return None
        remaining = self.expires_at - time.time()
        return max(0, int(remaining))


class TokenManager:
    """
    Token管理器
    
    功能：
    1. 预加载Token到全局缓存
    2. Token自动过期检测
    3. 支持Token刷新
    4. 多Token管理
    5. 与ExecutionContext集成
    """
    
    def __init__(self):
        self._tokens: Dict[str, TokenInfo] = {}
        logger.info("[TokenManager] Token管理器已初始化")
    
    def add_token(
        self,
        token_name: str,
        token_value: str,
        token_type: str = "Bearer",
        description: str = "",
        expires_in_seconds: Optional[int] = None,
        refresh_token: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ) -> TokenInfo:
        """
        添加Token到管理器
        
        Args:
            token_name: Token名称（用于引用）
            token_value: Token值
            token_type: Token类型（Bearer/API Key等）
            description: 描述
            expires_in_seconds: 过期时间（秒）
            refresh_token: 刷新Token
            metadata: 元数据
            
        Returns:
            TokenInfo: Token信息对象
        """
        expires_at = None
        if expires_in_seconds:
            expires_at = time.time() + expires_in_seconds
        
        token_info = TokenInfo(
            token_name=token_name,
            token_value=token_value,
            token_type=token_type,
            description=description,
            expires_at=expires_at,
            refresh_token=refresh_token,
            metadata=metadata or {}
        )
        
        self._tokens[token_name] = token_info
        
        logger.info(f"[TokenManager] ✅ Token已添加: {token_name}")
        if expires_in_seconds:
            logger.info(f"[TokenManager] ⏰ 过期时间: {expires_in_seconds}秒后")
        
        return token_info
    
    def get_token(self, token_name: str) -> Optional[TokenInfo]:
        """
        获取Token
        
        Args:
            token_name: Token名称
            
        Returns:
            TokenInfo: Token信息，如果不存在或已过期返回None
        """
        token_info = self._tokens.get(token_name)
        
        if not token_info:
            logger.warning(f"[TokenManager] ⚠️ Token不存在: {token_name}")
            return None
        
        if token_info.is_expired():
            logger.warning(f"[TokenManager] ⚠️ Token已过期: {token_name}")
            return None
        
        return token_info
    
    def get_token_value(self, token_name: str) -> Optional[str]:
        """
        获取Token值
        
        Args:
            token_name: Token名称
            
        Returns:
            str: Token值
        """
        token_info = self.get_token(token_name)
        if not token_info:
            return None
        
        return token_info.token_value
    
    def update_token(
        self,
        token_name: str,
        token_value: str,
        expires_in_seconds: Optional[int] = None
    ) -> bool:
        """
        更新Token
        
        Args:
            token_name: Token名称
            token_value: 新的Token值
            expires_in_seconds: 新的过期时间
            
        Returns:
            bool: 是否更新成功
        """
        if token_name not in self._tokens:
            logger.error(f"[TokenManager] ❌ Token不存在: {token_name}")
            return False
        
        token_info = self._tokens[token_name]
        token_info.token_value = token_value
        token_info.created_at = time.time()
        
        if expires_in_seconds:
            token_info.expires_at = time.time() + expires_in_seconds
        
        logger.info(f"[TokenManager] ✅ Token已更新: {token_name}")
        
        return True
    
    def remove_token(self, token_name: str) -> bool:
        """删除Token"""
        if token_name in self._tokens:
            del self._tokens[token_name]
            logger.info(f"[TokenManager] ✅ Token已删除: {token_name}")
            return True
        return False
    
    def list_tokens(self, include_expired: bool = False) -> Dict[str, TokenInfo]:
        """
        列出所有Token
        
        Args:
            include_expired: 是否包含已过期的Token
            
        Returns:
            Dict: Token字典
        """
        if include_expired:
            return self._tokens.copy()
        
        return {
            name: info for name, info in self._tokens.items()
            if not info.is_expired()
        }
    
    def check_expired_tokens(self) -> list[str]:
        """检查过期的Token"""
        expired = [
            name for name, info in self._tokens.items()
            if info.is_expired()
        ]
        
        if expired:
            logger.warning(f"[TokenManager] ⚠️ 发现{len(expired)}个过期Token: {expired}")
        
        return expired
    
    def inject_tokens_to_context(self, context):
        """
        将所有有效Token注入到ExecutionContext
        
        Args:
            context: ExecutionContext对象
        """
        injected_count = 0
        
        for token_name, token_info in self._tokens.items():
            if token_info.is_expired():
                logger.warning(f"[TokenManager] ⚠️ 跳过过期Token: {token_name}")
                continue
            
            # 注入Token值
            context.set_variable(token_name, token_info.token_value)
            
            # 注入Token类型
            context.set_variable(f"{token_name}_type", token_info.token_type)
            
            # 注入刷新Token（如果有）
            if token_info.refresh_token:
                context.set_variable(f"{token_name}_refresh", token_info.refresh_token)
            
            injected_count += 1
            
            logger.info(f"[TokenManager] 📝 已注入Token: {token_name}")
        
        logger.info(f"[TokenManager] ✅ 共注入{injected_count}个Token到上下文")
    
    def load_from_file(self, file_path: str):
        """从配置文件加载Token"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        tokens = data.get("tokens", [])
        for token_data in tokens:
            self.add_token(**token_data)
        
        logger.info(f"[TokenManager] ✅ 已从文件加载{len(tokens)}个Token")
    
    def save_to_file(self, file_path: str, include_expired: bool = False):
        """保存Token到配置文件"""
        tokens_data = []
        
        for token_name, token_info in self._tokens.items():
            if not include_expired and token_info.is_expired():
                continue
            
            token_dict = {
                "token_name": token_name,
                "token_value": token_info.token_value,
                "token_type": token_info.token_type,
                "description": token_info.description,
                "refresh_token": token_info.refresh_token,
                "metadata": token_info.metadata
            }
            
            # 计算剩余有效时间
            if token_info.expires_at:
                remaining = token_info.get_remaining_seconds()
                if remaining:
                    token_dict["expires_in_seconds"] = remaining
            
            tokens_data.append(token_dict)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({"tokens": tokens_data}, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[TokenManager] ✅ 已保存{len(tokens_data)}个Token到文件")
    
    def print_summary(self):
        """打印Token摘要"""
        print("\n" + "="*60)
        print("Token管理器摘要")
        print("="*60)
        
        total = len(self._tokens)
        valid = sum(1 for t in self._tokens.values() if not t.is_expired())
        expired = total - valid
        
        print(f"总Token数: {total}")
        print(f"  ✅ 有效: {valid}")
        print(f"  ⏰ 过期: {expired}")
        
        print("\nToken列表:")
        for name, info in self._tokens.items():
            status = "⏰ 已过期" if info.is_expired() else "✅ 有效"
            print(f"  {status} {name}")
            print(f"      类型: {info.token_type}")
            print(f"      描述: {info.description}")
            if not info.is_expired() and info.expires_at:
                remaining = info.get_remaining_seconds()
                print(f"      剩余: {remaining}秒 ({remaining//60}分钟)")
        
        print("="*60)


# 全局Token管理器实例
token_manager = TokenManager()


# ============================================================
# 便捷函数
# ============================================================

def preload_token(
    token_name: str,
    token_value: str,
    token_type: str = "Bearer",
    description: str = "",
    expires_in_minutes: Optional[int] = None
) -> TokenInfo:
    """
    快捷预加载Token
    
    Args:
        token_name: Token名称
        token_value: Token值
        token_type: Token类型
        description: 描述
        expires_in_minutes: 过期时间（分钟）
        
    Returns:
        TokenInfo: Token信息
    """
    expires_in_seconds = None
    if expires_in_minutes:
        expires_in_seconds = expires_in_minutes * 60
    
    return token_manager.add_token(
        token_name=token_name,
        token_value=token_value,
        token_type=token_type,
        description=description,
        expires_in_seconds=expires_in_seconds
    )


def get_cached_token(token_name: str) -> Optional[str]:
    """快捷获取缓存的Token值"""
    return token_manager.get_token_value(token_name)
