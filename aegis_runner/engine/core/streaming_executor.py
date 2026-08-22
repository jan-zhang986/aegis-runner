# -*- coding: utf-8 -*-
"""
流式执行器 - 支持实时事件流
inspired by LangGraph's streaming execution
"""

from typing import Iterator, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import time
import networkx as nx

from aegis_runner.engine.workflow_engine import WorkflowExecutor
from aegis_runner.engine.models import ExecutionStatus, StepStatus
from aegis_runner.engine.core.factory import ProcessorFactory
from aegis_runner.engine.core.simple_logger import logger


@dataclass
class StreamEvent:
    """
    流式事件
    
    事件类型：
    - workflow_start: 工作流开始
    - node_start: 节点开始执行
    - node_progress: 节点执行进度（可选）
    - node_output: 节点输出数据
    - node_end: 节点执行完成
    - node_error: 节点执行失败
    - workflow_end: 工作流完成
    """
    type: str
    node_id: str
    timestamp: datetime
    data: Dict[str, Any]
    
    def __str__(self) -> str:
        return f"[{self.timestamp.strftime('%H:%M:%S')}] {self.type}: {self.node_id}"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type,
            "node_id": self.node_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data
        }


class StreamingWorkflowExecutor(WorkflowExecutor):
    """
    流式执行工作流引擎
    
    特点：
    1. 实时返回执行事件
    2. 可以在前端实时显示进度
    3. 便于监控和调试
    
    使用示例:
        executor = StreamingWorkflowExecutor(workflow)
        for event in executor.stream():
            print(f"{event.type}: {event.node_id}")
            if event.type == "node_output":
                print(f"  输出: {event.data['output']}")
    """
    
    def __init__(self, workflow_data: Any, environment: str = None, verbose: bool = True):
        super().__init__(workflow_data, environment)
        self.verbose = verbose  # 是否输出详细日志
        self._event_buffer = []
    
    def stream(self, enable_checkpoints: bool = False) -> Iterator[StreamEvent]:
        """
        流式执行工作流，返回事件迭代器
        
        Args:
            enable_checkpoints: 是否启用检查点（未来功能）
            
        Yields:
            StreamEvent: 执行事件
        """
        workflow_id = self.execution_result.workflow_id
        
        # 发送工作流开始事件
        yield self._create_event(
            "workflow_start",
            "",
            {
                "workflow_id": workflow_id,
                "total_nodes": len(self.node_map),
                "environment": self.environment
            }
        )
        
        # 设置执行开始时间
        self.execution_result.start_time = datetime.now()
        self.execution_result.status = ExecutionStatus.RUNNING
        
        # 获取执行顺序
        execution_order = list(nx.topological_sort(self.graph))
        
        # 发送执行计划事件
        yield self._create_event(
            "execution_plan",
            "",
            {
                "execution_order": execution_order,
                "total_steps": len(execution_order)
            }
        )
        
        completed_count = 0
        
        for node_id in execution_order:
            node = self.node_map[node_id]
            node_type = node.type
            
            # 检查前置条件（分支逻辑）
            should_skip = self._check_should_skip(node_id)
            
            if should_skip:
                # 发送节点跳过事件
                yield self._create_event(
                    "node_skipped",
                    node_id,
                    {
                        "node_type": node_type,
                        "reason": "前置条件不满足（分支逻辑）"
                    }
                )
                continue
            
            # 发送节点开始事件
            start_time = time.time()
            yield self._create_event(
                "node_start",
                node_id,
                {
                    "node_type": node_type,
                    "progress": f"{completed_count}/{len(execution_order)}",
                    "percentage": int((completed_count / len(execution_order)) * 100)
                }
            )
            
            # 获取前驱节点结果
            predecessors = list(self.graph.predecessors(node_id))
            predecessor_results = {
                p: self.context.get_node_result(p) 
                for p in predecessors
            }
            
            try:
                # 执行节点
                processor = ProcessorFactory.get_processor(node_type)
                
                # 执行并捕获结果
                result = processor.execute(node.to_dict(), self.context, predecessor_results)
                
                # 保存结果到上下文（仅存 node_results，不再注册为全局变量以节省内存）
                self.context.set_node_result(node_id, result)
                
                # 计算耗时
                duration = time.time() - start_time
                
                # 发送节点输出事件
                yield self._create_event(
                    "node_output",
                    node_id,
                    {
                        "node_type": node_type,
                        "output": result,
                        "duration": duration
                    }
                )
                
                # 发送节点完成事件
                yield self._create_event(
                    "node_end",
                    node_id,
                    {
                        "node_type": node_type,
                        "status": "success",
                        "duration": duration,
                        "progress": f"{completed_count + 1}/{len(execution_order)}",
                        "percentage": int(((completed_count + 1) / len(execution_order)) * 100)
                    }
                )
                
                completed_count += 1
                
            except Exception as e:
                # 计算耗时
                duration = time.time() - start_time
                
                # 构建完整的错误响应结构
                import traceback
                error_traceback = traceback.format_exc()
                error_output = {
                    "status": "error",
                    "processor_type": node_type,
                    "error": str(e),
                    "error_code": getattr(e, 'error_id', None) or "UNKNOWN_ERROR",
                    "error_type": type(e).__name__,
                    "error_category": getattr(e, 'category', {}).value if hasattr(getattr(e, 'category', None), 'value') else 'unknown',
                    "node_id": node_id,
                    "node_type": node_type,
                    "retryable": getattr(e, 'retryable', False),
                    "traceback": error_traceback,
                    "body": None
                }
                
                # 保存错误结果到上下文
                self.context.set_node_result(node_id, error_output)
                
                # 发送节点错误事件
                yield self._create_event(
                    "node_error",
                    node_id,
                    {
                        "node_type": node_type,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "error_category": error_output["error_category"],
                        "retryable": error_output["retryable"],
                        "duration": duration,
                        "output": error_output  # 完整的错误响应
                    }
                )
                
                # 设置工作流失败状态
                self.execution_result.status = ExecutionStatus.FAILED
                self.execution_result.end_time = datetime.now()
                
                # 发送工作流失败事件
                yield self._create_event(
                    "workflow_error",
                    "",
                    {
                        "failed_node": node_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "completed_nodes": completed_count,
                        "total_nodes": len(execution_order),
                        "failed_output": error_output  # 完整的错误响应
                    }
                )
                
                return  # 停止执行
        
        # 设置工作流成功状态
        self.execution_result.status = ExecutionStatus.SUCCESS
        self.execution_result.end_time = datetime.now()
        total_duration = (self.execution_result.end_time - self.execution_result.start_time).total_seconds()
        
        # 发送工作流完成事件
        yield self._create_event(
            "workflow_end",
            "",
            {
                "workflow_id": workflow_id,
                "status": "success",
                "completed_nodes": completed_count,
                "total_nodes": len(execution_order),
                "total_duration": total_duration,
                "variables_count": len(self.context.get_all_variables())  # 仅返回变量数量，不返回全量数据
            }
        )
    
    def _create_event(self, event_type: str, node_id: str, data: Dict[str, Any]) -> StreamEvent:
        """创建事件"""
        event = StreamEvent(
            type=event_type,
            node_id=node_id,
            timestamp=datetime.now(),
            data=data
        )
        
        # 如果启用详细日志，输出到控制台
        if self.verbose:
            self._log_event(event)
        
        return event
    
    def _log_event(self, event: StreamEvent):
        """输出事件日志"""
        if event.type == "workflow_start":
            workflow_id = event.data.get('workflow_id', 'unknown')
            total_nodes = event.data.get('total_nodes', 0)
            environment = event.data.get('environment')
            logger.info(f"🚀 工作流开始执行: {workflow_id}")
            logger.info(f"   总节点数: {total_nodes}")
            if environment:
                logger.info(f"   执行环境: {environment}")
        
        elif event.type == "execution_plan":
            execution_order = event.data.get('execution_order', [])
            logger.info(f"📋 执行计划: {execution_order}")
        
        elif event.type == "node_start":
            percentage = event.data.get('percentage', 0)
            node_type = event.data.get('node_type', 'unknown')
            logger.info(f"⏳ [{percentage}%] 开始执行: {event.node_id} ({node_type})")
        
        elif event.type == "node_output":
            duration = event.data.get('duration', 0)
            node_type = event.data.get('node_type', 'unknown')
            output = event.data.get('output')
            logger.info(f"📊 节点输出: {event.node_id} ({node_type}) | 耗时: {duration:.3f}s")
            if output is not None:
                # 打印详细输出内容
                import json
                try:
                    if isinstance(output, (dict, list)):
                        output_str = json.dumps(output, ensure_ascii=False, indent=2)
                        logger.info(f"   输出内容:\n{output_str}")
                    else:
                        logger.info(f"   输出内容: {output}")
                except (TypeError, ValueError):
                    logger.info(f"   输出内容: {str(output)}")  # 完整显示输出内容
        
        elif event.type == "node_end":
            percentage = event.data.get('percentage', 0)
            duration = event.data.get('duration', 0)
            status = event.data.get('status', 'success')
            node_type = event.data.get('node_type', 'unknown')
            logger.info(f"✅ [{percentage}%] 完成: {event.node_id} ({node_type}) | 状态: {status} | 耗时: {duration:.3f}s")
        
        elif event.type == "node_error":
            error = event.data.get('error', 'unknown error')
            error_type = event.data.get('error_type', 'unknown')
            duration = event.data.get('duration', 0)
            node_type = event.data.get('node_type', 'unknown')
            logger.error(f"❌ 失败: {event.node_id} ({node_type}) | 错误类型: {error_type} | 耗时: {duration:.3f}s")
            logger.error(f"   错误详情: {error}")
        
        elif event.type == "node_skipped":
            reason = event.data.get('reason', 'unknown reason')
            logger.info(f"⏭️  跳过: {event.node_id} | 原因: {reason}")
        
        elif event.type == "workflow_end":
            workflow_id = event.data.get('workflow_id', 'unknown')
            total_duration = event.data.get('total_duration', 0)
            completed_nodes = event.data.get('completed_nodes', 0)
            total_nodes = event.data.get('total_nodes', 0)
            status = event.data.get('status', 'success')
            variables_count = event.data.get('variables_count', 0)
            logger.info(f"🎉 工作流完成: {workflow_id}")
            logger.info(f"   执行状态: {status}")
            logger.info(f"   总耗时: {total_duration:.2f}s")
            logger.info(f"   完成节点: {completed_nodes}/{total_nodes}")
            logger.info(f"   最终变量数量: {variables_count}")
        
        elif event.type == "workflow_error":
            failed_node = event.data.get('failed_node', 'unknown')
            error = event.data.get('error', 'unknown error')
            completed_nodes = event.data.get('completed_nodes', 0)
            total_nodes = event.data.get('total_nodes', 0)
            logger.error(f"💥 工作流执行失败")
            logger.error(f"   失败节点: {failed_node}")
            logger.error(f"   错误信息: {error}")
            logger.error(f"   已完成节点: {completed_nodes}/{total_nodes}")
    
    def _check_should_skip(self, node_id: str) -> bool:
        """
        检查节点是否应该跳过（分支逻辑）
        
        采用"多路径或"逻辑：只要有一条路径激活，节点就应该执行。
        只有当所有进入路径都失效时，才跳过该节点。
        """
        predecessors = list(self.graph.predecessors(node_id))
        
        # 如果没有前置节点，不跳过
        if not predecessors:
            return False
        
        # 检查是否有任何一条激活的路径
        has_active_path = False
        
        for pred_id in predecessors:
            pred_node = self.node_map[pred_id]
            
            if pred_node.type == "condition":
                # 条件节点：检查分支是否匹配
                pred_result = self.context.get_node_result(pred_id)
                edge_data = self.graph.get_edge_data(pred_id, node_id)
                source_handle = edge_data.get('source_handle')
                
                # 从条件节点的响应中提取分支值
                branch_value = self._extract_branch_value(pred_result)
                
                if branch_value == source_handle:
                    # 分支匹配，路径激活
                    has_active_path = True
                    break
            else:
                # 普通节点：检查前置节点是否成功执行（未被跳过）
                # 如果前置节点有结果，说明它已经执行过
                pred_result = self.context.get_node_result(pred_id)
                if pred_result is not None:
                    has_active_path = True
                    break
        
        # 只有没有任何激活路径时才跳过
        return not has_active_path
    
    def _extract_branch_value(self, pred_result: Any) -> str:
        """
        从条件节点的响应中提取分支值
        
        条件节点返回标准响应结构，布尔结果存放在 body.result 中
        """
        if not isinstance(pred_result, dict):
            # 兼容旧版本：直接返回字符串
            return str(pred_result).lower() if pred_result is not None else "false"
        
        body = pred_result.get("body", {})
        if isinstance(body, dict) and "result" in body:
            value = bool(body.get("result"))
            return "true" if value else "false"
        
        # 如果没有标准结构，尝试直接从 result 字段获取
        if "result" in pred_result:
            value = bool(pred_result.get("result"))
            return "true" if value else "false"
        
        return "false"


# 便捷函数
def stream_execute(workflow, environment: str = None, verbose: bool = True) -> Iterator[StreamEvent]:
    """
    便捷函数：流式执行工作流
    
    使用示例:
        from aegis_runner.engine.core.streaming_executor import stream_execute
        
        for event in stream_execute(workflow):
            if event.type == "node_end":
                print(f"✅ {event.node_id} 完成")
    """
    executor = StreamingWorkflowExecutor(workflow, environment, verbose)
    return executor.stream()
