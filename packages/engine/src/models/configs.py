# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName
@className Configs
@describe 节点配置类
"""

from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class BaseConfig(ABC):
    """配置基类"""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {}
        for key, value in self.__dict__.items():
            if value is not None:
                result[key] = value
        return result
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseConfig':
        """从字典创建配置"""
        pass


@dataclass
class ExtractionRule:
    """变量提取规则"""
    var_name: str = None  # 变量名
    source_path: str = None  # 源路径
    type: str = "jsonpath"  # 提取类型: jsonpath, xpath, regex, jmespath
    default: Any = None  # 默认值
    name: Optional[str] = None  # 变量名（var_name的别名）
    path: Optional[str] = None  # 路径（source_path的别名）

    def __post_init__(self):
        # 兼容：支持name作为var_name的别名
        if not self.var_name and self.name:
            self.var_name = self.name
        # 兼容：支持path作为source_path的别名
        if not self.source_path and self.path:
            self.source_path = self.path
        # 验证必填字段
        if not self.var_name:
            raise ValueError("var_name 或 name 必须提供其中一个")
        if not self.source_path:
            raise ValueError("source_path 或 path 必须提供其中一个")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "var_name": self.var_name,
            "source_path": self.source_path,
            "type": self.type
        }
        if self.default is not None:
            result["default"] = self.default
        # 同时输出别名以兼容
        if self.name:
            result["name"] = self.name
        if self.path:
            result["path"] = self.path
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExtractionRule':
        """从字典创建"""
        kwargs = {k: v for k, v in data.items() if k in ['var_name', 'source_path', 'type', 'default', 'name', 'path']}
        return cls(**kwargs)


@dataclass
class AssertionRule:
    """断言规则"""
    source: str = None  # 数据源字段
    operator: str = None  # 操作符: equals, not_equals, greater_than, less_than, contains, exists等
    target: Any = None  # 目标值
    message: Optional[str] = None  # 错误消息
    field: Optional[str] = None  # 字段名（source的别名）
    
    def __post_init__(self):
        # 兼容：如果只提供了field而没有source，使用field作为source
        if not self.source and self.field:
            self.source = self.field
        # 验证必填字段
        if not self.source:
            raise ValueError("source 或 field 必须提供其中一个")
        if not self.operator:
            raise ValueError("operator 是必填字段")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "source": self.source,
            "operator": self.operator
        }
        if self.target is not None:
            result["target"] = self.target
        if self.message:
            result["message"] = self.message
        if self.field:
            result["field"] = self.field
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssertionRule':
        """从字典创建"""
        # 提取所有相关字段
        kwargs = {k: v for k, v in data.items() if k in ['source', 'operator', 'target', 'message', 'field']}
        return cls(**kwargs)


@dataclass
class AssertionConfig(BaseConfig):
    """断言配置"""
    rules: List[Union[AssertionRule, Dict[str, Any]]] = None

    def __post_init__(self):
        if self.rules is None:
            self.rules = []
        # 转换字典为AssertionRule对象
        self.rules = [
            AssertionRule.from_dict(r) if isinstance(r, dict) else r
            for r in self.rules
        ]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "rules": [
                r.to_dict() if isinstance(r, AssertionRule) else r
                for r in self.rules
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssertionConfig':
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


@dataclass
class VariableExtractorConfig(BaseConfig):
    """变量提取配置"""
    extractions: List[Union[ExtractionRule, Dict[str, Any]]] = None

    def __post_init__(self):
        if self.extractions is None:
            self.extractions = []
        # 转换字典为ExtractionRule对象
        self.extractions = [
            ExtractionRule.from_dict(e) if isinstance(e, dict) else e
            for e in self.extractions
        ]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "extractions": [
                e.to_dict() if isinstance(e, ExtractionRule) else e
                for e in self.extractions
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VariableExtractorConfig':
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


@dataclass
class HttpConfig(BaseConfig):
    """
    HTTP请求配置
    
    参考 aegis-runner 的设计，支持完整的 HTTP 参数类型
    """
    # ========== 基础字段 ==========
    method: str = "GET"  # HTTP 方法: GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS
    url: str = ""  # 请求 URL
    
    # ========== URL 参数 ==========
    params: Optional[Dict[str, Any]] = None  # URL 查询参数 (?key=value)
    path_params: Optional[Dict[str, Any]] = None  # 路径参数 (/users/{userId})
    
    # ========== 请求头和 Cookie ==========
    headers: Optional[Dict[str, str]] = None  # 请求头
    cookies: Optional[Dict[str, str]] = None  # Cookies
    
    # ========== Body 数据（按优先级） ==========
    json: Optional[Union[Dict, List, str]] = None  # JSON 数据 (Content-Type: application/json)
    data: Optional[Union[Dict[str, Any], str]] = None  # 表单数据 (Content-Type: application/x-www-form-urlencoded)
    body: Optional[Any] = None  # 原始 body 数据 (如 XML, 纯文本)
    files: Optional[Dict[str, str]] = None  # 文件上传 (Content-Type: multipart/form-data)
    upload: Optional[Dict[str, Any]] = None  # 文件上传（upload 是 files 的别名）
    
    # ========== 请求配置 ==========
    timeout: Optional[Union[int, float]] = 120  # 超时时间（秒）
    verify: bool = True  # SSL 证书验证（verify_ssl 的别名）
    verify_ssl: Optional[bool] = None  # SSL 证书验证
    allow_redirects: bool = True  # 是否允许重定向
    follow_redirects: Optional[bool] = None  # 是否允许重定向（allow_redirects 的别名）
    
    # ========== 鉴权相关字段 ==========
    credential_id: Optional[str] = None  # 凭证中心的凭证ID
    credential: Optional[str] = None  # credential_id的别名
    auth: Optional[Dict[str, Any]] = None  # 节点级鉴权配置
    auth_config: Optional[Dict[str, Any]] = None  # auth 的别名
    
    # ========== 断言和提取 ==========
    assertion: Optional[AssertionConfig] = None
    extractions: Optional[List[ExtractionRule]] = None
    
    def __post_init__(self):
        """初始化后处理，处理别名字段"""
        # 处理 verify_ssl 别名
        if self.verify_ssl is not None:
            self.verify = self.verify_ssl
        
        # 处理 allow_redirects 别名
        if self.follow_redirects is not None:
            self.allow_redirects = self.follow_redirects
        
        # 处理 upload 别名（upload 是 files 的别名）
        if self.upload and not self.files:
            self.files = self.upload
        
        # 处理 auth_config 别名
        if self.auth_config and not self.auth:
            self.auth = self.auth_config
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HttpConfig':
        d = dict(data)
        if 'assertion' in d and isinstance(d['assertion'], dict):
            d['assertion'] = AssertionConfig.from_dict(d['assertion'])
        if 'extractions' in d:
            d['extractions'] = [ExtractionRule.from_dict(e) if isinstance(e, dict) else e for e in d['extractions']]
        return cls(**{k: v for k, v in d.items() if hasattr(cls, k)})


@dataclass
class DatabaseConnectionConfig(BaseConfig):
    """数据库连接配置"""
    host: str = "localhost"
    port: int = 3306
    user: str = ""
    password: str = ""
    database: str = ""
    charset: str = "utf8mb4"
    connect_timeout: int = 10
    read_timeout: int = 30
    write_timeout: int = 30
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DatabaseConnectionConfig':
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


@dataclass
class ConnectionPoolConfig(BaseConfig):
    """连接池配置"""
    min_connections: int = 2
    max_connections: int = 10
    idle_timeout: float = 300.0  # 空闲连接超时时间（秒），默认5分钟
    health_check_interval: float = 60.0  # 健康检查间隔（秒），默认1分钟
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConnectionPoolConfig':
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


@dataclass
class SqlConfig(BaseConfig):
    """SQL配置"""
    operation: str = "select"  # select, insert, update, delete, execute
    sql: str = ""
    sql_list: Optional[List[str]] = None  # 批量 SQL 执行列表
    query_type: Optional[str] = "fetchmany"  # 查询类型: fetchall, fetchone, fetchmany
    params: Optional[Union[List[Any], Dict[str, Any]]] = None
    connection: Optional[Union[DatabaseConnectionConfig, Dict[str, Any]]] = None
    pool: Optional[Union[ConnectionPoolConfig, Dict[str, Any]]] = None
    batch_config: Optional[Dict[str, Any]] = None  # 批量执行配置
    
    assertion: Optional[AssertionConfig] = None
    extractions: Optional[List[ExtractionRule]] = None
    
    def __post_init__(self):
        if self.connection and isinstance(self.connection, dict):
            self.connection = DatabaseConnectionConfig.from_dict(self.connection)
        if self.pool and isinstance(self.pool, dict):
            self.pool = ConnectionPoolConfig.from_dict(self.pool)
        if self.assertion and isinstance(self.assertion, dict):
            self.assertion = AssertionConfig.from_dict(self.assertion)
        if self.extractions:
            self.extractions = [ExtractionRule.from_dict(e) if isinstance(e, dict) else e for e in self.extractions]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {}
        for key, value in self.__dict__.items():
            if value is not None:
                if key == 'connection' and isinstance(value, DatabaseConnectionConfig):
                    result[key] = value.to_dict()
                elif key == 'pool' and isinstance(value, ConnectionPoolConfig):
                    result[key] = value.to_dict()
                elif key == 'assertion' and isinstance(value, AssertionConfig):
                    result[key] = value.to_dict()
                elif key == 'extractions' and isinstance(value, list):
                    result[key] = [e.to_dict() if hasattr(e, 'to_dict') else e for e in value]
                else:
                    result[key] = value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SqlConfig':
        d = dict(data)
        if 'assertion' in d and isinstance(d['assertion'], dict):
            d['assertion'] = AssertionConfig.from_dict(d['assertion'])
        if 'extractions' in d:
            d['extractions'] = [ExtractionRule.from_dict(e) if isinstance(e, dict) else e for e in d['extractions']]
        return cls(**{k: v for k, v in d.items() if hasattr(cls, k)})


@dataclass
class ScriptConfig(BaseConfig):
    """脚本配置"""
    script: str = ""
    script_type: str = "python"  # python, expression, function
    function_name: Optional[str] = None
    
    # ========== 断言和提取 ==========
    assertion: Optional[AssertionConfig] = None
    extractions: Optional[List[ExtractionRule]] = None
    
    def __post_init__(self):
        """初始化后处理，处理断言和提取配置"""
        if self.assertion and isinstance(self.assertion, dict):
            self.assertion = AssertionConfig.from_dict(self.assertion)
        if self.extractions:
            self.extractions = [ExtractionRule.from_dict(e) if isinstance(e, dict) else e for e in self.extractions]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {}
        for key, value in self.__dict__.items():
            if value is not None:
                if key == 'assertion' and isinstance(value, AssertionConfig):
                    result[key] = value.to_dict()
                elif key == 'extractions' and isinstance(value, list):
                    result[key] = [e.to_dict() if hasattr(e, 'to_dict') else e for e in value]
                else:
                    result[key] = value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScriptConfig':
        d = dict(data)
        if 'assertion' in d and isinstance(d['assertion'], dict):
            d['assertion'] = AssertionConfig.from_dict(d['assertion'])
        if 'extractions' in d:
            d['extractions'] = [ExtractionRule.from_dict(e) if isinstance(e, dict) else e for e in d['extractions']]
        return cls(**{k: v for k, v in d.items() if hasattr(cls, k)})


@dataclass
class LogConfig(BaseConfig):
    """日志配置"""
    message: str = ""
    level: str = "INFO"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LogConfig':
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


@dataclass
class ConditionConfig(BaseConfig):
    """条件配置"""
    expression: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConditionConfig':
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


@dataclass
class Viewport:
    """浏览器视口配置"""
    width: int = 1920
    height: int = 1080
    
    def to_dict(self) -> Dict[str, int]:
        """转换为字典"""
        return {
            "width": self.width,
            "height": self.height
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> 'Viewport':
        """从字典创建"""
        return cls(**{k: v for k, v in data.items() if k in ['width', 'height']})


@dataclass
class OssConfig(BaseConfig):
    """
    OSS 对象存储配置
    
    支持操作：
    - upload: 上传文件
    - upload_stream: 上传文件流
    - download: 下载文件
    - delete: 删除文件
    """
    # ========== 基础配置 ==========
    operation: str = "download"  # 操作类型: upload, upload_stream, download, delete
    access_key_id: str = ""  # OSS Access Key ID
    access_key_secret: str = ""  # OSS Access Key Secret
    endpoint: str = ""  # OSS Endpoint，如: https://oss-cn-hangzhou.aliyuncs.com
    bucket: str = ""  # Bucket 名称
    
    # ========== 路径配置 ==========
    oss_path: Optional[str] = None  # OSS 文件路径
    local_path: Optional[str] = None  # 本地文件路径
    
    # ========== 上传流配置 ==========
    content: Optional[Union[str, bytes]] = None  # 文件流内容（upload_stream 使用）
    
    # ========== 输出配置 ==========
    output_variable: Optional[str] = None  # 输出变量名
    
    # ========== 断言和提取 ==========
    assertion: Optional[AssertionConfig] = None
    extractions: Optional[List[ExtractionRule]] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OssConfig':
        d = dict(data)
        if 'assertion' in d and isinstance(d['assertion'], dict):
            d['assertion'] = AssertionConfig.from_dict(d['assertion'])
        if 'extractions' in d:
            d['extractions'] = [ExtractionRule.from_dict(e) if isinstance(e, dict) else e for e in d['extractions']]
        return cls(**{k: v for k, v in d.items() if hasattr(cls, k)})


@dataclass
class XxlJobConfig(BaseConfig):
    """
    XXL-Job 任务调度配置
    通过 Handler 名称触发任务
    """
    # ========== 任务配置 ==========
    executor_handler: str = ""  # 执行器 Handler（必需）
    executor_param: str = ""  # 执行参数（JSON 字符串）
    site_tenant: str = "DEFAULT"  # 站点租户
    address_list: str = ""  # 执行器地址列表（注意：字段名从 address 改为 address_list）

    # ========== 输出配置 ==========
    output_variable: Optional[str] = None  # 输出变量名
    # ========== 断言和提取 ==========
    assertion: Optional[AssertionConfig] = None
    extractions: Optional[List[ExtractionRule]] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'XxlJobConfig':
        d = dict(data)
        if 'assertion' in d and isinstance(d['assertion'], dict):
            d['assertion'] = AssertionConfig.from_dict(d['assertion'])
        if 'extractions' in d:
            d['extractions'] = [ExtractionRule.from_dict(e) if isinstance(e, dict) else e for e in d['extractions']]
        return cls(**{k: v for k, v in d.items() if hasattr(cls, k)})


@dataclass
class MqConfig(BaseConfig):
    """消息队列配置"""
    topic: str = ""
    message_body: str = ""
    mq_url: str = "dev"
    site_tenant: str = "default"
    tag: str = "*"
    key: str = "*"

    assertion: Optional[AssertionConfig] = None
    extractions: Optional[List[ExtractionRule]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MqConfig':
        d = dict(data)
        if 'assertion' in d and isinstance(d['assertion'], dict):
            d['assertion'] = AssertionConfig.from_dict(d['assertion'])
        if 'extractions' in d:
            d['extractions'] = [ExtractionRule.from_dict(e) if isinstance(e, dict) else e for e in d['extractions']]
        return cls(**{k: v for k, v in d.items() if hasattr(cls, k)})


@dataclass
class SubWorkflowConfig(BaseConfig):
    """子工作流配置"""
    workflow_file: Optional[str] = None  # 工作流文件路径
    workflow_data: Optional[Dict[str, Any]] = None  # 工作流数据
    workflow_name: Optional[str] = None  # 工作流名称（用于从注册表获取）
    input_mapping: Optional[Dict[str, str]] = None  # 输入变量映射
    output_mapping: Optional[Dict[str, str]] = None  # 输出变量映射
    timeout: Optional[int] = None  # 超时时间（秒）
    error_handling: str = "stop_on_error"  # 错误处理策略
    parallel: bool = False  # 是否并行执行
    
    def __post_init__(self):
        if self.input_mapping is None:
            self.input_mapping = {}
        if self.output_mapping is None:
            self.output_mapping = {}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SubWorkflowConfig':
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


@dataclass
class LoopConfig(BaseConfig):
    """循环控制器配置"""
    loop_type: str = ""  # count_loop, while_loop, foreach_loop
    count: Optional[Union[int, str]] = None  # 次数循环的执行次数
    condition: Optional[str] = None  # While 循环的条件表达式
    max_iterations: Optional[Union[int, str]] = None  # While 循环的最大迭代次数
    items: Optional[Union[List[Any], str]] = None  # ForEach 循环的遍历集合
    item_variable: str = "item"  # ForEach 循环中当前项目的变量名
    index_variable: str = "index"  # ForEach 循环中当前索引的变量名
    sub_nodes: Optional[List[Dict[str, Any]]] = None  # 循环内执行的子节点列表
    delay: Optional[Union[float, str]] = None  # 每次循环之间的延迟时间（秒）
    output_variable: str = "loop_result"  # 保存循环结果的变量名
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LoopConfig':
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


@dataclass
class RedisConfig(BaseConfig):
    """Redis 处理器配置"""
    operation: str = ""  # Redis 操作类型
    host: str = "localhost"  # Redis 服务器地址
    port: Union[int, str] = 6379  # Redis 服务器端口
    db: Union[int, str] = 0  # 数据库编号
    password: Optional[str] = None  # 认证密码
    timeout: Union[float, str] = 30  # 连接超时时间（秒）
    key: Optional[str] = None  # 键名
    field: Optional[str] = None  # 字段名（哈希操作）
    value: Optional[Any] = None  # 值
    values: Optional[List[Any]] = None  # 值列表
    members: Optional[Union[Dict[str, Any], List[Any]]] = None  # 成员（有序集合）
    member: Optional[str] = None  # 成员名（有序集合）
    new_key: Optional[str] = None  # 新键名（重命名）
    target_db: Union[int, str] = 1  # 目标数据库（移动）
    pattern: str = "*"  # 键模式（KEYS 操作）
    seconds: Union[int, str] = 3600  # 过期时间（秒）
    start: Union[int, str] = 0  # 起始位置
    end: Union[int, str] = -1  # 结束位置
    index: Union[int, str] = 0  # 索引位置
    withscores: bool = False  # 是否包含分数（有序集合）
    keys: Optional[List[str]] = None  # 键列表（集合运算）
    output_variable: Optional[str] = None  # 保存结果的变量名
    
    assertion: Optional[AssertionConfig] = None
    extractions: Optional[List[ExtractionRule]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RedisConfig':
        d = dict(data)
        if 'assertion' in d and isinstance(d['assertion'], dict):
            d['assertion'] = AssertionConfig.from_dict(d['assertion'])
        if 'extractions' in d:
            d['extractions'] = [ExtractionRule.from_dict(e) if isinstance(e, dict) else e for e in d['extractions']]
        return cls(**{k: v for k, v in d.items() if hasattr(cls, k)})


@dataclass
class MongoDBConfig(BaseConfig):
    """MongoDB 处理器配置"""
    operation: str = ""  # MongoDB 操作类型
    database: str = ""  # 数据库名称
    connection_string: Optional[str] = None  # MongoDB 连接字符串
    host: str = "localhost"  # MongoDB 服务器地址
    port: Union[int, str] = 27017  # MongoDB 服务器端口
    username: Optional[str] = None  # 用户名
    password: Optional[str] = None  # 密码
    timeout: Union[float, str] = 30  # 连接超时时间（秒）
    collection: Optional[str] = None  # 集合名称
    document: Optional[Dict[str, Any]] = None  # 文档数据（单个）
    documents: Optional[List[Dict[str, Any]]] = None  # 文档数据（多个）
    filter: Optional[Dict[str, Any]] = None  # 查询条件
    update: Optional[Dict[str, Any]] = None  # 更新数据
    replacement: Optional[Dict[str, Any]] = None  # 替换数据
    projection: Optional[Dict[str, Any]] = None  # 投影字段
    sort: Optional[List[tuple]] = None  # 排序规则
    limit: Union[int, str] = 0  # 限制数量
    skip: Union[int, str] = 0  # 跳过数量
    upsert: bool = False  # 是否插入不存在文档
    index: Optional[Union[List[tuple], str]] = None  # 索引规范
    options: Optional[Dict[str, Any]] = None  # 操作选项
    pipeline: Optional[List[Dict[str, Any]]] = None  # 聚合管道
    field: Optional[str] = None  # 字段名（distinct）
    output_variable: Optional[str] = None  # 保存结果的变量名
    
    assertion: Optional[AssertionConfig] = None
    extractions: Optional[List[ExtractionRule]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MongoDBConfig':
        d = dict(data)
        if 'assertion' in d and isinstance(d['assertion'], dict):
            d['assertion'] = AssertionConfig.from_dict(d['assertion'])
        if 'extractions' in d:
            d['extractions'] = [ExtractionRule.from_dict(e) if isinstance(e, dict) else e for e in d['extractions']]
        return cls(**{k: v for k, v in d.items() if hasattr(cls, k)})


@dataclass
class UIConfig(BaseConfig):
    """UI处理器通用配置"""
    operation: Optional[str] = None
    selector: Optional[str] = None
    selector_type: str = "css"
    timeout: int = 30000
    browser_type: str = "chromium"
    headless: bool = False
    viewport: Optional[Union[Viewport, Dict[str, int]]] = None
    args: Optional[List[str]] = None
    
    # Midscene AI 自动化相关字段
    action_type: Optional[str] = None
    natural_language_command: Optional[str] = None
    data_structure: Optional[Dict[str, Any]] = None
    url: Optional[str] = None
    
    def __post_init__(self):
        # 转换字典为Viewport对象
        if self.viewport and isinstance(self.viewport, dict):
            self.viewport = Viewport.from_dict(self.viewport)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {}
        for key, value in self.__dict__.items():
            if value is not None:
                if key == 'viewport' and isinstance(value, Viewport):
                    result[key] = value.to_dict()
                else:
                    result[key] = value
            # 对于 Midscene 相关字段，即使为 None 也要包含
            elif key in ['action_type', 'natural_language_command', 'data_structure', 'url']:
                result[key] = value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UIConfig':
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


@dataclass
class DubboConfig(BaseConfig):
    url: str
    application_name: Optional[str] = None
    interface_name: str = ""
    method_name: str = ""
    params: Optional[list] = None
    site_tenant: str = ""
    param_types: Optional[list] =None
    group: Optional[str] = None
    version: Optional[str] = None
    timeout: Optional[int] = None
    assertion: Optional[AssertionConfig] = None
    extractions: Optional[List[ExtractionRule]] = None
    def __post_init__(self):
        if self.assertion and isinstance(self.assertion, dict):
            self.assertion = AssertionConfig.from_dict(self.assertion)
        if self.extractions:
            self.extractions = [ExtractionRule.from_dict(e) if isinstance(e, dict) else e for e in self.extractions]
    def to_dict(self):
        d = super().to_dict()
        if self.assertion:
            d['assertion'] = self.assertion.to_dict() if hasattr(self.assertion, 'to_dict') else self.assertion
        if self.extractions:
            d['extractions'] = [e.to_dict() if hasattr(e, 'to_dict') else e for e in self.extractions]
        return d
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DubboConfig':
        d = dict(data)
        if 'assertion' in d and isinstance(d['assertion'], dict):
            d['assertion'] = AssertionConfig.from_dict(d['assertion'])
        if 'extractions' in d:
            d['extractions'] = [ExtractionRule.from_dict(e) if isinstance(e, dict) else e for e in d['extractions']]
        return cls(**{k: v for k, v in d.items() if hasattr(cls, k)})


# 配置类型映射
CONFIG_TYPE_MAP = {
    'http_request': HttpConfig,
    'mysql': SqlConfig,
    'script': ScriptConfig,
    'log_message': LogConfig,
    'assertion': AssertionConfig,
    'variable_extractor': VariableExtractorConfig,
    'condition': ConditionConfig,
    'rocketmq': MqConfig,
    'sub_workflow': SubWorkflowConfig,
    'loop': LoopConfig,
    'redis': RedisConfig,
    'mongodb': MongoDBConfig,
    'oss': OssConfig,
    'xxljob': XxlJobConfig,
    
    # 新的统一UI处理器配置
    'ui_browser': UIConfig,
    'ui_element': UIConfig,
    'ui_navigation': UIConfig,
    'ui_screenshot': UIConfig,
    'ui_wait': UIConfig,
    'ui_validation': UIConfig,
    'ui_action': UIConfig,
    'ui_recording': UIConfig,
    'ui_advanced': UIConfig,
    
    # 遗留UI处理器配置（向后兼容）
    'browser_launch': UIConfig,
    'browser_close': UIConfig,
    'browser_new_page': UIConfig,
    'browser_switch_page': UIConfig,
    'element_click': UIConfig,
    'element_input': UIConfig,
    'element_get_text': UIConfig,
    'element_get_attribute': UIConfig,
    'element_hover': UIConfig,
    'element_double_click': UIConfig,
    'element_right_click': UIConfig,
    'element_select_option': UIConfig,
    'element_upload_file': UIConfig,
    'element_key_press': UIConfig,
    'page_navigate': UIConfig,
    'page_go_back': UIConfig,
    'page_go_forward': UIConfig,
    'page_refresh': UIConfig,
    'page_wait_for_url': UIConfig,
    'page_wait_for_load': UIConfig,
    'page_screenshot': UIConfig,
    'element_screenshot': UIConfig,
    'viewport_screenshot': UIConfig,
    'full_page_screenshot': UIConfig,
    'wait_for_element': UIConfig,
    'wait_for_text': UIConfig,
    'wait_for_url': UIConfig,
    'wait_for_network': UIConfig,
    'wait_for_condition': UIConfig,
    'wait_for_time': UIConfig,
    'wait_for_download': UIConfig,
    'wait_for_element_visualization': UIConfig,
    'wait_for_viewport_visualization': UIConfig,
    'wait_for_full_page_visualization': UIConfig,
    'wait_for_page_load': UIConfig,
    'wait_for_network_request': UIConfig,
    'validate_element_visible': UIConfig,
    'validate_element_not_visible': UIConfig,
    'validate_element_text': UIConfig,
    'validate_css_property': UIConfig,
    'validate_html_attribute': UIConfig,
    'validate_checkbox': UIConfig,
    'validate_radio_button': UIConfig,
    'validate_download': UIConfig,
    'validate_email': UIConfig,
    'validate_api_response': UIConfig,
    'validate_element_visualization': UIConfig,
    'validate_viewport_visualization': UIConfig,
    'validate_full_page_visualization': UIConfig,
    'validate_page_accessibility': UIConfig,
    'validate_element_accessibility': UIConfig,
    'validate_network_request': UIConfig,
    'validate_custom': UIConfig,
    'action_hover': UIConfig,
    'action_extract_value': UIConfig,
    'action_generate_email': UIConfig,
    'action_set_cookie': UIConfig,
    'action_get_cookie': UIConfig,
    'action_navigation': UIConfig,
    'action_custom': UIConfig,
    'action_cli': UIConfig,
    'action_api': UIConfig,
    'action_refresh': UIConfig,
    'action_generate_random': UIConfig,
    'action_generate_date': UIConfig,
    'action_drag_drop': UIConfig,
    'action_scroll': UIConfig,
    'action_key_press': UIConfig,
    'action_file_upload': UIConfig,
    'action_auto_scroll': UIConfig,
    'action_keyboard_shortcut': UIConfig,
    'recording_start': UIConfig,
    'recording_stop': UIConfig,
    'recording_pause': UIConfig,
    'recording_resume': UIConfig,
    'recording_click': UIConfig,
    'recording_double_click': UIConfig,
    'recording_right_click': UIConfig,
    'recording_scroll': UIConfig,
    'recording_set_text': UIConfig,
    'recording_file_upload': UIConfig,
    'recording_file_drop': UIConfig,
    'recording_key_press': UIConfig,
    'recording_download': UIConfig,
    'recording_get_steps': UIConfig,
    'advanced_dynamic_text_input': UIConfig,
    'advanced_visual_validation': UIConfig,
    'advanced_accessibility_testing': UIConfig,
    'advanced_network_monitoring': UIConfig,
    'advanced_performance_testing': UIConfig,
    'advanced_iframe_handling': UIConfig,
    'advanced_shadow_dom': UIConfig,
    'advanced_locator_improvement': UIConfig,
}


def create_config(node_type: str, data: Dict[str, Any]) -> BaseConfig:
    """根据节点类型创建配置"""
    config_class = CONFIG_TYPE_MAP.get(node_type)
    if not config_class:
        # 对于未知类型（如插件处理器），使用 BaseConfig
        # 这样可以支持动态加载的插件处理器
        return BaseConfig.from_dict(data)
    
    return config_class.from_dict(data)



