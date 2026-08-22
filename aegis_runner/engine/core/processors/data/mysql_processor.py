# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-9-25
@packageName
@className MysqlProcessor
@describe Mysql数据库处理器
"""


import datetime
import json
import time

from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from aegis_runner.engine.context import ExecutionContext
from aegis_runner.engine.core.processors import BaseProcessor, render_recursive
from aegis_runner.engine.core.connection_pool import connection_pool
from aegis_runner.engine.core.simple_logger import logger
from aegis_runner.engine.core.elegant_processor_registry import register_processor, ProcessorCategory
from aegis_runner.engine.models.response import ResponseBuilder


@register_processor(
    processor_type="mysql",
    category=ProcessorCategory.DATA,
    description="MySQL数据库处理器，支持SQL查询和操作",
    tags={"database", "mysql", "sql", "data"},
    enabled=True,
    priority=60,
    dependencies=["pymysql"],
    version="1.0.0",
    author="Aegis Team"
)
class MysqlProcessor(BaseProcessor):
    """MySQL数据库处理器，支持增删改查操作"""
    
    def __init__(self):
        super().__init__()
    
    def _get_config_schema_name(self) -> str:
        """获取配置模式名称"""
        return "mysql"
    
    def _validate_specific_config(self, config: Dict[str, Any]) -> bool:
        """MySQL特定的配置验证"""
        # 检查是否有SQL或SQL列表
        sql = config.get("sql", "")
        sql_list = config.get("sql_list", [])
        
        if not sql and not sql_list:
            # 可选校验：仅提示，不阻断
            logger.warning(f"[MysqlProcessor] 未提供 sql 或 sql_list，将在执行阶段按需检查")
        
        if sql and sql_list:
            logger.warning(f"[MysqlProcessor] 同时提供了sql和sql_list，将使用sql_list")
        
        # 验证连接配置
        connection = config.get("connection", {})
        if connection and not isinstance(connection, dict):
            # 可选校验：仅提示，不阻断
            logger.warning(f"[MysqlProcessor] connection应为字典类型，当前类型为 {type(connection)}")
        
        return True

    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> Any:
        start_time = time.time()
        
        # 优先采用强类型 SqlConfig
        config_obj = self.get_typed_config(node_info)
        config = None
        if config_obj:
            # 如果使用强类型配置，需要转换为字典以保留所有字段（包括 sql_list）
            if hasattr(config_obj, 'to_dict'):
                config = config_obj.to_dict()
            else:
                config = config_obj.__dict__ if hasattr(config_obj, '__dict__') else {}
        else:
            # 兼容 data.config（标准节点）与顶层 config（子节点常见）：没有 sql_list 时用 sql
            config = node_info.get("data", {}).get("config") or node_info.get("config") or {}
        
        # 全量递归渲染配置
        config = render_recursive(config, context)
        
        # 是否为批量SQL执行：有 sql_list 走批量，否则走单条 sql
        sql_list = None
        if isinstance(config, dict):
            sql_list = config.get('sql_list', None)
        else:
            sql_list = getattr(config, 'sql_list', None) if hasattr(config, 'sql_list') else None
        
        # 检查 sql_list 是否存在且不为空（空列表也算有效，但会在 _execute_multiple_sqls 中验证）
        if sql_list is not None:
            return self._execute_multiple_sqls(config, context, node_info)
        # 单SQL执行
        operation = getattr(config, 'operation', None) if hasattr(config, 'operation') else config.get('operation', 'unknown')
        connection_config = getattr(config, 'connection', None) if hasattr(config, 'connection') else config.get('connection', {})
        # 防护：如果 connection_config 为 None，设置默认值
        if connection_config is None:
            connection_config = {}
        sql = getattr(config, 'sql', None) if hasattr(config, 'sql') else config.get('sql', '')
        query_type = getattr(config, 'query_type', None) if hasattr(config, 'query_type') else config.get('query_type', 'fetchmany')
        parameters = getattr(config, 'parameters', None) if hasattr(config, 'parameters') else config.get('parameters', [])
        pool_config = getattr(config, 'pool', None) if hasattr(config, 'pool') else config.get('pool', {})
        # 防护：如果 pool_config 为 None，设置默认值
        if pool_config is None:
            pool_config = {}
        min_connections = getattr(pool_config, 'min_connections', None) if hasattr(pool_config, 'min_connections') else pool_config.get('min_connections', 2)
        max_connections = getattr(pool_config, 'max_connections', None) if hasattr(pool_config, 'max_connections') else pool_config.get('max_connections', 10)
        idle_timeout = getattr(pool_config, 'idle_timeout', None) if hasattr(pool_config, 'idle_timeout') else pool_config.get('idle_timeout', 300.0)
        health_check_interval = getattr(pool_config, 'health_check_interval', None) if hasattr(pool_config, 'health_check_interval') else pool_config.get('health_check_interval', 60.0)
        # 记录详细的MySQL操作信息
        operation_details = f"""
