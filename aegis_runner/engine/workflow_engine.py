import pprint
import networkx as nx
import sys
import os
import importlib.util
import types
from typing import Any, Dict, List
from datetime import datetime

from aegis_runner.engine.context import ExecutionContext
from aegis_runner.engine.core.factory import ProcessorFactory
from aegis_runner.engine.core.elegant_processor_registry import elegant_processor_registry
# 延迟导入 StreamingWorkflowExecutor，避免循环导入
# from aegis_runner.engine.core.streaming_executor import StreamingWorkflowExecutor
from aegis_runner.engine.models import Workflow, Node, Edge, ExecutionResult, StepResult, ExecutionStatus, StepStatus
from aegis_runner.engine.core.simple_logger import logger
from aegis_runner.engine.core.exceptions import ValidationError, ExecutionError, ErrorCategory
from aegis_runner.engine.core.error_manager import error_manager
from aegis_runner.engine.models.configs import create_config
from aegis_runner.engine.core.log_collector import get_log_collector
from aegis_runner.engine.core.processor_discovery_paths import DEFAULT_PROCESSOR_DISCOVERY_PACKAGES
from aegis_runner.engine.core.processor_package_discovery import preload_processor_packages

# 导入平台鉴权函数
try:
    from aegis_runner.engine.core.platform_auth import (
        get_token,
        clear_token_cache,
        get_cache_info,
        refresh_token,
        validate_token
    )
    PLATFORM_AUTH_AVAILABLE = True
except ImportError:
    PLATFORM_AUTH_AVAILABLE = False
    logger.warning("[WorkflowExecutor] 平台鉴权模块未找到，函数式鉴权功能不可用")

def _preload_processor_modules():
    """预加载所有 discovery 路径下的处理器子模块，确保装饰器注册在 initialize 前完成。"""
    preload_processor_packages(
        DEFAULT_PROCESSOR_DISCOVERY_PACKAGES,
        log_tag="[WorkflowExecutor]",
    )


class WorkflowParser:
    """将前端的 JSON 解析为可执行的图结构。"""
    def __init__(self, workflow_data: Any):
        if isinstance(workflow_data, dict):
            self.workflow = Workflow.from_dict(workflow_data)
        elif isinstance(workflow_data, Workflow):
            self.workflow = workflow_data
        else:
            raise ValueError("不支持的工作流数据类型")
        
        self.graph = self.workflow._graph

    def parse(self) -> (nx.DiGraph, Dict[str, Node]):
        """解析工作流，返回图和节点映射"""
        if not self.workflow.is_acyclic():
            raise ValueError("工作流包含循环，无法执行。")
        
        node_map = {node.id: node for node in self.workflow.nodes}
        return self.graph, node_map


