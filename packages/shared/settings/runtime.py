# -*- coding: utf-8 -*-
"""
Compatibility wrapper for aegis_runner.core.config
"""
from aegis_runner.core.config import (
    PROJECT_ROOT,
    LOG_DIR,
    CONFIG_DIR,
    APPLICATION_CONFIG_PATH,
    APPLICATION_LOCAL_CONFIG_PATH,
    RuntimeConfigError,
    load_application_config,
    get_callback_workflow_config,
    get_database_config,
    get_primary_db_url,
    get_replica_db_url,
    get_sync_db_url,
    get_db_pool_settings,
    get_kafka_bootstrap_servers,
    get_redis_settings,
)
