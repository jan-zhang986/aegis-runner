# -*- coding: utf-8 -*-
"""
高级组合执行器 - 支持同时使用多个功能
"""

from typing import Any, Iterator, Optional, Dict, Tuple
from datetime import datetime
import time
import networkx as nx

from src.engine.workflow_engine import WorkflowExecutor
from src.engine.models import ExecutionResult, ExecutionStatus
from src.engine.core.factory import ProcessorFactory
from src.engine.core.simple_logger import logger

# 导入三大核心功能
from src.engine.core.streaming_executor import StreamEvent
from src.engine.core.observability import WorkflowMetrics, NodeMetrics
from src.engine.core.checkpoint import Checkpoint, CheckpointManager


class AdvancedWorkflowExecutor(WorkflowExecutor):
    """
    高级组合执行器
    
    支持灵活组合三大功能：
    1. 流式执行 (enable_streaming=True)
    2. 可观测性 (enable_metrics=True)
    3. 检查点恢复 (enable_checkpoint=True)
    
    使用示例:
        # 同时启用所有功能
        executor = AdvancedWorkflowExecutor(
            workflow,
            enable_streaming=True,
            enable_metrics=True,
            enable_checkpoint=True,
            execution_id="my_run"
        )
        
        # 流式执行 + 收集指标
        for event in executor.stream_with_metrics():
            print(event)
            if event.type == "workflow_end":
                metrics = event.data['metrics']
                print(f"总耗时: {metrics.total_duration}s")
    """
    
    def __init__(
        self,
        workflow_data: Any,
        environment: str = None,
        enable_streaming: bool = False,
        enable_metrics: bool = False,
        enable_checkpoint: bool = False,
        execution_id: str = None,
        checkpoint_manager: CheckpointManager = None,
        verbose: bool = True
    ):
        """
        初始化高级执行器
        
        Args:
            workflow_data: 工作流数据
            environment: 环境名称
            enable_streaming: 是否启用流式执行
            enable_metrics: 是否启用指标收集
            enable_checkpoint: 是否启用检查点恢复
            execution_id: 执行ID（用于检查点）
            checkpoint_manager: 检查点管理器
            verbose: 是否输出详细日志
        """
        super().__init__(workflow_data, environment)
        
        # 功能开关
        self.enable_streaming = enable_streaming
        self.enable_metrics = enable_metrics
        self.enable_checkpoint = enable_checkpoint
        self.verbose = verbose
        
        # 指标收集
        if self.enable_metrics:
            self.metrics = WorkflowMetrics(
                workflow_id=self.execution_result.workflow_id,
                start_time=time.time()
            )
        else:
            self.metrics = None
        
        # 检查点管理
        if self.enable_checkpoint:
            self.execution_id = execution_id or f"exec_{int(time.time() * 1000)}"
            self.checkpoint_manager = checkpoint_manager or CheckpointManager()
            self.checkpoint: Optional[Checkpoint] = None
            logger.info(f"🔄 检查点功能已启用 | 执行ID: {self.execution_id}")
        else:
            self.execution_id = None
            self.checkpoint_manager = None
            self.checkpoint = None
        
        logger.info(f"🚀 高级执行器初始化完成")
        logger.info(f"   流式执行: {'✅ 启用' if enable_streaming else '❌ 禁用'}")
        logger.info(f"   可观测性: {'✅ 启用' if enable_metrics else '❌ 禁用'}")
        logger.info(f"   检查点恢复: {'✅ 启用' if enable_checkpoint else '❌ 禁用'}")
    
    def execute(self) -> ExecutionResult:
        """
        标准执行（不使用流式）
        
        如果启用了指标或检查点，会自动收集
        """
        if self.enable_checkpoint:
            return self._execute_with_checkpoint()
        else:
            return self._execute_standard()
    
    def stream(self) -> Iterator[StreamEvent]:
        """
        流式执行
        
        如果启用了指标，会在 workflow_end 事件中包含指标
        如果启用了检查点，会自动保存
        """
        if not self.enable_streaming:
            raise ValueError("流式执行未启用，请设置 enable_streaming=True")
        
        # 发送工作流开始事件
        yield self._create_event(
            "workflow_start",
            "",
            {
                "workflow_id": self.execution_result.workflow_id,
                "total_nodes": len(self.node_map),
                "features": {
                    "streaming": self.enable_streaming,
                    "metrics": self.enable_metrics,
                    "checkpoint": self.enable_checkpoint
                }
            }
        )
        
        # 加载检查点（如果启用）
        if self.enable_checkpoint:
            self.checkpoint = self.checkpoint_manager.load_checkpoint(self.execution_id)
            if self.checkpoint:
                yield self._create_event(
                    "checkpoint_loaded",
                    "",
                    {
                        "execution_id": self.execution_id,
                        "completed_nodes": self.checkpoint.completed_nodes,
                        "completed_count": self.checkpoint.completed_count
                    }
                )
                # 恢复上下文
                self._restore_checkpoint()
        
        # 设置执行开始时间
        self.execution_result.start_time = datetime.now()
        self.execution_result.status = ExecutionStatus.RUNNING
        
        if self.enable_metrics:
            self.metrics.start_time = time.time()
        
        # 获取执行顺序
        execution_order = list(nx.topological_sort(self.graph))
        
        # 跳过已完成的节点
        if self.checkpoint and self.checkpoint.next_node_id:
            try:
                start_index = execution_order.index(self.checkpoint.next_node_id)
                execution_order = execution_order[start_index:]
                yield self._create_event(
                    "skip_completed",
                    "",
                    {"skipped_count": start_index}
                )
            except ValueError:
                pass
        
        yield self._create_event(
            "execution_plan",
            "",
            {"execution_order": execution_order, "total_steps": len(execution_order)}
        )
        
        completed_nodes = self.checkpoint.completed_nodes.copy() if self.checkpoint else []
        completed_count = len(completed_nodes)
        
        # 执行节点
        for node_id in execution_order:
            node = self.node_map[node_id]
            
            # 检查是否跳过
            should_skip = self._check_should_skip(node_id)
            if should_skip:
                yield self._create_event(
                    "node_skipped",
                    node_id,
                    {"node_type": node.type, "reason": "前置条件不满足"}
                )
                if self.enable_metrics:
                    self.metrics.skipped_nodes += 1
                continue
            
            # 节点开始
            start_time = time.time()
            
            if self.enable_metrics:
                node_metrics = NodeMetrics(
                    node_id=node_id,
                    node_type=node.type,
                    start_time=start_time
                )
            
            yield self._create_event(
                "node_start",
                node_id,
                {
                    "node_type": node.type,
                    "progress": f"{completed_count}/{len(self.node_map)}",
                    "percentage": int((completed_count / len(self.node_map)) * 100)
                }
            )
            
            # 获取前驱结果
            predecessors = list(self.graph.predecessors(node_id))
            predecessor_results = {
                p: self.context.get_node_result(p) for p in predecessors
            }
            
            try:
                # 执行节点
                processor = ProcessorFactory.get_processor(node.type)
                result = processor.execute(node.to_dict(), self.context, predecessor_results)
                
                # 保存结果（仅存 node_results，不再注册为全局变量以节省内存）
                self.context.set_node_result(node_id, result)
                
                # 记录成功
                completed_nodes.append(node_id)
                completed_count += 1
                
                duration = time.time() - start_time
                
                # 更新指标
                if self.enable_metrics:
                    node_metrics.status = "completed"
                    node_metrics.end_time = time.time()
                    node_metrics.duration = duration
                    self.metrics.node_metrics[node_id] = node_metrics
                    self.metrics.completed_nodes += 1
                
                # 保存检查点
                if self.enable_checkpoint:
                    self._save_checkpoint_after_node(node_id, execution_order, completed_nodes)
                
                # 发送完成事件
                yield self._create_event(
                    "node_end",
                    node_id,
                    {
                        "node_type": node.type,
                        "status": "success",
                        "duration": duration,
                        "progress": f"{completed_count}/{len(self.node_map)}",
                        "percentage": int((completed_count / len(self.node_map)) * 100)
                    }
                )
                
            except Exception as e:
                duration = time.time() - start_time
                
                # 构建完整的错误响应结构
                import traceback
                error_traceback = traceback.format_exc()
                error_output = {
                    "status": "error",
                    "processor_type": node.type,
                    "error": str(e),
                    "error_code": getattr(e, 'error_id', None) or "UNKNOWN_ERROR",
                    "error_type": type(e).__name__,
                    "error_category": getattr(e, 'category', {}).value if hasattr(getattr(e, 'category', None), 'value') else 'unknown',
                    "node_id": node_id,
                    "node_type": node.type,
                    "retryable": getattr(e, 'retryable', False),
                    "traceback": error_traceback,
                    "body": None
                }
                
                # 保存错误结果到上下文
                self.context.set_node_result(node_id, error_output)
                
                # 更新指标
                if self.enable_metrics:
                    node_metrics.status = "failed"
                    node_metrics.end_time = time.time()
                    node_metrics.duration = duration
                    node_metrics.error = str(e)
                    node_metrics.error_type = type(e).__name__
                    self.metrics.node_metrics[node_id] = node_metrics
                    self.metrics.failed_nodes += 1
                
                # 保存失败检查点
                if self.enable_checkpoint:
                    self._save_checkpoint_on_failure(node_id, execution_order, completed_nodes)
                
                # 发送错误事件
                yield self._create_event(
                    "node_error",
                    node_id,
                    {
                        "node_type": node.type,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "error_category": error_output["error_category"],
                        "retryable": error_output["retryable"],
                        "duration": duration,
                        "output": error_output  # 完整的错误响应
                    }
                )
                
                # 设置失败状态
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
                        "total_nodes": len(self.node_map),
                        "failed_output": error_output  # 完整的错误响应
                    }
                )
                
                return
        
        # 执行成功
        self.execution_result.status = ExecutionStatus.SUCCESS
        self.execution_result.end_time = datetime.now()
        total_duration = (self.execution_result.end_time - self.execution_result.start_time).total_seconds()
        
        # 完成指标收集
        if self.enable_metrics:
            self.metrics.end_time = time.time()
            self.metrics.total_duration = self.metrics.end_time - self.metrics.start_time
            self.metrics.total_nodes = len(self.node_map)
            self.metrics.finalize()
        
        # 清理检查点（如果成功）
        if self.enable_checkpoint:
            self.checkpoint_manager.delete_checkpoint(self.execution_id)
        
        # 发送完成事件（包含指标）
        event_data = {
            "workflow_id": self.execution_result.workflow_id,
            "status": "success",
            "completed_nodes": completed_count,
            "total_nodes": len(self.node_map),
            "total_duration": total_duration
        }
        
        if self.enable_metrics:
            event_data["metrics"] = self.metrics.to_dict()
        
        yield self._create_event("workflow_end", "", event_data)
    
    def _execute_standard(self) -> ExecutionResult:
        """标准执行（不使用流式）"""
        self.execution_result.start_time = datetime.now()
        self.execution_result.status = ExecutionStatus.RUNNING
        
        if self.enable_metrics:
            self.metrics.start_time = time.time()
        
        execution_order = list(nx.topological_sort(self.graph))
        
        for node_id in execution_order:
            node = self.node_map[node_id]
            
            if self._check_should_skip(node_id):
                continue
            
            start_time = time.time()
            predecessors = list(self.graph.predecessors(node_id))
            predecessor_results = {p: self.context.get_node_result(p) for p in predecessors}
            
            try:
                processor = ProcessorFactory.get_processor(node.type)
                result = processor.execute(node.to_dict(), self.context, predecessor_results)
                # 仅存 node_results，不再注册为全局变量以节省内存
                self.context.set_node_result(node_id, result)
                
                if self.enable_metrics:
                    node_metrics = NodeMetrics(
                        node_id=node_id,
                        node_type=node.type,
                        start_time=start_time,
                        end_time=time.time(),
                        status="completed"
                    )
                    node_metrics.duration = node_metrics.end_time - node_metrics.start_time
                    self.metrics.node_metrics[node_id] = node_metrics
                    self.metrics.completed_nodes += 1
                
            except Exception as e:
                if self.enable_metrics:
                    node_metrics = NodeMetrics(
                        node_id=node_id,
                        node_type=node.type,
                        start_time=start_time,
                        end_time=time.time(),
                        status="failed",
                        error=str(e)
                    )
                    self.metrics.node_metrics[node_id] = node_metrics
                    self.metrics.failed_nodes += 1
                
                self.execution_result.status = ExecutionStatus.FAILED
                self.execution_result.end_time = datetime.now()
                raise e
        
        self.execution_result.status = ExecutionStatus.SUCCESS
        self.execution_result.end_time = datetime.now()
        
        if self.enable_metrics:
            self.metrics.end_time = time.time()
            self.metrics.total_duration = self.metrics.end_time - self.metrics.start_time
            self.metrics.total_nodes = len(self.node_map)
            self.metrics.finalize()
        
        return self.execution_result
    
    def _execute_with_checkpoint(self) -> ExecutionResult:
        """带检查点的执行"""
        # 加载检查点
        self.checkpoint = self.checkpoint_manager.load_checkpoint(self.execution_id)
        if self.checkpoint:
            self._restore_checkpoint()
        
        return self._execute_standard()
    
    def _restore_checkpoint(self):
        """恢复检查点"""
        if self.checkpoint.context_variables:
            for key, value in self.checkpoint.context_variables.items():
                self.context.set_variable(key, value)
        
        if self.checkpoint.node_results:
            for node_id, result in self.checkpoint.node_results.items():
                self.context.set_node_result(node_id, result)
    
    def _save_checkpoint_after_node(self, node_id: str, execution_order: list, completed_nodes: list):
        """节点完成后保存检查点"""
        try:
            current_index = execution_order.index(node_id)
            next_node_id = execution_order[current_index + 1] if current_index + 1 < len(execution_order) else None
        except ValueError:
            next_node_id = None
        
        checkpoint = Checkpoint(
            workflow_id=self.execution_result.workflow_id,
            execution_id=self.execution_id,
            timestamp=datetime.now().isoformat(),
            completed_nodes=completed_nodes.copy(),
            next_node_id=next_node_id,
            context_variables=self.context.get_all_variables(),
            node_results=self.context.get_all_node_results(),
            total_nodes=len(self.node_map),
            completed_count=len(completed_nodes)
        )
        
        self.checkpoint_manager.save_checkpoint(checkpoint)
    
    def _save_checkpoint_on_failure(self, failed_node_id: str, execution_order: list, completed_nodes: list):
        """失败时保存检查点"""
        checkpoint = Checkpoint(
            workflow_id=self.execution_result.workflow_id,
            execution_id=self.execution_id,
            timestamp=datetime.now().isoformat(),
            completed_nodes=completed_nodes.copy(),
            failed_node=failed_node_id,
            next_node_id=failed_node_id,
            context_variables=self.context.get_all_variables(),
            node_results=self.context.get_all_node_results(),
            total_nodes=len(self.node_map),
            completed_count=len(completed_nodes)
        )
        
        self.checkpoint_manager.save_checkpoint(checkpoint)
    
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
    
    def _create_event(self, event_type: str, node_id: str, data: Dict[str, Any]) -> StreamEvent:
        """创建事件"""
        event = StreamEvent(
            type=event_type,
            node_id=node_id,
            timestamp=datetime.now(),
            data=data
        )
        
        if self.verbose and event_type in ["node_start", "node_end", "workflow_end"]:
            logger.info(f"[{event_type}] {node_id}")
        
        return event
    
    def get_metrics(self) -> Optional[WorkflowMetrics]:
        """获取指标（如果启用）"""
        return self.metrics if self.enable_metrics else None
    
    def print_metrics_summary(self):
        """打印指标摘要"""
        if not self.enable_metrics or not self.metrics:
            print("⚠️  指标收集未启用")
            return
        
        print(f"""
╔════════════════════════════════════════════════════════════════╗
║                    📊 执行指标摘要                              ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  工作流ID: {self.metrics.workflow_id:<48} ║
║  总耗时: {self.metrics.total_duration:>6.2f}秒                              ║
║  平均节点耗时: {self.metrics.avg_node_duration:>6.2f}秒                      ║
║                                                                ║
║  节点统计:                                                      ║
║    总数: {self.metrics.total_nodes:<3}  完成: {self.metrics.completed_nodes:<3}  失败: {self.metrics.failed_nodes:<3}  跳过: {self.metrics.skipped_nodes:<3}      ║
║                                                                ║""")
        
        bottlenecks = self.metrics.get_bottleneck_nodes(3)
        if bottlenecks:
            print(f"║  🐌 性能瓶颈 (Top 3):                                           ║")
            for i, node in enumerate(bottlenecks, 1):
                print(f"║    {i}. {node.node_id:<20} {node.duration:>6.2f}s ({node.node_type:<15})║")
        
        print(f"║                                                                ║")
        print(f"╚════════════════════════════════════════════════════════════════╝")


# 便捷创建函数
def create_executor(
    workflow,
    streaming: bool = False,
    metrics: bool = False,
    checkpoint: bool = False,
    execution_id: str = None,
    **kwargs
) -> AdvancedWorkflowExecutor:
    """
    便捷创建高级执行器
    
    使用示例:
        # 所有功能
        executor = create_executor(workflow, streaming=True, metrics=True, checkpoint=True)
        
        # 流式 + 指标
        executor = create_executor(workflow, streaming=True, metrics=True)
        
        # 只要检查点
        executor = create_executor(workflow, checkpoint=True, execution_id="test")
    """
    return AdvancedWorkflowExecutor(
        workflow,
        enable_streaming=streaming,
        enable_metrics=metrics,
        enable_checkpoint=checkpoint,
        execution_id=execution_id,
        **kwargs
    )
