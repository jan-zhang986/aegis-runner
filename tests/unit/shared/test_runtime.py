# -*- coding: utf-8 -*-
from unittest.mock import patch

import pytest

from packages.shared.settings import runtime


def test_get_primary_db_url_raises_when_config_missing():
    with patch.object(runtime, "load_application_config", return_value={}):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(runtime.RuntimeConfigError, match="database.datasource.host"):
                runtime.get_primary_db_url()


def test_get_primary_db_url_uses_environment_override():
    env = {
        "DB_HOST": "db.example.com",
        "DB_PORT": "3307",
        "DB_USER": "tester",
        "DB_PASSWORD": "secret",
        "DB_NAME": "aegis_runner_test",
    }
    with patch.dict("os.environ", env, clear=True):
        url = runtime.get_primary_db_url()

    assert url == "mysql+asyncmy://tester:secret@db.example.com:3307/aegis_runner_test?charset=utf8mb4"


def test_get_kafka_bootstrap_servers_raises_when_missing():
    with patch.object(runtime, "load_application_config", return_value={}):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(runtime.RuntimeConfigError, match="KAFKA_BOOTSTRAP_SERVERS"):
                runtime.get_kafka_bootstrap_servers()


def test_get_redis_settings_raises_when_missing():
    with patch.object(runtime, "load_application_config", return_value={}):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(runtime.RuntimeConfigError, match="REDIS_HOST or redis.host"):
                runtime.get_redis_settings()


def test_get_redis_settings_supports_yaml_values():
    config = {"redis": {"host": "redis.example.com", "port": 6380, "db": 2}}
    with patch.object(runtime, "load_application_config", return_value=config):
        with patch.dict("os.environ", {}, clear=True):
            settings = runtime.get_redis_settings()

    assert settings == {"host": "redis.example.com", "port": 6380, "db": 2, "password": None}
