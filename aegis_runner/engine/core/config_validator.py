# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName src.core
@className ConfigValidator
@describe 统一配置验证框架
"""

from typing import Any, Dict, List, Optional, Union, Callable
from enum import Enum
import re
import json
from aegis_runner.engine.core.simple_logger import logger


class ValidationResult:
    """配置验证结果"""
    
    def __init__(self, is_valid: bool = True, errors: List[str] = None, warnings: List[str] = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
    
    def add_error(self, message: str):
        """添加错误信息"""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str):
        """添加警告信息"""
        self.warnings.append(message)
    
    def merge(self, other: 'ValidationResult'):
        """合并验证结果"""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.is_valid:
            self.is_valid = False
    
    def __str__(self):
        result = f"ValidationResult(valid={self.is_valid})"
        if self.errors:
            result += f"\n  Errors: {self.errors}"
        if self.warnings:
            result += f"\n  Warnings: {self.warnings}"
        return result


class ConfigFieldType(Enum):
    """配置字段类型"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"
    URL = "url"
    EMAIL = "email"
    JSON = "json"
    SQL = "sql"
    EXPRESSION = "expression"


class ConfigField:
    """配置字段定义"""
    
    def __init__(
        self,
        name: str,
        field_type: ConfigFieldType,
        required: bool = True,
        default: Any = None,
        description: str = "",
        validation_rules: List[Callable] = None,
        allowed_values: List[Any] = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        min_value: Optional[Union[int, float]] = None,
        max_value: Optional[Union[int, float]] = None,
        pattern: Optional[str] = None
    ):
        self.name = name
        self.field_type = field_type
        self.required = required
        self.default = default
        self.description = description
        self.validation_rules = validation_rules or []
        self.allowed_values = allowed_values
        self.min_length = min_length
        self.max_length = max_length
        self.min_value = min_value
        self.max_value = max_value
        self.pattern = pattern
    
    def validate(self, value: Any) -> ValidationResult:
        """验证字段值"""
        result = ValidationResult()
        
        # 检查必填字段
        if self.required and value is None:
            result.add_error(f"字段 '{self.name}' 是必需的")
            return result
        
        # 如果值为None且不是必填，跳过验证
        if value is None:
            return result
        
        # 类型验证
        type_result = self._validate_type(value)
        result.merge(type_result)
        
        # 如果类型验证失败，不再进行后续验证
        if not type_result.is_valid:
            return result
        
        # 长度验证
        length_result = self._validate_length(value)
        result.merge(length_result)
        
        # 值范围验证
        range_result = self._validate_range(value)
        result.merge(range_result)
        
        # 允许值验证
        allowed_result = self._validate_allowed_values(value)
        result.merge(allowed_result)
        
        # 正则表达式验证
        pattern_result = self._validate_pattern(value)
        result.merge(pattern_result)
        
        # 自定义验证规则
        for rule in self.validation_rules:
            try:
                rule_result = rule(value)
                if not rule_result:
                    result.add_error(f"字段 '{self.name}' 未通过自定义验证规则")
            except Exception as e:
                result.add_error(f"字段 '{self.name}' 自定义验证规则执行失败: {str(e)}")
        
        return result
    
    def _validate_type(self, value: Any) -> ValidationResult:
        """验证类型"""
        result = ValidationResult()
        
        if self.field_type == ConfigFieldType.STRING and not isinstance(value, str):
            result.add_error(f"字段 '{self.name}' 必须是字符串类型")
        elif self.field_type == ConfigFieldType.INTEGER and not isinstance(value, int):
            result.add_error(f"字段 '{self.name}' 必须是整数类型")
        elif self.field_type == ConfigFieldType.FLOAT and not isinstance(value, (int, float)):
            result.add_error(f"字段 '{self.name}' 必须是数值类型")
        elif self.field_type == ConfigFieldType.BOOLEAN and not isinstance(value, bool):
            result.add_error(f"字段 '{self.name}' 必须是布尔类型")
        elif self.field_type == ConfigFieldType.LIST and not isinstance(value, list):
            result.add_error(f"字段 '{self.name}' 必须是列表类型")
        elif self.field_type == ConfigFieldType.DICT and not isinstance(value, dict):
            result.add_error(f"字段 '{self.name}' 必须是字典类型")
        elif self.field_type == ConfigFieldType.URL:
            if not isinstance(value, str):
                result.add_error(f"字段 '{self.name}' 必须是字符串类型")
            elif not self._is_valid_url(value):
                result.add_error(f"字段 '{self.name}' 必须是有效的URL")
        elif self.field_type == ConfigFieldType.EMAIL:
            if not isinstance(value, str):
                result.add_error(f"字段 '{self.name}' 必须是字符串类型")
            elif not self._is_valid_email(value):
                result.add_error(f"字段 '{self.name}' 必须是有效的邮箱地址")
        elif self.field_type == ConfigFieldType.JSON:
            if not isinstance(value, (str, dict, list)):
                result.add_error(f"字段 '{self.name}' 必须是JSON格式")
            elif isinstance(value, str):
                try:
                    json.loads(value)
                except json.JSONDecodeError:
                    result.add_error(f"字段 '{self.name}' 必须是有效的JSON字符串")
        elif self.field_type == ConfigFieldType.SQL:
            if not isinstance(value, str):
                result.add_error(f"字段 '{self.name}' 必须是字符串类型")
            elif not self._is_valid_sql(value):
                result.add_warning(f"字段 '{self.name}' 可能不是有效的SQL语句")
        
        return result
    
    def _validate_length(self, value: Any) -> ValidationResult:
        """验证长度"""
        result = ValidationResult()
        
        if isinstance(value, (str, list, dict)):
            length = len(value)
            if self.min_length is not None and length < self.min_length:
                result.add_error(f"字段 '{self.name}' 长度不能少于 {self.min_length}")
            if self.max_length is not None and length > self.max_length:
                result.add_error(f"字段 '{self.name}' 长度不能超过 {self.max_length}")
        
        return result
    
    def _validate_range(self, value: Any) -> ValidationResult:
        """验证数值范围"""
        result = ValidationResult()
        
        if isinstance(value, (int, float)):
            if self.min_value is not None and value < self.min_value:
                result.add_error(f"字段 '{self.name}' 值不能小于 {self.min_value}")
            if self.max_value is not None and value > self.max_value:
                result.add_error(f"字段 '{self.name}' 值不能超过 {self.max_value}")
        
        return result
    
    def _validate_allowed_values(self, value: Any) -> ValidationResult:
        """验证允许的值"""
        result = ValidationResult()
        
        if self.allowed_values is not None and value not in self.allowed_values:
            result.add_error(f"字段 '{self.name}' 的值必须是 {self.allowed_values} 中的一个")
        
        return result
    
    def _validate_pattern(self, value: Any) -> ValidationResult:
        """验证正则表达式模式"""
        result = ValidationResult()
        
        if self.pattern and isinstance(value, str):
            if not re.match(self.pattern, value):
                result.add_error(f"字段 '{self.name}' 格式不正确")
        
        return result
    
    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """验证URL格式"""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return url_pattern.match(url) is not None
    
    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """验证邮箱格式"""
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        return email_pattern.match(email) is not None
    
    @staticmethod
    def _is_valid_sql(sql: str) -> bool:
        """简单验证SQL格式"""
        sql = sql.strip().upper()
        sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER']
        return any(sql.startswith(keyword) for keyword in sql_keywords)


