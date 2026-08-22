# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-9-25
@packageName src.core.processors.base
@className AssertionProcessor
@describe 断言处理器
"""

from aegis_runner.engine.context import ExecutionContext
import jmespath
import time
from aegis_runner.engine.core.processors import BaseProcessor, render_recursive
from aegis_runner.engine.core.elegant_processor_registry import register_processor, ProcessorCategory
import decimal
import re
import json
from typing import Text, Any, Union, Dict

from aegis_runner.engine.core.processors.base.variable_extractor_processor import options
from aegis_runner.engine.core.simple_logger import logger
from aegis_runner.engine.models.response import ResponseBuilder


def equal(check_value: Any, expect_value: Any, message: Text = ""):

    assert check_value == expect_value, message

def greater_than(
    check_value: Union[int, float], expect_value: Union[int, float], message: Text = ""
):
    assert check_value > expect_value, message


def less_than(
    check_value: Union[int, float], expect_value: Union[int, float], message: Text = ""
):
    assert check_value < expect_value, message


def greater_or_equals(
    check_value: Union[int, float], expect_value: Union[int, float], message: Text = ""
):
    assert check_value >= expect_value, message


def less_or_equals(
    check_value: Union[int, float], expect_value: Union[int, float], message: Text = ""
):
    assert check_value <= expect_value, message


def not_equal(check_value: Any, expect_value: Any, message: Text = ""):
    assert check_value != expect_value, message


def string_equals(check_value: Text, expect_value: Any, message: Text = ""):
    assert str(check_value) == str(expect_value), message


def length_equal(check_value: Text, expect_value: int, message: Text = ""):
    assert isinstance(expect_value, int), "expect_value should be int type"
    assert len(check_value) == expect_value, message


def _parse_bool_target(value: Any) -> str:
    """将用户填写的目标值解析为字符串 'true' 或 'false'。支持 'true'/'false' 或 True/False。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    s = str(value).strip().lower()
    if s in ("true", "1", "yes"):
        return "true"
    if s in ("false", "0", "no"):
        return "false"
    raise ValueError(f"目标值必须是 true 或 false，当前为: {value!r}")


def _convert_to_bool_string(value: Any) -> str:
    """将实际值转换为布尔字符串 'true' 或 'false'。支持各种类型的值。"""
    # 如果已经是布尔类型，直接转换
    if isinstance(value, bool):
        return "true" if value else "false"
    
    # 如果是字符串，尝试解析
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("true", "1", "yes", "on"):
            return "true"
        if s in ("false", "0", "no", "off", ""):
            return "false"
        # 非空字符串视为 True
        return "true"
    
    # 如果是数字，0/0.0 为 false，其他为 true
    if isinstance(value, (int, float)):
        return "false" if value == 0 else "true"
    
    # 如果是 None，视为 false
    if value is None:
        return "false"
    
    # 其他类型（列表、字典等），非空为 true，空为 false
    if hasattr(value, "__len__"):
        return "true" if len(value) > 0 else "false"
    
    # 默认视为 true（对象存在）
    return "true"


def is_boolean(check_value: Any, expect_value: Any, message: Text = ""):
    """断言结果必须是布尔类型，且等于用户填写的目标值 true/false。"""
    # 首先严格检查类型是否为 bool
    assert isinstance(check_value, bool), message or f"期望布尔类型 (bool)，实际为 {type(check_value).__name__}，值为 {check_value!r}"
    
    # 如果是布尔类型，转换为字符串与目标值比较
    actual_bool_str = "true" if check_value else "false"
    expect_bool_str = _parse_bool_target(expect_value)
    assert actual_bool_str == expect_bool_str, message or f"期望 {expect_bool_str}，实际为 {actual_bool_str}（原始值: {check_value!r}）"



