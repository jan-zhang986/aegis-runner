# -*- coding: utf-8 -*-
"""
可观测性增强 - 指标收集与分析
inspired by LangGraph's observability features
"""

from typing import Dict, List, Any, Optional
import time
import sys
from dataclasses import dataclass, field
from datetime import datetime
import json
import networkx as nx

from aegis_runner.engine.workflow_engine import WorkflowExecutor
from aegis_runner.engine.models import ExecutionResult, ExecutionStatus
from aegis_runner.engine.core.factory import ProcessorFactory
from aegis_runner.engine.core.simple_logger import logger


@dataclass
class NodeMetrics:
    """节点执行指标"""
    node_id: str
    node_type: str
    start_time: float
    end_time: float = 0
    duration: float = 0
    status: str = "running"
    
    # 数据大小
    input_size: int = 0  # 输入数据大小（字节）
    output_size: int = 0  # 输出数据大小（字节）
    
    # 资源使用
    memory_usage: int = 0  # 内存使用（字节）
    
    # 错误信息
    error: str = ""
    error_type: str = ""
    
    # 重试信息
    retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "duration": round(self.duration, 3),
            "status": self.status,
            "input_size": self.input_size,
            "output_size": self.output_size,
            "memory_usage": self.memory_usage,
            "error": self.error,
            "error_type": self.error_type,
            "retry_count": self.retry_count
        }


