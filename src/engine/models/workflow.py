# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName
@className WorkflowModels
@describe 工作流对象模型
"""

from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
import networkx as nx

from .configs import BaseConfig, create_config


@dataclass
class Node:
    """工作流节点"""
    id: str
    name: str
    type: str
    config: BaseConfig
    position: Optional[Dict[str, float]] = None
    data: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.data is None:
            self.data = {"config": self.config.to_dict()}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "data": self.data,
            "position": self.position
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Node':
        """从字典创建节点"""
        node_id = data.get("id")
        node_type = data.get("type")
        node_name = data.get("name")
        node_data = data.get("data", {})
        config_data = node_data.get("config", {})
        config = create_config(node_type, config_data)
        
        return cls(
            id=node_id,
            name=node_name,
            type=node_type,
            config=config,
            position=data.get("position"),
            data=node_data
        )
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return getattr(self.config, key, default)
    
    def set_config_value(self, key: str, value: Any) -> None:
        """设置配置值"""
        if hasattr(self.config, key):
            setattr(self.config, key, value)
            # 同步更新data
            if self.data is None:
                self.data = {}
            if "config" not in self.data:
                self.data["config"] = {}
            self.data["config"][key] = value


@dataclass
class EdgeConfig:
    """边配置"""
    source_handle: Optional[str] = None
    target_handle: Optional[str] = None
    condition: Optional[str] = None
    weight: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {}
        for key, value in self.__dict__.items():
            if value is not None:
                result[key] = value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EdgeConfig':
        """从字典创建"""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


@dataclass
class Edge:
    """工作流边"""
    id: str
    source: str
    target: str
    config: EdgeConfig = field(default_factory=EdgeConfig)
    data: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.data is None:
            self.data = self.config.to_dict()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "id": self.id,
            "source": self.source,
            "target": self.target
        }
        result.update(self.config.to_dict())
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Edge':
        """从字典创建边"""
        edge_id = data.get("id")
        source = data.get("source")
        target = data.get("target")
        config = EdgeConfig.from_dict(data)
        
        return cls(
            id=edge_id,
            source=source,
            target=target,
            config=config,
            data=data
        )


@dataclass
class Workflow:
    """工作流对象"""
    work_id: Optional[str] = None
    work_name: Optional[str] = None
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    _graph: Optional[nx.DiGraph] = field(default=None, init=False)
    
    def __post_init__(self):
        self._build_graph()
    
    def _build_graph(self) -> None:
        """构建图结构"""
        self._graph = nx.DiGraph()
        
        # 添加节点
        for node in self.nodes:
            self._graph.add_node(node.id, node=node)
        
        # 添加边
        for edge in self.edges:
            self._graph.add_edge(
                edge.source, 
                edge.target,
                edge=edge,
                **edge.config.to_dict()
            )
    
    def add_node(self, node: Node) -> None:
        """添加节点"""
        self.nodes.append(node)
        if self._graph:
            self._graph.add_node(node.id, node=node)
    
    def add_edge(self, edge: Edge) -> None:
        """添加边"""
        self.edges.append(edge)
        if self._graph:
            self._graph.add_edge(
                edge.source,
                edge.target,
                edge=edge,
                **edge.config.to_dict()
            )
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """获取节点"""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None
    
    def get_edge(self, edge_id: str) -> Optional[Edge]:
        """获取边"""
        for edge in self.edges:
            if edge.id == edge_id:
                return edge
        return None
    
    def get_node_by_type(self, node_type: str) -> List[Node]:
        """根据类型获取节点"""
        return [node for node in self.nodes if node.type == node_type]
    
    def get_predecessors(self, node_id: str) -> List[Node]:
        """获取前置节点"""
        if not self._graph:
            return []
        
        predecessor_ids = list(self._graph.predecessors(node_id))
        return [self.get_node(node_id) for node_id in predecessor_ids if self.get_node(node_id)]
    
    def get_successors(self, node_id: str) -> List[Node]:
        """获取后继节点"""
        if not self._graph:
            return []
        
        successor_ids = list(self._graph.successors(node_id))
        return [self.get_node(node_id) for node_id in successor_ids if self.get_node(node_id)]
    
    def get_execution_order(self) -> List[str]:
        """获取执行顺序"""
        if not self._graph:
            return []
        
        try:
            return list(nx.topological_sort(self._graph))
        except nx.NetworkXError:
            raise ValueError("工作流包含循环，无法执行")
    
    def is_acyclic(self) -> bool:
        """检查是否为有向无环图"""
        if not self._graph:
            return True
        return nx.is_directed_acyclic_graph(self._graph)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "metadata": self.metadata
        }
        # 添加 work_id 和 work_name（如果存在）
        if self.work_id is not None:
            result["work_id"] = self.work_id
        if self.work_name is not None:
            result["work_name"] = self.work_name
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Workflow':
        """从字典创建工作流"""
        nodes = [Node.from_dict(node_data) for node_data in data.get("nodes", [])]
        edges = [Edge.from_dict(edge_data) for edge_data in data.get("edges", [])]
        metadata = data.get("metadata", {})
        work_id = data.get("work_id")
        work_name = data.get("work_name")
        
        return cls(
            work_id=work_id,
            work_name=work_name,
            nodes=nodes,
            edges=edges,
            metadata=metadata
        )
    
    def validate(self) -> List[str]:
        """验证工作流"""
        errors = []
        
        # 检查节点ID唯一性
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            errors.append("节点ID不唯一")
        
        # 检查边ID唯一性
        edge_ids = [edge.id for edge in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            errors.append("边ID不唯一")
        
        # 检查边的节点是否存在
        for edge in self.edges:
            if not any(node.id == edge.source for node in self.nodes):
                errors.append(f"边 {edge.id} 的源节点 {edge.source} 不存在")
            if not any(node.id == edge.target for node in self.nodes):
                errors.append(f"边 {edge.id} 的目标节点 {edge.target} 不存在")
        
        # 检查是否为有向无环图
        if not self.is_acyclic():
            errors.append("工作流包含循环")
        
        return errors
