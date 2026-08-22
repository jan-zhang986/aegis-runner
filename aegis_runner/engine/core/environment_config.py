# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName
@className EnvironmentConfig
@describe 环境配置管理 - 支持多环境动态切换
"""

import json
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from aegis_runner.engine.core.simple_logger import logger


class Environment(Enum):
    """环境枚举"""
    DEV = "dev"
    TEST = "test"
    UAT = "uat"
    STAGING = "staging"
    PROD = "prod"


@dataclass
class EnvironmentProfile:
    """环境配置文件"""
    env_name: str
    display_name: str
    description: str = ""
    
    # API配置
    api_base_urls: Dict[str, str] = field(default_factory=dict)
    api_credentials: Dict[str, str] = field(default_factory=dict)
    
    # 数据库配置
    database_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # 自定义配置
    custom_configs: Dict[str, Any] = field(default_factory=dict)
    
    # 环境变量
    environment_variables: Dict[str, str] = field(default_factory=dict)
    
    # 标签和元数据
    tags: List[str] = field(default_factory=list)
    enabled: bool = True


class EnvironmentConfigManager:
    """
    环境配置管理器
    
    功能：
    1. 管理多个环境配置（dev/test/uat/prod）
    2. 支持环境分组
    3. 动态环境切换
    4. 配置继承和覆盖
    """
    
    def __init__(self):
        self._environments: Dict[str, EnvironmentProfile] = {}
        self._current_env: Optional[str] = None
        self._groups: Dict[str, List[str]] = {}
        
        logger.info("[EnvironmentConfig] 环境配置管理器已初始化")
    
    def add_environment(
        self,
        env_name: str,
        display_name: str,
        description: str = "",
        api_base_urls: Dict[str, str] = None,
        api_credentials: Dict[str, str] = None,
        database_configs: Dict[str, Dict[str, Any]] = None,
        custom_configs: Dict[str, Any] = None,
        environment_variables: Dict[str, str] = None,
        tags: List[str] = None
    ) -> EnvironmentProfile:
        """
        添加环境配置
        
        Args:
            env_name: 环境名称（唯一标识）
            display_name: 显示名称
            description: 描述
            api_base_urls: API基础URL配置 {"service_name": "url"}
            api_credentials: API凭证映射 {"service_name": "credential_id"}
            database_configs: 数据库配置 {"db_name": {config}}
            custom_configs: 自定义配置
            environment_variables: 环境变量
            tags: 标签
            
        Returns:
            EnvironmentProfile: 环境配置对象
        """
        env_profile = EnvironmentProfile(
            env_name=env_name,
            display_name=display_name,
            description=description,
            api_base_urls=api_base_urls or {},
            api_credentials=api_credentials or {},
            database_configs=database_configs or {},
            custom_configs=custom_configs or {},
            environment_variables=environment_variables or {},
            tags=tags or []
        )
        
        self._environments[env_name] = env_profile
        
        logger.info(f"[EnvironmentConfig] ✅ 环境已添加: {env_name} ({display_name})")
        
        return env_profile
    
    def get_environment(self, env_name: str) -> Optional[EnvironmentProfile]:
        """获取环境配置"""
        return self._environments.get(env_name)
    
    def set_current_environment(self, env_name: str):
        """
        设置当前环境
        
        Args:
            env_name: 环境名称
        """
        if env_name not in self._environments:
            raise ValueError(f"环境不存在: {env_name}")
        
        self._current_env = env_name
        logger.info(f"[EnvironmentConfig] 🌍 当前环境已切换到: {env_name}")
    
    def get_current_environment(self) -> Optional[EnvironmentProfile]:
        """获取当前环境配置"""
        if not self._current_env:
            return None
        return self._environments.get(self._current_env)
    
    def add_group(self, group_name: str, env_names: List[str]):
        """
        添加环境分组
        
        Args:
            group_name: 分组名称
            env_names: 环境名称列表
        """
        self._groups[group_name] = env_names
        logger.info(f"[EnvironmentConfig] 📁 分组已添加: {group_name} (包含{len(env_names)}个环境)")
    
    def get_group(self, group_name: str) -> List[str]:
        """获取分组中的环境列表"""
        return self._groups.get(group_name, [])
    
    def get_api_config(self, service_name: str, env_name: str = None) -> Dict[str, Any]:
        """
        获取API配置
        
        Args:
            service_name: 服务名称
            env_name: 环境名称（如果不指定，使用当前环境）
            
        Returns:
            Dict: API配置 {"base_url": "...", "credential_id": "..."}
        """
        env_name = env_name or self._current_env
        if not env_name:
            raise ValueError("未设置当前环境")
        
        env_profile = self._environments.get(env_name)
        if not env_profile:
            raise ValueError(f"环境不存在: {env_name}")
        
        base_url = env_profile.api_base_urls.get(service_name, "")
        credential_id = env_profile.api_credentials.get(service_name, "")
        
        return {
            "base_url": base_url,
            "credential_id": credential_id,
            "env_name": env_name
        }
    
    def get_database_config(self, db_name: str, env_name: str = None) -> Dict[str, Any]:
        """
        获取数据库配置
        
        Args:
            db_name: 数据库名称
            env_name: 环境名称（如果不指定，使用当前环境）
            
        Returns:
            Dict: 数据库配置
        """
        env_name = env_name or self._current_env
        if not env_name:
            raise ValueError("未设置当前环境")
        
        env_profile = self._environments.get(env_name)
        if not env_profile:
            raise ValueError(f"环境不存在: {env_name}")
        
        return env_profile.database_configs.get(db_name, {})
    
    def get_environment_variables(self, env_name: str = None) -> Dict[str, str]:
        """
        获取环境变量
        
        Args:
            env_name: 环境名称（如果不指定，使用当前环境）
            
        Returns:
            Dict: 环境变量
        """
        env_name = env_name or self._current_env
        if not env_name:
            return {}
        
        env_profile = self._environments.get(env_name)
        if not env_profile:
            return {}
        
        return env_profile.environment_variables
    
    def load_from_file(self, file_path: str):
        """
        从配置文件加载环境配置
        
        Args:
            file_path: 配置文件路径
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        environments = config_data.get("environments", [])
        for env_data in environments:
            env_name = env_data.pop("env_name")
            self.add_environment(env_name, **env_data)
        
        # 加载分组
        groups = config_data.get("groups", {})
        for group_name, env_names in groups.items():
            self.add_group(group_name, env_names)
        
        # 设置默认环境
        default_env = config_data.get("default_environment")
        if default_env:
            self.set_current_environment(default_env)
        
        logger.info(f"[EnvironmentConfig] ✅ 已从文件加载{len(environments)}个环境配置")
    
    def save_to_file(self, file_path: str):
        """
        保存环境配置到文件
        
        Args:
            file_path: 配置文件路径
        """
        config_data = {
            "default_environment": self._current_env,
            "environments": [],
            "groups": self._groups
        }
        
        for env_name, env_profile in self._environments.items():
            env_dict = {
                "env_name": env_name,
                "display_name": env_profile.display_name,
                "description": env_profile.description,
                "api_base_urls": env_profile.api_base_urls,
                "api_credentials": env_profile.api_credentials,
                "database_configs": env_profile.database_configs,
                "custom_configs": env_profile.custom_configs,
                "environment_variables": env_profile.environment_variables,
                "tags": env_profile.tags,
                "enabled": env_profile.enabled
            }
            config_data["environments"].append(env_dict)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[EnvironmentConfig] ✅ 环境配置已保存到: {file_path}")
    
    def print_summary(self):
        """打印环境配置摘要"""
        print("\n" + "="*60)
        print("环境配置摘要")
        print("="*60)
        print(f"总环境数: {len(self._environments)}")
        print(f"当前环境: {self._current_env or '未设置'}")
        print(f"环境分组: {len(self._groups)}")
        
        print("\n环境列表:")
        for env_name, env_profile in self._environments.items():
            current_mark = "→" if env_name == self._current_env else " "
            status = "✅" if env_profile.enabled else "❌"
            print(f"  {current_mark} {status} {env_name}: {env_profile.display_name}")
            print(f"      API服务: {len(env_profile.api_base_urls)}个")
            print(f"      数据库: {len(env_profile.database_configs)}个")
            print(f"      凭证映射: {len(env_profile.api_credentials)}个")
        
        if self._groups:
            print("\n环境分组:")
            for group_name, env_names in self._groups.items():
                print(f"  📁 {group_name}: {', '.join(env_names)}")
        
        print("="*60)


