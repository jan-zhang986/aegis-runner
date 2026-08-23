"""
循环控制器处理器

支持多种循环类型：
1. 次数循环 (count_loop) - 按指定次数执行
2. While 循环 (while_loop) - 按条件执行
3. ForEach 循环 (foreach_loop) - 遍历集合执行

参考循环控制器设计
"""

import json
import time
from typing import Any, Dict, List, Union
from src.engine.core.processors import BaseProcessor, render_recursive
from src.engine.core.exceptions import ValidationError, ExecutionError
from src.engine.core.simple_logger import logger
from src.engine.core.elegant_processor_registry import register_processor, ProcessorCategory
from src.engine.core.factory import ProcessorFactory
from src.engine.models.response import ResponseBuilder

# 变量提取处理器类型，用于循环子节点内联提取
VARIABLE_EXTRACTOR_TYPE = "variable_extractor"


@register_processor(
    processor_type="loop",
    category=ProcessorCategory.WORKFLOW,
    description="循环控制器处理器，支持次数循环、While循环和ForEach循环",
    tags={"loop", "control", "workflow", "iteration"},
    enabled=True,
    priority=50,
    version="1.0.0",
    author="Aegis Team"
)
class LoopProcessor(BaseProcessor):
    """循环控制器处理器"""
    
    def _get_config_schema_name(self) -> str:
        """获取配置模式名称"""
        return "loop"
    
    def _validate_specific_config(self, config: Dict[str, Any]) -> bool:
        """循环特定的配置验证 - 代理给validate_config"""
        try:
            self.validate_config(config)
            return True
        except ValidationError:
            return False
    
    def __init__(self):
        super().__init__()
        self.processor_type = "loop"
        self.processor_name = "循环控制器"
        self.processor_description = "支持次数循环、While循环和ForEach循环的控制器"
    
    def validate_config(self, config: Dict[str, Any]) -> None:
        """
        验证配置参数
        
        Args:
            config: 配置参数
        """
        # 检查循环类型
        loop_type = config.get('loop_type')
        if not loop_type:
            raise ValidationError(
                message="loop_type 不能为空",
                field_name="loop_type",
                field_value=None,
                validation_rule="required"
            )
        
        if loop_type not in ['count_loop', 'while_loop', 'foreach_loop']:
            raise ValidationError(
                message="loop_type 必须是 count_loop、while_loop 或 foreach_loop 之一",
                field_name="loop_type",
                field_value=loop_type,
                validation_rule="enum"
            )
        
        # 根据循环类型验证特定参数
        if loop_type == 'count_loop':
            self._validate_count_loop_config(config)
        elif loop_type == 'while_loop':
            self._validate_while_loop_config(config)
        elif loop_type == 'foreach_loop':
            self._validate_foreach_loop_config(config)
        
        # 验证通用参数
        self._validate_common_config(config)
    
    def _validate_count_loop_config(self, config: Dict[str, Any]) -> None:
        """验证次数循环配置"""
        count = config.get('count')
        if count is None:
            raise ValidationError(
                message="次数循环需要指定 count 参数",
                field_name="count",
                field_value=None,
                validation_rule="required"
            )
        
        if not isinstance(count, (int, str)):
            raise ValidationError(
                message="count 必须是整数或可转换为整数的字符串",
                field_name="count",
                field_value=count,
                validation_rule="type"
            )
        
        # 尝试转换为整数
        try:
            count_int = int(count)
            if count_int <= 0:
                raise ValidationError(
                    message="count 必须大于 0",
                    field_name="count",
                    field_value=count,
                    validation_rule="range"
                )
        except ValueError:
            raise ValidationError(
                message="count 无法转换为整数",
                field_name="count",
                field_value=count,
                validation_rule="format"
            )
    
    def _validate_while_loop_config(self, config: Dict[str, Any]) -> None:
        """验证 While 循环配置"""
        condition = config.get('condition')
        if not condition:
            raise ValidationError(
                message="While 循环需要指定 condition 参数",
                field_name="condition",
                field_value=None,
                validation_rule="required"
            )
        
        if not isinstance(condition, str):
            raise ValidationError(
                message="condition 必须是字符串",
                field_name="condition",
                field_value=condition,
                validation_rule="type"
            )
        
        # 检查最大循环次数（防止无限循环）
        max_iterations = config.get('max_iterations', 1000)
        if not isinstance(max_iterations, (int, str)):
            raise ValidationError(
                message="max_iterations 必须是整数或可转换为整数的字符串",
                field_name="max_iterations",
                field_value=max_iterations,
                validation_rule="type"
            )
        
        try:
            max_iterations_int = int(max_iterations)
            if max_iterations_int <= 0:
                raise ValidationError(
                    message="max_iterations 必须大于 0",
                    field_name="max_iterations",
                    field_value=max_iterations,
                    validation_rule="range"
                )
        except ValueError:
            raise ValidationError(
                message="max_iterations 无法转换为整数",
                field_name="max_iterations",
                field_value=max_iterations,
                validation_rule="format"
            )
    
    def _validate_foreach_loop_config(self, config: Dict[str, Any]) -> None:
        """验证 ForEach 循环配置"""
        items = config.get('items')
        if not items:
            raise ValidationError(
                message="ForEach 循环需要指定 items 参数",
                field_name="items",
                field_value=None,
                validation_rule="required"
            )
        
        if not isinstance(items, (list, str)):
            raise ValidationError(
                message="items 必须是列表或可解析为列表的字符串",
                field_name="items",
                field_value=items,
                validation_rule="type"
            )
        
        # 如果是字符串，尝试解析为 JSON（但跳过变量占位符）
        if isinstance(items, str):
            # 如果包含变量占位符，跳过 JSON 验证（将在运行时渲染）
            if '${' not in items and '$' not in items:
                try:
                    parsed_items = json.loads(items)
                    if not isinstance(parsed_items, list):
                        raise ValidationError(
                            message="items 字符串解析后必须是列表",
                            field_name="items",
                            field_value=items,
                            validation_rule="format"
                        )
                except json.JSONDecodeError:
                    raise ValidationError(
                        message="items 字符串无法解析为有效的 JSON",
                        field_name="items",
                        field_value=items,
                        validation_rule="format"
                    )
    
    def _validate_common_config(self, config: Dict[str, Any]) -> None:
        """验证通用配置"""
        # 验证子节点配置
        sub_nodes = config.get('sub_nodes', [])
        if not isinstance(sub_nodes, list):
            raise ValidationError(
                message="sub_nodes 必须是列表",
                field_name="sub_nodes",
                field_value=sub_nodes,
                validation_rule="type"
            )
        
        # 验证延迟时间
        delay = config.get('delay', 0)
        if not isinstance(delay, (int, float, str)):
            raise ValidationError(
                message="delay 必须是数字或可转换为数字的字符串",
                field_name="delay",
                field_value=delay,
                validation_rule="type"
            )
        
        try:
            delay_float = float(delay)
            if delay_float < 0:
                raise ValidationError(
                    message="delay 不能为负数",
                    field_name="delay",
                    field_value=delay,
                    validation_rule="range"
                )
        except ValueError:
            raise ValidationError(
                message="delay 无法转换为数字",
                field_name="delay",
                field_value=delay,
                validation_rule="format"
            )
    
    def execute(self, node_info: dict, context: Any, predecessor_results: dict) -> Dict[str, Any]:
        """
        执行循环控制逻辑
        
        Args:
            node_info: 节点信息，包含配置等
            context: 执行上下文
            predecessor_results: 前置节点结果
            
        Returns:
            执行结果
        """
        start_time = time.time()
        
        try:
            # 从 node_info 中提取配置
            config = node_info.get("data", {}).get("config", {})
            
            # 子节点配置中可能包含循环变量（如 ${id}、${index}），需在每轮迭代时再渲染，
            # 此处先排除 sub_nodes，只渲染循环级配置（如 items、item_variable、delay 等）
            sub_nodes_raw = config.get("sub_nodes", [])
            config_without_sub_nodes = {k: v for k, v in config.items() if k != "sub_nodes"}
            rendered_config = render_recursive(config_without_sub_nodes, context)
            rendered_config["sub_nodes"] = sub_nodes_raw

            # 验证渲染后的配置
            self.validate_config(rendered_config)
            
            loop_type = rendered_config.get('loop_type')
            
            # 记录详细的循环请求信息
            import json
            request_details_lines = [
                "================== Loop Request Details ==================",
                f"Loop Type    : {loop_type}",
                f"Node ID      : {node_info.get('id', 'N/A')}",
            ]
            
            if loop_type == 'count_loop':
                count = rendered_config.get('count', 'N/A')
                delay = rendered_config.get('delay', 0)
                request_details_lines.extend([
                    f"Count        : {count}",
                    f"Delay        : {delay}s",
                ])
            elif loop_type == 'while_loop':
                condition = rendered_config.get('condition', 'N/A')
                max_iterations = rendered_config.get('max_iterations', 'N/A')
                request_details_lines.extend([
                    f"Condition    : {condition}",
                    f"Max Iterations: {max_iterations}",
                ])
            elif loop_type == 'foreach_loop':
                items = rendered_config.get('items', 'N/A')
                item_var = rendered_config.get('item_variable', 'item')
                items_display = json.dumps(items, indent=2, ensure_ascii=False) if isinstance(items, (list, dict)) else str(items)
                request_details_lines.extend([
                    f"Items        : {items_display}",
                    f"Item Variable: {item_var}",
                ])
            
            sub_nodes_count = len(rendered_config.get('sub_nodes', []))
            request_details_lines.append(f"Sub Nodes    : {sub_nodes_count}")
            
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
            
            # 根据循环类型执行相应逻辑
            if loop_type == 'count_loop':
                result = self._execute_count_loop(rendered_config, context)
            elif loop_type == 'while_loop':
                result = self._execute_while_loop(rendered_config, context)
            elif loop_type == 'foreach_loop':
                result = self._execute_foreach_loop(rendered_config, context)
            else:
                duration = time.time() - start_time
                return ResponseBuilder.error(
                    processor_type="loop",
                    error=f"不支持的循环类型: {loop_type}",
                    error_code="INVALID_LOOP_TYPE",
                    status_code=400,
                    duration=duration
                ).to_dict()
            
            logger.info(f"[LoopProcessor] {loop_type} 循环执行完成，共执行 {result['iterations']} 次")
            
            # 记录详细的循环响应信息
            duration = time.time() - start_time
            iterations = result.get('iterations', 0)
            results_list = result.get('results', [])
            status_emoji = "✅ 成功" if iterations > 0 else "⚠️ 未执行"
            
            response_details_lines = [
                "================== Loop Response Details ==================",
                f"Status       : {status_emoji}",
                f"Loop Type    : {loop_type}",
                f"Iterations   : {iterations}",
                f"Results Count: {len(results_list)}",
                f"Duration     : {duration:.3f}s",
            ]
            
            # 显示每次迭代的结果摘要
            if results_list:
                response_details_lines.append("Iteration Results:")
                for i, iter_result in enumerate(results_list[:5], 1):  # 最多显示5次迭代
                    if isinstance(iter_result, dict):
                        status = iter_result.get('status', 'N/A')
                        response_details_lines.append(f"  Iteration {i}: {status}")
                    else:
                        response_details_lines.append(f"  Iteration {i}: {str(iter_result)[:50]}")
                if len(results_list) > 5:
                    response_details_lines.append(f"  ... ({len(results_list) - 5} more iterations)")
            
            response_details_lines.append("=============================================================")
            logger.info("\n".join(response_details_lines))
            
            # 使用标准响应格式
            return ResponseBuilder.from_loop_response(
                loop_type=result['loop_type'],
                iterations=result['iterations'],
                results=result['results'],
                duration=duration
            ).to_dict()
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"[LoopProcessor] 循环执行失败: {str(e)}")
            return ResponseBuilder.error(
                processor_type="loop",
                error=f"循环执行失败: {str(e)}",
                error_code="LOOP_ERROR",
                status_code=500,
                duration=duration
            ).to_dict()
    
    def _execute_count_loop(self, config: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """执行次数循环"""
        count = int(config.get('count'))
        sub_nodes = config.get('sub_nodes', [])
        delay = float(config.get('delay', 0))
        output_variable = config.get('output_variable', 'loop_result')
        
        results = []
        
        for i in range(count):
            logger.info(f"[LoopProcessor] 执行第 {i + 1}/{count} 次循环")
            
            # 设置循环变量到上下文
            if context and hasattr(context, 'set_variable'):
                context.set_variable('loop_index', i)
                context.set_variable('loop_count', count)
                context.set_variable('is_first_iteration', i == 0)
                context.set_variable('is_last_iteration', i == count - 1)
            
            sub_results = self._run_sub_nodes(sub_nodes, context, i)
            iteration_result = {
                'iteration': i + 1,
                'timestamp': time.time(),
                'sub_results': sub_results
            }
            results.append(iteration_result)
            
            if delay > 0 and i < count - 1:
                time.sleep(delay)
        
        if context and hasattr(context, 'set_variable'):
            context.set_variable(output_variable, results)
        
        return {
            'loop_type': 'count_loop',
            'iterations': count,
            'results': results,
            'success': True
        }
    
    def _execute_while_loop(self, config: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """执行 While 循环"""
        condition = config.get('condition')
        max_iterations = int(config.get('max_iterations', 1000))
        sub_nodes = config.get('sub_nodes', [])
        delay = float(config.get('delay', 0))
        output_variable = config.get('output_variable', 'loop_result')
        
        results = []
        iteration = 0
        
        while iteration < max_iterations:
            condition_met = self._evaluate_condition(condition, context, iteration)
            if not condition_met:
                break
            
            logger.info(f"[LoopProcessor] 执行第 {iteration + 1} 次 While 循环")
            
            if context and hasattr(context, 'set_variable'):
                context.set_variable('loop_index', iteration)
                context.set_variable('loop_count', iteration + 1)
                context.set_variable('is_first_iteration', iteration == 0)
                context.set_variable('is_last_iteration', False)
            
            sub_results = self._run_sub_nodes(sub_nodes, context, iteration)
            iteration_result = {
                'iteration': iteration + 1,
                'timestamp': time.time(),
                'condition': condition,
                'sub_results': sub_results
            }
            results.append(iteration_result)
            
            iteration += 1
            
            if delay > 0:
                time.sleep(delay)
        
        if iteration >= max_iterations:
            logger.warning(f"[LoopProcessor] While 循环达到最大迭代次数 {max_iterations}，强制退出")
        
        if context and hasattr(context, 'set_variable'):
            context.set_variable(output_variable, results)
        
        return {
            'loop_type': 'while_loop',
            'iterations': iteration,
            'max_iterations': max_iterations,
            'results': results,
            'success': True
        }
    
    def _build_sub_node_info(self, rendered_sub_node: Dict[str, Any], index: int, sub_node_type: str) -> Dict[str, Any]:
        """
        构造子节点信息，供下游处理器使用。
        兼容两种结构：标准节点的 data.config，或子节点常见的顶层 config。
        """
        data = rendered_sub_node.get('data')
        if data is None or not data:
            data = {'config': rendered_sub_node.get('config', {})}
        return {
            'id': rendered_sub_node.get('id') or f"loop_{index}_{sub_node_type}",
            'type': sub_node_type,
            'name': rendered_sub_node.get('name', ''),
            'data': data
        }

    def _get_sub_node_extractions(self, rendered_sub_node: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        从子节点配置中读取提取规则，兼容 data.extractions / data.extract / config.extractions。
        返回提取规则列表，无则返回空列表。
        """
        data = rendered_sub_node.get("data") or {}
        config = rendered_sub_node.get("config") or data.get("config") or {}
        raw = (
            data.get("extractions")
            or data.get("extract")
            or config.get("extractions")
            or config.get("extract")
        )
        if not raw:
            return []
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict) and "extractions" in raw:
            return raw["extractions"] if isinstance(raw["extractions"], list) else []
        return []

    def _run_sub_nodes(self, sub_nodes: List[Dict[str, Any]], context: Any, iteration_index: int) -> List[Dict[str, Any]]:
        """
        执行一组子节点，返回每个子节点的执行结果列表。
        若子节点配置了 extractions，会在执行成功后执行内联变量提取并写入上下文，供同轮后续子节点使用。
        """
        sub_results = []
        for sub_node_config in sub_nodes:
            try:
                rendered_sub_node = render_recursive(sub_node_config, context)
                sub_node_type = rendered_sub_node.get('type')
                if not sub_node_type:
                    logger.warning("[LoopProcessor] 子节点缺少 type 字段，跳过")
                    continue
                logger.debug(f"[LoopProcessor] 执行子节点类型: {sub_node_type}")
                try:
                    sub_processor = ProcessorFactory.get_processor(sub_node_type)
                except ValueError as e:
                    logger.warning(f"[LoopProcessor] 无法创建子节点处理器: {e}")
                    continue
                sub_node_info = self._build_sub_node_info(rendered_sub_node, iteration_index, sub_node_type)
                sub_result = sub_processor.execute(sub_node_info, context, {})
                sub_results.append({
                    'type': sub_node_type,
                    'status': 'success',
                    'result': sub_result
                })
                logger.debug(f"[LoopProcessor] 子节点执行成功: {sub_node_type}")

                # 若子节点配置了 extractions，执行内联变量提取并写入上下文，供同轮后续子节点使用
                inline_extractions = self._get_sub_node_extractions(rendered_sub_node)
                if inline_extractions and context and hasattr(context, "set_variable"):
                    sub_node_id = rendered_sub_node.get("id") or f"loop_sub_{iteration_index}_{sub_node_type}"
                    try:
                        extractor_processor = ProcessorFactory.get_processor(VARIABLE_EXTRACTOR_TYPE)
                        extractor_config = {"extractions": inline_extractions}
                        extractor_node_info = {
                            "id": f"{sub_node_id}__inline_extractions",
                            "type": VARIABLE_EXTRACTOR_TYPE,
                            "data": {"config": extractor_config},
                        }
                        predecessor_results = {sub_node_id: sub_result}
                        extractor_processor.execute(extractor_node_info, context, predecessor_results)
                        logger.info(f"[LoopProcessor] 子节点 {sub_node_id} 内联变量提取完成，已写入上下文")
                    except Exception as ext_e:
                        logger.error(f"[LoopProcessor] 子节点 {sub_node_id} 变量提取失败: {str(ext_e)}")
                        sub_results.append({
                            "type": VARIABLE_EXTRACTOR_TYPE,
                            "status": "failed",
                            "error": str(ext_e),
                        })
                        break  # 本轮不再执行后续子节点，避免缺变量导致无意义失败
            except Exception as e:
                logger.error(f"[LoopProcessor] 子节点执行失败: {str(e)}")
                sub_results.append({
                    'type': sub_node_config.get('type', 'unknown'),
                    'status': 'failed',
                    'error': str(e)
                })
        return sub_results

    def _execute_foreach_loop(self, config: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """执行 ForEach 循环"""
        items = config.get('items')
        item_variable = config.get('item_variable', 'item')
        index_variable = config.get('index_variable', 'index')
        sub_nodes = config.get('sub_nodes', [])
        delay = float(config.get('delay', 0))
        output_variable = config.get('output_variable', 'loop_result')
        
        # 解析 items
        if isinstance(items, str):
            items = json.loads(items)
        
        results = []
        
        for index, item in enumerate(items):
            logger.info(f"[LoopProcessor] 执行第 {index + 1}/{len(items)} 次 ForEach 循环")
            
            # 设置循环变量到上下文
            if context and hasattr(context, 'set_variable'):
                context.set_variable(item_variable, item)
                context.set_variable(index_variable, index)
                context.set_variable('loop_index', index)
                context.set_variable('loop_count', len(items))
                context.set_variable('is_first_iteration', index == 0)
                context.set_variable('is_last_iteration', index == len(items) - 1)
            
            sub_results = self._run_sub_nodes(sub_nodes, context, index)
            iteration_result = {
                'iteration': index + 1,
                'item': item,
                'index': index,
                'timestamp': time.time(),
                'sub_results': sub_results
            }
            results.append(iteration_result)
            
            if delay > 0 and index < len(items) - 1:
                time.sleep(delay)
        
        if context and hasattr(context, 'set_variable'):
            context.set_variable(output_variable, results)
        
        return {
            'loop_type': 'foreach_loop',
            'iterations': len(items),
            'items_count': len(items),
            'results': results,
            'success': True
        }
    
    def _evaluate_condition(self, condition: str, context: Any, iteration: int) -> bool:
        """
        评估 While 循环条件
        
        Args:
            condition: 条件表达式
            context: 执行上下文
            iteration: 当前迭代次数
            
        Returns:
            条件是否满足
        """
        # 这里简化处理，实际应该实现一个表达式解析器
        # 支持简单的变量比较和逻辑运算
        
        # 简单的条件示例
        if condition == 'iteration < 5':
            return iteration < 5
        elif condition == 'iteration < 10':
            return iteration < 10
        elif 'iteration' in condition and '<' in condition:
            # 解析 iteration < number 格式
            try:
                parts = condition.split('<')
                if len(parts) == 2:
                    max_iter = int(parts[1].strip())
                    return iteration < max_iter
            except ValueError:
                pass
        
        # 默认返回 True（避免无限循环，实际应该更严格）
        return True
    
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
        return ['loop_type']
    
    def get_optional_config_keys(self) -> list:
        """获取可选的配置键"""
        return [
            'count', 'condition', 'max_iterations', 'items', 'item_variable', 'index_variable',
            'sub_nodes', 'delay', 'output_variable'
        ]
