# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-09-13
@packageName
@className ConnectionPool
@describe MySQL连接池管理器（优化版）
"""

import threading
import time
from typing import Dict, Optional, Any
from contextlib import contextmanager
import pymysql
from queue import Queue, Empty


class ConnectionWrapper:
    """连接包装器，用于跟踪连接的使用时间和状态"""
    def __init__(self, connection: pymysql.Connection):
        self.connection = connection
        self.created_at = time.time()
        self.last_used_at = time.time()
        self.use_count = 0
    
    def update_usage(self):
        """更新使用时间"""
        self.last_used_at = time.time()
        self.use_count += 1
    
    def is_idle(self, idle_timeout: float) -> bool:
        """检查连接是否空闲超时"""
        return time.time() - self.last_used_at > idle_timeout


class MySQLConnectionPool:
    """MySQL连接池管理器（优化版）"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._pools: Dict[str, Queue] = {}
            self._pool_configs: Dict[str, Dict] = {}
            self._pool_locks: Dict[str, threading.Lock] = {}
            # 连接包装器映射：pool_key -> {connection_id: ConnectionWrapper}
            self._connection_wrappers: Dict[str, Dict[int, ConnectionWrapper]] = {}
            # 清理线程控制
            self._cleanup_thread: Optional[threading.Thread] = None
            self._cleanup_running = False
            self._cleanup_lock = threading.Lock()
            self._initialized = True
            # 启动后台清理线程
            self._start_cleanup_thread()
    
    def create_pool(self, pool_key: str, connection_config: Dict[str, Any], 
                   min_connections: int = 2, max_connections: int = 10,
                   idle_timeout: float = 300.0, health_check_interval: float = 60.0) -> None:
        """
        创建连接池
        
        Args:
            pool_key: 连接池标识
            connection_config: 连接配置
            min_connections: 最小连接数
            max_connections: 最大连接数
            idle_timeout: 空闲连接超时时间（秒），默认300秒（5分钟）
            health_check_interval: 健康检查间隔（秒），默认60秒
        """
        if pool_key in self._pools:
            return
        
        # 创建连接池锁
        self._pool_locks[pool_key] = threading.Lock()
        
        # 存储配置
        self._pool_configs[pool_key] = {
            'config': connection_config,
            'min_connections': min_connections,
            'max_connections': max_connections,
            'current_connections': 0,
            'idle_timeout': idle_timeout,
            'health_check_interval': health_check_interval,
            'last_health_check': time.time(),
            'created_at': time.time(),
            'total_connections_created': 0,
            'total_connections_closed': 0,
            'total_connections_recycled': 0
        }
        
        # 创建连接队列
        self._pools[pool_key] = Queue(maxsize=max_connections)
        
        # 初始化连接包装器映射
        self._connection_wrappers[pool_key] = {}
        
        # 预创建最小连接数
        # 记录创建失败的原因，用于后续诊断
        creation_errors = []
        for i in range(min_connections):
            try:
                # 第一个连接使用 raise_on_error=True 来检测认证等致命错误
                conn = self._create_connection(connection_config, raise_on_error=(i == 0))
                if conn:
                    wrapper = ConnectionWrapper(conn)
                    conn_id = id(conn)
                    self._connection_wrappers[pool_key][conn_id] = wrapper
                    self._pools[pool_key].put(conn)
                    self._pool_configs[pool_key]['current_connections'] += 1
                    self._pool_configs[pool_key]['total_connections_created'] += 1
                else:
                    creation_errors.append(f"连接 {i+1} 创建失败")
            except RuntimeError as e:
                # 认证失败等致命错误，记录但继续（让后续获取连接时再报错）
                self._pool_configs[pool_key]['last_error'] = str(e)
                print(f"[ConnectionPool] 警告：连接池 {pool_key} 预创建连接失败: {e}")
                break
        
        # 如果所有预创建都失败，记录警告
        if self._pool_configs[pool_key]['current_connections'] == 0 and creation_errors:
            self._pool_configs[pool_key]['last_error'] = "; ".join(creation_errors)
            print(f"[ConnectionPool] 警告：连接池 {pool_key} 没有成功创建任何连接")
    
    def _create_connection(self, connection_config: Dict[str, Any], raise_on_error: bool = False) -> Optional[pymysql.Connection]:
        """
        创建数据库连接
        
        Args:
            connection_config: 连接配置
            raise_on_error: 如果为True，连接失败时抛出异常；否则返回None
        """
        try:
            # 处理 port 字段：确保为整数类型（变量替换后可能是字符串）
            port = connection_config.get('port', 3306)
            if port is not None:
                if isinstance(port, str):
                    try:
                        port = int(port)
                    except (ValueError, TypeError):
                        raise ValueError(f"port 字段无法转换为整数: {port}")
                elif isinstance(port, (float, int)):
                    port = int(port)
                else:
                    raise ValueError(f"port 字段类型不正确: {type(port)}, 值: {port}")
            
            conn_params = {
                'host': connection_config.get('host', 'localhost'),
                'port': port,
                'user': connection_config.get('user'),
                'password': connection_config.get('password'),
                'database': connection_config.get('database'),
                'charset': connection_config.get('charset', 'utf8mb4'),
                'autocommit': False,
                'connect_timeout': connection_config.get('connect_timeout', 10),
                'read_timeout': connection_config.get('read_timeout', 30),
                'write_timeout': connection_config.get('write_timeout', 30)
            }
            
            # 移除None值
            conn_params = {k: v for k, v in conn_params.items() if v is not None}
            
            if not conn_params.get('user'):
                raise ValueError("数据库用户名不能为空")
            if not conn_params.get('password'):
                raise ValueError("数据库密码不能为空")
            if not conn_params.get('database'):
                raise ValueError("数据库名不能为空")
            
            return pymysql.connect(**conn_params)
            
        except pymysql.err.OperationalError as e:
            error_code = e.args[0] if e.args else 0
            error_msg = e.args[1] if len(e.args) > 1 else str(e)
            
            # 认证失败错误，应该立即抛出
            if error_code in (1045, 1044, 1698):  # Access denied errors
                print(f"[ConnectionPool] 数据库认证失败: {error_msg}")
                if raise_on_error:
                    raise RuntimeError(f"数据库认证失败: {error_msg}") from e
            # 连接超时或网络问题
            elif error_code in (2003, 2006, 2013):  # Can't connect, server gone, lost connection
                print(f"[ConnectionPool] 数据库连接超时或网络问题: {error_msg}")
                if raise_on_error:
                    raise RuntimeError(f"数据库连接失败: {error_msg}") from e
            else:
                print(f"[ConnectionPool] 创建数据库连接失败 (错误码:{error_code}): {error_msg}")
                if raise_on_error:
                    raise RuntimeError(f"数据库连接失败: {error_msg}") from e
            return None
        except Exception as e:
            print(f"[ConnectionPool] 创建数据库连接失败: {e}")
            if raise_on_error:
                raise RuntimeError(f"数据库连接失败: {str(e)}") from e
            return None
    
    @contextmanager
    def get_connection(self, pool_key: str, timeout: int = 30):
        """
        获取连接池中的连接
        
        Args:
            pool_key: 连接池标识
            timeout: 超时时间（秒）
        """
        if pool_key not in self._pools:
            raise ValueError(f"连接池 {pool_key} 不存在")
        
        connection = None
        wrapper = None
        conn_id = None
        config = self._pool_configs[pool_key]
        
        # 检查是否有之前的致命错误（如认证失败）
        last_error = config.get('last_error')
        
        try:
            # 尝试从池中获取连接（非阻塞方式先尝试）
            try:
                # 先尝试非阻塞获取，如果有可用连接直接使用
                connection = self._pools[pool_key].get_nowait()
                conn_id = id(connection)
                wrapper = self._connection_wrappers[pool_key].get(conn_id)
                if wrapper:
                    wrapper.update_usage()
                print(f"[ConnectionPool] 从池中复用连接: pool={pool_key}, conn_id={conn_id}")
            except Empty:
                # 池中没有可用连接，尝试创建新连接或等待
                with self._pool_locks[pool_key]:
                    # 再次检查（可能其他线程已经放回连接）
                    try:
                        connection = self._pools[pool_key].get_nowait()
                        conn_id = id(connection)
                        wrapper = self._connection_wrappers[pool_key].get(conn_id)
                        if wrapper:
                            wrapper.update_usage()
                        print(f"[ConnectionPool] 从池中复用连接（二次检查）: pool={pool_key}, conn_id={conn_id}")
                    except Empty:
                        # 确实没有可用连接，需要创建新连接
                        if config['current_connections'] < config['max_connections']:
                            print(f"[ConnectionPool] 池中无可用连接，尝试创建新连接: pool={pool_key}, current={config['current_connections']}, max={config['max_connections']}")
                            # 使用 raise_on_error=True 获取详细错误信息
                            try:
                                connection = self._create_connection(config['config'], raise_on_error=True)
                            except RuntimeError as e:
                                # 保存错误信息供后续诊断
                                config['last_error'] = str(e)
                                raise RuntimeError(f"无法创建新的数据库连接: {e}") from e
                            
                            if connection:
                                conn_id = id(connection)
                                wrapper = ConnectionWrapper(connection)
                                self._connection_wrappers[pool_key][conn_id] = wrapper
                                config['current_connections'] += 1
                                config['total_connections_created'] += 1
                                # 清除之前的错误记录
                                config.pop('last_error', None)
                                print(f"[ConnectionPool] 成功创建新连接: pool={pool_key}, conn_id={conn_id}")
                            else:
                                error_msg = last_error or "未知错误"
                                raise RuntimeError(f"无法创建新的数据库连接: {error_msg}")
                        else:
                            # 连接池已满，等待可用连接
                            print(f"[ConnectionPool] 连接池已满，等待可用连接: pool={pool_key}, timeout={timeout}s")
                
                # 如果还没有获取到连接，尝试阻塞等待
                if connection is None:
                    try:
                        connection = self._pools[pool_key].get(timeout=timeout)
                        conn_id = id(connection)
                        wrapper = self._connection_wrappers[pool_key].get(conn_id)
                        if wrapper:
                            wrapper.update_usage()
                        print(f"[ConnectionPool] 等待后获取到连接: pool={pool_key}, conn_id={conn_id}")
                    except Empty:
                        error_msg = last_error or "连接池无可用连接且无法创建新连接"
                        raise RuntimeError(f"获取数据库连接超时: {error_msg}")
            
            # 检查连接是否有效
            if not self._is_connection_valid(connection):
                print(f"[ConnectionPool] 连接无效，需要重新创建: pool={pool_key}, conn_id={conn_id}")
                # 连接无效，关闭并重新创建
                old_conn_id = conn_id
                if wrapper and old_conn_id in self._connection_wrappers.get(pool_key, {}):
                    del self._connection_wrappers[pool_key][old_conn_id]
                try:
                    connection.close()
                except:
                    pass
                with self._pool_locks[pool_key]:
                    config['current_connections'] -= 1
                    config['total_connections_closed'] += 1
                    config['total_connections_recycled'] += 1
                
                # 重新创建连接
                try:
                    connection = self._create_connection(config['config'], raise_on_error=True)
                except RuntimeError as e:
                    config['last_error'] = str(e)
                    raise RuntimeError(f"无法创建有效的数据库连接: {e}") from e
                
                if not connection:
                    error_msg = config.get('last_error', "未知错误")
                    raise RuntimeError(f"无法创建有效的数据库连接: {error_msg}")
                
                conn_id = id(connection)
                wrapper = ConnectionWrapper(connection)
                self._connection_wrappers[pool_key][conn_id] = wrapper
                with self._pool_locks[pool_key]:
                    config['current_connections'] += 1
                    config['total_connections_created'] += 1
                print(f"[ConnectionPool] 重新创建连接成功: pool={pool_key}, conn_id={conn_id}")
            
            yield connection
            
        except Exception as e:
            if connection:
                try:
                    connection.rollback()
                except:
                    pass
            raise e
        finally:
            # 将连接返回池中
            if connection and wrapper:
                try:
                    self._pools[pool_key].put(connection, timeout=1)
                    print(f"[ConnectionPool] 连接已返回池中: pool={pool_key}, conn_id={conn_id}")
                except:
                    # 如果池已满，关闭连接
                    if conn_id and conn_id in self._connection_wrappers.get(pool_key, {}):
                        del self._connection_wrappers[pool_key][conn_id]
                    try:
                        connection.close()
                    except:
                        pass
                    with self._pool_locks[pool_key]:
                        config['current_connections'] -= 1
                        config['total_connections_closed'] += 1
                    print(f"[ConnectionPool] 池已满，关闭连接: pool={pool_key}, conn_id={conn_id}")
    
    def _is_connection_valid(self, connection: pymysql.Connection) -> bool:
        """检查连接是否有效"""
        try:
            connection.ping(reconnect=False)
            return True
        except:
            return False
    
    def close_pool(self, pool_key: str) -> None:
        """关闭连接池"""
        if pool_key not in self._pools:
            return
        
        with self._pool_locks[pool_key]:
            # 关闭所有连接
            while not self._pools[pool_key].empty():
                try:
                    conn = self._pools[pool_key].get_nowait()
                    conn_id = id(conn)
                    conn.close()
                    if conn_id in self._connection_wrappers.get(pool_key, {}):
                        del self._connection_wrappers[pool_key][conn_id]
                except Empty:
                    break
            
            # 清理资源
            if pool_key in self._pools:
                del self._pools[pool_key]
            if pool_key in self._pool_configs:
                del self._pool_configs[pool_key]
            if pool_key in self._pool_locks:
                del self._pool_locks[pool_key]
            if pool_key in self._connection_wrappers:
                del self._connection_wrappers[pool_key]
    
    def _start_cleanup_thread(self):
        """启动后台清理线程"""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return
        
        self._cleanup_running = True
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_idle_connections,
            daemon=True,
            name="ConnectionPoolCleanup"
        )
        self._cleanup_thread.start()
    
    def _cleanup_idle_connections(self):
        """后台清理空闲连接和健康检查"""
        while self._cleanup_running:
            try:
                time.sleep(30)  # 每30秒检查一次
                
                for pool_key in list(self._pools.keys()):
                    try:
                        self._cleanup_pool_connections(pool_key)
                        self._health_check_pool(pool_key)
                    except Exception as e:
                        print(f"清理连接池 {pool_key} 时出错: {e}")
            except Exception as e:
                print(f"连接池清理线程出错: {e}")
    
    def _cleanup_pool_connections(self, pool_key: str):
        """清理指定连接池的空闲连接"""
        if pool_key not in self._pools:
            return
        
        config = self._pool_configs[pool_key]
        idle_timeout = config.get('idle_timeout', 300.0)
        min_connections = config['min_connections']
        
        with self._pool_locks[pool_key]:
            # 收集需要清理的连接
            connections_to_remove = []
            temp_connections = []
            
            # 从队列中取出所有连接进行检查
            while not self._pools[pool_key].empty():
                try:
                    conn = self._pools[pool_key].get_nowait()
                    conn_id = id(conn)
                    wrapper = self._connection_wrappers[pool_key].get(conn_id)
                    
                    if wrapper and wrapper.is_idle(idle_timeout):
                        # 检查是否超过最小连接数
                        if config['current_connections'] > min_connections:
                            connections_to_remove.append((conn, conn_id))
                            config['current_connections'] -= 1
                            config['total_connections_closed'] += 1
                        else:
                            temp_connections.append(conn)
                    else:
                        temp_connections.append(conn)
                except Empty:
                    break
            
            # 关闭需要清理的连接
            for conn, conn_id in connections_to_remove:
                try:
                    conn.close()
                    if conn_id in self._connection_wrappers[pool_key]:
                        del self._connection_wrappers[pool_key][conn_id]
                except:
                    pass
            
            # 将保留的连接放回队列
            for conn in temp_connections:
                try:
                    self._pools[pool_key].put_nowait(conn)
                except:
                    pass
    
    def _health_check_pool(self, pool_key: str):
        """对连接池进行健康检查"""
        if pool_key not in self._pools:
            return
        
        config = self._pool_configs[pool_key]
        health_check_interval = config.get('health_check_interval', 60.0)
        
        # 检查是否需要执行健康检查
        if time.time() - config.get('last_health_check', 0) < health_check_interval:
            return
        
        config['last_health_check'] = time.time()
        
        # 检查池中的连接有效性
        temp_connections = []
        invalid_count = 0
        
        with self._pool_locks[pool_key]:
            while not self._pools[pool_key].empty():
                try:
                    conn = self._pools[pool_key].get_nowait()
                    if self._is_connection_valid(conn):
                        temp_connections.append(conn)
                    else:
                        # 连接无效，关闭并移除
                        conn_id = id(conn)
                        try:
                            conn.close()
                            if conn_id in self._connection_wrappers[pool_key]:
                                del self._connection_wrappers[pool_key][conn_id]
                            config['current_connections'] -= 1
                            config['total_connections_closed'] += 1
                            invalid_count += 1
                        except:
                            pass
                except Empty:
                    break
            
            # 如果连接数低于最小连接数，补充连接
            while config['current_connections'] < config['min_connections']:
                conn = self._create_connection(config['config'])
                if conn:
                    wrapper = ConnectionWrapper(conn)
                    conn_id = id(conn)
                    self._connection_wrappers[pool_key][conn_id] = wrapper
                    temp_connections.append(conn)
                    config['current_connections'] += 1
                    config['total_connections_created'] += 1
                else:
                    break
            
            # 将有效连接放回队列
            for conn in temp_connections:
                try:
                    self._pools[pool_key].put_nowait(conn)
                except:
                    pass
        
        if invalid_count > 0:
            print(f"[ConnectionPool] 连接池 {pool_key} 健康检查: 发现并清理了 {invalid_count} 个无效连接")
    
    def get_pool_stats(self, pool_key: str) -> Dict[str, Any]:
        """获取连接池统计信息"""
        if pool_key not in self._pools:
            return {}
        
        config = self._pool_configs[pool_key]
        wrappers = self._connection_wrappers.get(pool_key, {})
        
        # 计算平均使用次数和平均连接年龄
        total_uses = sum(w.use_count for w in wrappers.values())
        avg_uses = total_uses / len(wrappers) if wrappers else 0
        avg_age = sum(time.time() - w.created_at for w in wrappers.values()) / len(wrappers) if wrappers else 0
        
        return {
            'pool_key': pool_key,
            'min_connections': config['min_connections'],
            'max_connections': config['max_connections'],
            'current_connections': config['current_connections'],
            'available_connections': self._pools[pool_key].qsize(),
            'pool_size': self._pools[pool_key].maxsize,
            'idle_timeout': config.get('idle_timeout', 300.0),
            'health_check_interval': config.get('health_check_interval', 60.0),
            'total_connections_created': config.get('total_connections_created', 0),
            'total_connections_closed': config.get('total_connections_closed', 0),
            'total_connections_recycled': config.get('total_connections_recycled', 0),
            'pool_age_seconds': time.time() - config.get('created_at', time.time()),
            'average_connection_uses': avg_uses,
            'average_connection_age_seconds': avg_age,
            'utilization_rate': f"{(config['current_connections'] / config['max_connections'] * 100):.1f}%"
        }
    
    def cleanup_workflow_pools(self, pool_keys: Optional[list] = None):
        """
        清理工作流相关的连接池
        
        Args:
            pool_keys: 要清理的连接池键列表，如果为None则清理所有空闲连接
        """
        if pool_keys is None:
            # 清理所有连接池的空闲连接
            for pool_key in list(self._pools.keys()):
                self._cleanup_pool_connections(pool_key)
        else:
            # 清理指定的连接池
            for pool_key in pool_keys:
                if pool_key in self._pools:
                    self._cleanup_pool_connections(pool_key)
    
    def close_all_pools(self) -> None:
        """关闭所有连接池"""
        self._cleanup_running = False
        for pool_key in list(self._pools.keys()):
            self.close_pool(pool_key)


# 全局连接池实例
connection_pool = MySQLConnectionPool()