================== MySQL Database Operation Details ==================
Global variable:{context.get_variables}
operation  : {operation}
host       : {getattr(connection_config, 'host', None) if hasattr(connection_config, 'host') else connection_config.get('host', 'localhost')}
port       : {getattr(connection_config, 'port', None) if hasattr(connection_config, 'port') else connection_config.get('port', 3306)}
database   : {getattr(connection_config, 'database', None) if hasattr(connection_config, 'database') else connection_config.get('database', '')}
user   : {getattr(connection_config, 'user', None) if hasattr(connection_config, 'user') else connection_config.get('user', '')}
sql        : {sql}
parameters : {json.dumps(parameters, indent=4, ensure_ascii=False)}
node_id    : {node_info.get('id')}
================================================================
"""
        logger.info(operation_details)
        # 检查关键参数
        if not connection_config:
            raise ValueError("数据库连接配置不能为空")
        pool_key = self._generate_pool_key(connection_config if isinstance(connection_config, dict) else connection_config.__dict__)
        # 确保连接池存在
        if pool_key not in connection_pool._pools:
            connection_pool.create_pool(
                pool_key, 
                connection_config, 
                min_connections, 
                max_connections,
                idle_timeout=idle_timeout,
                health_check_interval=health_check_interval
            )
        # 操作类型
        operation = operation if operation is not None else 'select'
        if operation not in ["select", "insert", "update", "delete", "execute"]:
            raise ValueError(f"不支持的操作类型: {operation}")
        # SQL语句
        # 若既没有 sql 也没有 sql_list：记录警告并跳过执行，不中断工作流
        if not sql:
            sql_list_check = config.get('sql_list', None) if isinstance(config, dict) else (getattr(config, 'sql_list', None) if hasattr(config, 'sql_list') else None)
            if not sql_list_check:
                node_id = node_info.get('id', '')
                node_name = node_info.get('name', '') or node_info.get('stepName', '')
                logger.warning(
                    f"[MysqlProcessor] 节点未配置 SQL，已跳过执行 (node_id={node_id}, name={node_name})"
                )
                duration = time.time() - start_time
                return ResponseBuilder.success(
                    processor_type="mysql",
                    body=[],
                    message="未配置 SQL，已跳过执行",
                    status_code=200,
                    metadata={"skipped": True, "reason": "no_sql"},
                    duration=duration
                ).to_dict()
        # 查询类型（仅对 select 操作有效）
        query_type = getattr(config, 'query_type', None) if hasattr(config, 'query_type') else config.get('query_type', 'fetchmany')
        if query_type not in ['fetchall', 'fetchone', 'fetchmany']:
            query_type = 'fetchmany'  # 默认值
        # 参数
        params = getattr(config, 'params', None) if hasattr(config, 'params') else config.get('params', [])
        # 处理SQL中的变量替换
        sql = context.render_string(sql)
        # 处理参数中的变量替换
        if isinstance(params, list):
            processed_params = []
            for param in params:
                if isinstance(param, str):
                    processed_params.append(context.render_string(param))
                else:
                    processed_params.append(param)
            params = processed_params
        elif isinstance(params, dict):
            processed_params = {}
            for key, value in params.items():
                if isinstance(value, str):
                    processed_params[key] = context.render_string(value)
                else:
                    processed_params[key] = value
            params = processed_params

        # 构造仅用于展示的「已绑定参数」SQL 预览字符串（不参与实际执行，避免 SQL 注入风险）
        executed_sql_preview = sql
        try:
            def _format_param_for_preview(v):
                # 字符串加引号并转义单引号
                if isinstance(v, str):
                    return "'" + v.replace("'", "''") + "'"
                # None 显示为 NULL
                if v is None:
                    return "NULL"
                return str(v)

            # 只支持最常见的 %s 占位符预览
            if isinstance(params, (list, tuple)):
                preview_sql = sql
                for p in params:
                    placeholder = "%s"
                    idx = preview_sql.find(placeholder)
                    if idx == -1:
                        break
                    value_str = _format_param_for_preview(p)
                    preview_sql = preview_sql[:idx] + value_str + preview_sql[idx + len(placeholder):]
                executed_sql_preview = preview_sql
            elif isinstance(params, dict):
                # 简单处理 %(name)s 风格
                preview_sql = sql
                for k, v in params.items():
                    placeholder = f"%({k})s"
                    value_str = _format_param_for_preview(v)
                    preview_sql = preview_sql.replace(placeholder, value_str)
                executed_sql_preview = preview_sql
        except Exception:
            # 预览失败时退回原始 SQL，避免影响主流程
            executed_sql_preview = sql

        try:
            # 执行数据库操作（使用连接池）
            result = self._execute_database_operation_with_pool(
                pool_key, operation, sql, params, query_type
            )
            # 记录结果到上下文
            if result.get("success"):
                context.set_variable("last_mysql_result", result.get("data"))
                context.set_variable("last_mysql_operation", operation)
                if "affected_rows" in result:
                    context.set_variable("last_mysql_affected_rows", result["affected_rows"])
            # 记录详细的MySQL执行结果（截断超长数据，避免日志膨胀导致 Kafka 消息超限）
            _MAX_LOG_DATA_LEN = 2000
            data_json = json.dumps(result.get('data', []), indent=2, ensure_ascii=False)
            if len(data_json) > _MAX_LOG_DATA_LEN:
                data_json = data_json[:_MAX_LOG_DATA_LEN] + f"\n... [截断，原长度 {len(data_json)} 字符]"
            execution_result = f"""