class ConfigSchema:
    """配置模式定义"""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.fields: Dict[str, ConfigField] = {}
    
    def add_field(self, field: ConfigField):
        """添加字段定义"""
        self.fields[field.name] = field
    
    def validate(self, config: Dict[str, Any]) -> ValidationResult:
        """验证配置"""
        result = ValidationResult()
        
        # 检查必需的字段
        for field_name, field in self.fields.items():
            if field.required and field_name not in config:
                result.add_error(f"缺少必需字段: {field_name}")
        
        # 验证每个字段
        for field_name, value in config.items():
            if field_name in self.fields:
                field_result = self.fields[field_name].validate(value)
                result.merge(field_result)
            else:
                result.add_warning(f"未知字段: {field_name}")
        
        return result
    
    def get_required_fields(self) -> List[str]:
        """获取必需字段列表"""
        return [name for name, field in self.fields.items() if field.required]
    
    def get_optional_fields(self) -> List[str]:
        """获取可选字段列表"""
        return [name for name, field in self.fields.items() if not field.required]
    
    def get_field_info(self, field_name: str) -> Optional[Dict[str, Any]]:
        """获取字段信息"""
        if field_name not in self.fields:
            return None
        
        field = self.fields[field_name]
        return {
            'name': field.name,
            'type': field.field_type.value,
            'required': field.required,
            'default': field.default,
            'description': field.description,
            'allowed_values': field.allowed_values,
            'min_length': field.min_length,
            'max_length': field.max_length,
            'min_value': field.min_value,
            'max_value': field.max_value,
            'pattern': field.pattern
        }