@register_processor(
    processor_type="assertion",
    category=ProcessorCategory.CORE,
    description="断言处理器，支持各种数据验证和断言操作",
    tags={"assertion", "validation", "test", "verify"},
    enabled=True,
    priority=65,
    version="1.0.0",
    author="Jan"
)
class AssertionProcessor(BaseProcessor):
    def __init__(self):
        super().__init__()
        # 操作符到断言方法的映射
        self.operator_mapping = {
            "equals": lambda actual, target, message=None: equal(actual, target, message),
            "not_equal": lambda actual, target, message=None: not_equal(actual, target, message),
            "greater_than": lambda actual, target, message=None: greater_than(float(actual), float(target), message),
            "less_than": lambda actual, target, message=None: less_than(float(actual), float(target), message),
            "greater_or_equals": lambda actual, target, message=None: greater_or_equals(float(actual), float(target), message),
            "less_or_equals": lambda actual, target, message=None: less_or_equals(float(actual), float(target), message),
            "string_equals": lambda actual, target, message=None: string_equals(str(actual), str(target), message),
            "length_equal": lambda actual, target, message=None: length_equal(str(actual), int(target), message),
            "is_boolean": lambda actual, target, message=None: is_boolean(actual, target, message),
        }
    
    def _get_config_schema_name(self) -> str:
        """获取配置模式名称"""
        return "assertion"
    
    def _validate_specific_config(self, config: Dict[str, Any]) -> bool:
        """断言特定的配置验证"""
        rules = config.get("rules", [])
        if not rules:
            logger.error(f"[AssertionProcessor] rules不能为空")
            return False
        
        if not isinstance(rules, list):
            logger.error(f"[AssertionProcessor] rules必须是列表类型")
            return False
        
        # 验证每个断言规则
        for i, rule in enumerate(rules):
            if not isinstance(rule, dict):
                logger.error(f"[AssertionProcessor] 断言规则 {i+1} 必须是字典类型")
                return False
            
            required_fields = ["source", "operator", "target"]
            for field in required_fields:
                if field not in rule:
                    logger.error(f"[AssertionProcessor] 断言规则 {i+1} 缺少 {field}")
                    return False
            
            operator = rule.get("operator")
            if operator not in self.operator_mapping:
                logger.error(f"[AssertionProcessor] 断言规则 {i+1} 不支持的操作符: {operator}")
                return False
        
        return True

    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> dict:
        start_time = time.time()
        
        # 检查是否有前置结果
        if not predecessor_results:
            raise ValueError("❌ 断言处理器需要前置节点结果作为输入数据")
        
        input_data = list(predecessor_results.values())[0]
        
        # 获取原始配置（在 render_recursive 之前）
        original_config = node_info.get("data", {}).get("config", {})
        original_rules = original_config.get("rules", [])
        
        # 获取配置并进行全量递归变量渲染
        config = node_info.get("data", {}).get("config", {})
        config = render_recursive(config, context)
        
        rules = config.get("rules", [])
        if not rules:
            raise ValueError("❌ 断言配置中没有断言规则")
        
        # 记录详细的断言请求信息
        import json
        request_details_lines = [
            "================== Assertion Request Details ==================",
            f"Rules Count  : {len(rules)}",
            f"Node ID      : {node_info.get('id', 'N/A')}",
        ]
        
        # 显示每个断言规则
        for i, rule in enumerate(rules, 1):
            source = rule.get("source", "N/A")
            operator = rule.get("operator", "N/A")
            target = rule.get("target", "N/A")
            message = rule.get("message", "")
            request_details_lines.append(f"Rule {i}      :")
            request_details_lines.append(f"  Source     : {source}")
            request_details_lines.append(f"  Operator   : {operator}")
            request_details_lines.append(f"  Target     : {target}")
            if message:
                request_details_lines.append(f"  Message    : {message}")
        
        # 全局变量
        if hasattr(context, 'get_all_variables'):
            variables = context.get_all_variables()
            if variables:
                request_details_lines.append("Variables    :")
                # 完整显示所有变量，不做截断
                for key, value in variables.items():
                    if isinstance(value, (dict, list)):
                        value_str = json.dumps(value, indent=2, ensure_ascii=False)
                    else:
                        value_str = str(value)
                    request_details_lines.append(f"  {key}: {value_str}")
            else:
                request_details_lines.append("Variables    : None")
        
        request_details_lines.append("=============================================================")
        logger.info("\n".join(request_details_lines))

        results = []
        for rule_index, rule in enumerate(rules, 1):
            # 获取原始 source（在 render_recursive 之前）
            original_source = original_rules[rule_index - 1].get("source", "") if rule_index <= len(original_rules) else ""
            
            source_path = rule.get("source")
            operator = rule.get("operator")
            target = rule.get("target")
            message = rule.get("message", None)

            try:
                # 处理 source 字段的变量引用
                # 支持以下场景：
                # 1. source: "${node_id}" 或 "$variable" - 使用变量值作为实际值（不通过 JMESPath）
                # 2. source: "${node_id}.body.status_code" - 先获取节点结果，再使用 JMESPath body.status_code
                # 3. source: "body.status_code" - 直接使用 JMESPath body.status_code 访问 input_data
                actual_input_data = input_data
                actual_source_path = source_path
                use_direct_value = False  # 标记是否直接使用变量值
                actual = None  # 初始化 actual 变量
                
                # 检查原始 source 是否包含变量引用格式
                if isinstance(original_source, str):
                    # 检查 ${variable} 格式
                    if original_source.startswith("${") and original_source.endswith("}"):
                        var_content = original_source[2:-1].strip()
                        # 如果包含 . 且不在引号内，说明是变量引用 + 路径
                        if "." in var_content and not any(c in var_content for c in ['"', "'"]):
                            # 格式：${variable.path} - 变量引用 + 路径
                            parts = var_content.split(".", 1)
                            if len(parts) == 2:
                                var_part = parts[0].strip()
                                path_part = parts[1]
                                # 获取变量值
                                if hasattr(context, 'get_variable'):
                                    var_value = context.get_variable(var_part)
                                    if var_value is not None:
                                        # 使用变量值作为 input_data，剩余路径作为 JMESPath
                                        actual_input_data = var_value
                                        actual_source_path = path_part
                                        logger.debug(f"[AssertionProcessor] 使用变量引用和路径: {var_part}.{path_part}")
                        else:
                            # 格式：${variable} - 完整变量引用，直接使用变量值
                            var_name = var_content
                            if hasattr(context, 'get_variable'):
                                var_value = context.get_variable(var_name)
                                if var_value is not None:
                                    # 直接使用变量值作为实际值，不通过 JMESPath
                                    actual = var_value
                                    use_direct_value = True
                                    logger.debug(f"[AssertionProcessor] 使用变量引用作为实际值: {var_name}")
                    
                    # 检查 $variable 格式（简化语法，不支持路径）
                    elif original_source.startswith("$") and len(original_source) > 1 and " " not in original_source and "." not in original_source:
                        var_name = original_source[1:].strip()
                        if hasattr(context, 'get_variable'):
                            var_value = context.get_variable(var_name)
                            if var_value is not None:
                                # 直接使用变量值作为实际值，不通过 JMESPath
                                actual = var_value
                                use_direct_value = True
                                logger.debug(f"[AssertionProcessor] 使用变量引用作为实际值: {var_name}")
                    
                    # 检查 ${variable}.path 格式（变量引用后跟路径）
                    elif original_source.startswith("${") and "." in original_source:
                        # 找到第一个 } 的位置
                        end_brace = original_source.find("}")
                        if end_brace > 0:
                            var_part = original_source[2:end_brace].strip()
                            path_part = original_source[end_brace + 1:]
                            # 如果 path_part 以 . 开头，去掉它
                            if path_part.startswith("."):
                                path_part = path_part[1:]
                            
                            # 获取变量值
                            if hasattr(context, 'get_variable'):
                                var_value = context.get_variable(var_part)
                                if var_value is not None:
                                    # 使用变量值作为 input_data，剩余路径作为 JMESPath
                                    actual_input_data = var_value
                                    actual_source_path = path_part
                                    logger.debug(f"[AssertionProcessor] 使用变量引用和路径: {var_part}.{path_part}")
                
                # 如果直接使用变量值，跳过 JMESPath 解析
                if use_direct_value:
                    # actual 已经在上面定义了（在变量引用处理中）
                    if actual is None:
                        # 如果变量不存在，抛出错误
                        raise ValueError(f"❌ 断言规则 #{rule_index}: 变量引用 '{original_source}' 未找到或值为 None")
                else:
                    # 使用 JMESPath 提取实际值
                    # JMESPath 不需要 $ 前缀，直接使用路径
                    if not isinstance(actual_source_path, str):
                        actual_source_path = str(actual_source_path)
                    
                    # 提取实际值
                    try:
                        result = jmespath.search(actual_source_path, actual_input_data, options=options)
                    except Exception as e:
                        # JMESPath 解析错误
                        data_preview = self._generate_data_preview(actual_input_data)
                        error_msg = f"""
❌ 断言规则 #{rule_index} 失败: JMESPath 解析错误
📍 断言规则:
   - 路径: {source_path} (实际使用: {actual_source_path})
   - 操作符: {operator}
   - 期望值: {target}
   {f'- 自定义消息: {message}' if message else ''}
🔍 问题: JMESPath 路径 '{actual_source_path}' 解析失败: {str(e)}
📊 实际数据结构:
{data_preview}
💡 建议:
   1. 检查路径拼写是否正确
   2. 确认 JMESPath 语法是否正确
   3. 使用 path.to.field 格式访问嵌套字段
   4. 使用 list[0].field 访问数组元素
   5. 如果使用变量引用，确认变量值是否正确
"""
                        raise AssertionError(error_msg)
                    
                    # 详细的错误处理：路径未找到
                    if result is None:
                        # 生成友好的数据预览
                        data_preview = self._generate_data_preview(actual_input_data)
                        error_msg = f"""
❌ 断言规则 #{rule_index} 失败: 路径未找到
📍 断言规则:
   - 路径: {source_path} (实际使用: {actual_source_path})
   - 操作符: {operator}
   - 期望值: {target}
   {f'- 自定义消息: {message}' if message else ''}
🔍 问题: JMESPath 路径 '{actual_source_path}' 在数据中未找到任何匹配
📊 实际数据结构:
{data_preview}
💡 建议:
   1. 检查路径拼写是否正确
   2. 确认数据结构是否符合预期
   3. 使用 path.to.field 格式访问嵌套字段
   4. 使用 list[0].field 访问数组元素
   5. 如果使用变量引用，确认变量值是否正确
"""
                        raise AssertionError(error_msg)
                    
                    actual = result

                # 执行断言
                passed = self._execute_assertion(
                    operator, actual, target, source_path, message, 
                    rule_index, actual_input_data
                )
                
                # 对于 is_boolean，显示类型和值
                display_actual = actual
                if operator == "is_boolean":
                    is_bool_type = isinstance(actual, bool)
                    display_actual = f"{actual} (类型: {type(actual).__name__}, 是否为bool: {is_bool_type})"
                
                results.append({
                    "rule": f"{source_path} {operator} {target}", 
                    "actual": display_actual, 
                    "passed": passed
                })
                
            except AssertionError:
                # 断言错误直接抛出（已经格式化过）
                raise
            except Exception as e:
                # 其他异常进行格式化
                # 尝试获取实际输入数据（如果已定义）
                try:
                    preview_data = actual_input_data if 'actual_input_data' in locals() else input_data
                except:
                    preview_data = input_data
                data_preview = self._generate_data_preview(preview_data)
                error_msg = f"""
❌ 断言规则 #{rule_index} 执行失败
📍 断言规则:
   - 路径: {source_path} {'(实际使用: ' + actual_source_path + ')' if 'actual_source_path' in locals() else ''}
   - 操作符: {operator}
   - 期望值: {target}
   {f'- 自定义消息: {message}' if message else ''}
🔍 错误: {type(e).__name__}: {str(e)}
📊 实际数据结构:
{data_preview}
"""
                raise AssertionError(error_msg)

        logger.info(f"[AssertionProcessor] ✅ 所有断言通过 ({len(rules)} 条)")

        # 记录详细的断言响应信息
        duration = time.time() - start_time
        passed_count = sum(1 for r in results if r.get("passed", False))
        failed_count = len(results) - passed_count
        status_emoji = "✅ 全部通过" if failed_count == 0 else f"❌ {failed_count} 条失败"
        
        response_details_lines = [
            "================== Assertion Response Details ==================",
            f"Status       : {status_emoji}",
            f"Total Rules  : {len(rules)}",
            f"Passed       : {passed_count}",
            f"Failed       : {failed_count}",
            f"Duration     : {duration:.3f}s",
        ]
        
        # 显示每个断言的结果
        for i, result in enumerate(results, 1):
            rule_desc = result.get("rule", "N/A")
            actual = result.get("actual", "N/A")
            passed = result.get("passed", False)
            status = "✅ 通过" if passed else "❌ 失败"
            response_details_lines.append(f"Rule {i}      : {status}")
            response_details_lines.append(f"  Rule        : {rule_desc}")
            response_details_lines.append(f"  Actual      : {actual}")
        
        response_details_lines.append("=============================================================")
        logger.info("\n".join(response_details_lines))

        # 使用统一的 ProcessorResponse 格式，对外返回字典
        body = {
            "assertions_ran": len(rules),
            "results": results,
        }
        return ResponseBuilder.success(
            processor_type="assertion",
            body=body,
            message=f"{len(rules)} 条断言全部通过",
            status_code=200,
            duration=duration
        ).to_dict()

    def _execute_assertion(
        self, operator: str, actual: Any, target: Any, 
        source_path: str, message: str = None, 
        rule_index: int = 0, input_data: Any = None
    ) -> bool:
        """执行单个断言"""
        if operator not in self.operator_mapping:
            raise ValueError(f"不支持的操作符: {operator}")
        
        try:
            # 对于 is_boolean，显示类型检查信息
            if operator == "is_boolean":
                is_bool_type = isinstance(actual, bool)
                expect_bool_str = _parse_bool_target(target)
                logger.info(f"[Assertion #{rule_index}]: 检查 '{source_path}' ({actual}, 类型: {type(actual).__name__}, 是否为bool: {is_bool_type}) {operator} '{target}' (期望: {expect_bool_str})")
            else:
                logger.info(f"[Assertion #{rule_index}]: 检查 '{source_path}' ({actual}) {operator} '{target}'")
            
            assertion_func = self.operator_mapping[operator]
            assertion_func(actual, target, message)
            logger.info(f"[Assertion #{rule_index}]: ✅ 通过")
            return True
        except AssertionError as e:
            # 生成详细的错误报告
            if operator == "is_boolean":
                is_bool_type = isinstance(actual, bool)
                expect_bool_str = _parse_bool_target(target)
                if not is_bool_type:
                    error_msg = f"""
❌ 断言规则 #{rule_index} 失败

📍 断言规则:
   - 路径: {source_path}
   - 操作符: {operator}（判断结果是否为布尔类型）
   - 期望值: {target} (解析为: {expect_bool_str})
   - 实际值: {actual} (类型: {type(actual).__name__})

{f'💬 自定义消息: {message}' if message else ''}

🔍 类型检查:
   实际值类型: {type(actual).__name__}
   是否为布尔类型: ❌ 否

💡 可能的原因:
   - 实际值不是布尔类型 (bool)，而是 {type(actual).__name__}
   - {source_path} 的值 {actual!r} 不是 True 或 False
"""
                else:
                    actual_bool_str = "true" if actual else "false"
                    error_msg = f"""
❌ 断言规则 #{rule_index} 失败

📍 断言规则:
   - 路径: {source_path}
   - 操作符: {operator}（判断结果是否为布尔类型）
   - 期望值: {target} (解析为: {expect_bool_str})
   - 实际值: {actual} (类型: {type(actual).__name__}, 布尔值: {actual_bool_str})

{f'💬 自定义消息: {message}' if message else ''}

🔍 比较详情:
   类型检查: ✅ 是布尔类型
   值比较: {actual_bool_str} == {expect_bool_str} = False

💡 可能的原因:
   - 布尔值 {actual_bool_str} 与期望的 {expect_bool_str} 不一致
"""
            else:
                error_msg = f"""
❌ 断言规则 #{rule_index} 失败

📍 断言规则:
   - 路径: {source_path}
   - 操作符: {operator}
   - 期望值: {target} (类型: {type(target).__name__})
   - 实际值: {actual} (类型: {type(actual).__name__})

{f'💬 自定义消息: {message}' if message else ''}

🔍 比较详情:
   期望: {source_path} {operator} {target}
   实际: {actual} {self._get_comparison_symbol(operator)} {target} = False

💡 可能的原因:
   {'- 类型不匹配：期望 ' + type(target).__name__ + '，实际 ' + type(actual).__name__ if type(actual) != type(target) else ''}
   {'- 值不相等' if operator in ['equals', 'string_equals'] else ''}
   {'- 数值大小关系不符合' if operator in ['greater_than', 'less_than', 'greater_or_equals', 'less_or_equals'] else ''}
"""
            raise AssertionError(error_msg)
        except Exception as e:
            raise AssertionError(f"❌ 断言规则 #{rule_index} 执行失败: {type(e).__name__}: {str(e)}")
    
    def _get_comparison_symbol(self, operator: str) -> str:
        """获取比较符号"""
        symbols = {
            "equals": "==",
            "not_equal": "!=",
            "greater_than": ">",
            "less_than": "<",
            "greater_or_equals": ">=",
            "less_or_equals": "<=",
            "string_equals": "==",
            "length_equal": "len()==",
            "is_boolean": "is bool",
        }
        return symbols.get(operator, operator)
    
    def _generate_data_preview(self, data: Any, max_length: int = None) -> str:
        """生成数据预览，如果max_length为None则不截断"""
        try:
            if isinstance(data, (dict, list)):
                data_str = json.dumps(data, indent=2, ensure_ascii=False)
                if max_length is not None and len(data_str) > max_length:
                    data_str = data_str[:max_length] + "\n   ... (数据过长，已截断)"
                return data_str
            else:
                data_str = str(data)
                if max_length is not None and len(data_str) > max_length:
                    data_str = data_str[:max_length] + " ... (已截断)"
                return data_str
        except Exception:
            return f"<无法序列化的数据，类型: {type(data).__name__}>"