@dataclass
class WorkflowMetrics:
    """工作流执行指标"""
    workflow_id: str
    start_time: float
    end_time: float = 0
    total_duration: float = 0
    
    # 节点统计
    node_metrics: Dict[str, NodeMetrics] = field(default_factory=dict)
    total_nodes: int = 0
    completed_nodes: int = 0
    failed_nodes: int = 0
    skipped_nodes: int = 0
    
    # 性能统计
    slowest_node: Optional[NodeMetrics] = None
    fastest_node: Optional[NodeMetrics] = None
    avg_node_duration: float = 0
    
    def finalize(self):
        """完成指标收集，计算统计数据"""
        if not self.node_metrics:
            return
        
        # 计算平均耗时
        durations = [m.duration for m in self.node_metrics.values() if m.duration > 0]
        if durations:
            self.avg_node_duration = sum(durations) / len(durations)
        
        # 找出最慢和最快的节点
        completed_nodes = [m for m in self.node_metrics.values() if m.status == "completed"]
        if completed_nodes:
            self.slowest_node = max(completed_nodes, key=lambda x: x.duration)
            self.fastest_node = min(completed_nodes, key=lambda x: x.duration)
    
    def get_slow_nodes(self, threshold: float = 1.0) -> List[NodeMetrics]:
        """
        获取慢节点（超过阈值的节点）
        
        Args:
            threshold: 耗时阈值（秒）
        """
        return sorted(
            [m for m in self.node_metrics.values() if m.duration > threshold],
            key=lambda x: x.duration,
            reverse=True
        )
    
    def get_bottleneck_nodes(self, top_n: int = 5) -> List[NodeMetrics]:
        """
        获取性能瓶颈节点（耗时最长的N个节点）
        
        Args:
            top_n: 返回前N个
        """
        sorted_nodes = sorted(
            self.node_metrics.values(),
            key=lambda x: x.duration,
            reverse=True
        )
        return sorted_nodes[:top_n]
    
    def get_failed_nodes(self) -> List[NodeMetrics]:
        """获取失败的节点"""
        return [m for m in self.node_metrics.values() if m.status == "failed"]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "workflow_id": self.workflow_id,
            "total_duration": round(self.total_duration, 3),
            "avg_node_duration": round(self.avg_node_duration, 3),
            "total_nodes": self.total_nodes,
            "completed_nodes": self.completed_nodes,
            "failed_nodes": self.failed_nodes,
            "skipped_nodes": self.skipped_nodes,
            "slowest_node": self.slowest_node.to_dict() if self.slowest_node else None,
            "fastest_node": self.fastest_node.to_dict() if self.fastest_node else None,
            "slow_nodes": [n.to_dict() for n in self.get_slow_nodes()],
            "bottleneck_nodes": [n.to_dict() for n in self.get_bottleneck_nodes()],
            "failed_nodes_detail": [n.to_dict() for n in self.get_failed_nodes()],
            "node_details": {
                node_id: metrics.to_dict()
                for node_id, metrics in self.node_metrics.items()
            }
        }
    
    def save_to_file(self, filepath: str):
        """保存指标到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info(f"📊 指标已保存到: {filepath}")


class ObservabilityWorkflowExecutor(WorkflowExecutor):
    """
    增强可观测性的工作流引擎
    
    特点：
    1. 自动收集详细的执行指标
    2. 性能分析和瓶颈识别
    3. 可导出指标报告
    
    使用示例:
        executor = ObservabilityWorkflowExecutor(workflow)
        result, metrics = executor.execute_with_metrics()
        
        # 查看指标
        print(f"总耗时: {metrics.total_duration}s")
        print(f"慢节点: {metrics.get_slow_nodes()}")
        
        # 保存指标
        metrics.save_to_file("metrics.json")
    """
    
    def __init__(self, workflow_data: Any, environment: str = None):
        super().__init__(workflow_data, environment)
        self.metrics = WorkflowMetrics(
            workflow_id=self.execution_result.workflow_id,
            start_time=time.time()
        )
    
    def execute_with_metrics(self) -> tuple[ExecutionResult, WorkflowMetrics]:
        """
        执行工作流并收集指标
        
        Returns:
            (ExecutionResult, WorkflowMetrics): 执行结果和指标
        """
        logger.info(f"🚀 工作流开始执行（可观测模式）: {self.execution_result.workflow_id}")
        
        # 设置执行开始时间
        self.execution_result.start_time = datetime.now()
        self.execution_result.status = ExecutionStatus.RUNNING
        
        # 获取执行顺序
        execution_order = list(nx.topological_sort(self.graph))
        self.metrics.total_nodes = len(execution_order)
        
        logger.info(f"📋 执行计划: {execution_order}")
        
        for node_id in execution_order:
            node = self.node_map[node_id]
            node_type = node.type
            
            # 创建节点指标
            node_metrics = NodeMetrics(
                node_id=node_id,
                node_type=node_type,
                start_time=time.time()
            )
            
            # 检查前置条件
            should_skip = self._check_should_skip(node_id)
            
            if should_skip:
                node_metrics.status = "skipped"
                node_metrics.end_time = time.time()
                node_metrics.duration = node_metrics.end_time - node_metrics.start_time
                self.metrics.node_metrics[node_id] = node_metrics
                self.metrics.skipped_nodes += 1
                logger.info(f"⏭️  跳过节点: {node_id}")
                continue
            
            logger.info(f"⏳ 开始执行节点: {node_id} ({node_type})")
            
            # 获取前驱节点结果
            predecessors = list(self.graph.predecessors(node_id))
            predecessor_results = {
                p: self.context.get_node_result(p) 
                for p in predecessors
            }
            
            # 记录输入大小
            try:
                node_metrics.input_size = sys.getsizeof(str(predecessor_results))
            except:
                pass
            
            try:
                # 执行节点
                processor = ProcessorFactory.get_processor(node_type)
                result = processor.execute(node.to_dict(), self.context, predecessor_results)
                
                # 保存结果（仅存 node_results，不再注册为全局变量以节省内存）
                self.context.set_node_result(node_id, result)
                
                # 记录输出大小
                try:
                    node_metrics.output_size = sys.getsizeof(str(result))
                except:
                    pass
                
                # 标记成功
                node_metrics.status = "completed"
                self.metrics.completed_nodes += 1
                
            except Exception as e:
                # 记录错误
                node_metrics.status = "failed"
                node_metrics.error = str(e)
                node_metrics.error_type = type(e).__name__
                self.metrics.failed_nodes += 1
                
                logger.error(f"❌ 节点执行失败: {node_id} | 错误: {str(e)}")
                
                # 设置工作流失败状态
                self.execution_result.status = ExecutionStatus.FAILED
                self.execution_result.end_time = datetime.now()
            
            # 计算耗时
            node_metrics.end_time = time.time()
            node_metrics.duration = node_metrics.end_time - node_metrics.start_time
            
            # 保存节点指标
            self.metrics.node_metrics[node_id] = node_metrics
            
            logger.info(f"✅ 节点执行完成: {node_id} | 耗时: {node_metrics.duration:.3f}s")
            
            # 如果失败则停止
            if node_metrics.status == "failed":
                break
        
        # 设置工作流状态
        if self.execution_result.status != ExecutionStatus.FAILED:
            self.execution_result.status = ExecutionStatus.SUCCESS
            self.execution_result.end_time = datetime.now()
        
        # 计算总耗时
        self.metrics.end_time = time.time()
        self.metrics.total_duration = self.metrics.end_time - self.metrics.start_time
        
        # 完成指标统计
        self.metrics.finalize()
        
        # 保存变量到结果
        self.execution_result.variables = self.context.get_all_variables()
        
        # 打印指标摘要
        self.print_metrics_summary()
        
        logger.info(f"🎉 工作流执行完成: {self.execution_result.workflow_id}")
        
        return self.execution_result, self.metrics
    
    def print_metrics_summary(self):
        """打印指标摘要"""
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
        
        # 性能瓶颈
        bottlenecks = self.metrics.get_bottleneck_nodes(3)
        if bottlenecks:
            print(f"║  🐌 性能瓶颈 (Top 3):                                           ║")
            for i, node in enumerate(bottlenecks, 1):
                print(f"║    {i}. {node.node_id:<20} {node.duration:>6.2f}s ({node.node_type:<15})║")
        
        # 失败节点
        failed = self.metrics.get_failed_nodes()
        if failed:
            print(f"║                                                                ║")
            print(f"║  ❌ 失败节点:                                                   ║")
            for node in failed:
                print(f"║    • {node.node_id:<25} {node.error_type:<25}║")
        
        print(f"║                                                                ║")
        print(f"╚════════════════════════════════════════════════════════════════╝")
    
    def _check_should_skip(self, node_id: str) -> bool:
        """检查节点是否应该跳过"""
        predecessors = list(self.graph.predecessors(node_id))
        for pred_id in predecessors:
            pred_node = self.node_map[pred_id]
            if pred_node.type == "condition":
                pred_result = self.context.get_node_result(pred_id)
                edge_data = self.graph.get_edge_data(pred_id, node_id)
                source_handle = edge_data.get('source_handle')
                if pred_result != source_handle:
                    return True
        return False
