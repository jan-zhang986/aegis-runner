# -*- coding: utf-8 -*-
"""
@author Database Optimization Team
@date 2025-10-10
@packageName master.app.core
@className database_async
@describe 异步数据库连接模块（主从读写分离）
"""
import asyncio
from typing import AsyncGenerator
from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine
)
from sqlalchemy.orm import declarative_base

from src.core.logging import LOGGER
from src.core.config import get_db_pool_settings, get_primary_db_url, get_replica_db_url

# 统一索引/约束命名规范
NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)
AsyncBase = declarative_base(metadata=metadata)
db_pool_settings = get_db_pool_settings()

# 主库引擎（写）
primary_engine: AsyncEngine = create_async_engine(
    get_primary_db_url(),
    **db_pool_settings,
)

# 从库引擎（读）
replica_engine: AsyncEngine = create_async_engine(
    get_replica_db_url(),
    **db_pool_settings,
)

# 会话工厂
AsyncSessionWrite = async_sessionmaker(
    primary_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)

AsyncSessionRead = async_sessionmaker(
    replica_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)


# 依赖注入：写会话（用于 POST/PUT/DELETE）
async def get_db_write() -> AsyncGenerator[AsyncSession, None]:
    """
    获取写会话（主库）
    用于 POST/PUT/DELETE 等写操作
    自动处理事务提交和回滚
    注意：Service层需要显式调用 commit() 来提交事务
    """
    async with AsyncSessionWrite() as session:
        try:
            yield session
            # 不在这里自动commit，由Service层控制
        except Exception as e:
            await session.rollback()
            LOGGER.logger.error(f"Database write error: {e}")
            raise


# 依赖注入：读会话（用于 GET）
async def get_db_read() -> AsyncGenerator[AsyncSession, None]:
    """
    获取读会话（从库）
    用于 GET 等读操作
    从库失败时自动切换到主库
    """
    session = None
    try:
        # 先尝试从库连接
        session = AsyncSessionRead()
        db = await session.__aenter__()
        yield db
    except Exception as e:
        LOGGER.logger.warning(f"Replica database error, falling back to primary: {e}")
        # 如果从库失败，尝试主库
        if session:
            try:
                await session.__aexit__(None, None, None)
            except Exception as close_err:
                LOGGER.logger.debug(
                    "Replica session cleanup after fallback (ignored): %s", close_err
                )
        
        session = AsyncSessionWrite()
        db = await session.__aenter__()
        yield db
    finally:
        if session:
            try:
                await session.__aexit__(None, None, None)
            except Exception as e:
                LOGGER.logger.error(f"Error closing session: {e}")


# 强制读主（用于"读你所写"场景）
async def get_db_read_from_primary() -> AsyncGenerator[AsyncSession, None]:
    """
    强制读主库（避免复制延迟）
    用于需要强一致性的读操作，如：
    - 写操作后立即读取
    - 关键业务数据查询
    - 请求头包含 X-Read-From: primary
    """
    async with AsyncSessionWrite() as session:
        yield session


# 根据请求头选择数据库（一致性保证）
async def get_db_by_request(request) -> AsyncGenerator[AsyncSession, None]:
    """
    根据请求头决定使用主库还是从库
    支持 X-Read-From: primary 头部强制读主库
    
    需求: 6.4 - 支持通过请求头控制读取源
    
    Args:
        request: FastAPI Request 对象
        
    Yields:
        AsyncSession: 数据库会话
        
    Example:
        @app.get("/api/resource")
        async def get_resource(
            request: Request,
            db: AsyncSession = Depends(lambda r: get_db_by_request(r))
        ):
            ...
    """
    read_from = request.headers.get("X-Read-From", "").lower()
    
    if read_from == "primary":
        LOGGER.logger.info("请求头指定读取主库")
        async for db in get_db_read_from_primary():
            yield db
    else:
        async for db in get_db_read():
            yield db


# 健康检查
async def check_db_health() -> dict[str, str]:
    """
    检查主从数据库健康状态
    返回格式: {"primary": "ok", "replica": "ok", "pool_status": {...}}
    
    需求: 6.1, 6.2, 6.3
    - 6.1: 返回主从数据库的连接状态
    - 6.2: 提供连接池状态监控数据
    - 6.3: 记录详细的错误日志
    """
    health = {}
    
    # 检查主库
    try:
        LOGGER.logger.info("开始检查主库健康状态...")
        async with AsyncSessionWrite() as session:
            result = await session.execute(text("SELECT 1 as health_check"))
            result.scalar()
        health["primary"] = "ok"
        LOGGER.logger.info("主库健康检查通过")
    except Exception as e:
        health["primary"] = f"error: {str(e)[:100]}"
        LOGGER.logger.error(f"主库健康检查失败: {e}", exc_info=True)
    
    # 检查从库
    try:
        LOGGER.logger.info("开始检查从库健康状态...")
        async with AsyncSessionRead() as session:
            result = await session.execute(text("SELECT 1 as health_check"))
            result.scalar()
        health["replica"] = "ok"
        LOGGER.logger.info("从库健康检查通过")
    except Exception as e:
        health["replica"] = f"error: {str(e)[:100]}"
        LOGGER.logger.error(f"从库健康检查失败: {e}", exc_info=True)
    
    # 添加连接池状态
    try:
        pool_status = get_pool_status()
        health["pool_status"] = pool_status
        LOGGER.logger.info(f"连接池状态: {pool_status}")
    except Exception as e:
        health["pool_status"] = {"error": str(e)}
        LOGGER.logger.error(f"获取连接池状态失败: {e}")
    
    return health


