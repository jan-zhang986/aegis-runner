"""
MongoDB 处理器

支持基本的 MongoDB 操作：
- 文档操作 (INSERT, FIND, UPDATE, DELETE)
- 集合操作 (CREATE_COLLECTION, DROP_COLLECTION, LIST_COLLECTIONS)
- 索引操作 (CREATE_INDEX, DROP_INDEX, LIST_INDEXES)
- 聚合操作 (AGGREGATE)
- 计数操作 (COUNT)
- 批量操作 (BULK_WRITE)
"""

import json
import time
from typing import Any, Dict, List, Union, Optional
from src.engine.core.processors import BaseProcessor, render_recursive
from src.engine.core.exceptions import ValidationError, ExecutionError
from src.engine.core.simple_logger import logger
from src.engine.core.elegant_processor_registry import register_processor, ProcessorCategory
from src.engine.models.response import ResponseBuilder

try:
    from pymongo import MongoClient, ASCENDING, DESCENDING
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    logger.warning("[MongoDBProcessor] pymongo 模块未安装，请运行: pip install pymongo")


@register_processor(
    processor_type="mongodb",
    category=ProcessorCategory.DATA,
    description="MongoDB文档数据库处理器，支持文档、集合、索引等操作",
    tags={"mongodb", "document", "database", "data"},
    enabled=True,
    priority=55,
    dependencies=["pymongo"],
    version="1.0.0",
    author="Aegis Team"
)
class MongoDBProcessor(BaseProcessor):
    """MongoDB 处理器"""
    
    def __init__(self):
        super().__init__()
        self.processor_type = "mongodb"
        self.processor_name = "MongoDB 数据库处理器"
        self.processor_description = "支持 MongoDB 数据库的基本操作，包括文档、集合、索引等"
    
    def _get_config_schema_name(self) -> str:
        """获取配置模式名称"""
        return "mongodb"
    
    def _validate_specific_config(self, config: Dict[str, Any]) -> bool:
        """MongoDB 特定的配置验证"""
        try:
            self.validate_config(config)
            return True
        except ValidationError:
            return False
    
    def validate_config(self, config: Dict[str, Any]) -> None:
        """
        验证配置参数
        
        Args:
            config: 配置参数
        """
        if not MONGODB_AVAILABLE:
            raise ValidationError(
                message="MongoDB 模块未安装，请运行: pip install pymongo",
                field_name="mongodb_module",
                field_value=None,
                validation_rule="dependency"
            )
        
        # 检查操作类型
        operation = config.get('operation')
        if not operation:
            raise ValidationError(
                message="operation 不能为空",
                field_name="operation",
                field_value=None,
                validation_rule="required"
            )
        
        # 验证操作类型
        valid_operations = [
            # 文档操作
            'insert_one', 'insert_many', 'find_one', 'find', 'update_one', 'update_many',
            'delete_one', 'delete_many', 'replace_one', 'count_documents',
            # 集合操作
            'create_collection', 'drop_collection', 'list_collections', 'list_collection_names',
            # 索引操作
            'create_index', 'drop_index', 'list_indexes', 'drop_indexes',
            # 聚合操作
            'aggregate', 'distinct',
            # 批量操作
            'bulk_write',
            # 数据库操作
            'list_databases', 'drop_database'
        ]
        
        if operation not in valid_operations:
            raise ValidationError(
                message=f"不支持的 MongoDB 操作: {operation}",
                field_name="operation",
                field_value=operation,
                validation_rule="enum"
            )
        
        # 验证连接参数
        self._validate_connection_config(config)
        
        # 根据操作类型验证特定参数
        self._validate_operation_params(operation, config)
    
    def _validate_connection_config(self, config: Dict[str, Any]) -> None:
        """验证连接配置"""
        # 验证连接字符串
        connection_string = config.get('connection_string')
        host = config.get('host', 'localhost')
        port = config.get('port', 27017)
        
        if not connection_string and not host:
            raise ValidationError(
                message="必须提供 connection_string 或 host 参数",
                field_name="connection",
                field_value=None,
                validation_rule="required"
            )
        
        # 验证端口
        if port:
            if not isinstance(port, (int, str)):
                raise ValidationError(
                    message="port 必须是整数或可转换为整数的字符串",
                    field_name="port",
                    field_value=port,
                    validation_rule="type"
                )
            
            try:
                port_int = int(port)
                if not (1 <= port_int <= 65535):
                    raise ValidationError(
                        message="port 必须在 1-65535 范围内",
                        field_name="port",
                        field_value=port,
                        validation_rule="range"
                    )
            except ValueError:
                raise ValidationError(
                    message="port 无法转换为整数",
                    field_name="port",
                    field_value=port,
                    validation_rule="format"
                )
        
        # 验证数据库名
        database = config.get('database')
        if not database:
            raise ValidationError(
                message="database 不能为空",
                field_name="database",
                field_value=None,
                validation_rule="required"
            )
        
        if not isinstance(database, str):
            raise ValidationError(
                message="database 必须是字符串",
                field_name="database",
                field_value=database,
                validation_rule="type"
            )
        
        # 验证集合名
        collection = config.get('collection')
        if collection and not isinstance(collection, str):
            raise ValidationError(
                message="collection 必须是字符串",
                field_name="collection",
                field_value=collection,
                validation_rule="type"
            )
        
        # 验证超时时间
        timeout = config.get('timeout', 30)
        if not isinstance(timeout, (int, float, str)):
            raise ValidationError(
                message="timeout 必须是数字或可转换为数字的字符串",
                field_name="timeout",
                field_value=timeout,
                validation_rule="type"
            )
        
        try:
            timeout_float = float(timeout)
            if timeout_float <= 0:
                raise ValidationError(
                    message="timeout 必须大于 0",
                    field_name="timeout",
                    field_value=timeout,
                    validation_rule="range"
                )
        except ValueError:
            raise ValidationError(
                message="timeout 无法转换为数字",
                field_name="timeout",
                field_value=timeout,
                validation_rule="format"
            )
    
    def _validate_operation_params(self, operation: str, config: Dict[str, Any]) -> None:
        """根据操作类型验证特定参数"""
        # 需要集合名的操作
        collection_required_ops = [
            'insert_one', 'insert_many', 'find_one', 'find', 'update_one', 'update_many',
            'delete_one', 'delete_many', 'replace_one', 'count_documents', 'create_index',
            'drop_index', 'list_indexes', 'drop_indexes', 'aggregate', 'distinct', 'bulk_write'
        ]
        
        if operation in collection_required_ops:
            if 'collection' not in config:
                raise ValidationError(
                    message=f"{operation} 操作需要 collection 参数",
                    field_name="collection",
                    field_value=None,
                    validation_rule="required"
                )
        
        # 需要文档数据的操作
        if operation in ['insert_one', 'replace_one']:
            if 'document' not in config:
                raise ValidationError(
                    message=f"{operation} 操作需要 document 参数",
                    field_name="document",
                    field_value=None,
                    validation_rule="required"
                )
        
        elif operation in ['insert_many', 'bulk_write']:
            if 'documents' not in config:
                raise ValidationError(
                    message=f"{operation} 操作需要 documents 参数",
                    field_name="documents",
                    field_value=None,
                    validation_rule="required"
                )
        
        # 需要查询条件的操作
        if operation in ['find', 'find_one', 'update_one', 'update_many', 'delete_one', 'delete_many', 'count_documents']:
            if 'filter' not in config:
                raise ValidationError(
                    message=f"{operation} 操作需要 filter 参数",
                    field_name="filter",
                    field_value=None,
                    validation_rule="required"
                )
        
        # 需要更新数据的操作
        if operation in ['update_one', 'update_many', 'replace_one']:
            if operation == 'replace_one':
                if 'replacement' not in config:
                    raise ValidationError(
                        message="replace_one 操作需要 replacement 参数",
                        field_name="replacement",
                        field_value=None,
                        validation_rule="required"
                    )
            else:
                if 'update' not in config:
                    raise ValidationError(
                        message=f"{operation} 操作需要 update 参数",
                        field_name="update",
                        field_value=None,
                        validation_rule="required"
                    )
        
        # 需要索引的操作
        if operation in ['create_index', 'drop_index']:
            if 'index' not in config:
                raise ValidationError(
                    message=f"{operation} 操作需要 index 参数",
                    field_name="index",
                    field_value=None,
                    validation_rule="required"
                )
        
        # 需要聚合管道的操作
        if operation == 'aggregate':
            if 'pipeline' not in config:
                raise ValidationError(
                    message="aggregate 操作需要 pipeline 参数",
                    field_name="pipeline",
                    field_value=None,
                    validation_rule="required"
                )
        
        # 需要字段名的操作
        if operation == 'distinct':
            if 'field' not in config:
                raise ValidationError(
                    message="distinct 操作需要 field 参数",
                    field_name="field",
                    field_value=None,
                    validation_rule="required"
                )
    
    def execute(self, config: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        """
        执行 MongoDB 操作
        
        Args:
            config: 配置参数
            context: 执行上下文
            
        Returns:
            执行结果
        """
        start_time = time.time()
        
        try:
            # 渲染配置中的变量（全量递归渲染）
            rendered_config = render_recursive(config, context) if context else config
            
            # 验证渲染后的配置
            self.validate_config(rendered_config)
            
            operation = rendered_config.get('operation')
            logger.info(f"[MongoDBProcessor] 开始执行 MongoDB 操作: {operation}")
            
            # 创建 MongoDB 连接
            client, database = self._create_mongodb_connection(rendered_config)
            
            # 执行操作
            result = self._execute_operation(client, database, rendered_config)
            duration = time.time() - start_time
            
            # 保存结果到上下文
            output_variable = rendered_config.get('output_variable')
            if output_variable and context and hasattr(context, 'set_variable'):
                context.set_variable(output_variable, result)
            
            logger.info(f"[MongoDBProcessor] MongoDB 操作 {operation} 执行成功")
            
            # 使用标准响应格式
            return ResponseBuilder.success(
                processor_type="mongodb",
                body=result,
                message=f"{operation} 操作成功",
                status_code=200,
                metadata={
                    "operation": operation,
                    "collection": rendered_config.get('collection', '')
                },
                duration=duration
            ).to_dict()
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"[MongoDBProcessor] MongoDB 操作执行失败: {str(e)}")
            return ResponseBuilder.error(
                processor_type="mongodb",
                error=f"MongoDB 操作执行失败: {str(e)}",
                error_code="MONGODB_ERROR",
                status_code=500,
                duration=duration
            ).to_dict()
    
    def _create_mongodb_connection(self, config: Dict[str, Any]):
        """创建 MongoDB 连接"""
        connection_string = config.get('connection_string')
        host = config.get('host', 'localhost')
        port = int(config.get('port', 27017))
        database = config.get('database')
        username = config.get('username')
        password = config.get('password')
        timeout = float(config.get('timeout', 30))
        
        # 构建连接字符串
        if connection_string:
            uri = connection_string
        else:
            # 构建基本连接字符串
            if username and password:
                uri = f"mongodb://{username}:{password}@{host}:{port}/{database}"
            else:
                uri = f"mongodb://{host}:{port}/{database}"
        
        # 创建连接参数
        connection_params = {
            'serverSelectionTimeoutMS': int(timeout * 1000),
            'connectTimeoutMS': int(timeout * 1000),
            'socketTimeoutMS': int(timeout * 1000),
        }
        
        # 创建 MongoDB 客户端
        try:
            client = MongoClient(uri, **connection_params)
            
            # 测试连接
            client.admin.command('ping')
            logger.debug(f"[MongoDBProcessor] 成功连接到 MongoDB: {host}:{port}")
            
            # 获取数据库
            db = client[database]
            
            return client, db
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            raise ExecutionError(
                message=f"无法连接到 MongoDB 服务器: {str(e)}",
                operation="mongodb_connection",
                original_error=e
            )
    
    def _execute_operation(self, client, database, config: Dict[str, Any]) -> Any:
        """执行 MongoDB 操作"""
        operation = config.get('operation')
        collection_name = config.get('collection')
        
        try:
            if operation in ['list_databases']:
                return [db['name'] for db in client.list_databases()]
            
            elif operation == 'drop_database':
                database_name = config.get('database')
                client.drop_database(database_name)
                return f"数据库 {database_name} 已删除"
            
            elif operation in ['create_collection', 'drop_collection', 'list_collections', 'list_collection_names']:
                if operation == 'create_collection':
                    collection_name = config.get('collection')
                    options = config.get('options', {})
                    database.create_collection(collection_name, **options)
                    return f"集合 {collection_name} 已创建"
                
                elif operation == 'drop_collection':
                    collection_name = config.get('collection')
                    database.drop_collection(collection_name)
                    return f"集合 {collection_name} 已删除"
                
                elif operation == 'list_collections':
                    return list(database.list_collections())
                
                elif operation == 'list_collection_names':
                    return database.list_collection_names()
            
            else:
                # 需要集合的操作
                if not collection_name:
                    raise ValueError(f"{operation} 操作需要 collection 参数")
                
                collection = database[collection_name]
                
                if operation == 'insert_one':
                    document = config.get('document')
                    result = collection.insert_one(document)
                    return {
                        'inserted_id': str(result.inserted_id),
                        'acknowledged': result.acknowledged
                    }
                
                elif operation == 'insert_many':
                    documents = config.get('documents')
                    result = collection.insert_many(documents)
                    return {
                        'inserted_ids': [str(id) for id in result.inserted_ids],
                        'acknowledged': result.acknowledged
                    }
                
                elif operation == 'find_one':
                    filter_query = config.get('filter', {})
                    projection = config.get('projection')
                    sort = config.get('sort')
                    
                    query_params = {'filter': filter_query}
                    if projection:
                        query_params['projection'] = projection
                    if sort:
                        query_params['sort'] = sort
                    
                    result = collection.find_one(**query_params)
                    return result
                
                elif operation == 'find':
                    filter_query = config.get('filter', {})
                    projection = config.get('projection')
                    sort = config.get('sort')
                    limit = config.get('limit')
                    skip = config.get('skip')
                    
                    query_params = {'filter': filter_query}
                    if projection:
                        query_params['projection'] = projection
                    if sort:
                        query_params['sort'] = sort
                    if limit:
                        query_params['limit'] = int(limit)
                    if skip:
                        query_params['skip'] = int(skip)
                    
                    cursor = collection.find(**query_params)
                    return list(cursor)
                
                elif operation == 'update_one':
                    filter_query = config.get('filter', {})
                    update_data = config.get('update')
                    upsert = config.get('upsert', False)
                    
                    result = collection.update_one(filter_query, update_data, upsert=upsert)
                    return {
                        'matched_count': result.matched_count,
                        'modified_count': result.modified_count,
                        'upserted_id': str(result.upserted_id) if result.upserted_id else None,
                        'acknowledged': result.acknowledged
                    }
                
                elif operation == 'update_many':
                    filter_query = config.get('filter', {})
                    update_data = config.get('update')
                    upsert = config.get('upsert', False)
                    
                    result = collection.update_many(filter_query, update_data, upsert=upsert)
                    return {
                        'matched_count': result.matched_count,
                        'modified_count': result.modified_count,
                        'upserted_id': str(result.upserted_id) if result.upserted_id else None,
                        'acknowledged': result.acknowledged
                    }
                
                elif operation == 'replace_one':
                    filter_query = config.get('filter', {})
                    replacement = config.get('replacement')
                    upsert = config.get('upsert', False)
                    
                    result = collection.replace_one(filter_query, replacement, upsert=upsert)
                    return {
                        'matched_count': result.matched_count,
                        'modified_count': result.modified_count,
                        'upserted_id': str(result.upserted_id) if result.upserted_id else None,
                        'acknowledged': result.acknowledged
                    }
                
                elif operation == 'delete_one':
                    filter_query = config.get('filter', {})
                    result = collection.delete_one(filter_query)
                    return {
                        'deleted_count': result.deleted_count,
                        'acknowledged': result.acknowledged
                    }
                
                elif operation == 'delete_many':
                    filter_query = config.get('filter', {})
                    result = collection.delete_many(filter_query)
                    return {
                        'deleted_count': result.deleted_count,
                        'acknowledged': result.acknowledged
                    }
                
                elif operation == 'count_documents':
                    filter_query = config.get('filter', {})
                    result = collection.count_documents(filter_query)
                    return result
                
                elif operation == 'create_index':
                    index_spec = config.get('index')
                    options = config.get('options', {})
                    result = collection.create_index(index_spec, **options)
                    return result
                
                elif operation == 'drop_index':
                    index_name = config.get('index')
                    collection.drop_index(index_name)
                    return f"索引 {index_name} 已删除"
                
                elif operation == 'drop_indexes':
                    collection.drop_indexes()
                    return "所有索引已删除"
                
                elif operation == 'list_indexes':
                    return list(collection.list_indexes())
                
                elif operation == 'aggregate':
                    pipeline = config.get('pipeline')
                    result = collection.aggregate(pipeline)
                    return list(result)
                
                elif operation == 'distinct':
                    field = config.get('field')
                    filter_query = config.get('filter', {})
                    result = collection.distinct(field, filter_query)
                    return result
                
                elif operation == 'bulk_write':
                    operations = config.get('documents')  # 这里应该是操作列表
                    result = collection.bulk_write(operations)
                    return {
                        'inserted_count': result.inserted_count,
                        'matched_count': result.matched_count,
                        'modified_count': result.modified_count,
                        'deleted_count': result.deleted_count,
                        'upserted_count': result.upserted_count,
                        'upserted_ids': [str(id) for id in result.upserted_ids]
                    }
                
                else:
                    raise ValueError(f"不支持的 MongoDB 操作: {operation}")
        
        except Exception as e:
            raise ExecutionError(
                message=f"MongoDB 操作 {operation} 执行失败: {str(e)}",
                operation=f"mongodb_{operation}",
                original_error=e
            )
    
    def get_processor_type(self) -> str:
        """获取处理器类型"""
        return self.processor_type
    
    def get_processor_name(self) -> str:
        """获取处理器名称"""
        return self.processor_name
    
    def get_processor_description(self) -> str:
        """获取处理器描述"""
        return self.processor_description
    
    def get_required_config_keys(self) -> list:
        """获取必需的配置键"""
        return ['operation', 'database']
    
    def get_optional_config_keys(self) -> list:
        """获取可选的配置键"""
        return [
            'connection_string', 'host', 'port', 'username', 'password', 'timeout',
            'collection', 'document', 'documents', 'filter', 'update', 'replacement',
            'projection', 'sort', 'limit', 'skip', 'upsert', 'index', 'options',
            'pipeline', 'field', 'output_variable'
        ]
