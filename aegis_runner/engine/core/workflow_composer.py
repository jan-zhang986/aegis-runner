# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName
@className WorkflowComposer
@describe 工作流组合器，支持多个workflow的合并执行
"""

import json
import networkx as nx
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from ..models.workflow import Workflow, Node, Edge
from ..models.execution import ExecutionContext, ExecutionResult, ExecutionStatus
from .factory import ProcessorFactory


@dataclass
class WorkflowInfo:
    """工作流信息"""
    name: str
    workflow_data: Union[Dict[str, Any], Workflow]
    dependencies: List[str] = field(default_factory=list)
    data_mappings: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MergeConfig:
    """合并配置"""
    strategy: str = "sequential"  # sequential, parallel, conditional
    node_id_prefix: bool = True
    preserve_original_ids: bool = False
    data_passing: bool = True
    error_handling: str = "stop_on_error"  # stop_on_error, continue_on_error, retry


class WorkflowComposer:
    """工作流组合器"""
    
    def __init__(self):
        self.workflows: Dict[str, WorkflowInfo] = {}
        self.merged_workflow: Optional[Workflow] = None
        self.merge_config = MergeConfig()
        self.execution_context = ExecutionContext()
        
    def add_workflow(self, 
                    name: str, 
                    workflow_data: Union[Dict[str, Any], Workflow],
                    dependencies: Optional[List[str]] = None,
                    data_mappings: Optional[Dict[str, str]] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> 'WorkflowComposer':
        """
        添加工作流到组合中
        
        Args:
            name: 工作流名称
            workflow_data: 工作流数据（字典或Workflow对象）
            dependencies: 依赖的其他工作流名称列表
            data_mappings: 数据映射规则 {"source_var": "target_var"}
            metadata: 元数据
        """
        if dependencies is None:
            dependencies = []
        if data_mappings is None:
            data_mappings = {}
        if metadata is None:
            metadata = {}
            
        self.workflows[name] = WorkflowInfo(
            name=name,
            workflow_data=workflow_data,
            dependencies=dependencies,
            data_mappings=data_mappings,
            metadata=metadata
        )
        return self
    
    def set_merge_config(self, config: MergeConfig) -> 'WorkflowComposer':
        """设置合并配置"""
        self.merge_config = config
        return self
    
    def merge_workflows(self) -> Workflow:
        """
        合并所有工作流
        
        Returns:
            合并后的工作流
        """
        if not self.workflows:
            raise ValueError("没有工作流可以合并")
        
        # 验证依赖关系
        self._validate_dependencies()
        
        # 获取执行顺序
        execution_order = self._get_execution_order()
        
        # 合并节点和边
        merged_nodes = []
        merged_edges = []
        node_id_mapping = {}
        
        for workflow_name in execution_order:
            workflow_info = self.workflows[workflow_name]
            workflow = self._get_workflow_object(workflow_info.workflow_data)
            
            # 处理节点ID冲突
            prefix = f"{workflow_name}_" if self.merge_config.node_id_prefix else ""
            workflow_node_mapping = {}
            
            for node in workflow.nodes:
                new_id = f"{prefix}{node.id}"
                workflow_node_mapping[node.id] = new_id
                node_id_mapping[f"{workflow_name}.{node.id}"] = new_id
                
                # 创建新节点
                new_node = Node(
                    id=new_id,
                    type=node.type,
                    config=node.config,
                    position=node.position,
                    data=node.data
                )
                merged_nodes.append(new_node)
            
            # 处理边
            for edge in workflow.edges:
                new_source = workflow_node_mapping[edge.source]
                new_target = workflow_node_mapping[edge.target]
                
                new_edge = Edge(
                    id=f"{prefix}{edge.id}",
                    source=new_source,
                    target=new_target,
                    config=edge.config,
                    data=edge.data
                )
                merged_edges.append(new_edge)
        
        # 添加工作流间的连接边
        connection_edges = self._create_connection_edges(execution_order, node_id_mapping)
        merged_edges.extend(connection_edges)
        
        # 创建合并后的工作流
        self.merged_workflow = Workflow(
            nodes=merged_nodes,
            edges=merged_edges,
            metadata={
                "composed": True,
                "original_workflows": list(self.workflows.keys()),
                "merge_config": self.merge_config.__dict__
            }
        )
        
        return self.merged_workflow
    
    def execute(self) -> ExecutionResult:
        """
        执行合并后的工作流
        
        Returns:
            执行结果
        """
        if self.merged_workflow is None:
            self.merge_workflows()
        
        # 使用现有的WorkflowExecutor执行
        from aegis_runner.engine.workflow_engine import WorkflowExecutor
        executor = WorkflowExecutor(self.merged_workflow)
        return executor.execute()
    
    def _validate_dependencies(self) -> None:
        """验证依赖关系"""
        for name, workflow_info in self.workflows.items():
            for dep in workflow_info.dependencies:
                if dep not in self.workflows:
                    raise ValueError(f"工作流 '{name}' 依赖的工作流 '{dep}' 不存在")
    
    def _get_execution_order(self) -> List[str]:
        """获取执行顺序"""
        if self.merge_config.strategy == "sequential":
            return self._get_sequential_order()
        elif self.merge_config.strategy == "parallel":
            return self._get_parallel_order()
        elif self.merge_config.strategy == "conditional":
            return self._get_conditional_order()
        else:
            raise ValueError(f"不支持的合并策略: {self.merge_config.strategy}")
    
    def _get_sequential_order(self) -> List[str]:
        """获取顺序执行顺序"""
        # 构建依赖图
        dep_graph = nx.DiGraph()
        for name in self.workflows.keys():
            dep_graph.add_node(name)
        
        for name, workflow_info in self.workflows.items():
            for dep in workflow_info.dependencies:
                dep_graph.add_edge(dep, name)
        
        # 检查循环依赖
        if not nx.is_directed_acyclic_graph(dep_graph):
            raise ValueError("工作流依赖关系包含循环")
        
        # 拓扑排序
        return list(nx.topological_sort(dep_graph))
    
    def _get_parallel_order(self) -> List[str]:
        """获取并行执行顺序（返回所有工作流，实际并行执行）"""
        return list(self.workflows.keys())
    
    def _get_conditional_order(self) -> List[str]:
        """获取条件执行顺序"""
        # 对于条件执行，我们仍然需要依赖关系来确定顺序
        return self._get_sequential_order()
    
    def _get_workflow_object(self, workflow_data: Union[Dict[str, Any], Workflow]) -> Workflow:
        """获取Workflow对象"""
        if isinstance(workflow_data, Workflow):
            return workflow_data
        else:
            return Workflow.from_dict(workflow_data)
    
    def _create_connection_edges(self, execution_order: List[str], node_id_mapping: Dict[str, str]) -> List[Edge]:
        """创建工作流间的连接边"""
        connection_edges = []
        
        for i in range(len(execution_order) - 1):
            current_workflow = execution_order[i]
            next_workflow = execution_order[i + 1]
            
            # 获取当前工作流的最后一个节点
            current_workflow_obj = self._get_workflow_object(self.workflows[current_workflow].workflow_data)
            current_last_nodes = self._get_last_nodes(current_workflow_obj)
            
            # 获取下一个工作流的第一个节点
            next_workflow_obj = self._get_workflow_object(self.workflows[next_workflow].workflow_data)
            next_first_nodes = self._get_first_nodes(next_workflow_obj)
            
            # 创建连接边
            for current_node in current_last_nodes:
                for next_node in next_first_nodes:
                    current_id = node_id_mapping[f"{current_workflow}.{current_node.id}"]
                    next_id = node_id_mapping[f"{next_workflow}.{next_node.id}"]
                    
                    connection_edge = Edge(
                        id=f"conn_{current_workflow}_{next_workflow}_{current_node.id}_{next_node.id}",
                        source=current_id,
                        target=next_id,
                        config=EdgeConfig(),
                        data={"type": "workflow_connection"}
                    )
                    connection_edges.append(connection_edge)
        
        return connection_edges
    
    def _get_last_nodes(self, workflow: Workflow) -> List[Node]:
        """获取工作流的最后一个节点（没有后继节点的节点）"""
        if not workflow._graph:
            return []
        
        last_nodes = []
        for node in workflow.nodes:
            if workflow._graph.out_degree(node.id) == 0:
                last_nodes.append(node)
        
        return last_nodes
    
    def _get_first_nodes(self, workflow: Workflow) -> List[Node]:
        """获取工作流的第一个节点（没有前驱节点的节点）"""
        if not workflow._graph:
            return []
        
        first_nodes = []
        for node in workflow.nodes:
            if workflow._graph.in_degree(node.id) == 0:
                first_nodes.append(node)
        
        return first_nodes
    
    def get_merged_workflow(self) -> Optional[Workflow]:
        """获取合并后的工作流"""
        return self.merged_workflow
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "workflows": {name: {
                "name": info.name,
                "dependencies": info.dependencies,
                "data_mappings": info.data_mappings,
                "metadata": info.metadata
            } for name, info in self.workflows.items()},
            "merge_config": self.merge_config.__dict__,
            "merged_workflow": self.merged_workflow.to_dict() if self.merged_workflow else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowComposer':
        """从字典创建"""
        composer = cls()
        
        # 恢复工作流信息
        for name, info_data in data.get("workflows", {}).items():
            composer.workflows[name] = WorkflowInfo(
                name=name,
                workflow_data={},  # 需要单独加载
                dependencies=info_data.get("dependencies", []),
                data_mappings=info_data.get("data_mappings", {}),
                metadata=info_data.get("metadata", {})
            )
        
        # 恢复合并配置
        config_data = data.get("merge_config", {})
        composer.merge_config = MergeConfig(**config_data)
        
        return composer


# 为了兼容性，导入EdgeConfig
from ..models.workflow import EdgeConfig