# 全局环境配置管理器实例
env_config_manager = EnvironmentConfigManager()


# ============================================================
# 便捷函数
# ============================================================

def init_standard_environments():
    """初始化标准环境配置（dev/test/uat/prod）"""
    
    # 开发环境
    env_config_manager.add_environment(
        env_name="dev",
        display_name="开发环境",
        description="本地开发环境",
        api_base_urls={
            "user_service": "http://localhost:8001",
            "order_service": "http://localhost:8002",
            "payment_service": "http://localhost:8003"
        },
        api_credentials={
            "user_service": "user_service_dev",
            "order_service": "order_service_dev",
            "payment_service": "payment_service_dev"
        },
        database_configs={
            "main_db": {
                "host": "localhost",
                "port": 3306,
                "database": "myapp_dev",
                "user": "dev_user",
                "password": "dev_password"
            }
        },
        environment_variables={
            "LOG_LEVEL": "DEBUG",
            "ENABLE_DEBUG": "true"
        },
        tags=["development", "local"]
    )
    
    # 测试环境
    env_config_manager.add_environment(
        env_name="test",
        display_name="测试环境",
        description="集成测试环境",
        api_base_urls={
            "user_service": "https://test-user-api.example.com",
            "order_service": "https://test-order-api.example.com",
            "payment_service": "https://test-payment-api.example.com"
        },
        api_credentials={
            "user_service": "user_service_test",
            "order_service": "order_service_test",
            "payment_service": "payment_service_test"
        },
        database_configs={
            "main_db": {
                "host": "test-db.example.com",
                "port": 3306,
                "database": "myapp_test",
                "user": "test_user",
                "password": "${TEST_DB_PASSWORD}"
            }
        },
        environment_variables={
            "LOG_LEVEL": "INFO",
            "ENABLE_DEBUG": "false"
        },
        tags=["testing", "integration"]
    )
    
    # UAT环境
    env_config_manager.add_environment(
        env_name="uat",
        display_name="UAT环境",
        description="用户验收测试环境",
        api_base_urls={
            "user_service": "https://uat-user-api.example.com",
            "order_service": "https://uat-order-api.example.com",
            "payment_service": "https://uat-payment-api.example.com"
        },
        api_credentials={
            "user_service": "user_service_uat",
            "order_service": "order_service_uat",
            "payment_service": "payment_service_uat"
        },
        database_configs={
            "main_db": {
                "host": "uat-db.example.com",
                "port": 3306,
                "database": "myapp_uat",
                "user": "uat_user",
                "password": "${UAT_DB_PASSWORD}"
            }
        },
        environment_variables={
            "LOG_LEVEL": "INFO",
            "ENABLE_DEBUG": "false"
        },
        tags=["uat", "pre-production"]
    )
    
    # 生产环境
    env_config_manager.add_environment(
        env_name="prod",
        display_name="生产环境",
        description="正式生产环境",
        api_base_urls={
            "user_service": "https://user-api.example.com",
            "order_service": "https://order-api.example.com",
            "payment_service": "https://payment-api.example.com"
        },
        api_credentials={
            "user_service": "user_service_prod",
            "order_service": "order_service_prod",
            "payment_service": "payment_service_prod"
        },
        database_configs={
            "main_db": {
                "host": "prod-db-master.example.com",
                "port": 3306,
                "database": "myapp_prod",
                "user": "prod_user",
                "password": "${PROD_DB_PASSWORD}"
            }
        },
        environment_variables={
            "LOG_LEVEL": "WARN",
            "ENABLE_DEBUG": "false"
        },
        tags=["production", "critical"]
    )
    
    # 添加环境分组
    env_config_manager.add_group("non_prod", ["dev", "test", "uat"])
    env_config_manager.add_group("production", ["prod"])
    env_config_manager.add_group("all", ["dev", "test", "uat", "prod"])
    
    logger.info("[EnvironmentConfig] ✅ 标准环境配置已初始化")
    
    return env_config_manager


