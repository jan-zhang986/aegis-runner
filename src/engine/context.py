import re
import time
import json
import random
import string
import copy
from typing import Dict, Any, Callable, Optional, List
from src.engine.core.interfaces.context_interface import ContextInterface


class ExecutionContext(ContextInterface):
    """在整个工作流执行期间存储和管理状态（变量、节点结果）。"""

    def __init__(self, enable_shard_storage: bool = False, task_id: str = None, run_id: str = None):
        """
        初始化执行上下文
        
        Args:
            enable_shard_storage: 是否启用分片存储（解决大 workflow 内存问题）
            task_id: 任务ID（分片存储时必需）
            run_id: 运行ID（分片存储时必需）
        """
        self._variables: Dict[str, Any] = {}
        self._node_results: Dict[str, Any] = {}
        self._functions: Dict[str, Callable] = {}
        
        # UI上下文相关属性
        self._ui_variables: Dict[str, Any] = {}
        self._recording_state: Optional[Dict[str, Any]] = None
        self._screenshots: List[Dict[str, Any]] = []
        self._network_requests: List[Dict[str, Any]] = []
        self._performance_metrics: Dict[str, Any] = {}
        self._accessibility_results: Dict[str, Any] = {}
        self._session_info: Dict[str, Any] = {}
        
        # 分片存储支持（解决大 workflow 内存问题）
        self._enable_shard_storage = enable_shard_storage
        self._step_storage = None
        if enable_shard_storage and task_id:
            from src.engine.core.step_result_storage import SyncStepResultStorage
            self._step_storage = SyncStepResultStorage(task_id, run_id or task_id)
            print(f"  [Context] 分片存储已启用: task_id={task_id}, run_id={run_id}")
        
        self._register_builtin_functions()

    def set_variable(self, key: str, value: Any):
        """
        设置变量
        
        如果启用了分片存储，且值是节点结果（可能很大），只保存摘要
        """
        if self._enable_shard_storage and self._step_storage:
            # 分片存储模式：检查值是否是节点结果
            # 如果 key 在 _node_results 中，说明这是节点结果，使用摘要
            if key in self._node_results:
                # 这是节点结果，使用摘要
                summary = self._step_storage.get_node_summary(key)
                if summary is not None:
                    self._variables[key] = summary
                    print(f"  [Context] 设置变量（摘要）: '{key}' = <summary>")
                else:
                    # 如果还没有摘要，检查值大小
                    import json
                    try:
                        value_str = json.dumps(value, default=str) if value else ""
                        if len(value_str) > 50 * 1024:  # 50KB
                            # 大值，创建摘要
                            self._variables[key] = self._create_value_summary(value)
                            print(f"  [Context] 设置变量（大值摘要）: '{key}' = <summary>")
                        else:
                            self._variables[key] = value
                            print(f"  [Context] 设置变量: '{key}' = '{value}'")
                    except:
                        # JSON 序列化失败，直接保存
                        self._variables[key] = value
                        print(f"  [Context] 设置变量: '{key}' = '{value}'")
            else:
                # 普通变量，检查大小
                import json
                try:
                    value_str = json.dumps(value, default=str) if value else ""
                    if len(value_str) > 50 * 1024:  # 50KB
                        # 大值，创建摘要
                        self._variables[key] = self._create_value_summary(value)
                        print(f"  [Context] 设置变量（大值摘要）: '{key}' = <summary>")
                    else:
                        self._variables[key] = value
                        print(f"  [Context] 设置变量: '{key}' = '{value}'")
                except:
                    # JSON 序列化失败，直接保存
                    self._variables[key] = value
                    print(f"  [Context] 设置变量: '{key}' = '{value}'")
        else:
            # 传统模式：直接保存
            print(f"  [Context] 设置变量: '{key}' = '{value}'")
            self._variables[key] = value
    
    def _create_value_summary(self, value: Any) -> Dict[str, Any]:
        """
        创建值的摘要（用于大值）
        
        只保留关键字段，不保留大的响应体
        """
        import json
        if value is None:
            return None
        
        if not isinstance(value, dict):
            # 非字典类型，返回摘要
            value_str = json.dumps(value, default=str)
            return {
                "_type": type(value).__name__,
                "_preview": value_str[:500] + "..." if len(value_str) > 500 else value_str,
                "_truncated": True,
                "_size": len(value_str)
            }
        
        # 字典类型，提取摘要
        summary = {}
        
        # 保留关键元数据
        for key in ("status", "status_code", "message", "error", "error_code", "extract_vars", "assertion"):
            if key in value:
                summary[key] = value[key]
        
        # body 字段：只保留小数据或摘要
        if "body" in value:
            body = value["body"]
            if isinstance(body, dict):
                body_str = json.dumps(body, default=str)
                if len(body_str) < 5000:  # 5KB 以下保留
                    summary["body"] = body
                else:
                    # 保留结构但截断大值
                    summary["body"] = {"_preview": body_str[:500] + "...", "_truncated": True, "_size": len(body_str)}
            else:
                body_str = str(body)
                if len(body_str) < 5000:
                    summary["body"] = body
                else:
                    summary["body"] = {"_preview": body_str[:500] + "...", "_truncated": True, "_size": len(body_str)}
        
        summary["_shard_stored"] = True
        summary["_truncated"] = True
        return summary

    def get_variable(self, key: str) -> Any:
        return self._variables.get(key)

    @property
    def get_variables(self):
        return self._variables
    
    def get_all_variables(self) -> Dict[str, Any]:
        """获取所有变量"""
        return self._variables.copy()
    
    def clear_variables(self) -> None:
        """清空所有变量"""
        self._variables.clear()

    def set_node_result(self, node_id: str, result: Any):
        """
        设置节点执行结果
        
        如果启用了分片存储，只在内存中保留摘要数据供后续节点引用
        """
        if self._enable_shard_storage and self._step_storage:
            # 分片存储模式：只保留摘要在内存中
            summary = self._step_storage.get_node_summary(node_id)
            if summary is not None:
                self._node_results[node_id] = summary
            else:
                # 如果还没有摘要（可能是在 save_step_result 之前调用的），保存完整结果
                self._node_results[node_id] = result
        else:
            # 传统模式：保存完整结果
            self._node_results[node_id] = result

    def get_node_result(self, node_id: str) -> Any:
        """
        获取节点执行结果
        
        分片存储模式下返回摘要数据
        """
        return self._node_results.get(node_id)
    
    def set_node_result_with_shard(
        self, 
        node_id: str, 
        result: Any,
        node_type: str = "unknown",
        status: str = "success",
        error: Optional[str] = None,
        start_time: Any = None,
        end_time: Any = None,
        logs: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """
        设置节点结果并分片存储
        
        用于大 workflow 执行，立即将结果存储到 Redis 释放内存
        
        Args:
            node_id: 节点ID
            result: 执行结果（完整数据）
            node_type: 节点类型
            status: 执行状态
            error: 错误信息
            start_time: 开始时间
            end_time: 结束时间
            logs: 日志
            metadata: 元数据
        """
        if self._enable_shard_storage and self._step_storage:
            # 分片存储：立即保存到 Redis
            self._step_storage.save_step_result(
                node_id=node_id,
                node_type=node_type,
                status=status,
                output=result,
                error=error,
                start_time=start_time,
                end_time=end_time,
                logs=logs,
                metadata=metadata
            )
            # 只在内存中保留摘要
            summary = self._step_storage.get_node_summary(node_id)
            self._node_results[node_id] = summary
        else:
            # 传统模式
            self._node_results[node_id] = result
    
    def get_step_storage(self):
        """获取分片存储服务实例"""
        return self._step_storage
    
    def is_shard_storage_enabled(self) -> bool:
        """检查是否启用了分片存储"""
        return self._enable_shard_storage and self._step_storage is not None

    def register_function(self, name: str, func: Callable):
        """注册自定义函数"""
        self._functions[name] = func
        print(f"  [Context] 注册函数: '{name}'")

    def register_functions(self, functions: Dict[str, Callable]):
        """批量注册函数"""
        for name, func in functions.items():
            self.register_function(name, func)

    def _register_builtin_functions(self):
        """注册内置函数"""
        # 注册一些常用的内置函数
        builtin_functions = {
            'len': len,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'list': list,
            'dict': dict,
            'tuple': tuple,
            'set': set,
            'max': max,
            'min': min,
            'sum': sum,
            'abs': abs,
            'round': round,
            'sorted': sorted,
            'reversed': reversed,
            'enumerate': enumerate,
            'zip': zip,
            'map': map,
            'filter': filter,
            'any': any,
            'all': all,
        }
        
        # 注册一些自定义函数
        custom_functions = {
            'say_hello': self._say_hello,
            'add_numbers': self._add_numbers,
            'get_timestamp': self._get_timestamp,
            'format_json': self._format_json,
            'random_string': self._random_string,
        }
        
        for name, func in builtin_functions.items():
            self._functions[name] = func
            
        for name, func in custom_functions.items():
            self._functions[name] = func

    def _say_hello(self, name: str = "World") -> str:
        """说你好函数"""
        return f"Hello, {name}!"
    
    def _add_numbers(self, a: int, b: int) -> int:
        """加法函数"""
        return a + b
    
    def _get_timestamp(self) -> str:
        """获取时间戳"""
        return str(int(time.time()))
    
    def _format_json(self, data: Any) -> str:
        """格式化JSON"""
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def _random_string(self, length: int = 10) -> str:
        """生成随机字符串"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    def render_string(self, template_str: str) -> str:
        """
        增强版字符串渲染，支持变量和函数调用
        支持语法：
        - ${variable} - 简单变量（支持嵌套属性访问，如 ${user.name}）
        - $variable - 简单变量（简化语法，仅支持简单变量名，不支持嵌套属性）
        - ${function_name(arg1, arg2)} - 函数调用
        - ${function_name($var1, $var2)} - 函数调用中使用变量
        - $$variable - 转义为字面量 $variable（不会替换为变量值）
        
        注意：
        - $variable 格式在字符串中现在已支持（如 JSON 中的 "x-site-tenant": "$site"）
        - $variable 格式不支持嵌套属性访问（如 $user.name 不支持，请使用 ${user.name}）
        - 如果变量找不到，会抛出 VariableNotFoundError 异常，导致节点执行失败
        """
        from src.engine.core.exceptions import VariableNotFoundError
        
        if not isinstance(template_str, str):
            return template_str
            
        try:
            return self._parse_string_with_functions(template_str)
        except VariableNotFoundError:
            # 变量未找到错误直接抛出，不进行回退处理
            raise
        except Exception as e:
            print(f"  [Context] 渲染字符串失败: {e}")
            # 如果解析失败，回退到简单的变量替换
            try:
                return self._fallback_render(template_str)
            except VariableNotFoundError:
                # 变量未找到错误直接抛出
                raise

    def _parse_string_with_functions(self, template_str: str) -> str:
        """解析包含函数调用的字符串"""
        # 使用占位符先标记转义的 $$，避免被当作变量处理
        # 使用一个不太可能出现在正常文本中的占位符
        ESCAPE_PLACEHOLDER = '\x00ESCAPE_DOLLAR\x00'
        result = template_str.replace('$$', ESCAPE_PLACEHOLDER)
        
        # 递归处理函数调用，直到没有更多的函数调用
        max_iterations = 10  # 防止无限递归
        iteration = 0
        
        while iteration < max_iterations:
            # 正则表达式匹配函数调用 ${function_name(args)}
            function_pattern = r'\$\{([a-zA-Z_]\w*)\(([^)]*)\)\}'
            
            def replace_function(match):
                func_name = match.group(1)
                args_str = match.group(2)
                
                if func_name not in self._functions:
                    return match.group(0)  # 如果函数不存在，保持原样
                
                try:
                    # 解析参数
                    args = self._parse_function_args(args_str)
                    # 调用函数
                    func_result = self._functions[func_name](*args)
                    return str(func_result)
                except Exception as e:
                    print(f"  [Context] 函数调用失败 {func_name}: {e}")
                    return match.group(0)
            
            # 处理函数调用
            new_result = re.sub(function_pattern, replace_function, result)
            
            # 如果没有变化，说明没有更多的函数调用需要处理
            if new_result == result:
                break
                
            result = new_result
            iteration += 1
        
        # 处理简单变量（此时 ESCAPE_PLACEHOLDER 不会被匹配为变量）
        result = self._fallback_render(result)
        
        # 最后将占位符替换回单个 $
        result = result.replace(ESCAPE_PLACEHOLDER, '$')
        
        return result

    def _parse_function_args(self, args_str: str) -> list:
        """解析函数参数"""
        if not args_str.strip():
            return []
        
        args = []
        # 更智能的参数分割，支持引号字符串和嵌套函数调用
        current_arg = ""
        in_quotes = False
        quote_char = None
        paren_count = 0
        i = 0
        
        while i < len(args_str):
            char = args_str[i]
            
            if not in_quotes:
                if char in ['"', "'"]:
                    in_quotes = True
                    quote_char = char
                    current_arg += char
                elif char == '(':
                    paren_count += 1
                    current_arg += char
                elif char == ')':
                    paren_count -= 1
                    current_arg += char
                elif char == ',' and paren_count == 0:
                    # 参数结束（不在嵌套函数调用中）
                    parsed_arg = self._parse_single_arg(current_arg.strip())
                    args.append(parsed_arg)
                    current_arg = ""
                else:
                    current_arg += char
            else:
                current_arg += char
                if char == quote_char and (i == 0 or args_str[i-1] != '\\'):
                    in_quotes = False
                    quote_char = None
            
            i += 1
        
        # 处理最后一个参数
        if current_arg.strip():
            parsed_arg = self._parse_single_arg(current_arg.strip())
            args.append(parsed_arg)
        
        return args
    
    def _evaluate_function_call(self, func_call: str) -> Any:
        """评估单个函数调用"""
        # 提取函数名和参数
        match = re.match(r'\$\{([a-zA-Z_]\w*)\(([^)]*)\)\}', func_call)
        if not match:
            return func_call
        
        func_name = match.group(1)
        args_str = match.group(2)
        
        if func_name not in self._functions:
            return func_call
        
        try:
            # 解析参数
            args = self._parse_function_args(args_str)
            # 调用函数
            result = self._functions[func_name](*args)
            return result
        except Exception as e:
            print(f"  [Context] 函数调用失败 {func_name}: {e}")
            return func_call
    
    def _parse_single_arg(self, arg: str) -> Any:
        """解析单个参数"""
        from src.engine.core.exceptions import VariableNotFoundError, ErrorContext
        
        # 如果参数以$开头，尝试解析为变量
        if arg.startswith('$'):
            var_name = arg[1:]  # 去掉$符号
            if var_name in self._variables:
                return self._variables[var_name]
            else:
                # 变量不存在，抛出异常
                error_context = ErrorContext()
                raise VariableNotFoundError(
                    variable_name=var_name,
                    template_str=arg,
                    context=error_context,
                    retryable=False
                )
        
        # 处理引号字符串
        if (arg.startswith('"') and arg.endswith('"')) or (arg.startswith("'") and arg.endswith("'")):
            return arg[1:-1]  # 去掉引号
        
        # 检查是否是函数调用结果（已经是处理过的）
        if arg.startswith('${') and arg.endswith('}'):
            # 这是一个函数调用，需要递归处理
            # 避免无限递归，使用简化的处理
            return self._evaluate_function_call(arg)
        
        # 尝试解析为字面量
        try:
            # 尝试解析为数字
            if '.' in arg:
                return float(arg)
            else:
                return int(arg)
        except ValueError:
            # 如果不是数字，作为字符串处理
            return arg

    def _fallback_render(self, template_str: str) -> str:
        """回退渲染方法，处理简单变量和嵌套属性访问"""
        from src.engine.core.exceptions import VariableNotFoundError, ErrorContext
        
        result = template_str
        
        # 先处理 ${variable.path.to.property} 或 ${variable} 格式（优先级更高）
        pattern_braces = r'\$\{([^}]+)\}'
        
        def replace_variable_braces(match):
            var_path = match.group(1).strip()
            
            # 分割路径（支持 obj.field 语法）
            parts = var_path.split('.')
            var_name = parts[0]
            
            # 获取变量值
            value = self._variables.get(var_name)
            if value is None:
                # 变量不存在，抛出异常
                error_context = ErrorContext()
                raise VariableNotFoundError(
                    variable_name=var_name,
                    template_str=template_str,
                    context=error_context,
                    retryable=False
                )
            
            # 如果有嵌套路径，递归获取属性
            current_path = [var_name]  # 用于构建完整路径
            for i, part in enumerate(parts[1:], start=1):
                if value is None:
                    # 路径不存在，抛出异常
                    error_context = ErrorContext()
                    raise VariableNotFoundError(
                        variable_name='.'.join(current_path),
                        template_str=template_str,
                        context=error_context,
                        retryable=False
                    )
                    
                # 支持字典和对象属性访问
                if isinstance(value, dict):
                    value = value.get(part)
                elif hasattr(value, part):
                    value = getattr(value, part)
                elif isinstance(value, (list, tuple)) and part.isdigit():
                    # 支持数组索引访问，如 data[0]
                    try:
                        value = value[int(part)]
                    except (IndexError, ValueError):
                        error_context = ErrorContext()
                        raise VariableNotFoundError(
                            variable_name='.'.join(current_path + [part]),
                            template_str=template_str,
                            context=error_context,
                            retryable=False
                        )
                else:
                    # 路径不存在，抛出异常
                    error_context = ErrorContext()
                    raise VariableNotFoundError(
                        variable_name='.'.join(current_path + [part]),
                        template_str=template_str,
                        context=error_context,
                        retryable=False
                    )
                
                current_path.append(part)
            
            # 如果最终值为None，抛出异常
            if value is None:
                error_context = ErrorContext()
                raise VariableNotFoundError(
                    variable_name='.'.join(current_path),
                    template_str=template_str,
                    context=error_context,
                    retryable=False
                )
            
            # 返回字符串化的值
            if isinstance(value, (list, dict)):
                return json.dumps(value, ensure_ascii=False)
            return str(value)
        
        result = re.sub(pattern_braces, replace_variable_braces, result)
        
        # 然后处理 $variable 格式（无大括号，仅支持简单变量名，不支持嵌套属性）
        # 匹配 $variable，其中 variable 是有效的标识符（字母、数字、下划线，但必须以字母或下划线开头）
        # 使用负向前瞻确保变量名后面不是字母、数字、下划线（即变量名的边界）
        pattern_simple = r'\$([a-zA-Z_][a-zA-Z0-9_]*)'
        
        def replace_variable_simple(match):
            var_name = match.group(1)
            
            # 获取变量值
            value = self._variables.get(var_name)
            if value is None:
                # 变量不存在，抛出异常
                error_context = ErrorContext()
                raise VariableNotFoundError(
                    variable_name=var_name,
                    template_str=template_str,
                    context=error_context,
                    retryable=False
                )
            
            # 返回字符串化的值（$variable 格式不支持嵌套属性访问）
            if isinstance(value, (list, dict)):
                return json.dumps(value, ensure_ascii=False)
            return str(value) if value is not None else match.group(0)
        
        result = re.sub(pattern_simple, replace_variable_simple, result)
        
        return result

    # ========== UI上下文管理方法 ==========
    
    def set_ui_variable(self, key: str, value: Any) -> None:
        """设置UI变量"""
        self._ui_variables[key] = {
            "value": value,
            "timestamp": time.time(),
            "type": type(value).__name__
        }
        print(f"  [Context] 设置UI变量: '{key}' = '{value}'")
    
    def get_ui_variable(self, key: str) -> Any:
        """获取UI变量"""
        if key in self._ui_variables:
            return self._ui_variables[key]["value"]
        return None
    
    def get_ui_variables(self) -> Dict[str, Any]:
        """获取所有UI变量"""
        return {k: v["value"] for k, v in self._ui_variables.items()}
    
    def clear_ui_variables(self) -> None:
        """清空UI变量"""
        self._ui_variables.clear()
        print("  [Context] 清空所有UI变量")
    
    def set_recording_state(self, state: Dict[str, Any]) -> None:
        """设置录制状态"""
        self._recording_state = state
        print(f"  [Context] 设置录制状态: {state}")
    
    def get_recording_state(self) -> Optional[Dict[str, Any]]:
        """获取录制状态"""
        return self._recording_state
    
    def add_screenshot(self, screenshot_info: Dict[str, Any]) -> None:
        """添加截图信息"""
        screenshot_info["timestamp"] = time.time()
        self._screenshots.append(screenshot_info)
        print(f"  [Context] 添加截图: {screenshot_info.get('path', 'unknown')}")
    
    def get_screenshots(self) -> List[Dict[str, Any]]:
        """获取所有截图信息"""
        return self._screenshots
    
    def add_network_request(self, request_info: Dict[str, Any]) -> None:
        """添加网络请求信息"""
        request_info["timestamp"] = time.time()
        self._network_requests.append(request_info)
        print(f"  [Context] 添加网络请求: {request_info.get('url', 'unknown')}")
    
    def get_network_requests(self) -> List[Dict[str, Any]]:
        """获取所有网络请求"""
        return self._network_requests
    
    def set_performance_metrics(self, metrics: Dict[str, Any]) -> None:
        """设置性能指标"""
        self._performance_metrics = metrics
        print(f"  [Context] 设置性能指标: {metrics}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return self._performance_metrics
    
    def set_accessibility_results(self, results: Dict[str, Any]) -> None:
        """设置可访问性测试结果"""
        self._accessibility_results = results
        print(f"  [Context] 设置可访问性结果: {results}")
    
    def get_accessibility_results(self) -> Dict[str, Any]:
        """获取可访问性测试结果"""
        return self._accessibility_results
    
    def set_session_info(self, info: Dict[str, Any]) -> None:
        """设置会话信息"""
        self._session_info = info
        print(f"  [Context] 设置会话信息: {info}")
    
    def get_session_info(self) -> Dict[str, Any]:
        """获取会话信息"""
        return self._session_info
    
    def get_ui_context_summary(self) -> Dict[str, Any]:
        """获取UI上下文摘要"""
        return {
            "ui_variables_count": len(self._ui_variables),
            "screenshots_count": len(self._screenshots),
            "network_requests_count": len(self._network_requests),
            "recording_active": self._recording_state is not None,
            "has_performance_metrics": bool(self._performance_metrics),
            "has_accessibility_results": bool(self._accessibility_results),
            "session_info": self._session_info
        }
    
    def clear_ui_context(self) -> None:
        """清空所有UI上下文"""
        self._ui_variables.clear()
        self._recording_state = None
        self._screenshots.clear()
        self._network_requests.clear()
        self._performance_metrics.clear()
        self._accessibility_results.clear()
        self._session_info.clear()
        print("  [Context] 清空所有UI上下文")
    
    # ========== 接口实现方法 ==========
    
    def has_variable(self, key: str) -> bool:
        """检查变量是否存在"""
        return key in self._variables
    
    def remove_variable(self, key: str) -> bool:
        """移除变量"""
        if key in self._variables:
            del self._variables[key]
            return True
        return False
    
    def has_node_result(self, node_id: str) -> bool:
        """检查节点结果是否存在"""
        return node_id in self._node_results
    
    def remove_node_result(self, node_id: str) -> bool:
        """移除节点结果"""
        if node_id in self._node_results:
            del self._node_results[node_id]
            return True
        return False
    
    def get_all_node_results(self) -> Dict[str, Any]:
        """获取所有节点结果"""
        return self._node_results.copy()
    
    def clear_node_results(self) -> None:
        """清空所有节点结果"""
        self._node_results.clear()
    
    def get_function(self, name: str) -> Optional[Callable]:
        """获取函数"""
        return self._functions.get(name)
    
    def has_function(self, name: str) -> bool:
        """检查函数是否存在"""
        return name in self._functions
    
    def remove_function(self, name: str) -> bool:
        """移除函数"""
        if name in self._functions:
            del self._functions[name]
            return True
        return False
    
    def get_all_functions(self) -> Dict[str, Callable]:
        """获取所有函数"""
        return self._functions.copy()
    
    def clear_functions(self) -> None:
        """清空所有函数"""
        self._functions.clear()
        # 重新注册内置函数
        self._register_builtin_functions()
    
    def get_context_summary(self) -> Dict[str, Any]:
        """获取上下文摘要"""
        return {
            "variables_count": len(self._variables),
            "node_results_count": len(self._node_results),
            "functions_count": len(self._functions),
            "ui_variables_count": len(self._ui_variables),
            "screenshots_count": len(self._screenshots),
            "network_requests_count": len(self._network_requests),
            "recording_active": self._recording_state is not None,
            "has_performance_metrics": bool(self._performance_metrics),
            "has_accessibility_results": bool(self._accessibility_results),
            "session_info": self._session_info
        }
    
    def clear_all(self) -> None:
        """清空所有上下文"""
        self.clear_variables()
        self.clear_node_results()
        self.clear_ui_context()
        # 保留内置函数
        self._register_builtin_functions()
    
    def clone(self) -> 'ExecutionContext':
        """克隆上下文"""
        new_context = ExecutionContext()
        new_context._variables = self._variables.copy()
        new_context._node_results = self._node_results.copy()
        new_context._functions = self._functions.copy()
        new_context._ui_variables = self._ui_variables.copy()
        new_context._recording_state = self._recording_state.copy() if self._recording_state else None
        new_context._screenshots = self._screenshots.copy()
        new_context._network_requests = self._network_requests.copy()
        new_context._performance_metrics = self._performance_metrics.copy()
        new_context._accessibility_results = self._accessibility_results.copy()
        new_context._session_info = self._session_info.copy()
        return new_context
    
    def merge(self, other: 'ExecutionContext') -> None:
        """合并另一个上下文"""
        # 合并变量（其他上下文的变量优先）
        self._variables.update(other._variables)
        
        # 合并节点结果（其他上下文的结果优先）
        self._node_results.update(other._node_results)
        
        # 合并函数（其他上下文的函数优先）
        self._functions.update(other._functions)
        
        # 合并UI变量
        self._ui_variables.update(other._ui_variables)
        
        # 合并其他UI上下文数据
        if other._recording_state:
            self._recording_state = other._recording_state.copy()
        
        self._screenshots.extend(other._screenshots)
        self._network_requests.extend(other._network_requests)
        
        if other._performance_metrics:
            self._performance_metrics.update(other._performance_metrics)
        
        if other._accessibility_results:
            self._accessibility_results.update(other._accessibility_results)
        
        if other._session_info:
            self._session_info.update(other._session_info)
    
    # ========== 兼容性方法 ==========
    
    def get_ui_context(self):
        """获取UI上下文（兼容性方法）"""
        return self