================== MySQL Execution Result ==================
success      : {result.get('success', False)}
operation    : {operation}
affected_rows: {result.get('affected_rows', 0)}
data         : {data_json}
duration     : {result.get('duration', 0):.3f}s
=========================================================
"""
            logger.info(execution_result)
            
            # 使用标准响应格式（兼容旧返回格式）
            duration = time.time() - start_time
            if result.get("status") == "success":
                # sql和params已经在前面渲染过了，直接使用
                # 使用success方法以便传入包含sql和params的metadata
                return ResponseBuilder.success(
                    processor_type="mysql",
                    body=result.get("body", {}).get("data", result.get("data", [])),
                    message=f"{operation.upper()} 操作成功",
                    status_code=200,
                    metadata={
                        "operation": operation,
                        "affected_rows": result.get("body", {}).get("affected_rows", result.get("affected_rows", 0)),
                        "sql": sql,  # 模板 SQL（已做变量渲染，仍包含占位符）
                        "params": params,  # 绑定参数（已做变量渲染）
                        # 仅用于展示的最终 SQL 预览，包含参数替换效果
                        "executed_sql": executed_sql_preview
                    },
                    duration=duration
                ).to_dict()
            else:
                # SQL_ERROR 场景：也在 error_details 中附带 operation/sql/params/executed_sql，便于前端展示
                return ResponseBuilder.error(
                    processor_type="mysql",
                    error=result.get("body", {}).get("error", result.get("error", "未知错误")),
                    error_code="SQL_ERROR",
                    status_code=500,
                    error_details={
                        "operation": operation,
                        "sql": sql,
                        "params": params,
                        "executed_sql": executed_sql_preview,
                        "affected_rows": result.get("body", {}).get("affected_rows", result.get("affected_rows", 0)),
                    },
                    duration=duration
                ).to_dict()
                
        except Exception as e:
            duration = time.time() - start_time
            # DB_ERROR 场景：同样附带 operation/sql/params/executed_sql 便于前端展示
            return ResponseBuilder.error(
                processor_type="mysql",
                error=f"MySQL操作失败: {str(e)}",
                error_code="DB_ERROR",
                status_code=500,
                error_details={
                    "operation": operation,
                    "sql": sql,
                    "params": params,
                    "executed_sql": executed_sql_preview,
                },
                duration=duration
            ).to_dict()

    def _execute_multiple_sqls(self, config: Dict, context: ExecutionContext, node_info: dict) -> Dict[str, Any]:
        """
        批量执行多个SQL语句
        
        Args:
            config: 配置信息
            context: 执行上下文
            node_info: 节点信息
            
        Returns:
            Dict: 批量执行结果
        """
        import time
        start_time = time.time()
        
        # 获取SQL列表
        sql_list = config.get("sql_list", [])
        if not sql_list:
            return {
                "success": False,
                "error": "SQL列表不能为空",
                "results": []
            }
        
        # 数据库连接配置
        connection_config = config.get("connection", {})
        if not connection_config:
            return {
                "success": False,
                "error": "数据库连接配置不能为空",
                "results": []
            }
        
        # 批量执行模式配置
        batch_config = config.get("batch_config", {})
        transaction_mode = batch_config.get("transaction_mode", "auto")  # auto, single, none
        stop_on_error = batch_config.get("stop_on_error", True)
        save_results = batch_config.get("save_results", True)
        
        # 获取默认查询类型和操作类型（用于批量执行中的字符串类型 SQL 项）
        default_query_type = config.get("query_type", "fetchmany")
        default_operation = config.get("operation", "select")
        
        # 记录批量操作信息
        batch_details = f"""
