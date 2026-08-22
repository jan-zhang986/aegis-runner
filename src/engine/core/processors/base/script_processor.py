import ast
import json
import sys
import time
import traceback
from typing import Any, Dict
from io import StringIO
from datetime import datetime, date, timedelta
from src.engine.context import ExecutionContext
from src.engine.core.processors import BaseProcessor, render_recursive
from src.engine.core.simple_logger import logger
from src.engine.core.elegant_processor_registry import register_processor, ProcessorCategory
from src.engine.models.response import ResponseBuilder


@register_processor(
    processor_type="script",
    category=ProcessorCategory.CORE,
    description="脚本执行处理器，支持Python脚本执行",
    tags={"script", "execution", "core", "python"},
    enabled=True,
    priority=90,
    version="1.0.0",
    author="Aegis Team",
)
class ScriptProcessor(BaseProcessor):

    def __init__(self):
        super().__init__()
        # 禁止导入的模块黑名单（仅禁止数据库等敏感驱动，其余模块均允许）
        self.blocked_modules = {
            "pymysql",
            "MySQLdb",
            "psycopg2",
            "psycopg2_",
            "mysql",
            "mysql.connector",
            "cx_Oracle",
            "oracledb",
            "sqlite3",
        }
        # 允许的内置函数
        self.allowed_builtins = {
            "len",
            "str",
            "int",
            "float",
            "bool",
            "list",
            "dict",
            "tuple",
            "set",
            "range",
            "enumerate",
            "zip",
            "map",
            "filter",
            "sorted",
            "min",
            "max",
            "sum",
            "abs",
            "round",
            "print",
            "isinstance",  # 类型检查函数，用于判断对象类型
            "type",  # 获取对象类型
        }

    def _get_config_schema_name(self) -> str:
        """获取配置模式名称"""
        return "script"

    def _validate_specific_config(self, config: Dict[str, Any]) -> bool:
        """脚本特定的配置验证"""
        script_code = config.get("script", "")
        if not script_code or not script_code.strip():
            logger.error(f"[ScriptProcessor] 脚本内容不能为空")
            return False

        # 检查脚本类型
        script_type = config.get("type", "python")
        if script_type not in ["python", "expression", "function"]:
            logger.error(f"[ScriptProcessor] 不支持的脚本类型: {script_type}")
            return False

        return True

    def execute(
        self, node_info: dict, context: ExecutionContext, predecessor_results: dict
    ) -> Dict[str, Any]:
        """动态执行脚本"""
        start_time = time.time()
        script_config = node_info.get("data", {}).get("config", {})

        # 全量递归渲染配置
        script_config = render_recursive(script_config, context)

        script_code = script_config.get("script", "")
        script_type = script_config.get(
            "type", "python"
        )  # 支持python, expression, function
        function_name = script_config.get("function_name", "execute")  # 默认函数名
        function_args = script_config.get("function_args", None)  # 函数参数（可选）

        if not script_code:
            raise ValueError("脚本内容不能为空")

        # 记录详细的脚本请求信息（特别是表达式类型）
        import json
        request_details_lines = [
            "================== Script Request Details ==================",
            f"Script Type  : {script_type}",
            f"Node ID      : {node_info.get('id', 'N/A')}",
        ]
        
        if script_type == "expression":
            request_details_lines.append(f"Expression   : {script_code}")
        elif script_type == "function":
            request_details_lines.append(f"Function Name: {function_name}")
            if function_args is not None:
                args_display = json.dumps(function_args, indent=2, ensure_ascii=False) if isinstance(function_args, (dict, list)) else str(function_args)
                request_details_lines.append(f"Function Args : {args_display}")
            request_details_lines.append(f"Script Code  : {script_code}")
        else:
            request_details_lines.append(f"Script Code  : {script_code}")
        
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

        # 安全检查
        self._validate_script(script_code)

        # 准备执行环境
        execution_context = self._prepare_execution_context(
            context, predecessor_results
        )

        try:
            if script_type == "python":
                result = self._execute_python_script(script_code, execution_context)
            elif script_type == "expression":
                result = self._execute_expression(script_code, execution_context)
            elif script_type == "function":
                result = self._execute_dynamic_function(
                    script_code, function_name, execution_context, function_args
                )
            else:
                raise ValueError(f"不支持的脚本类型: {script_type}")

            # 记录详细的脚本执行信息
            # 使用友好的格式化方式，避免双重序列化导致的转义字符问题
            def format_result_for_log(obj, max_depth=10, current_depth=0, indent=2):
                """格式化结果用于日志输出，完整显示所有内容"""
                indent_str = " " * (indent * current_depth)
                next_indent_str = " " * (indent * (current_depth + 1))
                
                if current_depth >= max_depth:
                    return f"{indent_str}... (max depth: {max_depth})"
                
                if isinstance(obj, dict):
                    if not obj:
                        return "{}"
                    lines = ["{"]
                    for k, v in obj.items():
                        key_str = str(k)
                        if callable(v):
                            value_str = f"<function {key_str}>"
                        elif isinstance(v, dict):
                            if current_depth < max_depth - 1:
                                value_str = format_result_for_log(v, max_depth, current_depth + 1, indent)
                            else:
                                value_str = f"<dict with {len(v)} keys>"
                        elif isinstance(v, list):
                            if current_depth < max_depth - 1:
                                value_str = format_result_for_log(v, max_depth, current_depth + 1, indent)
                            else:
                                value_str = f"<list with {len(v)} items>"
                        elif isinstance(v, str):
                            # 完整显示字符串，不截断
                            value_str = repr(v)
                        else:
                            value_str = repr(v)  # 完整显示，不限制长度
                        lines.append(f"{next_indent_str}{key_str}: {value_str}")
                    lines.append(f"{indent_str}}}")
                    return "\n".join(lines)
                elif isinstance(obj, list):
                    if not obj:
                        return "[]"
                    lines = ["["]
                    for item in obj:
                        if callable(item):
                            item_str = "<function>"
                        elif isinstance(item, (dict, list)):
                            if current_depth < max_depth - 1:
                                item_str = format_result_for_log(item, max_depth, current_depth + 1, indent)
                            else:
                                item_str = f"<{type(item).__name__}>"
                        else:
                            item_str = repr(item)  # 完整显示，不限制长度
                        lines.append(f"{next_indent_str}{item_str}")
                    lines.append(f"{indent_str}]")
                    return "\n".join(lines)
                else:
                    return repr(obj)  # 完整显示，不限制长度
            
            # 对结果进行格式化，特别处理 variables 字段
            if isinstance(result, dict):
                # 创建一个简化的结果用于日志
                log_result = {}
                for k, v in result.items():
                    if k == "variables" and isinstance(v, dict):
                        # variables 字段完整显示所有变量
                        log_result[k] = v
                    else:
                        log_result[k] = v
                result_str = format_result_for_log(log_result)
            else:
                result_str = format_result_for_log(result) if isinstance(result, (dict, list)) else str(result)
            
            script_details = f"""
================== Script Execution Details ==================
script_type : {script_type}
script_code : {script_code}
result      : {result_str}
node_id     : {node_info.get('id')}
=============================================================
"""
            logger.info(script_details)

            # 使用 ResponseBuilder 统一返回格式
            duration = time.time() - start_time
            return ResponseBuilder.success(
                processor_type="script",
                body=result,  # 脚本执行结果
                message="脚本执行成功",
                status_code=200,
                metadata={
                    "script_type": script_type,
                    "function_name": function_name if script_type == "function" else None,
                    "node_id": node_info.get('id')
                },
                duration=duration
            ).to_dict()

        except AssertionError as e:
            # 断言错误直接抛出，不转换为 RuntimeError，以便工作流引擎能正确识别为断言失败
            duration = time.time() - start_time
            
            # 记录详细的断言错误信息
            import traceback
            # 格式化时间显示（如果小于1毫秒，显示微秒）
            if duration < 0.001:
                duration_str = f"{duration * 1000000:.2f}μs"
            elif duration < 1:
                duration_str = f"{duration * 1000:.2f}ms"
            else:
                duration_str = f"{duration:.3f}s"
            
            error_details_lines = [
                "================== Script Execution Error Details ==================",
                f"Status       : ❌ 断言失败",
                f"Script Type  : {script_type if 'script_type' in locals() else 'N/A'}",
                f"Node ID      : {node_info.get('id', 'N/A')}",
                f"Error Type   : {type(e).__name__}",
                f"Error Message: {str(e)}",
            ]
            
            if 'script_code' in locals():
                # 显示脚本代码，如果太长则截断
                script_display = script_code
                error_details_lines.append(f"Script Code  : {script_display}")
            
            # 添加输入数据预览（如果有前置结果）
            if predecessor_results:
                error_details_lines.append("Input Data   :")
                first_input = list(predecessor_results.values())[0]
                if isinstance(first_input, dict):
                    input_preview = json.dumps(first_input, indent=2, ensure_ascii=False)
                    error_details_lines.append(f"  {input_preview}")
                else:
                    input_str = str(first_input)
                    error_details_lines.append(f"  {input_str}")
            
            # 添加堆栈跟踪（简化版，只显示关键信息）
            tb_str = traceback.format_exc()
            if tb_str:
                error_details_lines.append("Traceback    :")
                tb_lines = tb_str.split("\n")
                # 过滤并显示关键堆栈信息（最多15行）
                relevant_lines = []
                for line in tb_lines:
                    line = line.strip()
                    if line and not line.startswith('File "<frozen'):
                        relevant_lines.append(line)
                    if len(relevant_lines) >= 15:
                        break
                for line in relevant_lines:
                    error_details_lines.append(f"  {line}")
            
            # 全局变量（完整显示）
            if hasattr(context, 'get_all_variables'):
                variables = context.get_all_variables()
                if variables:
                    error_details_lines.append("Variables    :")
                    for key, value in variables.items():
                        # 完整格式化变量值
                        if isinstance(value, (dict, list)):
                            value_str = json.dumps(value, indent=2, ensure_ascii=False)
                        else:
                            value_str = str(value)
                        error_details_lines.append(f"  {key}: {value_str}")
                else:
                    error_details_lines.append("Variables    : None")
            
            error_details_lines.extend([
                f"Duration     : {duration_str}",
                "============================================================="
            ])
            logger.error("\n".join(error_details_lines))
            
            # 使用 ResponseBuilder 包装断言错误
            return ResponseBuilder.error(
                processor_type="script",
                error=f"脚本断言失败: {str(e)}",
                error_code="ASSERTION_ERROR",
                status_code=400,
                duration=duration
            ).to_dict()
        except Exception as e:
            duration = time.time() - start_time
            
            # 记录详细的执行错误信息
            import traceback
            script_type = script_config.get("type", "python") if 'script_config' in locals() else "python"
            script_code_str = script_config.get("script", "") if 'script_config' in locals() else ""
            
            # 格式化时间显示（如果小于1毫秒，显示微秒）
            if duration < 0.001:
                duration_str = f"{duration * 1000000:.2f}μs"
            elif duration < 1:
                duration_str = f"{duration * 1000:.2f}ms"
            else:
                duration_str = f"{duration:.3f}s"
            
            error_details_lines = [
                "================== Script Execution Error Details ==================",
                f"Status       : ❌ 执行失败",
                f"Script Type  : {script_type}",
                f"Node ID      : {node_info.get('id', 'N/A')}",
                f"Error Type   : {type(e).__name__}",
                f"Error Message: {str(e)}",
            ]
            
            if script_code_str:
                # 显示脚本代码，如果太长则截断
                script_display = script_code_str
                error_details_lines.append(f"Script Code  : {script_display}")
            
            # 添加输入数据预览（如果有前置结果）
            if predecessor_results:
                error_details_lines.append("Input Data   :")
                first_input = list(predecessor_results.values())[0]
                if isinstance(first_input, dict):
                    input_preview = json.dumps(first_input, indent=2, ensure_ascii=False)
                    error_details_lines.append(f"  {input_preview}")
                else:
                    input_str = str(first_input)
                    error_details_lines.append(f"  {input_str}")
            
            # 添加堆栈跟踪（简化版，只显示关键信息）
            tb_str = traceback.format_exc()
            if tb_str:
                error_details_lines.append("Traceback    :")
                tb_lines = tb_str.split("\n")
                # 过滤并显示关键堆栈信息（最多15行）
                relevant_lines = []
                for line in tb_lines:
                    line = line.strip()
                    if line and not line.startswith('File "<frozen'):
                        relevant_lines.append(line)
                    if len(relevant_lines) >= 15:
                        break
                for line in relevant_lines:
                    error_details_lines.append(f"  {line}")
            
            # 全局变量（完整显示）
            if hasattr(context, 'get_all_variables'):
                variables = context.get_all_variables()
                if variables:
                    error_details_lines.append("Variables    :")
                    for key, value in variables.items():
                        # 完整格式化变量值
                        if isinstance(value, (dict, list)):
                            value_str = json.dumps(value, indent=2, ensure_ascii=False)
                        else:
                            value_str = str(value)
                        error_details_lines.append(f"  {key}: {value_str}")
                else:
                    error_details_lines.append("Variables    : None")
            
            error_details_lines.extend([
                f"Duration     : {duration_str}",
                "============================================================="
            ])
            logger.error("\n".join(error_details_lines))
            
            # 使用 ResponseBuilder 包装执行错误
            return ResponseBuilder.error(
                processor_type="script",
                error=f"脚本执行失败: {str(e)}",
                error_code="SCRIPT_EXECUTION_ERROR",
                status_code=500,
                error_details={
                    "script_type": script_type,
                    "node_id": node_info.get('id'),
                    "exception_type": type(e).__name__
                },
                duration=duration
            ).to_dict()

    def _validate_script(self, script_code: str):
        """验证脚本安全性（模块采用黑名单：仅禁止数据库等敏感模块）"""
        try:
            # 解析AST
            tree = ast.parse(script_code)

            # 跟踪已导入的名称（用于后续允许其被调用）
            imported_names = set()

            def _base_module(name: str) -> str:
                return name.split(".")[0] if name else ""

            # 第一遍遍历：检查禁止模块，并收集所有导入的名称
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        base = _base_module(alias.name)
                        if base in self.blocked_modules:
                            raise SecurityError(f"不允许导入模块: {alias.name}（数据库等敏感模块已禁止）")
                        if alias.asname:
                            imported_names.add(alias.asname)
                        else:
                            imported_names.add(alias.name)

                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        base = _base_module(node.module)
                        if base in self.blocked_modules:
                            raise SecurityError(f"不允许从模块导入: {node.module}（数据库等敏感模块已禁止）")
                    if node.names:
                        for alias in node.names:
                            if alias.asname:
                                imported_names.add(alias.asname)
                            else:
                                imported_names.add(alias.name)

            # 第二遍遍历：验证函数调用和其他安全检查
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        # 允许内置函数和从允许模块导入的函数
                        if node.func.id not in self.allowed_builtins and node.func.id not in imported_names:
                            raise SecurityError(f"不允许调用函数: {node.func.id} (Node: {node.func.lineno if hasattr(node.func, 'lineno') else 'N/A'})")
                    elif isinstance(node.func, ast.Attribute):
                        # 处理 datetime.timedelta() 这种形式的调用
                        # 如果属性访问的是从允许模块导入的模块，则允许调用
                        if isinstance(node.func.value, ast.Name):
                            # 如果模块名在导入的名称集合中，允许调用其属性
                            if node.func.value.id in imported_names:
                                pass  # 允许调用
                            elif node.func.value.id == "__builtins__":
                                raise SecurityError("不允许访问__builtins__")

                elif isinstance(node, ast.Attribute):
                    # 检查属性访问
                    if isinstance(node.value, ast.Name):
                        if node.value.id == "__builtins__":
                            raise SecurityError("不允许访问__builtins__")

                # 注意：在 Python 3.8+ 中，ast.Exec 和 ast.Eval 已被移除
                # exec 和 eval 现在通过 ast.Call 节点调用，已在上面检查

                elif isinstance(node, ast.Assert):
                    # 允许 assert 语句，用于断言/校验
                    pass

                elif isinstance(node, ast.FunctionDef):
                    # 允许函数定义，但检查函数名
                    if node.name.startswith("_"):
                        raise SecurityError(f"不允许以下划线开头的函数名: {node.name}")

                elif isinstance(node, ast.ClassDef):
                    raise SecurityError("不允许定义类")

        except SyntaxError as e:
            raise ValueError(f"脚本语法错误: {str(e)}")

    def _prepare_execution_context(
        self, context: ExecutionContext, predecessor_results: dict
    ) -> Dict[str, Any]:
        """准备执行环境"""
        def extract_actual_result(value):
            """从节点响应结构中提取实际的结果值"""
            if not isinstance(value, dict):
                return value
            
            # 如果包含 body.result，说明是脚本处理器的响应结构，提取实际结果
            if "body" in value and isinstance(value["body"], dict) and "result" in value["body"]:
                return value["body"]["result"]
            # 如果直接包含 result 字段（可能是函数执行结果）
            elif "result" in value:
                return value["result"]
            # 否则返回原值
            else:
                return value
        
        # 提取第一个前置节点的实际结果作为 input_data
        input_data = None
        if predecessor_results:
            first_result = list(predecessor_results.values())[0]
            input_data = extract_actual_result(first_result)
        
        execution_context = {
            # 添加前置结果
            **predecessor_results,
            # 添加上下文变量
            "context": context,
            # 添加常用变量（提取实际结果值，而不是整个响应结构）
            "input_data": input_data,
        }

        # 添加安全的builtins
        # 注意：__builtins__ 可能是模块或字典，需要处理两种情况
        if isinstance(__builtins__, dict):
            builtins_dict = __builtins__
        else:
            builtins_dict = __builtins__.__dict__
        
        safe_builtins = {
            name: builtins_dict[name]
            for name in self.allowed_builtins
            if name in builtins_dict
        }
        
        # 保存原始的 __import__ 函数
        original_import = builtins_dict.get("__import__")
        
        # 添加安全的 __import__ 函数：允许所有模块，仅禁止黑名单中的模块（如数据库驱动）
        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            """安全的导入函数：除黑名单外均可导入"""
            if not name:
                if fromlist:
                    module_name = fromlist[0] if fromlist else ""
                else:
                    raise ImportError("无法确定要导入的模块名")
            else:
                module_name = name

            base_module = module_name.split(".")[0] if module_name else ""

            if base_module and base_module in self.blocked_modules:
                raise ImportError(
                    f"不允许导入模块: {base_module}（数据库等敏感模块已禁止）。"
                    f"禁止的模块: {', '.join(sorted(self.blocked_modules))}"
                )

            if original_import:
                return original_import(name, globals, locals, fromlist, level)
            else:
                raise ImportError("无法导入模块：原始 __import__ 函数不可用")
        
        # 将安全的 __import__ 添加到 builtins
        safe_builtins["__import__"] = safe_import
        
        execution_context["__builtins__"] = safe_builtins
        
        # 同时将允许的内置函数直接添加到执行上下文中，方便表达式和脚本使用
        for name, func in safe_builtins.items():
            execution_context[name] = func
        
        logger.debug(f"[ScriptProcessor] 已添加 {len(safe_builtins)} 个内置函数到执行上下文: {list(safe_builtins.keys())}")

        return execution_context

    @staticmethod
    def _is_json_serializable(value: Any) -> bool:
        """检查值是否可以 JSON 序列化"""
        try:
            json.dumps(value)
            return True
        except (TypeError, ValueError):
            return False
    
    @staticmethod
    def _convert_to_json_serializable(value: Any) -> Any:
        """将值转换为 JSON 可序列化的格式"""
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        elif isinstance(value, timedelta):
            return str(value)
        elif isinstance(value, dict):
            return {k: ScriptProcessor._convert_to_json_serializable(v) for k, v in value.items()}
        elif isinstance(value, (list, tuple)):
            return [ScriptProcessor._convert_to_json_serializable(item) for item in value]
        else:
            return value

    @classmethod
    def _execute_python_script(
        cls, script_code: str, execution_context: Dict[str, Any]
    ) -> Any:
        """执行Python脚本"""
        # 捕获输出
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_capture = StringIO()
        stderr_capture = StringIO()

        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture

            # 执行脚本
            try:
                exec(script_code, execution_context)
            except AssertionError as e:
                # 断言错误直接抛出，不转换为 RuntimeError
                raise

            # 获取输出
            stdout_output = stdout_capture.getvalue()
            stderr_output = stderr_capture.getvalue()

            # 判断一个值是否是前置节点的结果
            def is_predecessor_result(value):
                """判断一个值是否是前置节点的结果"""
                if not isinstance(value, dict):
                    return False
                # 检查是否包含脚本处理器返回的标准字段
                has_stdout = "stdout" in value
                has_stderr = "stderr" in value
                has_variables = "variables" in value
                # 如果包含这些字段，很可能是前置节点的结果
                return has_stdout or has_stderr or has_variables

            # 检查是否有 result 变量（脚本的返回值）
            script_result = execution_context.get("result")
            result_variables = {}
            
            # 如果脚本定义了 result 变量且是字典，将其中的键值对作为变量
            if script_result is not None and isinstance(script_result, dict):
                # 转换 result 中的值，确保可以 JSON 序列化
                result_variables = {
                    k: cls._convert_to_json_serializable(v) 
                    for k, v in script_result.items()
                }
                logger.info(f"[ScriptProcessor] 检测到 result 变量，包含 {len(result_variables)} 个键值对: {list(result_variables.keys())}")

            # 收集其他用户定义的变量（排除 result，因为已经单独处理了）
            # 只保留可以 JSON 序列化的变量
            other_variables = {}
            for k, v in execution_context.items():
                if (not k.startswith("__") 
                    and k not in ["context", "input_data", "result"]  # 排除 result，因为已经单独处理
                    and not callable(v)  # 过滤掉函数对象
                    and not is_predecessor_result(v)  # 排除前置节点结果
                    and type(v).__name__ != "module"):  # 过滤掉模块对象
                    # 检查是否可以 JSON 序列化，如果可以则转换
                    if cls._is_json_serializable(v):
                        other_variables[k] = v
                    else:
                        # 尝试转换为可序列化的格式
                        try:
                            converted = cls._convert_to_json_serializable(v)
                            if cls._is_json_serializable(converted):
                                other_variables[k] = converted
                        except Exception:
                            # 如果转换失败，跳过该变量
                            logger.debug(f"[ScriptProcessor] 跳过无法序列化的变量: {k} (类型: {type(v).__name__})")
            
            # 合并 result 中的变量和其他变量（result 中的变量优先级更高）
            all_variables = {**other_variables, **result_variables}

            # 返回结果
            return {
                "stdout": stdout_output,
                "stderr": stderr_output,
                "result": script_result,  # 保留原始的 result 值
                "variables": all_variables,
            }

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    @classmethod
    def _execute_expression(
        cls, expression: str, execution_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行表达式，返回统一的结果结构"""
        # 捕获输出（虽然表达式通常不会有stdout，但为了统一格式）
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_capture = StringIO()
        stderr_capture = StringIO()

        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture

            # 创建全局命名空间，直接包含执行上下文中的所有内容
            # 这样内置函数（如 len）可以直接使用
            globals_dict = dict(execution_context)
            
            # 使用eval执行表达式，传入 globals 和 locals（使用相同的字典）
            # 这样表达式可以直接访问执行上下文中的所有变量和函数
            result = eval(expression, globals_dict, globals_dict)
            
            # 获取输出
            stdout_output = stdout_capture.getvalue()
            stderr_output = stderr_capture.getvalue()

            # 判断一个值是否是前置节点的结果
            def is_predecessor_result(value):
                """判断一个值是否是前置节点的结果"""
                if not isinstance(value, dict):
                    return False
                # 检查是否包含脚本处理器返回的标准字段
                has_stdout = "stdout" in value
                has_stderr = "stderr" in value
                has_variables = "variables" in value
                # 如果包含这些字段，很可能是前置节点的结果
                return has_stdout or has_stderr or has_variables

            # 返回统一的结果结构
            return {
                "result": result,  # 表达式的执行结果
                "stdout": stdout_output,
                "stderr": stderr_output,
                "variables": {
                    k: v
                    for k, v in execution_context.items()
                    if not k.startswith("__") 
                    and k not in ["context", "input_data"]
                    and not callable(v)  # 过滤掉函数对象
                    and not is_predecessor_result(v)  # 排除前置节点结果
                    and type(v).__name__ != "module"  # 过滤掉模块对象（无法JSON序列化）
                },
            }
        except AssertionError as e:
            # 断言错误直接抛出
            raise
        except Exception as e:
            raise RuntimeError(f"表达式执行失败: {str(e)}")
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    @classmethod
    def _execute_dynamic_function(
        cls,
        script_code: str,
        function_name: str,
        execution_context: Dict[str, Any],
        function_args: Any = None,
    ) -> Any:
        """
        执行动态函数

        Args:
            script_code: 脚本代码
            function_name: 函数名
            execution_context: 执行上下文
            function_args: 函数参数，可以是：
                - None: 传入 execution_context（向后兼容）
                - dict: 作为关键字参数传入
                - list/tuple: 作为位置参数传入
                - 其他类型: 作为单个位置参数传入
        """
        # 捕获输出
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_capture = StringIO()
        stderr_capture = StringIO()

        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture

            # 执行脚本以定义函数
            exec(script_code, execution_context)

            # 检查函数是否存在
            if function_name not in execution_context:
                raise RuntimeError(f"函数 '{function_name}' 未在脚本中定义")

            # 获取函数并执行
            func = execution_context[function_name]
            if not callable(func):
                raise RuntimeError(f"'{function_name}' 不是一个可调用的函数")

            # 调用函数，根据参数类型决定如何传递
            try:
                if function_args is None:
                    # 向后兼容：如果没有提供参数，传入 execution_context
                    result = func(execution_context)
                elif isinstance(function_args, dict):
                    # 字典类型：作为关键字参数传入
                    result = func(**function_args)
                elif isinstance(function_args, (list, tuple)):
                    # 列表/元组：作为位置参数传入
                    result = func(*function_args)
                else:
                    # 其他类型：作为单个位置参数传入
                    result = func(function_args)
            except AssertionError as e:
                # 断言错误直接抛出
                raise

            # 获取输出
            stdout_output = stdout_capture.getvalue()
            stderr_output = stderr_capture.getvalue()

            # 记录执行脚本前已有的变量键（用于识别前置节点结果）
            # 前置节点的结果通常包含 stdout、stderr、variables 等字段
            def is_predecessor_result(value):
                """判断一个值是否是前置节点的结果"""
                if not isinstance(value, dict):
                    return False
                # 检查是否包含脚本处理器返回的标准字段
                has_stdout = "stdout" in value
                has_stderr = "stderr" in value
                has_variables = "variables" in value
                # 如果包含这些字段，很可能是前置节点的结果
                return has_stdout or has_stderr or has_variables
            
            # 返回结果
            # variables：先收集脚本执行过程中的新变量，若函数返回 dict 则合并进去（返回值优先，供后续节点 $name 等引用）
            variables = {
                k: v
                for k, v in execution_context.items()
                if not k.startswith("__")
                and k not in ["context", "input_data", function_name]
                and not callable(v)  # 排除函数对象
                and not is_predecessor_result(v)  # 排除前置节点结果
                and type(v).__name__ != "module"  # 过滤掉模块对象（无法JSON序列化）
            }
            # 若函数返回的是 dict，将其键值对合并到 variables，便于工作流后续节点使用 $name、$beginTimeMs 等
            if result is not None and isinstance(result, dict):
                for k, v in result.items():
                    try:
                        variables[k] = cls._convert_to_json_serializable(v)
                    except Exception:
                        variables[k] = v
                logger.info(
                    f"[ScriptProcessor] 函数返回值已合并到 variables，共 {len(result)} 个键: {list(result.keys())}"
                )
            return {
                "result": result,
                "stdout": stdout_output,
                "stderr": stderr_output,
                "function_name": function_name,
                "variables": variables,
            }

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr


class SecurityError(Exception):
    """安全错误"""

    pass