class ConfigValidator:
    """配置验证器"""
    
    def __init__(self):
        self.schemas: Dict[str, ConfigSchema] = {}
        self._register_builtin_schemas()
    
    def register_schema(self, schema: ConfigSchema):
        """注册配置模式"""
        self.schemas[schema.name] = schema
        logger.debug(f"[ConfigValidator] 注册配置模式: {schema.name}")
    
    def validate_config(self, schema_name: str, config: Dict[str, Any]) -> ValidationResult:
        """验证配置"""
        if schema_name not in self.schemas:
            result = ValidationResult()
            result.add_error(f"未找到配置模式: {schema_name}")
            return result
        
        schema = self.schemas[schema_name]
        return schema.validate(config)
    
    def get_schema_info(self, schema_name: str) -> Optional[Dict[str, Any]]:
        """获取模式信息"""
        if schema_name not in self.schemas:
            return None
        
        schema = self.schemas[schema_name]
        return {
            'name': schema.name,
            'description': schema.description,
            'required_fields': schema.get_required_fields(),
            'optional_fields': schema.get_optional_fields(),
            'fields': {name: schema.get_field_info(name) for name in schema.fields.keys()}
        }
    
    def _register_builtin_schemas(self):
        """注册内置配置模式"""
        
        # HTTP请求配置模式
        http_schema = ConfigSchema("http_request", "HTTP请求处理器配置")
        http_schema.add_field(ConfigField("method", ConfigFieldType.STRING, True, 
                                         allowed_values=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]))
        http_schema.add_field(ConfigField("url", ConfigFieldType.URL, True))
        http_schema.add_field(ConfigField("headers", ConfigFieldType.DICT, False, {}))
        http_schema.add_field(ConfigField("body", ConfigFieldType.JSON, False))
        http_schema.add_field(ConfigField("timeout", ConfigFieldType.INTEGER, False, 30, min_value=1, max_value=300))
        http_schema.add_field(ConfigField("retries", ConfigFieldType.INTEGER, False, 0, min_value=0, max_value=5))
        self.register_schema(http_schema)
        
        # 脚本执行配置模式
        script_schema = ConfigSchema("script", "脚本执行处理器配置")
        script_schema.add_field(ConfigField("script", ConfigFieldType.STRING, True, min_length=1))
        script_schema.add_field(ConfigField("type", ConfigFieldType.STRING, False, "python", 
                                           allowed_values=["python", "expression", "function"]))
        script_schema.add_field(ConfigField("function_name", ConfigFieldType.STRING, False, "execute"))
        self.register_schema(script_schema)
        
        # 条件判断配置模式
        condition_schema = ConfigSchema("condition", "条件判断处理器配置")
        condition_schema.add_field(ConfigField("expression", ConfigFieldType.EXPRESSION, True))
        self.register_schema(condition_schema)
        
        # 变量提取配置模式
        variable_extractor_schema = ConfigSchema("variable_extractor", "变量提取处理器配置")
        variable_extractor_schema.add_field(ConfigField("extractions", ConfigFieldType.LIST, True, min_length=1))
        self.register_schema(variable_extractor_schema)
        
        # 断言配置模式
        assertion_schema = ConfigSchema("assertion", "断言处理器配置")
        assertion_schema.add_field(ConfigField("rules", ConfigFieldType.LIST, True, min_length=1))
        self.register_schema(assertion_schema)
        
        # 休眠配置模式
        sleep_schema = ConfigSchema("sleep", "休眠处理器配置")
        sleep_schema.add_field(ConfigField("duration", ConfigFieldType.FLOAT, True, min_value=0))
        sleep_schema.add_field(ConfigField("unit", ConfigFieldType.STRING, False, "seconds", 
                                          allowed_values=["seconds", "milliseconds"]))
        sleep_schema.add_field(ConfigField("reason", ConfigFieldType.STRING, False, "流程暂停"))
        sleep_schema.add_field(ConfigField("max_duration", ConfigFieldType.FLOAT, False, 3600, min_value=1))
        self.register_schema(sleep_schema)
        
        # MySQL配置模式
        mysql_schema = ConfigSchema("mysql", "MySQL数据库处理器配置")
        mysql_schema.add_field(ConfigField("operation", ConfigFieldType.STRING, False, "execute",
                                          allowed_values=["execute", "query", "insert", "update", "delete"]))
        mysql_schema.add_field(ConfigField("sql", ConfigFieldType.SQL, False))
        mysql_schema.add_field(ConfigField("parameters", ConfigFieldType.LIST, False, []))
        mysql_schema.add_field(ConfigField("connection", ConfigFieldType.DICT, False, {}))
        self.register_schema(mysql_schema)
        
        logger.info(f"[ConfigValidator] 已注册 {len(self.schemas)} 个内置配置模式")


# 全局配置验证器实例
config_validator = ConfigValidator()
