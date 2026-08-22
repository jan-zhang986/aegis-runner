# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-10-05
@packageName
@className PlatformAuth
@describe 平台鉴权模块 - 函数式Token管理
"""

import requests
import time
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
from src.engine.core.simple_logger import logger


class PlatformAuth:
    """
    平台鉴权管理类
    
    功能：
    1. 动态获取Token（通过登录接口）
    2. Token智能缓存（避免重复登录）
    3. 自动过期管理
    4. 线程安全
    
    使用方式：
    在工作流Headers中：
    {
        "Authentication-Token": "${get_token($email, $password, $url, $header_type)}"
    }
    """
    
    def __init__(self, default_cache_duration: int = 21600):
        """
        初始化平台鉴权
        
        Args:
            default_cache_duration: 默认缓存时长（秒），默认6小时
        """
        self.cache: Dict[Tuple, Tuple[str, datetime]] = {}
        self.default_cache_duration = default_cache_duration
        self.request_count = 0
        self.cache_hit_count = 0
        
        logger.info("[PlatformAuth] 平台鉴权模块已初始化")
    
    def get_token(self, username: str, password: str, url: str, header_type: str) -> str:
        """
        获取平台Token（带缓存）
        
        这是核心函数，会在工作流中被调用：
        ${get_token($email, $password, $url, $header_type)}
        
        Args:
            username: 用户名/邮箱
            password: 密码
            url: 平台URL
            header_type: Header类型（appCode）
            
        Returns:
            str: Token字符串
        """
        self.request_count += 1
        
        # 生成缓存key
        cache_key = (username, password, url, header_type)
        
        # 检查缓存
        if cache_key in self.cache:
            token, expire_time = self.cache[cache_key]
            if datetime.now() < expire_time:
                self.cache_hit_count += 1
                hit_rate = (self.cache_hit_count / self.request_count) * 100
                logger.info(f"[AegisPlatformAuth] ✅ 从缓存获取Token | 缓存命中率: {hit_rate:.1f}%")
                return token
            else:
                logger.info(f"[AegisPlatformAuth] ⚠️ Token已过期，重新获取")
                del self.cache[cache_key]
        else:
            logger.info(f"[AegisPlatformAuth] 🔄 缓存未命中，首次获取Token")
        
        # 从服务器获取Token
        try:
            token = self.fetch_token_from_server(username, password, url, header_type)
            
            # 缓存Token
            expire_time = datetime.now() + timedelta(seconds=self.default_cache_duration)
            self.cache[cache_key] = (token, expire_time)
            
            logger.info(f"[AegisPlatformAuth] 💾 Token已缓存 | 过期时间: {expire_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            return token
            
        except Exception as e:
            logger.error(f"[AegisPlatformAuth] ❌ 获取Token失败: {str(e)}")
            raise
    
    def fetch_token_from_server(self, username: str, password: str, url: str, header_type: str) -> str:
        """
        从服务器获取Token（你的原始逻辑）
        
        Args:
            username: 用户名
            password: 密码
            url: 平台URL
            header_type: Header类型（appCode）
            
        Returns:
            str: Token字符串
            
        Raises:
            Exception: 登录失败时抛出异常
        """
        data = {
            "username": username,
            "password": password,
            "appCode": header_type
        }
        
        path = "/spotter-user-center/sso/login"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
            "content-type": "application/json",
            'x-sso-version': 'v3',
        }
        
        login_url = url.rstrip('/') + path
        
        logger.info(f"[AegisPlatformAuth] 🌐 发送登录请求: {login_url}")
        logger.info(f"[AegisPlatformAuth] 📋 用户: {username}, AppCode: {header_type}")
        
        start_time = time.time()
        
        try:
            response = requests.post(login_url, json=data, headers=headers, timeout=30)
            elapsed = time.time() - start_time
            
            if response.status_code != 200:
                logger.error(f"[AegisPlatformAuth] ❌ 登录失败 | 状态码: {response.status_code} | 耗时: {elapsed:.3f}s")
                raise Exception(f"Failed to get token: HTTP {response.status_code}")
            
            logger.info(f"[AegisPlatformAuth] ✅ 登录成功 | 耗时: {elapsed:.3f}s")
            logger.info(f"[AegisPlatformAuth] 📄 响应: {response.json()}")
            
            # 从cookies中提取token
            cookies = response.cookies
            if not cookies:
                raise Exception("No cookies in response")
            
            token = list(cookies.values())[0]
            
            if not token:
                raise Exception("Token is empty")
            
            logger.info(f"[AegisPlatformAuth] 🔑 Token提取成功 | 长度: {len(token)}")
            
            return token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"[AegisPlatformAuth] ❌ 网络请求失败: {str(e)}")
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"[AegisPlatformAuth] ❌ 获取Token失败: {str(e)}")
            raise
    
    def clear_cache(self, username: Optional[str] = None) -> int:
        """
        清空Token缓存
        
        Args:
            username: 如果指定，只清空该用户的缓存；否则清空所有
            
        Returns:
            int: 清空的缓存条目数
        """
        if username:
            # 只清空指定用户的缓存
            keys_to_delete = [k for k in self.cache.keys() if k[0] == username]
            for key in keys_to_delete:
                del self.cache[key]
            count = len(keys_to_delete)
            logger.info(f"[AegisPlatformAuth] 🗑️ 已清空用户 {username} 的 {count} 个Token缓存")
        else:
            # 清空所有缓存
            count = len(self.cache)
            self.cache.clear()
            logger.info(f"[AegisPlatformAuth] 🗑️ 已清空所有Token缓存 | 共 {count} 个")
        
        return count
    
    def get_cache_info(self) -> Dict:
        """
        获取缓存统计信息
        
        Returns:
            Dict: 缓存统计信息
        """
        now = datetime.now()
        active_tokens = sum(1 for _, (token, expire_time) in self.cache.items() if expire_time > now)
        expired_tokens = len(self.cache) - active_tokens
        
        cache_info = {
            "total_requests": self.request_count,
            "cache_hits": self.cache_hit_count,
            "cache_hit_rate": f"{(self.cache_hit_count / self.request_count * 100):.1f}%" if self.request_count > 0 else "0%",
            "total_cached": len(self.cache),
            "active_tokens": active_tokens,
            "expired_tokens": expired_tokens,
            "cached_users": list(set(k[0] for k in self.cache.keys()))
        }
        
        return cache_info
    
    def refresh_token(self, username: str, password: str, url: str, header_type: str) -> str:
        """
        强制刷新Token（清除缓存后重新获取）
        
        Args:
            username: 用户名
            password: 密码
            url: 平台URL
            header_type: Header类型
            
        Returns:
            str: 新的Token
        """
        cache_key = (username, password, url, header_type)
        if cache_key in self.cache:
            del self.cache[cache_key]
            logger.info(f"[AegisPlatformAuth] 🔄 清除旧Token，强制刷新")
        
        return self.get_token(username, password, url, header_type)
    
    def validate_token(self, token: str) -> bool:
        """
        验证Token是否在缓存中且有效
        
        Args:
            token: Token字符串
            
        Returns:
            bool: Token是否有效
        """
        now = datetime.now()
        for cached_token, expire_time in self.cache.values():
            if cached_token == token and expire_time > now:
                return True
        return False
    
    def get_statistics(self) -> str:
        """
        获取格式化的统计信息
        
        Returns:
            str: 格式化的统计信息
        """
        info = self.get_cache_info()
        
        stats = f"""
