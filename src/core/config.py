from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml

from src.core.exceptions import ConfigError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOG_DIR = PROJECT_ROOT / "logs"
CONFIG_DIR = PROJECT_ROOT / "configs"
APPLICATION_CONFIG_PATH = CONFIG_DIR / "application.yml"
APPLICATION_LOCAL_CONFIG_PATH = CONFIG_DIR / "application_local.yml"


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_yaml_file(path: Path, *, required: bool) -> Dict[str, Any]:
    if not path.exists():
        if required:
            raise ConfigError(f"配置文件不存在: {path}")
        return {}

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"配置文件解析失败: {path}") from exc
    except OSError as exc:
        raise ConfigError(f"配置文件读取失败: {path}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"配置文件内容必须是对象结构: {path}")
    return data


def _require_setting(value: Any, setting_name: str) -> Any:
    if value is None or value == "":
        raise ConfigError(f"缺少运行配置: {setting_name}")
    return value


@lru_cache(maxsize=1)
def load_application_config() -> Dict[str, Any]:
    base = _load_yaml_file(APPLICATION_CONFIG_PATH, required=False)
    local = _load_yaml_file(APPLICATION_LOCAL_CONFIG_PATH, required=False)
    return _deep_merge(base, local)


def get_callback_workflow_config() -> Dict[str, Any]:
    return load_application_config().get("callback", {}).get("workflow", {})


def get_database_config() -> Dict[str, Any]:
    return load_application_config().get("database", {}).get("datasource", {})


def get_primary_db_url() -> str:
    override = os.getenv("DB_PRIMARY_URL")
    if override:
        return override

    host_override = os.getenv("DB_HOST")
    if host_override:
        host = host_override
        port = int(os.getenv("DB_PORT", "3306"))
        username = os.getenv("DB_USER") or os.getenv("DB_USERNAME") or "root"
        password = os.getenv("DB_PASSWORD", "")
        db_name = os.getenv("DB_NAME", "aegis_runner")
        return f"mysql+asyncmy://{username}:{password}@{host}:{port}/{db_name}?charset=utf8mb4"

    db_info = get_database_config()
    host = db_info.get("host") or "127.0.0.1"
    port = int(db_info.get("port") or 3306)
    username = db_info.get("username") or "root"
    password = db_info.get("password") or ""
    db_name = db_info.get("name") or "aegis_runner"
    return f"mysql+asyncmy://{username}:{password}@{host}:{port}/{db_name}?charset=utf8mb4"


def get_replica_db_url() -> str:
    return os.getenv("DB_REPLICA_URL", get_primary_db_url())


def get_sync_db_url() -> str:
    return os.getenv("DB_SYNC_URL", get_primary_db_url().replace("mysql+asyncmy://", "mysql+pymysql://", 1))


def get_db_pool_settings() -> Dict[str, Any]:
    return {
        "pool_size": int(os.getenv("DB_POOL_SIZE", "20")),
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "7200")),
        "pool_pre_ping": os.getenv("DB_POOL_PRE_PING", "true").lower() in {"1", "true", "yes", "on"},
        "echo": os.getenv("DB_ECHO", "false").lower() in {"1", "true", "yes", "on"},
    }


def get_kafka_bootstrap_servers() -> str:
    env_value = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
    if env_value:
        return env_value

    config = load_application_config()
    kafka_config = config.get("kafka", {}) if isinstance(config, dict) else {}
    value = kafka_config.get("bootstrap_servers") or kafka_config.get("bootstrap-servers")
    return value or "127.0.0.1:9092"


def get_redis_settings() -> Dict[str, Any]:
    config = load_application_config()
    redis_config = config.get("redis", {}) if isinstance(config, dict) else {}
    return {
        "host": os.getenv("REDIS_HOST") or redis_config.get("host") or "127.0.0.1",
        "port": int(os.getenv("REDIS_PORT") or redis_config.get("port") or 6379),
        "db": int(os.getenv("REDIS_DB") or redis_config.get("db") or 0),
        "password": os.getenv("REDIS_PASSWORD") or redis_config.get("password") or None,
    }
