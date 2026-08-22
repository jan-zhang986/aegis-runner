# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName
@className SQLClient
@describe SQL客户端 - 独立的数据库操作能力
"""

import time
import json
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime
import pymysql
from contextlib import contextmanager


INSERT_INTO = "INSERT INTO"
WHERE = "WHERE"
VALUES = "VALUES"
UPDATE = "UPDATE"
DELETE_FROM ="DELETE FROM"

@dataclass
class SQLResult:
    """SQL执行结果封装"""
    success: bool
    data: List[Dict[str, Any]]
    affected_rows: int = 0
    insert_id: Optional[int] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    operation: str = ""
    
    def row_count(self) -> int:
        """获取行数"""
        return len(self.data)
    
    def is_empty(self) -> bool:
        """判断结果是否为空"""
        return len(self.data) == 0
    
    def first(self) -> Optional[Dict[str, Any]]:
        """获取第一行数据"""
        return self.data[0] if self.data else None
    
    def last(self) -> Optional[Dict[str, Any]]:
        """获取最后一行数据"""
        return self.data[-1] if self.data else None
    
    def get_column(self, column_name: str) -> List[Any]:
        """获取指定列的所有值"""
        return [row.get(column_name) for row in self.data]


class SQLClient:
    """SQL客户端 - 提供独立的数据库操作能力"""
    
    def __init__(self, host: str, port: int = 3306, user: str = None, 
                 password: str = None, database: str = None, 
                 charset: str = 'utf8mb4', **kwargs):
        """
        初始化SQL客户端
        
        Args:
            host: 数据库主机
            port: 数据库端口
            user: 用户名
            password: 密码
            database: 数据库名
            charset: 字符集
        """
        self.connection_config = {
            'host': host,
            'port': port,
            'user': user,
            'password': password,
            'database': database,
            'charset': charset,
            **kwargs
        }
        self.connection_pool = None
    
    def _get_connection(self):
        """获取数据库连接"""
        return pymysql.connect(**self.connection_config)
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接上下文管理器"""
        conn = None
        try:
            conn = self._get_connection()
            yield conn
        finally:
            if conn:
                conn.close()
    
    def _execute_query(self, sql: str, params: Union[List, Dict] = None) -> SQLResult:
        """执行查询操作"""
        start_time = time.time()
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
                    
                    # 处理特殊数据类型
                    processed_rows = []
                    for row in rows:
                        processed_row = {}
                        for key, value in row.items():
                            if isinstance(value, datetime):
                                processed_row[key] = value.isoformat()
                            elif hasattr(value, 'isoformat'):  # date类型
                                processed_row[key] = value.isoformat()
                            else:
                                processed_row[key] = value
                        processed_rows.append(processed_row)
                    
                    execution_time = time.time() - start_time
                    
                    return SQLResult(
                        success=True,
                        data=processed_rows,
                        affected_rows=len(processed_rows),
                        execution_time=execution_time,
                        operation="select"
                    )
                    
        except Exception as e:
            execution_time = time.time() - start_time
            return SQLResult(
                success=False,
                data=[],
                error=str(e),
                execution_time=execution_time,
                operation="select"
            )
    
    def _execute_insert(self, sql: str, params: Union[List, Dict] = None) -> SQLResult:
        """执行插入操作"""
        start_time = time.time()
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    affected_rows = cursor.execute(sql, params)
                    insert_id = cursor.lastrowid
                    conn.commit()
                    
                    execution_time = time.time() - start_time
                    
                    return SQLResult(
                        success=True,
                        data=[{"insert_id": insert_id}],
                        affected_rows=affected_rows,
                        insert_id=insert_id,
                        execution_time=execution_time,
                        operation="insert"
                    )
                    
        except Exception as e:
            execution_time = time.time() - start_time
            return SQLResult(
                success=False,
                data=[],
                error=str(e),
                execution_time=execution_time,
                operation="insert"
            )
    
    def _execute_update(self, sql: str, params: Union[List, Dict] = None) -> SQLResult:
        """执行更新操作"""
        start_time = time.time()
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    affected_rows = cursor.execute(sql, params)
                    conn.commit()
                    
                    execution_time = time.time() - start_time
                    
                    return SQLResult(
                        success=True,
                        data=[{"affected_rows": affected_rows}],
                        affected_rows=affected_rows,
                        execution_time=execution_time,
                        operation="update"
                    )
                    
        except Exception as e:
            execution_time = time.time() - start_time
            return SQLResult(
                success=False,
                data=[],
                error=str(e),
                execution_time=execution_time,
                operation="update"
            )
    
    def _execute_delete(self, sql: str, params: Union[List, Dict] = None) -> SQLResult:
        """执行删除操作"""
        start_time = time.time()
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    affected_rows = cursor.execute(sql, params)
                    conn.commit()
                    
                    execution_time = time.time() - start_time
                    
                    return SQLResult(
                        success=True,
                        data=[{"affected_rows": affected_rows}],
                        affected_rows=affected_rows,
                        execution_time=execution_time,
                        operation="delete"
                    )
                    
        except Exception as e:
            execution_time = time.time() - start_time
            return SQLResult(
                success=False,
                data=[],
                error=str(e),
                execution_time=execution_time,
                operation="delete"
            )
    
    def _execute_generic(self, sql: str, params: Union[List, Dict] = None) -> SQLResult:
        """执行通用SQL操作"""
        start_time = time.time()
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    affected_rows = cursor.execute(sql, params)
                    conn.commit()
                    
                    execution_time = time.time() - start_time
                    
                    return SQLResult(
                        success=True,
                        data=[{"affected_rows": affected_rows}],
                        affected_rows=affected_rows,
                        execution_time=execution_time,
                        operation="execute"
                    )
                    
        except Exception as e:
            execution_time = time.time() - start_time
            return SQLResult(
                success=False,
                data=[],
                error=str(e),
                execution_time=execution_time,
                operation="execute"
            )
    
    def select(self, sql: str, params: Union[List, Dict] = None) -> SQLResult:
        """执行SELECT查询"""
        return self._execute_query(sql, params)
    
    def insert(self, sql: str, params: Union[List, Dict] = None) -> SQLResult:
        """执行INSERT操作"""
        return self._execute_insert(sql, params)
    
    def update(self, sql: str, params: Union[List, Dict] = None) -> SQLResult:
        """执行UPDATE操作"""
        return self._execute_update(sql, params)
    
    def delete(self, sql: str, params: Union[List, Dict] = None) -> SQLResult:
        """执行DELETE操作"""
        return self._execute_delete(sql, params)
    
    def execute(self, sql: str, params: Union[List, Dict] = None) -> SQLResult:
        """执行通用SQL"""
        return self._execute_generic(sql, params)
    
    def query(self, sql: str, params: Union[List, Dict] = None) -> SQLResult:
        """查询方法别名"""
        return self.select(sql, params)
    
    def insert_record(self, table: str, data: Dict[str, Any]) -> SQLResult:
        """插入单条记录"""
        columns = list(data.keys())
        values = list(data.values())
        placeholders = ', '.join(['%s'] * len(columns))
        sql = f"{INSERT_INTO} {table} ({', '.join(columns)}) {VALUES} ({placeholders})"
        return self.insert(sql, values)
    
    def update_record(self, table: str, data: Dict[str, Any], where: str, where_params: Union[List, Dict] = None) -> SQLResult:
        """更新记录"""
        set_clause = ', '.join([f"{key} = %s" for key in data.keys()])
        sql = f"{UPDATE} {table} SET {set_clause} {WHERE} {where}"
        params = list(data.values())
        if where_params:
            if isinstance(where_params, list):
                params.extend(where_params)
            else:
                params.extend(list(where_params.values()))
        return self.update(sql, params)
    
    def delete_record(self, table: str, where: str, where_params: Union[List, Dict] = None) -> SQLResult:
        """删除记录"""
        sql = f"{DELETE_FROM} {table} WHERE {where}"
        return self.delete(sql, where_params)
    
    def select_record(self, table: str, where: str = None, where_params: Union[List, Dict] = None, 
                     columns: str = "*", limit: int = None) -> SQLResult:
        """查询记录"""
        sql = f"SELECT {columns} FROM {table}"
        params = None
        
        if where:
            sql += f" WHERE {where}"
            params = where_params
        
        if limit:
            sql += f" LIMIT {limit}"
        
        return self.select(sql, params)
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    return True
        except Exception:
            return False


class TestableSQLClient(SQLClient):
    """测试友好的SQL客户端"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.query_history = []
        self.mock_results = {}
    
    def _execute_query(self, sql: str, params: Union[List, Dict] = None) -> SQLResult:
        """重写查询方法，支持Mock和记录历史"""
        # 记录查询历史
        self.query_history.append({
            'sql': sql,
            'params': params,
            'timestamp': datetime.now()
        })
        
        # 检查是否有Mock结果
        mock_key = f"SELECT:{sql}"
        if mock_key in self.mock_results:
            return self.mock_results[mock_key]
        
        # 执行真实查询
        return super()._execute_query(sql, params)
    
    def mock_result(self, sql: str, result: SQLResult):
        """设置Mock结果"""
        mock_key = f"SELECT:{sql}"
        self.mock_results[mock_key] = result
    
    def clear_mocks(self):
        """清空Mock结果"""
        self.mock_results.clear()
    
    def get_query_history(self) -> List[Dict]:
        """获取查询历史"""
        return self.query_history
    
    def clear_history(self):
        """清空查询历史"""
        self.query_history.clear()