# 获取连接池状态
def get_pool_status() -> dict:
    """
    获取连接池状态信息
    用于监控和调试
    
    需求: 6.2 - 提供连接池监控数据
    """
    try:
        primary_pool = primary_engine.pool
        replica_pool = replica_engine.pool
        
        status = {
            "primary": {
                "size": primary_pool.size(),
                "checked_out": primary_pool.checkedout(),
                "overflow": primary_pool.overflow(),
                "checked_in": primary_pool.checkedin(),
                "utilization": round(primary_pool.checkedout() / primary_pool.size() * 100, 2) if primary_pool.size() > 0 else 0
            },
            "replica": {
                "size": replica_pool.size(),
                "checked_out": replica_pool.checkedout(),
                "overflow": replica_pool.overflow(),
                "checked_in": replica_pool.checkedin(),
                "utilization": round(replica_pool.checkedout() / replica_pool.size() * 100, 2) if replica_pool.size() > 0 else 0
            }
        }
        
        # 记录连接池状态日志
        LOGGER.logger.debug(f"连接池状态 - 主库利用率: {status['primary']['utilization']}%, 从库利用率: {status['replica']['utilization']}%")
        
        return status
    except Exception as e:
        LOGGER.logger.error(f"Failed to get pool status: {e}")
        return {"error": str(e)}


# 数据库操作日志记录
def log_database_operation(operation: str, db_type: str, duration: float = None, success: bool = True, error: str = None):
    """
    记录数据库操作日志
    
    需求: 6.3 - 在日志中记录详细的错误信息
    
    Args:
        operation: 操作类型 (read/write/health_check)
        db_type: 数据库类型 (primary/replica)
        duration: 操作耗时（秒）
        success: 操作是否成功
        error: 错误信息（如果有）
    """
    log_data = {
        "operation": operation,
        "db_type": db_type,
        "success": success
    }
    
    if duration is not None:
        log_data["duration_ms"] = round(duration * 1000, 2)
    
    if error:
        log_data["error"] = error
        LOGGER.logger.error(f"数据库操作失败: {log_data}")
    else:
        LOGGER.logger.info(f"数据库操作: {log_data}")


# 关闭引擎（应用关闭时调用）
async def close_engines():
    """
    关闭数据库引擎
    应在应用关闭时调用
    """
    try:
        LOGGER.logger.info("开始关闭数据库引擎...")
        await primary_engine.dispose()
        await replica_engine.dispose()
        LOGGER.logger.info("数据库引擎已成功关闭")
    except Exception as e:
        LOGGER.logger.error(f"关闭数据库引擎时出错: {e}", exc_info=True)


if __name__ == '__main__':
    # 测试异步数据库连接
    async def test_connection():
        print("=" * 60)
        print("测试异步数据库连接和一致性保证机制")
        print("=" * 60)
        
        # 测试主库连接
        print("\n1. 测试主库连接（写）...")
        async for db in get_db_write():
            result = await db.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            print(f"   ✓ 主库连接成功: {row}")
        
        # 测试从库连接
        print("\n2. 测试从库连接（读）...")
        async for db in get_db_read():
            result = await db.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            print(f"   ✓ 从库连接成功: {row}")
        
        # 测试强制读主库
        print("\n3. 测试强制读主库...")
        async for db in get_db_read_from_primary():
            result = await db.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            print(f"   ✓ 强制读主库成功: {row}")
        
        # 测试健康检查
        print("\n4. 测试健康检查...")
        health = await check_db_health()
        print(f"   健康状态: {health}")
        
        # 测试连接池状态
        print("\n5. 测试连接池状态...")
        pool_status = get_pool_status()
        print(f"   连接池状态: {pool_status}")
        
        # 测试主从复制延迟检测
        print("\n6. 测试主从复制延迟检测...")
        try:
            lag = await check_replication_lag()
            if lag >= 0:
                print(f"   ✓ 复制延迟: {lag:.3f} 秒")
            else:
                print(f"   ⚠ 无法检测复制延迟（可能需要先创建 replication_check 表）")
        except Exception as e:
            print(f"   ⚠ 延迟检测失败: {e}")
        
        print("\n" + "=" * 60)
        print("✓ 所有测试完成！")
        print("=" * 60)
        print("\n提示：")
        print("- 如需测试复制延迟检测，请先运行对应的新目录下初始化脚本")
        print("- 使用 get_db_by_request() 支持请求头控制读取源")
        print("- 使用 get_db_read_with_lag_check() 自动处理延迟过高的情况")
        print()
    
    # 运行测试
    asyncio.run(test_connection())