class WorkflowExecutor:
    """执行工作流的核心引擎。"""
    def __init__(self, workflow_data: Any, environment: str = None, hook_file: str = None, 
                 enable_shard_storage: bool = False, task_id: str = None, run_id: str = None):
        """
        初始化工作流执行器
        
        Args:
            workflow_data: 工作流数据
            environment: 环境名称（如：dev/test/uat/prod）
            hook_file: Hook函数文件路径（可选），用于加载自定义函数
            enable_shard_storage: 是否启用分片存储（解决大 workflow 内存问题）
            task_id: 任务ID（分片存储时必需）
            run_id: 运行ID（分片存储时必需）
        """
        self.workflow_data = workflow_data
        self.parser = WorkflowParser(workflow_data)
        self.graph, self.node_map = self.parser.parse()
        self.context = ExecutionContext(
            enable_shard_storage=enable_shard_storage,
            task_id=task_id,
            run_id=run_id
        )
        self.environment = environment
        self.execution_result = ExecutionResult(
            workflow_id=getattr(self.parser.workflow, 'work_id', 'unknown'),
            status=ExecutionStatus.PENDING
        )
        
        # 注册平台鉴权函数到上下文
        self._register_platform_auth_functions()
        
        # 如果指定了hook文件，加载自定义函数
        if hook_file:
            self._load_functions_from_file(hook_file)
        
        # 如果指定了环境，自动注入环境配置到上下文
        if environment:
            self._inject_environment_config(environment)
        
        # 自动注入预加载的Token到上下文
        self._inject_preloaded_tokens()
        
        # 加载工作流定义中的变量到执行上下文
        if isinstance(workflow_data, dict) and "variables" in workflow_data:
            variables = workflow_data["variables"]
            for key, value in variables.items():
                self.context.set_variable(key, value)
            logger.info(f"[WorkflowExecutor] 📌 已加载 {len(variables)} 个工作流变量: {list(variables.keys())}")
        
        # 预加载所有 discovery 路径下的处理器模块，避免工作目录/配置异常时部分处理器未注册
        _preload_processor_modules()
        # 初始化优雅的处理器注册中心（配置路径优先用 engine 包内，避免 cwd 导致找不到）
        _config_path = None
        try:
            from pathlib import Path
            _engine_dir = Path(__file__).resolve().parent
            _cfg = _engine_dir / "processor_config.yaml"
            if _cfg.exists():
                _config_path = str(_cfg)
        except Exception:
            pass
        elegant_processor_registry.initialize(config_file=_config_path)
        
        # 使用简化的日志系统

    def execute(self) -> ExecutionResult:
        """执行工作流"""
        workflow_id = self.execution_result.workflow_id
        logger.info(f"工作流开始执行: {workflow_id}")
        
        # 设置执行开始时间
        self.execution_result.start_time = datetime.now()
        self.execution_result.status = ExecutionStatus.RUNNING
        
        execution_order = list(nx.topological_sort(self.graph))
        logger.info(f"执行顺序: {execution_order}")

        # 获取日志收集器
        log_collector = get_log_collector()
        
        def format_logs_to_message(logs: List[Dict[str, Any]]) -> str:
            """将日志列表格式化为单个message字符串"""
            if not logs:
                return ""
            log_messages = []
            for log in logs:
                timestamp = log.get('timestamp', '')
                level = log.get('level', 'INFO')
                message = log.get('message', '')
                # 简化时间戳显示（只显示时间部分，去掉时区）
                if timestamp:
                    try:
                        # 如果包含时区信息，只取前面的部分
                        if '+' in timestamp or 'Z' in timestamp:
                            timestamp = timestamp.split('+')[0].split('Z')[0]
                    except:
                        pass
                log_messages.append(f"[{timestamp}] {level}: {message}")
            return "\n".join(log_messages)
        
        for index, node_id in enumerate(execution_order):
            node = self.node_map[node_id]
            node_type = node.type

            # 记录节点开始
            logger.info(f"开始执行节点: {node_id} (类型: {node_type})")

            # 创建步骤结果
            step_result = StepResult(
                node_id=node_id,
                node_type=node_type,
                status=StepStatus.PENDING,
                start_time=datetime.now()
            )
            
            # 开始收集该节点的日志
            log_collector.start_collection(node_id)


            # 检查前置条件是否满足（用于处理分支）
            # 采用"多路径或"逻辑：只要有一条路径激活，节点就应该执行
            # 只有当所有进入路径都失效时，才跳过该节点
            should_skip = False
            predecessors = list(self.graph.predecessors(node_id))
            
            if predecessors:
                # 检查是否有任何一条激活的路径
                has_active_path = False
                
                for pred_id in predecessors:
                    pred_node = self.node_map[pred_id]
                    
                    if pred_node.type == "condition":
                        # 条件节点：检查分支是否匹配
                        pred_result = self.context.get_node_result(pred_id)
                        edge_data = self.graph.get_edge_data(pred_id, node_id)
                        source_handle = edge_data.get('source_handle')

                        # 新版约定：condition 节点必须返回标准响应结构，
                        # 其中布尔结果存放在 body.result 中
                        if not isinstance(pred_result, dict):
                            raise ValueError(
                                f"[WorkflowExecutor] 条件节点 {pred_id} 返回了非标准结果类型: {type(pred_result)}"
                            )

                        body = pred_result.get("body", {})
                        if not isinstance(body, dict) or "result" not in body:
                            raise ValueError(
                                f"[WorkflowExecutor] 条件节点 {pred_id} 的响应中缺少 body.result 字段"
                            )

                        value = bool(body.get("result"))
                        branch_value = "true" if value else "false"

                        if branch_value == source_handle:
                            # 分支匹配，路径激活
                            logger.debug(
                                f"节点 {node_id} 的条件路径激活 "
                                f"(分支 '{branch_value}' == 边 '{source_handle}')"
                            )
                            has_active_path = True
                            break
                    else:
                        # 普通节点：检查前置节点是否成功执行（未被跳过）
                        # 如果前置节点有结果，说明它已经执行过
                        pred_result = self.context.get_node_result(pred_id)
                        if pred_result is not None:
                            logger.debug(
                                f"节点 {node_id} 的普通路径激活 (前置节点 {pred_id} 已执行)"
                            )
                            has_active_path = True
                            break
                
                # 只有没有任何激活路径时才跳过
                if not has_active_path:
                    logger.info(
                        f"跳过节点 {node_id}，因为没有任何激活的进入路径"
                    )
                    should_skip = True
            
            if should_skip:
                step_result.status = StepStatus.SKIPPED
                step_result.end_time = datetime.now()
                
                # 停止日志收集并获取日志（即使跳过也可能有日志）
                log_collector.stop_collection(node_id)
                logs_list = log_collector.get_logs(node_id)
                
                # 将所有日志拼接成一个字符串，存储在logs字段中
                step_result.logs = format_logs_to_message(logs_list)
                
                self.execution_result.add_step(step_result)
                logger.info(f"节点跳过: {node_id} (类型: {node_type})")
                continue

            # 获取所有前驱节点的输出作为当前节点的输入
            predecessor_results = {p: self.context.get_node_result(p) for p in predecessors}
            
            # 记录节点输入数据
            if predecessor_results:
                logger.info(f"节点输入: {node_id} - {len(predecessor_results)}个前置结果")

            try:
                processor = ProcessorFactory.get_processor(node_type)

                # 统一准备强类型配置对象，并进行可选校验
                # 注意：若类型创建或配置校验失败，将作为配置/执行错误向上抛出，由统一错误处理逻辑接管
                node_config = node.to_dict().get("data", {}).get("config", {})
                if node_config is None:
                    node_config = {}

                # 将 config 字典转换为强类型配置对象，挂载到 node.data 上，供处理器按需使用
                typed_config = create_config(node_type, node_config or {})
                node.data = node.data or {}
                node.data["_config_obj"] = typed_config

                # 当处理器没有自带 execute_with_error_handling（其内已校验）时，预先校验一次
                if hasattr(processor, 'validate_config') and not hasattr(processor, 'execute_with_error_handling'):
                    processor.validate_config(node_config)

                # 使用带错误处理的执行方法
                if hasattr(processor, 'execute_with_error_handling'):
                    raw_result = processor.execute_with_error_handling(
                        node.to_dict(),
                        self.context,
                        predecessor_results,
                    )
                else:
                    raw_result = processor.execute(node.to_dict(), self.context, predecessor_results)

                # 统一规范化节点结果，确保上下文中存储的是稳定结构（dict 为主）
                result = self._normalize_result(raw_result)

                # 仅保存到 node_results，不再注册为全局变量以节省内存
                # 如需引用前置节点输出，请使用变量提取处理器显式提取
                self.context.set_node_result(node_id, result)
                
                # 如果节点配置了自定义变量名，也保存一份
                node_data = node.to_dict().get("data", {})
                output_var_name = node_data.get("output_variable") or node_data.get("output_var")
                if output_var_name:
                    self.context.set_variable(output_var_name, result)
                    logger.info(f"✅ 节点结果已保存为自定义变量: ${{{output_var_name}}}")

                # 可选提取：若节点内配置了 extractions，则复用变量提取处理器进行提取
                extracted_vars = {}
                extraction_error = None  # 保存提取错误，稍后处理
                inline_extractions = node_data.get("extractions") or node_data.get("extract")
                if inline_extractions:
                    try:
                        extractor_processor = ProcessorFactory.get_processor("variable_extractor")

                        # 兼容两种写法：直接传列表 或 传 dict 包含 key "extractions"
                        if isinstance(inline_extractions, dict):
                            extractor_config = inline_extractions
                        else:
                            extractor_config = {"extractions": inline_extractions}

                        extractor_node_info = {
                            "id": f"{node_id}__inline_extractions",
                            "type": "variable_extractor",
                            "data": {
                                "config": extractor_config
                            }
                        }

                        if hasattr(extractor_processor, 'execute_with_error_handling'):
                            extraction_result = extractor_processor.execute_with_error_handling(
                                extractor_node_info,
                                self.context,
                                {node_id: result}
                            )
                        else:
                            extraction_result = extractor_processor.execute(
                                extractor_node_info,
                                self.context,
                                {node_id: result}
                            )
                        # 变量提取处理器返回 extracted_vars 字典
                        if isinstance(extraction_result, dict):
                            extracted_vars = extraction_result
                        logger.info(f"🧰 节点 {node_id} 内联变量提取完成")
                    except Exception as e:
                        logger.error(f"[WorkflowExecutor] 节点 {node_id} 内联变量提取失败: {str(e)}")
                        extraction_error = e  # 暂存错误，稍后处理

                # 可选断言：若节点内配置了 assertion，则复用断言处理器进行校验
                assertion_results = None
                assertion_error = None  # 保存断言错误，稍后处理
                inline_assertion = node_data.get("assertion") or node_data.get("assertions")
                if inline_assertion and isinstance(inline_assertion, dict):
                    try:
                        assertion_processor = ProcessorFactory.get_processor("assertion")
                        assertion_node_info = {
                            "id": f"{node_id}__inline_assertion",
                            "type": "assertion",
                            "data": {
                                "config": inline_assertion
                            }
                        }
                        # 使用当前节点产出的 result 作为断言输入
                        assertion_result = assertion_processor.execute_with_error_handling(
                            assertion_node_info,
                            self.context,
                            {node_id: result}
                        )
                        # 断言处理器返回包含 body.results 的字典结构
                        if isinstance(assertion_result, dict):
                            body = assertion_result.get("body", {})
                            raw_results = body.get("results", [])
                            
                            # 重新组织断言结果结构：将校验方式单独作为字段
                            # 从原始配置中获取 rules，以便提取 operator 和 target
                            rules = inline_assertion.get("rules", [])
                            
                            assertion_results = []
                            for idx, raw_result in enumerate(raw_results):
                                # 从原始结果中提取信息
                                actual = raw_result.get("actual")
                                passed = raw_result.get("passed")
                                rule_str = raw_result.get("rule", "")
                                
                                # 从原始配置中获取 operator 和 target
                                operator = None
                                target = None
                                source_path = None
                                if idx < len(rules):
                                    rule_config = rules[idx]
                                    operator = rule_config.get("operator")
                                    target = rule_config.get("target")
                                    source_path = rule_config.get("source")
                                
                                # 构建新的断言结果结构
                                assertion_results.append({
                                    "operator": operator,          # 校验方式（如 equals, contains 等）
                                    "actual": actual,              # 实际结果
                                    "target": target,              # 预期结果
                                    "rule": rule_str,              # 校验规则（完整描述）
                                    "passed": passed               # 是否通过
                                })
                        
                        logger.info(f"🧪 节点 {node_id} 内联断言通过")
                    except Exception as e:
                        logger.error(f"[WorkflowExecutor] 节点 {node_id} 内联断言失败: {str(e)}")
                        assertion_error = e  # 暂存错误，稍后处理

                # 将 assertion 和 extract_vars 添加到 output 中
                # 确保 result 是字典格式
                if not isinstance(result, dict):
                    result = {"body": result}

                result["assertion"] = assertion_results
                result["extract_vars"] = extracted_vars

                # 若节点返回了 body.variables（如脚本节点 function 的 return dict 合并进 variables），写入上下文供后续节点使用 $name、$beginTimeMs 等
                body = result.get("body") if isinstance(result.get("body"), dict) else {}
                output_vars = body.get("variables")
                if isinstance(output_vars, dict) and output_vars:
                    for var_name, var_value in output_vars.items():
                        self.context.set_variable(var_name, var_value)
                    logger.info(f"✅ 已将节点 {node_id} 的 body.variables 写入上下文: {list(output_vars.keys())}")

                # 如果变量提取失败，将错误信息添加到 result 中，但保留原始的请求/响应数据
                if extraction_error:
                    import traceback
                    error_traceback = traceback.format_exc()
                    
                    # 保留原始的请求/响应数据，同时添加错误信息
                    result["status"] = "error"
                    result["error"] = str(extraction_error)
                    result["error_code"] = "EXTRACTION_ERROR"
                    result["error_type"] = type(extraction_error).__name__
                    result["error_category"] = "extraction"
                    result["node_id"] = node_id
                    result["node_type"] = node_type
                    result["retryable"] = True
                    
                    step_result.status = StepStatus.FAILED
                    step_result.error = str(extraction_error)
                    step_result.output = result  # 保留完整的 result（包含请求/响应数据）
                    
                    # 停止日志收集并获取日志
                    log_collector.stop_collection(node_id)
                    logs_list = log_collector.get_logs(node_id)
                    step_result.logs = format_logs_to_message(logs_list)
                    
                    logger.error(f"[WorkflowExecutor] 节点 {node_id} 变量提取失败: {step_result.error}")
                    return self._finalize_failure(step_result, execution_order, index)

                # 如果断言失败，将错误信息添加到 result 中，但保留原始的请求/响应数据
                if assertion_error:
                    import traceback
                    error_traceback = traceback.format_exc()
                    
                    # 保留原始的请求/响应数据，同时添加错误信息
                    result["status"] = "error"
                    result["error"] = str(assertion_error)
                    result["error_code"] = "ASSERTION_ERROR"
                    result["error_type"] = type(assertion_error).__name__
                    result["error_category"] = "assertion"
                    result["node_id"] = node_id
                    result["node_type"] = node_type
                    result["retryable"] = True
                    
                    step_result.status = StepStatus.FAILED
                    step_result.error = str(assertion_error)
                    step_result.output = result  # 保留完整的 result（包含请求/响应数据）
                    
                    # 停止日志收集并获取日志
                    log_collector.stop_collection(node_id)
                    logs_list = log_collector.get_logs(node_id)
                    step_result.logs = format_logs_to_message(logs_list)
                    
                    logger.error(f"[WorkflowExecutor] 节点 {node_id} 执行失败: {step_result.error}")
                    return self._finalize_failure(step_result, execution_order, index)

                # 检查processor返回的状态，判断节点是否成功
                result_status = result.get("status", "success")
                if result_status in ["error", "failed"]:
                    # processor返回了错误状态，将节点标记为失败
                    step_result.status = StepStatus.FAILED
                    step_result.error = result.get("error") or result.get("message") or f"节点执行失败: {result_status}"
                    
                    # 增强错误响应结构，确保包含完整的错误信息
                    enhanced_result = result.copy()
                    
                    # 提取错误信息（从多个可能的位置）
                    error_message = (
                        result.get("error") or 
                        result.get("message") or 
                        (result.get("body", {}).get("error") if isinstance(result.get("body"), dict) else None) or
                        f"节点执行失败: {result_status}"
                    )
                    
                    # 补充缺失的错误字段
                    if "error" not in enhanced_result:
                        enhanced_result["error"] = error_message
                    if "error_type" not in enhanced_result:
                        enhanced_result["error_type"] = "ProcessorError"
                    if "error_code" not in enhanced_result:
                        enhanced_result["error_code"] = result.get("status_code", "PROCESSOR_ERROR")
                    if "error_category" not in enhanced_result:
                        enhanced_result["error_category"] = "execution"
                    if "node_id" not in enhanced_result:
                        enhanced_result["node_id"] = node_id
                    if "node_type" not in enhanced_result:
                        enhanced_result["node_type"] = node_type
                    if "retryable" not in enhanced_result:
                        enhanced_result["retryable"] = True  # 默认可重试
                    if "traceback" not in enhanced_result:
                        enhanced_result["traceback"] = None  # 处理器返回的错误通常没有 traceback
                    
                    step_result.output = enhanced_result
                    
                    # 将错误代码存储到metadata中（如果需要）
                    if enhanced_result.get("error_code"):
                        step_result.metadata["error_code"] = enhanced_result.get("error_code")
                    
                    # 停止日志收集并获取日志
                    log_collector.stop_collection(node_id)
                    logs_list = log_collector.get_logs(node_id)
                    step_result.logs = format_logs_to_message(logs_list)
                    
                    logger.error(f"[WorkflowExecutor] 节点 {node_id} 执行失败: {step_result.error}")
                    return self._finalize_failure(step_result, execution_order, index)
                else:
                    # 节点执行成功
                    step_result.status = StepStatus.SUCCESS
                    step_result.output = result
                    
                    # 记录节点输出数据
                    logger.info(f"节点输出: {node_id} - 执行成功")
                
            except ValidationError as e:
                # 配置验证错误
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(f"[WorkflowExecutor] 节点 {node_id} 配置验证失败: {e.message}")
                step_result.status = StepStatus.FAILED
                step_result.error = f"配置验证失败: {e.message}"
                
                # 构建完整的错误响应结构
                step_result.output = {
                    "status": "error",
                    "processor_type": node_type,
                    "error": e.message,
                    "error_code": getattr(e, 'error_code', 'VALIDATION_ERROR'),
                    "error_type": "ValidationError",
                    "error_category": getattr(e, 'category', 'validation').value if hasattr(getattr(e, 'category', None), 'value') else 'validation',
                    "node_id": node_id,
                    "node_type": node_type,
                    "traceback": error_traceback,
                    "suggestion": getattr(e, 'suggestion', '请检查节点配置是否正确'),
                    "body": None
                }
                
                # 停止日志收集并获取日志
                log_collector.stop_collection(node_id)
                logs_list = log_collector.get_logs(node_id)
                
                # 将所有日志拼接成一个字符串，存储在logs字段中
                step_result.logs = format_logs_to_message(logs_list)
                
                return self._finalize_failure(step_result, execution_order, index)
                
            except ExecutionError as e:
                # 执行错误
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(f"[WorkflowExecutor] 节点 {node_id} 执行失败: {e.message}")
                step_result.status = StepStatus.FAILED
                step_result.error = e.message
                
                # 构建完整的错误响应结构
                step_result.output = {
                    "status": "error",
                    "processor_type": node_type,
                    "error": e.message,
                    "error_code": getattr(e, 'error_id', 'EXECUTION_ERROR'),
                    "error_type": type(e).__name__,
                    "error_category": e.category.value if hasattr(e, 'category') else 'execution',
                    "node_id": node_id,
                    "node_type": node_type,
                    "operation": getattr(e, 'operation', None),
                    "retryable": getattr(e, 'retryable', False),
                    "traceback": error_traceback,
                    "original_error": str(e.original_error) if hasattr(e, 'original_error') and e.original_error else None,
                    "body": None
                }
                
                # 停止日志收集并获取日志
                log_collector.stop_collection(node_id)
                logs_list = log_collector.get_logs(node_id)
                
                # 将所有日志拼接成一个字符串，存储在logs字段中
                step_result.logs = format_logs_to_message(logs_list)
                
                return self._finalize_failure(step_result, execution_order, index)
                
            except Exception as e:
                # 其他未分类错误
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(f"[WorkflowExecutor] 节点 {node_id} 执行失败: {str(e)}")
                step_result.status = StepStatus.FAILED
                step_result.error = str(e)
                
                # 构建完整的错误响应结构
                step_result.output = {
                    "status": "error",
                    "processor_type": node_type,
                    "error": str(e),
                    "error_code": "UNKNOWN_ERROR",
                    "error_type": type(e).__name__,
                    "error_category": "unknown",
                    "node_id": node_id,
                    "node_type": node_type,
                    "retryable": False,
                    "traceback": error_traceback,
                    "suggestion": "请检查节点配置和输入数据是否正确，或联系技术支持",
                    "body": None
                }
                
                # 停止日志收集并获取日志
                log_collector.stop_collection(node_id)
                logs_list = log_collector.get_logs(node_id)
                
                # 将所有日志拼接成一个字符串，存储在logs字段中
                step_result.logs = format_logs_to_message(logs_list)
                
                return self._finalize_failure(step_result, execution_order, index)

            step_result.end_time = datetime.now()
            
            # 停止日志收集并获取日志
            log_collector.stop_collection(node_id)
            logs_list = log_collector.get_logs(node_id)
            
            # 将所有日志拼接成一个字符串，存储在logs字段中
            step_result.logs = format_logs_to_message(logs_list)
            
            # ==================== 分片存储：立即保存节点结果 ====================
            # 如果启用了分片存储，立即将结果保存到 Redis，step_result.output 只保存引用
            if self.context.is_shard_storage_enabled() and step_result.status == StepStatus.SUCCESS:
                try:
                    # 立即分片存储
                    self.context.set_node_result_with_shard(
                        node_id=node_id,
                        result=step_result.output,
                        node_type=node_type,
                        status="success",
                        start_time=step_result.start_time,
                        end_time=step_result.end_time,
                        logs=step_result.logs,
                        metadata=step_result.metadata
                    )
                    # step_result.output 只保存引用和摘要
                    step_storage = self.context.get_step_storage()
                    if step_storage:
                        step_refs = step_storage.get_step_refs()
                        step_ref = step_refs.get(node_id)
                        if step_ref:
                            # 获取摘要
                            summary = step_storage.get_node_summary(node_id)
                            step_result.output = {
                                "_shard_stored": True,
                                "storage_key": step_ref.storage_key,
                                "summary": summary
                            }
                            logger.debug(f"[WorkflowExecutor] 节点 {node_id} 结果已分片存储，output 只保留引用")
                except Exception as e:
                    logger.warning(f"[WorkflowExecutor] 节点 {node_id} 分片存储失败: {e}，保留完整结果")
                    # 分片存储失败，保留完整结果（降级处理）
            # ==================== 分片存储结束 ====================
            
            self.execution_result.add_step(step_result)
            
            # 记录节点结束
            duration = (step_result.end_time - step_result.start_time).total_seconds()
            logger.info(f"节点执行完成: {node_id} (状态: SUCCESS) (耗时: {duration:.3f}s)")

        self.execution_result.status = ExecutionStatus.SUCCESS
        self.execution_result.end_time = datetime.now()
        
        # 保存上下文变量
        # 如果启用了分片存储，只保存变量摘要，不保存完整数据
        if self.context.is_shard_storage_enabled():
            # 分片存储模式：只保存变量名和摘要
            variables_summary = {}
            for key, value in self.context._variables.items():
                if isinstance(value, dict) and (value.get("_shard_stored") or value.get("_truncated")):
                    # 这是分片存储的节点结果或大值，只保存摘要
                    variables_summary[key] = {
                        "_shard_stored": True,
                        "summary": value.get("summary") or value
                    }
                else:
                    # 普通变量，直接保存
                    variables_summary[key] = value
            self.execution_result.variables = variables_summary
            logger.debug(f"[WorkflowExecutor] 分片存储模式：变量已保存为摘要（{len(variables_summary)} 个变量）")
        else:
            # 传统模式：保存完整变量
            self.execution_result.variables = self.context._variables
        
        # 记录工作流结束
        total_duration = (self.execution_result.end_time - self.execution_result.start_time).total_seconds()
        logger.info(f"工作流执行完成: {workflow_id} (状态: SUCCESS) (总耗时: {total_duration:.3f}s)")
        
        # 可选：清理工作流相关的连接池空闲连接
        # 注意：这里不关闭连接池，只是清理空闲连接，保持连接池复用
        try:
            from aegis_runner.engine.core.connection_pool import connection_pool
            # 获取所有连接池键（基于工作流中使用的数据库连接）
            # 这里可以根据实际需求决定是否清理
            # connection_pool.cleanup_workflow_pools()  # 可选调用
        except Exception as e:
            logger.debug(f"清理连接池时出错（可忽略）: {e}")

        return self.execution_result
    
    def _finalize_failure(self, step_result: StepResult, execution_order: List[str], failed_index: int) -> ExecutionResult:
        """
        统一处理失败收尾，补充未执行节点的占位结果并返回 ExecutionResult
        """
        # 补充失败节点的时间戳
        step_result.end_time = datetime.now()
        self.execution_result.add_step(step_result)
        
        # 将后续未执行的节点标记为PENDING（未执行状态），便于调用方看到完整节点列表
        pending_count = 0
        for pending_node_id in execution_order[failed_index + 1:]:
            pending_node = self.node_map[pending_node_id]
            pending_step = StepResult(
                node_id=pending_node_id,
                node_type=pending_node.type,
                status=StepStatus.PENDING,  # 使用PENDING状态表示未执行
                start_time=None,
                end_time=None
            )
            self.execution_result.add_step(pending_step)
            pending_count += 1
        
        if pending_count > 0:
            logger.info(f"[WorkflowExecutor] 📋 已添加 {pending_count} 个未执行节点（状态: PENDING）到执行结果中")
        
        # 标记失败并补齐元数据
        self.execution_result.status = ExecutionStatus.FAILED
        self.execution_result.end_time = datetime.now()
        self.execution_result.variables = self.context._variables

        return self.execution_result
    
    def _inject_environment_config(self, environment: str):
        """
        注入环境配置到执行上下文
        
        Args:
            environment: 环境名称
        """
        try:
            from aegis_runner.engine.core.environment_config import env_config_manager
            # 获取环境配置
            env_profile = env_config_manager.get_environment(environment)
            if not env_profile:
                logger.warning(f"[WorkflowExecutor] ⚠️ 环境不存在: {environment}，跳过环境配置注入")
                return
            
            if not env_profile.enabled:
                logger.warning(f"[WorkflowExecutor] ⚠️ 环境已禁用: {environment}")
                return
            
            logger.info(f"[WorkflowExecutor] 🌍 开始注入环境配置: {environment} ({env_profile.display_name})")
            
            # 注入1: API Base URLs
            for service, url in env_profile.api_base_urls.items():
                var_name = f"{service}_base_url"
                self.context.set_variable(var_name, url)
                logger.info(f"[WorkflowExecutor] 📝 注入API地址: {var_name} = {url}")
            
            # 注入2: API凭证映射
            for service, credential_id in env_profile.api_credentials.items():
                var_name = f"{service}_credential_id"
                self.context.set_variable(var_name, credential_id)
                logger.info(f"[WorkflowExecutor] 🔐 注入API凭证: {var_name} = {credential_id}")
            
            # 注入3: 数据库配置
            for db_name, db_config in env_profile.database_configs.items():
                self.context.set_variable(db_name, db_config)
                logger.info(f"[WorkflowExecutor] 🗄️  注入数据库配置: {db_name}")
            
            # 注入4: 环境变量
            for key, value in env_profile.environment_variables.items():
                self.context.set_variable(key, value)
                logger.info(f"[WorkflowExecutor] 📌 注入环境变量: {key} = {value}")
            
            # 注入5: 自定义配置
            for key, value in env_profile.custom_configs.items():
                self.context.set_variable(key, value)
                logger.info(f"[WorkflowExecutor] ⚙️  注入自定义配置: {key} = {value}")
            
            # 注入6: 环境元数据
            self.context.set_variable("CURRENT_ENVIRONMENT", environment)
            self.context.set_variable("ENVIRONMENT_NAME", env_profile.display_name)
            logger.info(f"[WorkflowExecutor] 🏷️  当前环境: {environment} ({env_profile.display_name})")
            
            logger.info(f"[WorkflowExecutor] ✅ 环境配置注入完成")
            
        except ImportError:
            logger.warning(f"[WorkflowExecutor] ⚠️ 环境配置模块未导入，跳过环境配置注入")
        except Exception as e:
            logger.error(f"[WorkflowExecutor] ❌ 环境配置注入失败: {str(e)}")
    
    def _register_platform_auth_functions(self):
        """
        注册平台鉴权函数到执行上下文
        
        将平台鉴权相关的函数注册到context中，
        这样工作流中可以使用：${get_token($email, $password, $url, $header_type)}
        """
        if not PLATFORM_AUTH_AVAILABLE:
            return
        
        try:
            # 注册平台鉴权函数
            auth_functions = {
                'get_token': get_token,
                'clear_token_cache': clear_token_cache,
                'get_cache_info': get_cache_info,
                'refresh_token': refresh_token,
                'validate_token': validate_token,
            }
            
            self.context.register_functions(auth_functions)
            
            logger.info(f"[WorkflowExecutor] ✅ 已注册 {len(auth_functions)} 个平台鉴权函数")
            
        except Exception as e:
            logger.warning(f"[WorkflowExecutor] ⚠️ 平台鉴权函数注册失败: {str(e)}")
    
    def _load_functions_from_file(self, file_path: str):
        """
        从指定文件加载Hook函数到执行上下文
        
        Args:
            file_path: Hook函数文件的路径（绝对路径或相对路径）
        
        将文件中定义的所有函数注册到context中，
        这样工作流中可以使用：${function_name(...)}
        """
        logger.info(f"[WorkflowExecutor] 🔍 开始加载Hook文件: {file_path}")
        
        try:
            # 检查文件是否存在
            abs_path = os.path.abspath(file_path)
            if not os.path.exists(abs_path):
                logger.warning(f"[WorkflowExecutor] ⚠️ Hook文件不存在: {abs_path}")
                return
            
            logger.info(f"[WorkflowExecutor] 📄 Hook文件路径: {abs_path}")
            
            # 临时将文件所在目录加入导入路径，支持 hook 文件引用同目录辅助模块。
            file_dir = os.path.dirname(abs_path)
            inserted_to_sys_path = False
            if file_dir not in sys.path:
                sys.path.insert(0, file_dir)
                inserted_to_sys_path = True
                logger.info(f"[WorkflowExecutor] 📁 已临时将目录添加到sys.path: {file_dir}")
            
            # 获取模块名称（文件名，不包含扩展名）
            module_name = os.path.splitext(os.path.basename(abs_path))[0]
            logger.info(f"[WorkflowExecutor] 📦 模块名称: {module_name}")
            
            # 使用 importlib.util 动态加载模块
            spec = importlib.util.spec_from_file_location(module_name, abs_path)
            if spec is None or spec.loader is None:
                logger.error(f"[WorkflowExecutor] ❌ 无法创建模块spec: {abs_path}")
                return
            
            module = importlib.util.module_from_spec(spec)
            logger.info(f"[WorkflowExecutor] 🔄 开始执行模块...")
            spec.loader.exec_module(module)
            logger.info(f"[WorkflowExecutor] ✅ 模块执行完成")
            
            # 提取模块中的所有函数
            hook_functions = {}
            module_vars = vars(module)
            logger.info(f"[WorkflowExecutor] 🔍 模块中的对象数量: {len(module_vars)}")
            
            for name, item in module_vars.items():
                # 只提取函数类型，排除私有函数（以_开头的函数）
                if isinstance(item, types.FunctionType) and not name.startswith('_'):
                    hook_functions[name] = item
                    logger.debug(f"[WorkflowExecutor] 📝 找到函数: {name}")
            
            if hook_functions:
                # 注册函数到上下文
                self.context.register_functions(hook_functions)
                logger.info(f"[WorkflowExecutor] ✅ 已从 {abs_path} 加载 {len(hook_functions)} 个Hook函数: {list(hook_functions.keys())}")
            else:
                logger.warning(f"[WorkflowExecutor] ⚠️ Hook文件中未找到可用的函数: {abs_path}")
                logger.warning(f"[WorkflowExecutor] 💡 提示: 请确保文件中定义了公开函数（不以_开头的函数）")
            
            if inserted_to_sys_path:
                try:
                    sys.path.remove(file_dir)
                    logger.info(f"[WorkflowExecutor] ♻️ 已恢复sys.path: {file_dir}")
                except ValueError:
                    logger.warning(f"[WorkflowExecutor] ⚠️ 恢复sys.path时未找到目录: {file_dir}")
                
        except Exception as e:
            logger.error(f"[WorkflowExecutor] ❌ 加载Hook文件失败 {file_path}: {str(e)}", exc_info=True)
    
    def _inject_preloaded_tokens(self):
        """
        注入预加载的Token到执行上下文
        
        从TokenManager获取所有预加载的Token并注入到context
        这样工作流中可以直接使用 ${TOKEN_NAME} 引用
        """
        try:
            from aegis_runner.engine.core.token_manager import token_manager
            
            # 将所有有效Token注入到上下文
            token_manager.inject_tokens_to_context(self.context)
            
        except ImportError:
            # Token管理器是可选的，如果未导入则跳过
            pass
        except Exception as e:
            logger.warning(f"[WorkflowExecutor] ⚠️ Token注入失败: {str(e)}")

    def _normalize_result(self, raw_result: Any) -> Any:
        """
        规范化处理器返回结果：
        - 若为具有 to_dict 方法的对象（如 ProcessorResponse），则转换为 dict
        - 否则原样返回，保持向后兼容
        """
        try:
            if hasattr(raw_result, "to_dict") and callable(getattr(raw_result, "to_dict")):
                return raw_result.to_dict()
        except Exception:
            # 转换失败时退回原始结果，避免影响执行链
            return raw_result
        return raw_result