================== MySQL Batch Operation Details ==================
Global variables: {context.get_variables}
Total SQLs      : {len(sql_list)}
Transaction Mode: {transaction_mode}
Stop On Error   : {stop_on_error}
Database        : {connection_config.get('host', 'localhost')}:{connection_config.get('port', 3306)}/{connection_config.get('database', '')}
================================================================
"""
        logger.info(batch_details)
        
        # 连接池配置
        pool_config = config.get("pool", {})
        min_connections = pool_config.get("min_connections", 2)
        max_connections = pool_config.get("max_connections", 10)
        
        # 生成连接池标识
        pool_key = self._generate_pool_key(connection_config)
        
        # 确保连接池存在
        if pool_key not in connection_pool._pools:
            connection_pool.create_pool(pool_key, connection_config, min_connections, max_connections)
        
        # 执行批量SQL
        results = []
        all_success = True
        total_affected_rows = 0
        
        try:
            if transaction_mode == "single":
                # 单事务模式：所有SQL在同一个事务中执行
                result = self._execute_sqls_in_single_transaction(
                    pool_key, sql_list, context, stop_on_error, save_results, default_query_type, default_operation
                )
                results = result["results"] # response 返回结果
                all_success = result["all_success"]
                total_affected_rows = result["total_affected_rows"]
                
            else:
                # 自动事务模式：每个SQL独立事务
                for i, sql_item in enumerate(sql_list):
                    sql_index = i + 1
                    logger.info(f"[MySQL Batch] 执行 SQL {sql_index}/{len(sql_list)}")
                    
                    # 解析SQL项
                    if isinstance(sql_item, str):
                        sql = sql_item
                        # 自动检测 SQL 类型：如果以 SELECT 开头，使用 select 操作；否则使用默认操作
                        sql_upper = sql.strip().upper()
                        if sql_upper.startswith('SELECT'):
                            operation = "select"
                        else:
                            operation = default_operation
                        params = []
                        description = ""
                        query_type = default_query_type  # 使用默认查询类型
                    elif isinstance(sql_item, dict):
                        sql = sql_item.get("sql", "")
                        operation = sql_item.get("operation", "execute")
                        # 如果 operation 未指定，自动检测 SQL 类型
                        if operation == "execute":
                            sql_upper = sql.strip().upper()
                            if sql_upper.startswith('SELECT'):
                                operation = "select"
                        params = sql_item.get("params", [])
                        description = sql_item.get("description", "")
                        query_type = sql_item.get("query_type", default_query_type)
                    else:
                        results.append({
                            "success": False,
                            "error": f"SQL格式错误: {type(sql_item)}",
                            "sql_index": sql_index
                        })
                        all_success = False
                        if stop_on_error:
                            break
                        continue
                    
                    # 处理变量替换
                    sql = context.render_string(sql)
                    if isinstance(params, list):
                        params = [context.render_string(str(p)) if isinstance(p, str) else p for p in params]
                    
                    # 记录SQL详情（包含描述）
                    if description:
                        logger.info(f"[MySQL Batch] 📝 {description}")
                        logger.info(f"[MySQL Batch] SQL: {sql}")
                    else:
                        logger.info(f"[MySQL Batch] SQL: {sql}")
                    
                    # 执行SQL
                    result = self._execute_database_operation_with_pool(
                        pool_key, operation, sql, params, query_type
                    )
                    
                    # 添加索引和描述信息
                    result["sql_index"] = sql_index
                    result["sql"] = sql
                    if description:
                        result["description"] = description
                    
                    # 保存结果（如果配置了save_results）
                    if save_results:
                        results.append(result)
                    
                    # 检查执行结果（兼容 status 和 success 两种格式）
                    is_success = result.get("success", False) or result.get("status") == "success"
                    if not is_success:
                        all_success = False
                        error_msg = result.get('error') or result.get("body", {}).get("error", "未知错误")
                        logger.warning(f"[MySQL Batch] SQL {sql_index} 执行失败: {error_msg}")
                        if stop_on_error:
                            logger.error(f"[MySQL Batch] 遇到错误，停止执行")
                            break
                    else:
                        # 处理查询结果：如果是 SELECT 查询，提取变量
                        if operation == "select":
                            # 获取查询结果数据
                            query_data = result.get("body", {}).get("data", result.get("data", []))
                            if query_data and isinstance(query_data, list) and len(query_data) > 0:
                                # 提取第一条记录的所有字段作为变量
                                first_row = query_data[0]
                                if isinstance(first_row, dict):
                                    for key, value in first_row.items():
                                        context.set_variable(key, value)
                                        logger.info(f"[MySQL Batch] 提取变量: {key} = {value}")
                        
                        # 获取影响行数（兼容不同格式）
                        affected_rows = 0
                        if "affected_rows" in result:
                            affected_rows = result["affected_rows"]
                        elif "body" in result and "affected_rows" in result["body"]:
                            affected_rows = result["body"]["affected_rows"]
                        elif operation == "select":
                            # SELECT 查询返回的是行数
                            query_data = result.get("body", {}).get("data", result.get("data", []))
                            if isinstance(query_data, list):
                                affected_rows = len(query_data)
                        
                        total_affected_rows += affected_rows
                        logger.info(f"[MySQL Batch] SQL {sql_index} 执行成功，影响行数: {affected_rows}")
            
            # 计算执行时间
            duration = time.time() - start_time
            
            # 合并所有SQL查询结果的数据（类似单个SQL返回的body格式）
            merged_data = []
            for r in results:
                # 提取每个SQL的结果数据，格式与单个SQL一致
                if r.get("status") == "success" or r.get("success"):
                    # 获取查询结果数据
                    query_data = r.get("body", {}).get("data", r.get("data", []))
                    if query_data:
                        if isinstance(query_data, list):
                            merged_data.extend(query_data)
                        else:
                            merged_data.append(query_data)
            
            # 构建最终结果
            final_result = {
                "success": all_success,
                "batch_mode": True,
                "transaction_mode": transaction_mode,
                "total_sqls": len(sql_list),
                "executed_sqls": len(results),
                "success_count": sum(1 for r in results if r.get("success") or r.get("status") == "success"),
                "failed_count": sum(1 for r in results if not (r.get("success") or r.get("status") == "success")),
                "total_affected_rows": total_affected_rows,
                "duration": duration,
                "results": results if save_results else []
            }
            
            # 记录批量执行结果
            batch_result = f"""