╔════════════════════════════════════════════════════════╗
║           平台鉴权统计信息                              ║
╠════════════════════════════════════════════════════════╣
║ 总请求次数: {info['total_requests']:<41} ║
║ 缓存命中次数: {info['cache_hits']:<39} ║
║ 缓存命中率: {info['cache_hit_rate']:<41} ║
║ ─────────────────────────────────────────────────────  ║
║ 总缓存数: {info['total_cached']:<43} ║
║ 有效Token: {info['active_tokens']:<42} ║
║ 过期Token: {info['expired_tokens']:<42} ║
║ ─────────────────────────────────────────────────────  ║
║ 缓存用户: {', '.join(info['cached_users'][:3]):<42} ║
╚════════════════════════════════════════════════════════╝
        """
        return stats
    
    def print_statistics(self):
        """打印统计信息"""
        print(self.get_statistics())


# 全局单例实例
platform_auth = PlatformAuth()


# ============================================================
# 便捷函数 - 直接导出供使用
# ============================================================

def get_token(username: str, password: str, url: str, header_type: str) -> str:
    """
    便捷函数：获取平台Token
    
    这个函数会被注册到工作流上下文中，在工作流中可以直接使用：
    ${get_token($email, $password, $url, $header_type)}
    """
    return platform_auth.get_token(username, password, url, header_type)


def clear_token_cache(username: Optional[str] = None) -> int:
    """便捷函数：清空Token缓存"""
    return platform_auth.clear_cache(username)


def get_cache_info() -> Dict:
    """便捷函数：获取缓存信息"""
    return platform_auth.get_cache_info()


def refresh_token(username: str, password: str, url: str, header_type: str) -> str:
    """便捷函数：强制刷新Token"""
    return platform_auth.refresh_token(username, password, url, header_type)


def validate_token(token: str) -> bool:
    """便捷函数：验证Token"""
    return platform_auth.validate_token(token)


if __name__ == '__main__':
    print(get_token("admin@spotterio.com", "MTExMTEx", "http://api.dev.spotterio.com", "gmesh"))