if __name__ == "__main__":
    # 直接使用对象初始化工作流数据
    workflow_data = {
        "work_id":"work_id-test",
        "work_name":"work_name",
        "nodes": [

            {
                "id": "login",
                "name": "登录",
                "type": "http_request",
                "data": {
                    "config": {
                        "method": "POST",
                        "url": "http://api.tst.spotterio.com/spotter-marketing-web/gmesh/promotionCentral/product/page",
                        "json": {"tabName":"promotion_error","pageSize":20,"sortQuery":{},"currentPage":1,"endTimeMsRange":{},"startTimeMsRange":{}},
                        "headers": {
                            "x-app": "gmesh",
                            "Content-Type": "application/json",
                            "x-site-tenant": "US_AMZ",
                            "Authentication-Token": "${get_token($email,$password,$url,$header_type)}",
                            "x-sso-version":"v3",
                            "x-spotter-i18n":"zh_Hans",

                        }
                    },
                    "assertion": {
                        "rules": [
                            {"source": "body.data.pageSize", "operator": "equals", "target": 20},
                            {"source": "$password", "operator": "equals", "target": "$password"}

                        ]

                    },
                    "extractions": [
                        {
                            "source_path": "body.code",
                            "var_name": "userId"
                        }
                    ]

                }
            },

            {
                "id": "dubbo调用",
                "name": "dubbo调用",
                "type": "dubbo",
                "data": {
                    "config": {
                        "url": "${dubbo_url}",
                        "application_name": "spotter-order",
                        "interface_name": "com.spotter.order.api.IOrderAmzItemService",
                        "method_name": "listByAmzCodeList",
                        "param_types": ["java.util.List"],
                        "params": [["P04AB1CUL4"]],
                        "site_tenant": "US_AMZ"
                    },
                    "assertion": {
                        "rules": [
                            {
                                "source": "body.data[0].companyName",
                                "operator": "string_equals",
                                "target": "${companyName}",
                                "message": "不是宇宙中心断言失败。"
                            }
                        ]
                    },
                    "extractions": [
                        {
                            "var_name": "orderType",
                            "source_path": "body.data[0].orderType"
                        },
                        {
                            "var_name": "companyName",
                            "source_path": "body.data[0].companyName"
                        },
                        {
                            "var_name": "dubbo_message",
                            "source_path": "body.message"
                        }
                    ]
                }
            },
            {
                "id": "check_dubbo_success",
                "name": "check_dubbo_success",
                "type": "condition",
                "data": {
                    "config": {
                        "expression": "'${dubbo_message}' == 'success'"
                    }
                }
            },
            {
                "id": "loop_process",
                "name": "循环处理器",
                "type": "loop",
                "data": {
                    "config": {
                        "loop_type": "foreach_loop",
                        "items": "${dubbo调用.body.data}",
                        "item_variable": "order_item",
                        "index_variable": "order_index",
                        "delay": 0.1,
                        "sub_nodes": [
                            {
                                "type": "log_message",
                                "data": {
                                    "config": {
                                        "message": "处理订单 "
                                    }
                                }
                            }
                        ],
                        "output_variable": "loop_result"
                    }
                }
            },
            {
                "id": "sql_query",
                "name": "sql查询",
                "type": "mysql",
                "data": {
                    "config": {
                        "sql": "SELECT id,strategy_name FROM spotter_plutus.plutus_finance_strategy_config where deleted_at is null and (svc_id_list like '[5,' or svc_id_list like ',5,' or svc_id_list like ',5]' or svc_id_list like '[5]');",
                        "operation": "select",
                        "connection": {
                            "host": "mysql.dev.spotter.ink",
                            "port": 30070,
                            "user": "root",
                            "password": "root",
                            "database": "spotter_plutus"
                        }
                    },
                    "assertion": {
                        "rules": [
                            {
                                "source": "body.data[0].name",
                                "operator": "string_equals",
                                "target": "Yuki",
                                "message": "期望用户名为张三！实际查询不是张三或无数据。"
                            }
                        ]
                    },
                    "extractions": [
                        {
                            "var_name": "email",
                            "source_path": "body.data[0].email"
                        }
                    ]
                }
            },
            {
                "id": "send_mq_message",
                "name": "mq 发送",
                "type": "rocketmq",
                "data": {
                    "config": {
                        "topic": "SUPPLY_LINK_RET",
                        "message_body": '{"type":"normal","eventId":"KEPtFogQ5hWE2Pkw","payloads":[{"ssku":"ssku6623462","status":5,"amzPoNo":"AmzOrderNol077D","outNums":6,"syncFlag":false,"companyId":54,"innerPack":1,"orderCode":"AmzOrderNol077D","transType":"SP","outboundNo":"VCOUTBOUNDno7625558","saOrderCode":"SAno8884792","outboundDate":1761126325103,"outboundType":1,"orderTotalNums":6,"outStorageCode":"CNSZSN91752A","outboundDateMs":1761126325103,"channelOrderCode":"AmzOrderNol077D","vcpoShipmentCode":"VCOUTBOUNDno7625558","fulfillmentOrderNo":"FoNoFZTTD"}],"eventName":"OutboundFinanceEvent","retryTimes":0,"sourceService":"spotter-warehouse","eventClassPath":"com.spotter.warehouse.event.OutboundFinanceEvent","eventTriggerMs":1724211900815,"destinationService":[],"targetListenerClassPath":""}',
                        "mq_url": "http://api.dev.spotterio.com/spotter-utility-web/mock/sendMQMessage",
                        "site_tenant": "DEFAULT",
                        "tag": "*",
                        "key": "*"
                    },
                    "assertion": {
                        "rules": [
                            {
                                "source": "status_code",
                                "operator": "string_equals",
                                "target": 500,
                                "message": "MQ消息发送失败"
                            }
                        ]
                    },
                    "extractions": [
                        {
                            "var_name": "error_code",
                            "source_path": "error_code"
                        }
                    ]
                }
            },
            {
                "id": "log_not_user_1",
                "name": "日志打印",
                "type": "log_message",
                "data": {
                    "config": {
                        "message": "检测到用户ID (${userId}) 不是 1，跳过获取详情。MQ消息ID: ${mq_msg_id}"
                    }
                }
            },
            {
                "id": "final_log",
                "type": "log_message",
                "data": {
                    "config": {
                        "message": "流程结束。"
                    }
                }
            }
        ],
        "edges": [
            {"id": "e1", "source": "login", "target": "dubbo调用"},
            {"id": "e2", "source": "dubbo调用", "target": "check_dubbo_success"},
            {"id": "e3", "source": "check_dubbo_success", "target": "loop_process", "source_handle": "true"},
            {"id": "e4", "source": "check_dubbo_success", "target": "sql_query", "source_handle": "false"},
            {"id": "e5", "source": "loop_process", "target": "send_mq_message"},
            {"id": "e6", "source": "sql_query", "target": "send_mq_message"},
            {"id": "e7", "source": "send_mq_message", "target": "log_not_user_1"},
            {"id": "e8", "source": "log_not_user_1", "target": "final_log"},
        ]
    }

    # 实例化并执行
    executor = WorkflowExecutor(workflow_data, hook_file="/Users/jan/PycharmProjects/aegis-runner/hooks.py")
    # 延迟导入避免循环导入
    # from aegis_runner.engine.core.streaming_executor import StreamingWorkflowExecutor
    # executor = StreamingWorkflowExecutor(workflow_data)
    # print(executor.workflow_data)

    executor.context.set_variable("email", "admin@spotterio.com")
    executor.context.set_variable("password", "MTExMTEx")
    executor.context.set_variable("url", "http://api.tst.spotterio.com")
    executor.context.set_variable("header_type", "gmesh")
    executor.context.set_variable("sevc_url","http://api.dev.spotterio.com")
    executor.context.set_variable("dubbo_url","http://spotter-snap-rpc.tst.spotter.ink/rpc/invoke-async")
    
    # 流式执行并打印每个事件
    print("\n" + "="*60)
    print("开始流式执行工作流")
    print("="*60 + "\n")
    

    # 打印最终执行结果
    executor.execute()
    execution_result = executor.execution_result
    print("\n最终执行结果:")
    print(f"  工作流ID: {execution_result.workflow_id}")
    print(f"  执行状态: {execution_result.status.value if hasattr(execution_result.status, 'value') else execution_result.status}")
    if execution_result.start_time and execution_result.end_time:
        execution_result.duration = (execution_result.end_time - execution_result.start_time).total_seconds()
        print(f"  执行时间: {execution_result.duration:.4f} 秒")
    print(f"  总步骤数: {len(execution_result.steps)}")
    print(f"  成功步骤: {len([s for s in execution_result.steps if (hasattr(s.status, 'value') and s.status.value == 'success') or (isinstance(s.status, str) and s.status == 'success')])}")
    print(f"  失败步骤: {len([s for s in execution_result.steps if (hasattr(s.status, 'value') and s.status.value == 'failed') or (isinstance(s.status, str) and s.status == 'failed')])}")

    # 也可以打印完整的执行结果
    print("\n完整执行结果（字典格式）:")
    pprint.pprint(execution_result.to_dict() if hasattr(execution_result, 'to_dict') else execution_result, indent=2, width=120)


    # 记录最终报告
    logger.info(f"工作流ID: {execution_result.workflow_id}")
    logger.info(f"执行状态: {execution_result.status.value}")

    # 计算 duration 并处理 None 的情况
    if execution_result.start_time and execution_result.end_time:
        execution_result.duration = (execution_result.end_time - execution_result.start_time).total_seconds()
    else:
        execution_result.duration = None

    if execution_result.duration is not None:
        logger.info(f"执行时间: {execution_result.duration:.4f} 秒")
    else:
        logger.info("执行时间: 无法计算")
    logger.info(f"成功率: {execution_result.get_success_rate():.2%}")
    logger.info(f"总步骤数: {len(execution_result.steps)}")
    logger.info(f"成功步骤: {len(execution_result.get_successful_steps())}")
    logger.info(f"失败步骤: {len(execution_result.get_failed_steps())}")
    logger.info(f"跳过步骤: {len(execution_result.get_skipped_steps())}")
    # print(execution_result.steps[0].output)

    # 打印第一个节点的日志（用于测试）

    pprint.pprint(execution_result.to_dict())