def apply_environment_to_context(context, env_name: str = None):
    """
    将环境配置应用到执行上下文
    
    Args:
        context: ExecutionContext对象
        env_name: 环境名称（如果不指定，使用当前环境）
    """
    env_name = env_name or env_config_manager._current_env
    if not env_name:
        logger.warning("[EnvironmentConfig] ⚠️ 未指定环境，跳过环境配置应用")
        return
    
    env_profile = env_config_manager.get_environment(env_name)
    if not env_profile:
        logger.error(f"[EnvironmentConfig] ❌ 环境不存在: {env_name}")
        return
    
    # 应用环境变量到上下文
    for key, value in env_profile.environment_variables.items():
        context.set_variable(key, value)
    
    # 应用API base URLs
    for service, url in env_profile.api_base_urls.items():
        context.set_variable(f"{service}_base_url", url)
    
    # 应用API凭证映射
    for service, credential_id in env_profile.api_credentials.items():
        context.set_variable(f"{service}_credential_id", credential_id)
    
    # 应用自定义配置
    for key, value in env_profile.custom_configs.items():
        context.set_variable(key, value)
    
    # 设置当前环境名
    context.set_variable("CURRENT_ENVIRONMENT", env_name)
    context.set_variable("ENVIRONMENT_NAME", env_profile.display_name)
    
    logger.info(f"[EnvironmentConfig] ✅ 环境配置已应用到上下文: {env_name}")


