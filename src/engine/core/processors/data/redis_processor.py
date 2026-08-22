"""
Redis 处理器

支持基本的 Redis 操作：
- 字符串操作 (GET, SET, DEL, EXISTS)
- 哈希操作 (HGET, HSET, HDEL, HGETALL)
- 列表操作 (LPUSH, RPUSH, LPOP, RPOP, LLEN)
- 集合操作 (SADD, SREM, SMEMBERS, SISMEMBER)
- 有序集合操作 (ZADD, ZREM, ZRANGE, ZSCORE)
- 键操作 (KEYS, EXPIRE, TTL, TYPE)
- 事务操作 (MULTI, EXEC, DISCARD)
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
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("[RedisProcessor] redis 模块未安装，请运行: pip install redis")


@register_processor(
    processor_type="redis",
    category=ProcessorCategory.DATA,
    description="Redis缓存处理器，支持字符串、哈希、列表、集合等操作",
    tags={"redis", "cache", "database", "data"},
    enabled=True,
    priority=55,
    dependencies=["redis"],
    version="1.0.0",
    author="Aegis Team"
)
class RedisProcessor(BaseProcessor):
    """Redis 处理器"""
    
    def __init__(self):
        super().__init__()
        self.processor_type = "redis"
        self.processor_name = "Redis 数据库处理器"
        self.processor_description = "支持 Redis 数据库的基本操作，包括字符串、哈希、列表、集合等"
    
    def _get_config_schema_name(self) -> str:
        """获取配置模式名称"""
        return "redis"
    
    def _validate_specific_config(self, config: Dict[str, Any]) -> bool:
        """Redis 特定的配置验证"""
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
        if not REDIS_AVAILABLE:
            # 可选校验：仅提示，不阻断（执行阶段会因依赖缺失失败）
            logger.warning("[RedisProcessor] redis 模块未安装，运行时将无法连接 Redis。请运行: pip install redis")
        
        # 检查操作类型
        operation = config.get('operation')
        if not operation:
            logger.warning("[RedisProcessor] 未指定 operation，将在执行阶段校验并可能失败")
        
        # 验证操作类型
        valid_operations = [
            # 字符串操作
            'get', 'set', 'del', 'exists', 'incr', 'decr', 'expire', 'ttl',
            # 哈希操作
            'hget', 'hset', 'hdel', 'hgetall', 'hkeys', 'hvals', 'hlen',
            # 列表操作
            'lpush', 'rpush', 'lpop', 'rpop', 'llen', 'lrange', 'lindex',
            # 集合操作
            'sadd', 'srem', 'smembers', 'sismember', 'scard', 'sunion', 'sinter',
            # 有序集合操作
            'zadd', 'zrem', 'zrange', 'zscore', 'zcard', 'zrank', 'zrevrank',
            # 键操作
            'keys', 'type', 'rename', 'move',
            # 事务操作
            'multi', 'exec', 'discard', 'watch', 'unwatch'
        ]
        
        if operation and operation not in valid_operations:
            logger.warning(f"[RedisProcessor] 不支持的 Redis 操作: {operation}，执行阶段将失败")
        
        # 验证连接参数
        self._validate_connection_config(config)
        
        # 根据操作类型验证特定参数
        if operation:
            try:
                self._validate_operation_params(operation, config)
            except ValidationError as e:
                # 可选校验：降级为警告
                logger.warning(f"[RedisProcessor] 配置校验警告: {e.message}")
        
        return None
    
    def _validate_connection_config(self, config: Dict[str, Any]) -> None:
        """验证连接配置"""
        # 验证主机
        host = config.get('host', 'localhost')
        if not isinstance(host, str):
            logger.warning(f"[RedisProcessor] host 应为字符串，当前类型为 {type(host)}")
        
        # 验证端口
        port = config.get('port', 6379)
        if not isinstance(port, (int, str)):
            logger.warning(f"[RedisProcessor] port 应为整数或数字字符串，当前类型为 {type(port)}")
        
        try:
            port_int = int(port)
            if not (1 <= port_int <= 65535):
                logger.warning("[RedisProcessor] port 应在 1-65535 范围内")
        except ValueError:
            logger.warning("[RedisProcessor] port 无法转换为整数")
        
        # 验证数据库
        db = config.get('db', 0)
        if not isinstance(db, (int, str)):
            logger.warning(f"[RedisProcessor] db 应为整数或数字字符串，当前类型为 {type(db)}")
        
        try:
            db_int = int(db)
            if db_int < 0:
                logger.warning("[RedisProcessor] db 不能为负数")
        except ValueError:
            logger.warning("[RedisProcessor] db 无法转换为整数")
        
        # 验证超时时间
        timeout = config.get('timeout', 30)
        if not isinstance(timeout, (int, float, str)):
            logger.warning(f"[RedisProcessor] timeout 应为数字或数字字符串，当前类型为 {type(timeout)}")
        
        try:
            timeout_float = float(timeout)
            if timeout_float <= 0:
                logger.warning("[RedisProcessor] timeout 应大于 0")
        except ValueError:
            logger.warning("[RedisProcessor] timeout 无法转换为数字")
    
    def _validate_operation_params(self, operation: str, config: Dict[str, Any]) -> None:
        """根据操作类型验证特定参数"""
        if operation in ['get', 'del', 'exists', 'expire', 'ttl', 'type', 'rename', 'move']:
            # 需要 key 参数
            if 'key' not in config:
                raise ValidationError(
                    message=f"{operation} 操作需要 key 参数",
                    field_name="key",
                    field_value=None,
                    validation_rule="required"
                )
        
        elif operation in ['set', 'incr', 'decr']:
            # 需要 key 参数
            if 'key' not in config:
                raise ValidationError(
                    message=f"{operation} 操作需要 key 参数",
                    field_name="key",
                    field_value=None,
                    validation_rule="required"
                )
            
            # set 操作需要 value 参数
            if operation == 'set' and 'value' not in config:
                raise ValidationError(
                    message="set 操作需要 value 参数",
                    field_name="value",
                    field_value=None,
                    validation_rule="required"
                )
        
        elif operation in ['hget', 'hdel', 'hlen']:
            # 需要 key 和 field 参数
            if 'key' not in config:
                raise ValidationError(
                    message=f"{operation} 操作需要 key 参数",
                    field_name="key",
                    field_value=None,
                    validation_rule="required"
                )
            if 'field' not in config:
                raise ValidationError(
                    message=f"{operation} 操作需要 field 参数",
                    field_name="field",
                    field_value=None,
                    validation_rule="required"
                )
        
        elif operation in ['hset', 'hgetall', 'hkeys', 'hvals']:
            # 需要 key 参数
            if 'key' not in config:
                raise ValidationError(
                    message=f"{operation} 操作需要 key 参数",
                    field_name="key",
                    field_value=None,
                    validation_rule="required"
                )
            
            # hset 操作需要 field 和 value 参数
            if operation == 'hset':
                if 'field' not in config:
                    raise ValidationError(
                        message="hset 操作需要 field 参数",
                        field_name="field",
                        field_value=None,
                        validation_rule="required"
                    )
                if 'value' not in config:
                    raise ValidationError(
                        message="hset 操作需要 value 参数",
                        field_name="value",
                        field_value=None,
                        validation_rule="required"
                    )
        
        elif operation in ['lpush', 'rpush', 'llen', 'lrange', 'lindex']:
            # 需要 key 参数
            if 'key' not in config:
                raise ValidationError(
                    message=f"{operation} 操作需要 key 参数",
                    field_name="key",
                    field_value=None,
                    validation_rule="required"
                )
            
            # lpush, rpush 操作需要 values 参数
            if operation in ['lpush', 'rpush'] and 'values' not in config:
                raise ValidationError(
                    message=f"{operation} 操作需要 values 参数",
                    field_name="values",
                    field_value=None,
                    validation_rule="required"
                )
        
        elif operation in ['sadd', 'srem', 'smembers', 'sismember', 'scard']:
            # 需要 key 参数
            if 'key' not in config:
                raise ValidationError(
                    message=f"{operation} 操作需要 key 参数",
                    field_name="key",
                    field_value=None,
                    validation_rule="required"
                )
            
            # sadd, srem 操作需要 values 参数
            if operation in ['sadd', 'srem'] and 'values' not in config:
                raise ValidationError(
                    message=f"{operation} 操作需要 values 参数",
                    field_name="values",
                    field_value=None,
                    validation_rule="required"
                )
            
            # sismember 操作需要 value 参数
            if operation == 'sismember' and 'value' not in config:
                raise ValidationError(
                    message="sismember 操作需要 value 参数",
                    field_name="value",
                    field_value=None,
                    validation_rule="required"
                )
        
        elif operation in ['zadd', 'zrem', 'zrange', 'zscore', 'zcard', 'zrank', 'zrevrank']:
            # 需要 key 参数
            if 'key' not in config:
                raise ValidationError(
                    message=f"{operation} 操作需要 key 参数",
                    field_name="key",
                    field_value=None,
                    validation_rule="required"
                )
            
            # zadd 操作需要 members 参数
            if operation == 'zadd' and 'members' not in config:
                raise ValidationError(
                    message="zadd 操作需要 members 参数",
                    field_name="members",
                    field_value=None,
                    validation_rule="required"
                )
            
            # zrem 操作需要 members 参数
            if operation == 'zrem' and 'members' not in config:
                raise ValidationError(
                    message="zrem 操作需要 members 参数",
                    field_name="members",
                    field_value=None,
                    validation_rule="required"
                )
            
            # zscore 操作需要 member 参数
            if operation == 'zscore' and 'member' not in config:
                raise ValidationError(
                    message="zscore 操作需要 member 参数",
                    field_name="member",
                    field_value=None,
                    validation_rule="required"
                )
    
    def execute(self, config: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        """
        执行 Redis 操作
        
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
            logger.info(f"[RedisProcessor] 开始执行 Redis 操作: {operation}")
            
            # 创建 Redis 连接
            redis_client = self._create_redis_client(rendered_config)
            
            # 执行操作
            result = self._execute_operation(redis_client, rendered_config)
            duration = time.time() - start_time
            
            # 保存结果到上下文
            output_variable = rendered_config.get('output_variable')
            if output_variable and context and hasattr(context, 'set_variable'):
                context.set_variable(output_variable, result)
            
            logger.info(f"[RedisProcessor] Redis 操作 {operation} 执行成功")
            
            # 使用标准响应格式
            return ResponseBuilder.success(
                processor_type="redis",
                body=result,
                message=f"{operation} 操作成功",
                status_code=200,
                metadata={
                    "operation": operation,
                    "key": rendered_config.get('key', '')
                },
                duration=duration
            ).to_dict()
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"[RedisProcessor] Redis 操作执行失败: {str(e)}")
            return ResponseBuilder.error(
                processor_type="redis",
                error=f"Redis 操作执行失败: {str(e)}",
                error_code="REDIS_ERROR",
                status_code=500,
                duration=duration
            ).to_dict()
    
    def _create_redis_client(self, config: Dict[str, Any]):
        """创建 Redis 客户端"""
        host = config.get('host', 'localhost')
        port = int(config.get('port', 6379))
        db = int(config.get('db', 0))
        password = config.get('password')
        timeout = float(config.get('timeout', 30))
        
        # 创建连接参数
        connection_params = {
            'host': host,
            'port': port,
            'db': db,
            'decode_responses': True,  # 自动解码响应
            'socket_timeout': timeout,
            'socket_connect_timeout': timeout,
        }
        
        if password:
            connection_params['password'] = password
        
        # 创建 Redis 客户端
        redis_client = redis.Redis(**connection_params)
        
        # 测试连接
        try:
            redis_client.ping()
            logger.debug(f"[RedisProcessor] 成功连接到 Redis: {host}:{port}/{db}")
        except Exception as e:
            raise ExecutionError(
                message=f"无法连接到 Redis 服务器: {str(e)}",
                operation="redis_connection",
                original_error=e
            )
        
        return redis_client
    
    def _execute_operation(self, redis_client, config: Dict[str, Any]) -> Any:
        """执行 Redis 操作"""
        operation = config.get('operation')
        
        try:
            if operation == 'get':
                return redis_client.get(config['key'])
            
            elif operation == 'set':
                value = config['value']
                # 如果 value 是字典或列表，转换为 JSON 字符串
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                return redis_client.set(config['key'], value)
            
            elif operation == 'del':
                return redis_client.delete(config['key'])
            
            elif operation == 'exists':
                return redis_client.exists(config['key'])
            
            elif operation == 'incr':
                return redis_client.incr(config['key'])
            
            elif operation == 'decr':
                return redis_client.decr(config['key'])
            
            elif operation == 'expire':
                seconds = int(config.get('seconds', 3600))
                return redis_client.expire(config['key'], seconds)
            
            elif operation == 'ttl':
                return redis_client.ttl(config['key'])
            
            elif operation == 'type':
                return redis_client.type(config['key'])
            
            elif operation == 'rename':
                new_key = config.get('new_key')
                if not new_key:
                    raise ValueError("rename 操作需要 new_key 参数")
                return redis_client.rename(config['key'], new_key)
            
            elif operation == 'move':
                db = int(config.get('target_db', 1))
                return redis_client.move(config['key'], db)
            
            elif operation == 'keys':
                pattern = config.get('pattern', '*')
                return redis_client.keys(pattern)
            
            elif operation == 'hget':
                return redis_client.hget(config['key'], config['field'])
            
            elif operation == 'hset':
                value = config['value']
                # 如果 value 是字典或列表，转换为 JSON 字符串
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                return redis_client.hset(config['key'], config['field'], value)
            
            elif operation == 'hdel':
                return redis_client.hdel(config['key'], config['field'])
            
            elif operation == 'hgetall':
                return redis_client.hgetall(config['key'])
            
            elif operation == 'hkeys':
                return redis_client.hkeys(config['key'])
            
            elif operation == 'hvals':
                return redis_client.hvals(config['key'])
            
            elif operation == 'hlen':
                return redis_client.hlen(config['key'])
            
            elif operation == 'lpush':
                values = config['values']
                if not isinstance(values, list):
                    values = [values]
                return redis_client.lpush(config['key'], *values)
            
            elif operation == 'rpush':
                values = config['values']
                if not isinstance(values, list):
                    values = [values]
                return redis_client.rpush(config['key'], *values)
            
            elif operation == 'lpop':
                return redis_client.lpop(config['key'])
            
            elif operation == 'rpop':
                return redis_client.rpop(config['key'])
            
            elif operation == 'llen':
                return redis_client.llen(config['key'])
            
            elif operation == 'lrange':
                start = int(config.get('start', 0))
                end = int(config.get('end', -1))
                return redis_client.lrange(config['key'], start, end)
            
            elif operation == 'lindex':
                index = int(config.get('index', 0))
                return redis_client.lindex(config['key'], index)
            
            elif operation == 'sadd':
                values = config['values']
                if not isinstance(values, list):
                    values = [values]
                return redis_client.sadd(config['key'], *values)
            
            elif operation == 'srem':
                values = config['values']
                if not isinstance(values, list):
                    values = [values]
                return redis_client.srem(config['key'], *values)
            
            elif operation == 'smembers':
                return redis_client.smembers(config['key'])
            
            elif operation == 'sismember':
                return redis_client.sismember(config['key'], config['value'])
            
            elif operation == 'scard':
                return redis_client.scard(config['key'])
            
            elif operation == 'sunion':
                keys = config.get('keys', [])
                if not isinstance(keys, list):
                    keys = [keys]
                return redis_client.sunion(*keys)
            
            elif operation == 'sinter':
                keys = config.get('keys', [])
                if not isinstance(keys, list):
                    keys = [keys]
                return redis_client.sinter(*keys)
            
            elif operation == 'zadd':
                members = config['members']
                if isinstance(members, dict):
                    return redis_client.zadd(config['key'], members)
                elif isinstance(members, list):
                    return redis_client.zadd(config['key'], *members)
                else:
                    raise ValueError("zadd 操作的 members 参数必须是字典或列表")
            
            elif operation == 'zrem':
                members = config['members']
                if not isinstance(members, list):
                    members = [members]
                return redis_client.zrem(config['key'], *members)
            
            elif operation == 'zrange':
                start = int(config.get('start', 0))
                end = int(config.get('end', -1))
                withscores = config.get('withscores', False)
                return redis_client.zrange(config['key'], start, end, withscores=withscores)
            
            elif operation == 'zscore':
                return redis_client.zscore(config['key'], config['member'])
            
            elif operation == 'zcard':
                return redis_client.zcard(config['key'])
            
            elif operation == 'zrank':
                return redis_client.zrank(config['key'], config['member'])
            
            elif operation == 'zrevrank':
                return redis_client.zrevrank(config['key'], config['member'])
            
            else:
                raise ValueError(f"不支持的 Redis 操作: {operation}")
        
        except Exception as e:
            raise ExecutionError(
                message=f"Redis 操作 {operation} 执行失败: {str(e)}",
                operation=f"redis_{operation}",
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
        return ['operation']
    
    def get_optional_config_keys(self) -> list:
        """获取可选的配置键"""
        return [
            'host', 'port', 'db', 'password', 'timeout',
            'key', 'field', 'value', 'values', 'members', 'member',
            'new_key', 'target_db', 'pattern', 'seconds',
            'start', 'end', 'index', 'withscores', 'keys',
            'output_variable'
        ]
