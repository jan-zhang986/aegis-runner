#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aegis Runner Async Redis Client Infrastructure
"""
import redis.asyncio as aioredis
from src.core.config import RUNTIME_SETTINGS

_redis_client_instance = None


class RedisClient:
    def __init__(self, host: str, port: int, password: str = None, db: int = 0):
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.client = None

    async def connect(self):
        if not self.client:
            self.client = aioredis.Redis(
                host=self.host,
                port=self.port,
                password=self.password or None,
                db=self.db,
                decode_responses=True,
            )

    async def close(self):
        if self.client:
            await self.client.close()
            self.client = None


async def get_redis_client() -> RedisClient:
    global _redis_client_instance
    if not _redis_client_instance:
        cfg = RUNTIME_SETTINGS.get_redis_config()
        _redis_client_instance = RedisClient(
            host=cfg.get("host", "127.0.0.1"),
            port=int(cfg.get("port", 6379)),
            password=cfg.get("password", ""),
            db=int(cfg.get("db", 0)),
        )
        await _redis_client_instance.connect()
    return _redis_client_instance