# ============================================================
# 环境感知的工作流执行器
# ============================================================

class EnvironmentAwareWorkflowExecutor:
    """环境感知的工作流执行器"""
    
    def __init__(self, workflow_data, env_name: str = None):
        """
        初始化环境感知的工作流执行器
        
        Args:
            workflow_data: 工作流数据
            env_name: 环境名称
        """
        from aegis_runner.engine.workflow_engine import WorkflowExecutor
        
        self.workflow_data = workflow_data
        self.env_name = env_name
        self.executor = WorkflowExecutor(workflow_data)
        
        # 应用环境配置到上下文
        if env_name:
            apply_environment_to_context(self.executor.context, env_name)
            logger.info(f"[EnvironmentAwareExecutor] 🌍 工作流将在 {env_name} 环境中执行")
    
    def execute(self):
        """执行工作流"""
        logger.info(f"[EnvironmentAwareExecutor] 🚀 开始执行工作流（环境: {self.env_name or '默认'}）")
        result = self.executor.execute()
        logger.info(f"[EnvironmentAwareExecutor] ✅ 工作流执行完成")
        return result


def execute_in_environment(workflow_data, env_name: str):
    """
    在指定环境中执行工作流
    
    Args:
        workflow_data: 工作流数据
        env_name: 环境名称
        
    Returns:
        执行结果
    """
    executor = EnvironmentAwareWorkflowExecutor(workflow_data, env_name)
    return executor.execute()


def execute_in_multiple_environments(workflow_data, env_names: List[str]):
    """
    在多个环境中执行工作流
    
    Args:
        workflow_data: 工作流数据
        env_names: 环境名称列表
        
    Returns:
        Dict: 各环境的执行结果
    """
    results = {}
    
    for env_name in env_names:
        logger.info(f"\n{'='*60}")
        logger.info(f"在环境 {env_name} 中执行工作流")
        logger.info(f"{'='*60}")
        
        try:
            result = execute_in_environment(workflow_data, env_name)
            results[env_name] = {
                "success": True,
                "result": result
            }
        except Exception as e:
            results[env_name] = {
                "success": False,
                "error": str(e)
            }
            logger.error(f"[EnvironmentAwareExecutor] ❌ 环境 {env_name} 执行失败: {str(e)}")
    
    return results