================== MySQL Batch Execution Result ==================
Success         : {all_success}
Transaction Mode: {transaction_mode}
Total SQLs      : {len(sql_list)}
Executed SQLs   : {len(results)}
Success Count   : {final_result['success_count']}
Failed Count    : {final_result['failed_count']}
Total Affected  : {total_affected_rows}
Duration        : {duration:.3f}s
================================================================
"""
            logger.info(batch_result)
            
            # 保存到上下文
            context.set_variable("last_mysql_batch_result", final_result)
            context.set_variable("last_mysql_batch_success", all_success)
            context.set_variable("last_mysql_batch_affected_rows", total_affected_rows)
            
            # 使用标准响应格式返回，确保前端能正确解析
            # body字段返回合并后的查询结果数据，格式与单个SQL一致
            # 拼接批量执行的所有 SQL 供前端「执行SQL」展示（与单条 sql 路径行为一致）
            executed_sql_parts = [str(r.get("sql", "")) for r in results if r.get("sql")]
            executed_sql_batch = "\n".join(executed_sql_parts) if executed_sql_parts else None
            sql_batch = results[0].get("sql") if len(results) == 1 and results[0].get("sql") else executed_sql_batch

            if all_success:
                metadata_batch = {
                    "batch_mode": True,
                    "transaction_mode": transaction_mode,
                    "total_sqls": len(sql_list),
                    "executed_sqls": len(results),
                    "success_count": final_result['success_count'],
                    "failed_count": final_result['failed_count'],
                    "total_affected_rows": total_affected_rows
                }
                if executed_sql_batch:
                    metadata_batch["executed_sql"] = executed_sql_batch
                if sql_batch:
                    metadata_batch["sql"] = sql_batch
                return ResponseBuilder.success(
                    processor_type="mysql",
                    body=merged_data,  # 返回合并后的查询结果数据，格式与单个SQL一致
                    message=f"批量SQL执行成功 ({len(results)}/{len(sql_list)})",
                    status_code=200,
                    metadata=metadata_batch,
                    duration=duration
                ).to_dict()
            else:
                return ResponseBuilder.error(
                    processor_type="mysql",
                    error=f"批量SQL执行失败 ({final_result['failed_count']}/{len(sql_list)})",
                    error_code="BATCH_SQL_ERROR",
                    status_code=500,
                    error_details=final_result,
                    duration=duration
                ).to_dict()
            
        except Exception as e:
            error_result = {
                "success": False,
                "error": f"批量SQL执行失败: {str(e)}",
                "batch_mode": True,
                "results": results
            }
            logger.error(f"[MySQL Batch] 批量执行失败: {str(e)}")
            return error_result

    def _has_bind_params(self, params: Union[List, Dict, None]) -> bool:
        """判断是否有有效参数。无参数时应调用 cursor.execute(sql) 不传参，避免 PyMySQL 对 SQL 中的 % 做格式化（如 %70、%Y-%m-%d）导致报错。"""
        if params is None:
            return False
        if isinstance(params, list) and len(params) == 0:
            return False
        if isinstance(params, dict) and len(params) == 0:
            return False
        return True

    def _execute_sql(self, cursor, sql: str, params: Union[List, Dict, None]) -> int:
        """执行一条 SQL：有 params 时走参数绑定，无 params 时不传第二参数，避免 % 被误格式化。"""
        if self._has_bind_params(params):
            return cursor.execute(sql, params)
        return cursor.execute(sql)

    def _execute_sqls_in_single_transaction(
        self, pool_key: str, sql_list: List, context: ExecutionContext,
        stop_on_error: bool, save_results: bool, default_query_type: str = "fetchmany",
        default_operation: str = "select"
    ) -> Dict[str, Any]:
        """
        在单个事务中执行多个SQL
        
        Args:
            pool_key: 连接池标识
            sql_list: SQL列表
            context: 执行上下文
            stop_on_error: 遇到错误是否停止
            save_results: 是否保存结果
            
        Returns:
            Dict: 执行结果
        """
        results = []
        all_success = True
        total_affected_rows = 0
        
        try:
            with connection_pool.get_connection(pool_key) as conn:
                with conn.cursor() as cursor:
                    logger.info("[MySQL Transaction] 开始单事务批量执行")
                    
                    for i, sql_item in enumerate(sql_list):
                        sql_index = i + 1
                        
                        # 解析SQL项
                        if isinstance(sql_item, str):
                            sql = sql_item
                            # 自动检测 SQL 类型：如果以 SELECT 开头，使用 select 操作；否则使用默认操作
                            sql_upper = sql.strip().upper()
                            if sql_upper.startswith('SELECT'):
                                operation = "select"
                            else:
                                operation = default_operation
                            params = []
                            description = ""
                            query_type = default_query_type  # 使用默认查询类型
                        elif isinstance(sql_item, dict):
                            sql = sql_item.get("sql", "")
                            operation = sql_item.get("operation", "execute")
                            params = sql_item.get("params", [])
                            description = sql_item.get("description", "")
                            query_type = sql_item.get("query_type", default_query_type)
                        else:
                            results.append({
                                "success": False,
                                "error": f"SQL格式错误: {type(sql_item)}",
                                "sql_index": sql_index
                            })
                            all_success = False
                            if stop_on_error:
                                conn.rollback()
                                logger.error("[MySQL Transaction] 遇到错误，回滚事务")
                                break
                            continue
                        
                        # 处理变量替换
                        sql = context.render_string(sql)
                        if isinstance(params, list):
                            params = [context.render_string(str(p)) if isinstance(p, str) else p for p in params]
                        
                        # 记录SQL描述
                        if description:
                            logger.info(f"[MySQL Transaction] 📝 {description}")
                        
                        try:
                            # 执行SQL
                            affected_rows = self._execute_sql(cursor, sql, params)
                            total_affected_rows += affected_rows
                            
                            # 获取结果数据
                            data = None
                            if operation == "select" and cursor.description:
                                columns = [desc[0] for desc in cursor.description]
                                
                                # 根据查询类型获取结果
                                rows = []
                                if query_type == "fetchone":
                                    row = cursor.fetchone()
                                    if row:
                                        rows = [row]
                                elif query_type == "fetchmany":
                                    rows = cursor.fetchmany(10)
                                else:  # fetchall (默认)
                                    rows = cursor.fetchall()
                                
                                data = []
                                for row in rows:
                                    row_dict = {}
                                    for j, value in enumerate(row):
                                        # 处理特殊数据类型
                                        if isinstance(value, datetime.datetime):
                                            value = value.isoformat()
                                        elif isinstance(value, datetime.date):
                                            value = value.isoformat()
                                        elif isinstance(value, Decimal):
                                            value = float(value)
                                        elif isinstance(value, bytes):
                                            value = value.decode('utf-8')
                                        row_dict[columns[j]] = value
                                    data.append(row_dict)
                            elif operation == "insert":
                                data = {"insert_id": cursor.lastrowid}
                            
                            result = {
                                "success": True,
                                "status": "success",
                                "sql_index": sql_index,
                                "sql": sql,
                                "operation": operation,
                                "affected_rows": affected_rows,
                                "data": data,
                                "body": {
                                    "data": data,
                                    "affected_rows": affected_rows
                                }
                            }
                            
                            if description:
                                result["description"] = description
                            
                            if save_results:
                                results.append(result)
                            
                            # 处理查询结果：如果是 SELECT 查询，提取变量
                            if operation == "select" and data and isinstance(data, list) and len(data) > 0:
                                # 提取第一条记录的所有字段作为变量
                                first_row = data[0]
                                if isinstance(first_row, dict):
                                    for key, value in first_row.items():
                                        context.set_variable(key, value)
                                        logger.debug(f"[MySQL Transaction] 提取变量: {key} = {value}")
                            
                            logger.info(f"[MySQL Transaction] SQL {sql_index} 执行成功")
                            
                        except Exception as e:
                            all_success = False
                            error_result = {
                                "success": False,
                                "sql_index": sql_index,
                                "sql": sql,
                                "error": str(e)
                            }
                            
                            if description:
                                error_result["description"] = description
                            
                            if save_results:
                                results.append(error_result)
                            
                            logger.error(f"[MySQL Transaction] SQL {sql_index} 执行失败: {str(e)}")
                            
                            if stop_on_error:
                                conn.rollback()
                                logger.error("[MySQL Transaction] 遇到错误，回滚事务")
                                break
                    
                    # 提交或回滚事务
                    if all_success:
                        conn.commit()
                        logger.info("[MySQL Transaction] 所有SQL执行成功，提交事务")
                    else:
                        if stop_on_error:
                            # 已经在上面回滚了
                            pass
                        else:
                            # 部分成功，根据配置决定是否提交
                            conn.commit()
                            logger.warning("[MySQL Transaction] 部分SQL执行失败，但已提交事务")
            
            return {
                "results": results,
                "all_success": all_success,
                "total_affected_rows": total_affected_rows
            }
            
        except Exception as e:
            logger.error(f"[MySQL Transaction] 事务执行失败: {str(e)}")
            return {
                "results": results,
                "all_success": False,
                "total_affected_rows": 0,
                "error": str(e)
            }

    def _generate_pool_key(self, connection_config: Dict) -> str:
        """生成连接池标识"""
        key_parts = [
            connection_config.get('host', 'localhost'),
            str(connection_config.get('port', 3306)),
            connection_config.get('user', ''),
            connection_config.get('database', '')
        ]
        return '_'.join(key_parts)

    def _execute_database_operation_with_pool(self, pool_key: str, operation: str, 
                                            sql: str, params: Union[List, Dict], 
                                            query_type: str = "fetchmany") -> Dict[str, Any]:
        """
        使用连接池执行数据库操作
        
        Args:
            pool_key: 连接池标识
            operation: 操作类型
            sql: SQL语句
            params: 参数
            query_type: 查询类型 (fetchall, fetchone, fetchmany)
            
        Returns:
            Dict: 执行结果
        """
        try:
            with connection_pool.get_connection(pool_key) as conn:
                with conn.cursor() as cursor:
                    if operation == "select":
                        result = self._execute_select(cursor, sql, params, query_type)
                        # SELECT 查询后提交事务，确保下次查询能看到最新数据
                        # 这对于连接池复用场景很重要，避免 REPEATABLE READ 隔离级别下读取旧快照
                        conn.commit()
                        return result
                    elif operation == "insert":
                        return self._execute_insert(cursor, conn, sql, params)
                    elif operation == "update":
                        return self._execute_update(cursor, conn, sql, params)
                    elif operation == "delete":
                        return self._execute_delete(cursor, conn, sql, params)
                    elif operation == "execute":
                        return self._execute_generic(cursor, conn, sql, params, query_type)
                    else:
                        raise ValueError(f"不支持的操作类型: {operation}")
                        
        except Exception as e:
            return {
                "success": False,
                "error": f"数据库操作失败: {str(e)}",
                "operation": operation
            }

    def _execute_database_operation(self, connection_config: Dict, operation: str, 
                                  sql: str, params: Union[List, Dict],
                                  query_type: str = "fetchmany") -> Dict[str, Any]:
        """
        执行数据库操作
        
        Args:
            connection_config: 连接配置
            operation: 操作类型
            sql: SQL语句
            params: 参数
            query_type: 查询类型
            
        Returns:
            Dict: 执行结果
        """
        try:
            with self._get_connection(connection_config) as conn:
                with conn.cursor() as cursor:
                    if operation == "select":
                        result = self._execute_select(cursor, sql, params, query_type)
                        # SELECT 查询后提交事务，确保下次查询能看到最新数据
                        conn.commit()
                        return result
                    elif operation == "insert":
                        return self._execute_insert(cursor, conn, sql, params)
                    elif operation == "update":
                        return self._execute_update(cursor, conn, sql, params)
                    elif operation == "delete":
                        return self._execute_delete(cursor, conn, sql, params)
                    elif operation == "execute":
                        return self._execute_generic(cursor, conn, sql, params, query_type)
                    else:
                        raise ValueError(f"不支持的操作类型: {operation}")
                        
        except Exception as e:
            return {
                "success": False,
                "error": f"数据库操作失败: {str(e)}",
                "operation": operation
            }

    def _execute_select(self, cursor, sql: str, params: Union[List, Dict], query_type: str = "fetchmany") -> Dict[str, Any]:
        """执行查询操作
        
        Args:
            cursor: 数据库游标
            sql: SQL语句
            params: 参数
            query_type: 查询类型 (fetchall, fetchone, fetchmany)
            
        Returns:
            Dict: 执行结果
        """
        try:
            self._execute_sql(cursor, sql, params)
            
            # 获取列名
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # 根据查询类型获取结果
            rows = []
            if query_type == "fetchone":
                row = cursor.fetchone()
                if row:
                    rows = [row]
            elif query_type == "fetchmany":
                # fetchmany 默认获取 10 条记录
                rows = cursor.fetchmany(10)
            else:  # fetchall (默认)
                rows = cursor.fetchall()
            
            # 转换结果为字典列表
            results = []
            for row in rows:
                row_dict = {}
                for i, value in enumerate(row):
                    # 处理特殊数据类型
                    if isinstance(value, datetime.datetime):
                        value = value.isoformat()
                    elif isinstance(value, datetime.date):
                        value = value.isoformat()
                    elif isinstance(value, Decimal):
                        value = float(value)
                    elif isinstance(value, bytes):
                        value = value.decode('utf-8')
                    
                    row_dict[columns[i]] = value
                results.append(row_dict)
            
            return {
                "status": "success",
                "status_code": 200,
                "body": {
                    "data": results,
                    "row_count": len(results)
                },
                "operation": "select",
                "query_type": query_type
            }
            
        except Exception as e:
            return {
                "status": "error",
                "status_code": 500,
                "body": {
                    "error": f"查询执行失败: {str(e)}"
                },
                "operation": "select"
            }

    def _execute_insert(self, cursor, conn, sql: str, params: Union[List, Dict]) -> Dict[str, Any]:
        """执行插入操作"""
        try:
            affected_rows = self._execute_sql(cursor, sql, params)
            conn.commit()
            
            # 获取插入的ID
            insert_id = cursor.lastrowid
            
            return {
                "status": "success",
                "status_code": 200,
                "body": {
                    "data": {"insert_id": insert_id},
                    "affected_rows": affected_rows
                },
                "operation": "insert"
            }
            
        except Exception as e:
            conn.rollback()
            return {
                "status": "error",
                "status_code": 500,
                "body": {
                    "error": f"插入执行失败: {str(e)}"
                },
                "operation": "insert"
            }

    def _execute_update(self, cursor, conn, sql: str, params: Union[List, Dict]) -> Dict[str, Any]:
        """执行更新操作"""
        try:
            affected_rows = self._execute_sql(cursor, sql, params)
            conn.commit()
            
            return {
                "status": "success",
                "status_code": 200,
                "body": {
                    "data": {"affected_rows": affected_rows},
                    "affected_rows": affected_rows
                },
                "operation": "update"
            }
            
        except Exception as e:
            conn.rollback()
            return {
                "status": "error",
                "status_code": 500,
                "body": {
                    "error": f"更新执行失败: {str(e)}"
                },
                "operation": "update"
            }

    def _execute_delete(self, cursor, conn, sql: str, params: Union[List, Dict]) -> Dict[str, Any]:
        """执行删除操作"""
        try:
            affected_rows = self._execute_sql(cursor, sql, params)
            conn.commit()
            
            return {
                "status": "success",
                "status_code": 200,
                "body": {
                    "data": {"affected_rows": affected_rows},
                    "affected_rows": affected_rows
                },
                "operation": "delete"
            }
            
        except Exception as e:
            conn.rollback()
            return {
                "status": "error",
                "status_code": 500,
                "body": {
                    "error": f"删除执行失败: {str(e)}"
                },
                "operation": "delete"
            }

    def _execute_generic(self, cursor, conn, sql: str, params: Union[List, Dict], query_type: str = "fetchmany") -> Dict[str, Any]:
        """执行通用SQL操作
        
        Args:
            cursor: 数据库游标
            conn: 数据库连接
            sql: SQL语句
            params: 参数
            query_type: 查询类型（仅对 SELECT 有效）
            
        Returns:
            Dict: 执行结果
        """
        try:
            affected_rows = self._execute_sql(cursor, sql, params)
            
            # 检查是否是 SELECT 查询
            sql_upper = sql.strip().upper()
            if sql_upper.startswith('SELECT'):
                # SELECT 查询，返回查询结果
                return self._execute_select(cursor, sql, params, query_type)
            else:
                # 非 SELECT 查询，提交事务并返回影响行数
                conn.commit()
                return {
                    "status": "success",
                    "status_code": 200,
                    "body": {
                        "data": {"affected_rows": affected_rows},
                        "affected_rows": affected_rows
                    },
                    "operation": "execute"
                }
            
        except Exception as e:
            conn.rollback()
            return {
                "status": "error",
                "status_code": 500,
                "body": {
                    "error": f"SQL执行失败: {str(e)}"
                },
                "operation": "execute"
            }

    def get_pool_stats(self, connection_config: Dict) -> Dict[str, Any]:
        """获取连接池统计信息"""
        pool_key = self._generate_pool_key(connection_config)
        return connection_pool.get_pool_stats(pool_key)