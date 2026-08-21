# -*- coding: utf-8 -*-
"""
@author Fred.fan
@date 2025-10-10
@packageName master.app.api.request
@className HealthRouter
@describe 健康检查和监控端点
"""
from datetime import datetime
from fastapi import APIRouter, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

from apps.master.infrastructure.db.database_async import check_db_health, get_pool_status
from packages.shared.responses.base_resp import success_response, error_response
from packages.shared.logging.log_component import LOGGER

app = APIRouter()

# Prometheus 指标定义
db_connections_total = Counter(
    'db_connections_total',
    'Total database connections',
    ['type']  # primary/replica
)

db_query_duration = Histogram(
    'db_query_duration_seconds',
    'Database query duration',
    ['type', 'operation']  # type: primary/replica, operation: read/write
)

db_pool_size = Gauge(
    'db_pool_size',
    'Database connection pool size',
    ['type', 'status']  # type: primary/replica, status: size/checked_out/overflow
)

app_health_status = Gauge(
    'app_health_status',
    'Application health status (1=healthy, 0=unhealthy)',
    ['component']  # database/primary/replica
)


@app.get("/healthz", tags=["健康检查"])
@app.get("/health", tags=["健康检查"])  # 添加别名以兼容不同的健康检查路径
async def health_check():
    """
    基础健康检查端点
    
    需求: 6.1 - 返回主从数据库的连接状态
    
    Returns:
        简单的健康状态，用于 Kubernetes liveness probe
    """
    try:
        return {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "aegis-runner"
        }
    except Exception as e:
        LOGGER.logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@app.get("/readyz", tags=["健康检查"])
async def readiness_check():
    """
    就绪检查端点（包含数据库状态验证）
    
    需求: 6.1, 6.2 - 返回主从数据库的连接状态和连接池状态
    
    Returns:
        详细的就绪状态，包括数据库连接和连接池状态
        用于 Kubernetes readiness probe
    """
    try:
        # 检查数据库健康状态
        db_health = await check_db_health()
        
        # 获取连接池状态
        pool_status = get_pool_status()
        
        # 判断是否就绪
        primary_ok = db_health.get("primary") == "ok"
        replica_ok = db_health.get("replica") == "ok"
        all_healthy = primary_ok and replica_ok
        
        # 更新 Prometheus 指标
        app_health_status.labels(component='primary').set(1 if primary_ok else 0)
        app_health_status.labels(component='replica').set(1 if replica_ok else 0)
        app_health_status.labels(component='database').set(1 if all_healthy else 0)
        
        status_code = 200 if all_healthy else 503
        
        return {
            "status": "ready" if all_healthy else "not_ready",
            "timestamp": datetime.utcnow().isoformat(),
            "database": {
                "primary": db_health.get("primary"),
                "replica": db_health.get("replica")
            },
            "pool_status": pool_status,
            "checks": {
                "primary_database": primary_ok,
                "replica_database": replica_ok
            }
        }
    except Exception as e:
        LOGGER.logger.error(f"Readiness check failed: {e}", exc_info=True)
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@app.get("/metrics", tags=["监控"])
async def metrics():
    """
    Prometheus 指标端点
    
    需求: 6.2 - 提供连接池状态监控数据
    
    Returns:
        Prometheus 格式的指标数据
    """
    try:
        # 更新连接池指标
        pool_status = get_pool_status()
        
        if "primary" in pool_status and "error" not in pool_status["primary"]:
            primary = pool_status["primary"]
            db_pool_size.labels(type='primary', status='size').set(primary.get('size', 0))
            db_pool_size.labels(type='primary', status='checked_out').set(primary.get('checked_out', 0))
            db_pool_size.labels(type='primary', status='overflow').set(primary.get('overflow', 0))
            db_pool_size.labels(type='primary', status='checked_in').set(primary.get('checked_in', 0))
        
        if "replica" in pool_status and "error" not in pool_status["replica"]:
            replica = pool_status["replica"]
            db_pool_size.labels(type='replica', status='size').set(replica.get('size', 0))
            db_pool_size.labels(type='replica', status='checked_out').set(replica.get('checked_out', 0))
            db_pool_size.labels(type='replica', status='overflow').set(replica.get('overflow', 0))
            db_pool_size.labels(type='replica', status='checked_in').set(replica.get('checked_in', 0))
        
        # 生成 Prometheus 格式的指标
        metrics_output = generate_latest()
        return Response(content=metrics_output, media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        LOGGER.logger.error(f"Metrics generation failed: {e}", exc_info=True)
        return Response(
            content=f"# Error generating metrics: {str(e)}\n",
            media_type="text/plain"
        )


@app.get("/health/database", tags=["健康检查"])
async def database_health():
    """
    数据库详细健康检查
    
    需求: 6.1, 6.2 - 返回详细的数据库状态信息
    
    Returns:
        详细的数据库健康状态和连接池信息
    """
    try:
        # 检查数据库健康状态
        db_health = await check_db_health()
        
        # 获取连接池状态
        pool_status = get_pool_status()
        
        return success_response({
            "database_health": db_health,
            "pool_status": pool_status,
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        LOGGER.logger.error(f"Database health check failed: {e}", exc_info=True)
        return error_response(500, f"Database health check failed: {str(e)}")


@app.get("/health/pool", tags=["健康检查"])
async def pool_health():
    """
    连接池状态检查
    
    需求: 6.2 - 提供连接池状态监控数据
    
    Returns:
        连接池的详细状态信息
    """
    try:
        pool_status = get_pool_status()
        
        # 计算告警信息
        warnings = []
        if "primary" in pool_status and "error" not in pool_status["primary"]:
            primary_util = pool_status["primary"].get("utilization", 0)
            if primary_util > 80:
                warnings.append(f"主库连接池利用率过高: {primary_util}%")
        
        if "replica" in pool_status and "error" not in pool_status["replica"]:
            replica_util = pool_status["replica"].get("utilization", 0)
            if replica_util > 80:
                warnings.append(f"从库连接池利用率过高: {replica_util}%")
        
        return success_response({
            "pool_status": pool_status,
            "warnings": warnings,
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        LOGGER.logger.error(f"Pool health check failed: {e}", exc_info=True)
        return error_response(500, f"Pool health check failed: {str(e)}")


# 辅助函数：记录数据库操作指标
def record_db_operation(db_type: str, operation: str, duration: float):
    """
    记录数据库操作指标到 Prometheus
    
    Args:
        db_type: 数据库类型 (primary/replica)
        operation: 操作类型 (read/write)
        duration: 操作耗时（秒）
    """
    try:
        db_connections_total.labels(type=db_type).inc()
        db_query_duration.labels(type=db_type, operation=operation).observe(duration)
    except Exception as e:
        LOGGER.logger.debug(f"Failed to record metrics: {e}")
