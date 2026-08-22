# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-10-03
@packageName
@className Builders
@describe 工作流构建器 - 提供链式API用于构建工作流
"""

from typing import Dict, Any, List, Optional, Union
import uuid

from .workflow import Workflow, Node, Edge, EdgeConfig
from .configs import (
    HttpConfig, SqlConfig, ScriptConfig, LogConfig,
    AssertionConfig, VariableExtractorConfig, ConditionConfig,
    MqConfig, SubWorkflowConfig, UIConfig, BaseConfig,
    AssertionRule, ExtractionRule, Viewport,
    DatabaseConnectionConfig, ConnectionPoolConfig
)


class NodeBuilder:
    """节点构建器 - 使用链式API构建节点"""
    
    def __init__(self, node_id: Optional[str] = None):
        """
        初始化节点构建器
        
        Args:
            node_id: 节点ID，如果不提供则自动生成
        """
        self._id = node_id or f"node_{uuid.uuid4().hex[:8]}"
        self._type: Optional[str] = None
        self._config: Optional[BaseConfig] = None
        self._position: Optional[Dict[str, float]] = None
        self._data: Optional[Dict[str, Any]] = None
    
    def http_request(self, 
                     url: str,
                     method: str = "GET",
                     headers: Optional[Dict[str, str]] = None,
                     body: Optional[Any] = None,
                     timeout: Optional[int] = None,
                     credential_id: Optional[str] = None) -> 'NodeBuilder':
        """
        配置HTTP请求节点
        
        Args:
            url: 请求URL
            method: HTTP方法
            headers: 请求头
            body: 请求体
            timeout: 超时时间（秒）
            credential_id: 凭证ID
        """
        self._type = "http_request"
        self._config = HttpConfig(
            method=method,
            url=url,
            headers=headers,
            body=body,
            timeout=timeout,
            credential_id=credential_id
        )
        return self
    
    def sql_query(self,
                  sql: str,
                  operation: str = "select",
                  params: Optional[Union[List[Any], Dict[str, Any]]] = None,
                  connection: Optional[Union[DatabaseConnectionConfig, Dict[str, Any]]] = None,
                  pool: Optional[Union[ConnectionPoolConfig, Dict[str, Any]]] = None) -> 'NodeBuilder':
        """
        配置SQL查询节点
        
        Args:
            sql: SQL语句
            operation: 操作类型 (select/insert/update/delete/execute)
            params: SQL参数
            connection: 数据库连接配置（可以是 DatabaseConnectionConfig 对象或字典）
            pool: 连接池配置（可以是 ConnectionPoolConfig 对象或字典）
        """
        self._type = "mysql"
        config_dict = {
            "sql": sql,
            "operation": operation
        }
        if params is not None:
            config_dict["params"] = params
        if connection is not None:
            config_dict["connection"] = connection
        if pool is not None:
            config_dict["pool"] = pool
        
        self._config = SqlConfig.from_dict(config_dict)
        return self
    
    def script(self,
               script: str,
               script_type: str = "python",
               function_name: Optional[str] = None) -> 'NodeBuilder':
        """
        配置脚本节点
        
        Args:
            script: 脚本内容
            script_type: 脚本类型 (python/expression/function)
            function_name: 函数名（当script_type为function时）
        """
        self._type = "script"
        self._config = ScriptConfig(
            script=script,
            script_type=script_type,
            function_name=function_name
        )
        return self
    
    def log(self, message: str, level: str = "INFO") -> 'NodeBuilder':
        """
        配置日志节点
        
        Args:
            message: 日志消息
            level: 日志级别
        """
        self._type = "log_message"
        self._config = LogConfig(message=message, level=level)
        return self
    
    def assertion(self, rules: List[Union[AssertionRule, Dict[str, Any]]]) -> 'NodeBuilder':
        """
        配置断言节点
        
        Args:
            rules: 断言规则列表（可以是 AssertionRule 对象或字典）
        """
        self._type = "assertion"
        self._config = AssertionConfig(rules=rules)
        return self
    
    def variable_extractor(self, extractions: List[Union[ExtractionRule, Dict[str, Any]]]) -> 'NodeBuilder':
        """
        配置变量提取节点
        
        Args:
            extractions: 提取规则列表（可以是 ExtractionRule 对象或字典）
        """
        self._type = "variable_extractor"
        self._config = VariableExtractorConfig(extractions=extractions)
        return self
    
    def condition(self, expression: str) -> 'NodeBuilder':
        """
        配置条件节点
        
        Args:
            expression: 条件表达式
        """
        self._type = "condition"
        self._config = ConditionConfig(expression=expression)
        return self
    
    def mq_send(self,
                topic: str,
                message_body: str,
                environment: str = "dev",
                tag: str = "*",
                key: str = "*") -> 'NodeBuilder':
        """
        配置消息队列发送节点
        
        Args:
            topic: 主题
            message_body: 消息体
            environment: 环境
            tag: 标签
            key: 键
        """
        self._type = "rocketmq"
        self._config = MqConfig(
            topic=topic,
            message_body=message_body,
            environment=environment,
            tag=tag,
            key=key
        )
        return self
    
    def sub_workflow(self,
                     workflow_file: Optional[str] = None,
                     workflow_data: Optional[Dict[str, Any]] = None,
                     input_mapping: Optional[Dict[str, str]] = None,
                     output_mapping: Optional[Dict[str, str]] = None) -> 'NodeBuilder':
        """
        配置子工作流节点
        
        Args:
            workflow_file: 工作流文件路径
            workflow_data: 工作流数据
            input_mapping: 输入映射
            output_mapping: 输出映射
        """
        self._type = "sub_workflow"
        self._config = SubWorkflowConfig(
            workflow_file=workflow_file,
            workflow_data=workflow_data,
            input_mapping=input_mapping,
            output_mapping=output_mapping
        )
        return self
    
    def ui_action(self,
                  operation: str,
                  selector: Optional[str] = None,
                  selector_type: str = "css",
                  timeout: int = 30000,
                  viewport: Optional[Union[Viewport, Dict[str, int]]] = None,
                  **kwargs) -> 'NodeBuilder':
        """
        配置UI操作节点
        
        Args:
            operation: 操作类型 (click/input/navigate等)
            selector: 元素选择器
            selector_type: 选择器类型 (css/xpath)
            timeout: 超时时间（毫秒）
            viewport: 视口配置（可以是 Viewport 对象或字典）
            **kwargs: 其他配置参数
        """
        self._type = "ui_action"
        config_dict = {
            "operation": operation,
            "selector": selector,
            "selector_type": selector_type,
            "timeout": timeout
        }
        if viewport is not None:
            config_dict["viewport"] = viewport
        config_dict.update(kwargs)
        self._config = UIConfig.from_dict(config_dict)
        return self
    
    def custom(self, node_type: str, config: Dict[str, Any]) -> 'NodeBuilder':
        """
        配置自定义节点（用于插件等）
        
        Args:
            node_type: 节点类型
            config: 配置字典
        """
        self._type = node_type
        # 创建一个临时的BaseConfig子类
        class CustomConfig(BaseConfig):
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)
            
            @classmethod
            def from_dict(cls, data: Dict[str, Any]) -> 'CustomConfig':
                return cls(**data)
        
        self._config = CustomConfig(**config)
        return self
    

    def position(self, x: float, y: float) -> 'NodeBuilder':
        """
        设置节点位置

        Args:
            x: X坐标
            y: Y坐标
        """
        self._position = {"x": x, "y": y}
        return self
    
    def data(self, data: Dict[str, Any]) -> 'NodeBuilder':
        """
        设置节点额外数据
        
        Args:
            data: 数据字典
        """
        self._data = data
        return self
    
    def build(self) -> Node:
        """构建节点对象"""
        if not self._type or not self._config:
            raise ValueError("节点类型和配置不能为空")
        
        return Node(
            id=self._id,
            type=self._type,
            config=self._config,
            position=self._position,
            data=self._data
        )


class EdgeBuilder:
    """边构建器 - 使用链式API构建边"""
    
    def __init__(self, source: str, target: str, edge_id: Optional[str] = None):
        """
        初始化边构建器
        
        Args:
            source: 源节点ID
            target: 目标节点ID
            edge_id: 边ID，如果不提供则自动生成
        """
        self._id = edge_id or f"edge_{uuid.uuid4().hex[:8]}"
        self._source = source
        self._target = target
        self._config = EdgeConfig()
        self._data: Optional[Dict[str, Any]] = None
    
    def condition(self, condition: str) -> 'EdgeBuilder':
        """
        设置边的条件
        
        Args:
            condition: 条件表达式
        """
        self._config.condition = condition
        return self
    
    def weight(self, weight: float) -> 'EdgeBuilder':
        """
        设置边的权重
        
        Args:
            weight: 权重值
        """
        self._config.weight = weight
        return self
    
    def handles(self, source_handle: str, target_handle: str) -> 'EdgeBuilder':
        """
        设置边的连接点
        
        Args:
            source_handle: 源节点连接点
            target_handle: 目标节点连接点
        """
        self._config.source_handle = source_handle
        self._config.target_handle = target_handle
        return self
    
    def data(self, data: Dict[str, Any]) -> 'EdgeBuilder':
        """
        设置边的额外数据
        
        Args:
            data: 数据字典
        """
        self._data = data
        return self
    
    def build(self) -> Edge:
        """构建边对象"""
        return Edge(
            id=self._id,
            source=self._source,
            target=self._target,
            config=self._config,
            data=self._data
        )


class WorkflowBuilder:
    """工作流构建器 - 使用链式API构建工作流"""
    
    def __init__(self):
        """初始化工作流构建器"""
        self._work_id: Optional[str] = None
        self._work_name: Optional[str] = None
        self._nodes: List[Node] = []
        self._edges: List[Edge] = []
        self._metadata: Dict[str, Any] = {}
        self._node_builders: Dict[str, NodeBuilder] = {}
    
    def node(self, node_id: Optional[str] = None) -> NodeBuilder:
        """
        创建节点构建器
        
        Args:
            node_id: 节点ID，如果不提供则自动生成
        
        Returns:
            NodeBuilder实例
        """
        builder = NodeBuilder(node_id)
        if builder._id:
            self._node_builders[builder._id] = builder
        return builder
    
    def add_node(self, node: Union[Node, NodeBuilder]) -> 'WorkflowBuilder':
        """
        添加节点
        
        Args:
            node: Node对象或NodeBuilder对象
        """
        if isinstance(node, NodeBuilder):
            node = node.build()
        self._nodes.append(node)
        return self
    
    def edge(self, source: str, target: str, edge_id: Optional[str] = None) -> EdgeBuilder:
        """
        创建边构建器
        
        Args:
            source: 源节点ID
            target: 目标节点ID
            edge_id: 边ID
        
        Returns:
            EdgeBuilder实例
        """
        return EdgeBuilder(source, target, edge_id)
    
    def add_edge(self, edge: Union[Edge, EdgeBuilder]) -> 'WorkflowBuilder':
        """
        添加边
        
        Args:
            edge: Edge对象或EdgeBuilder对象
        """
        if isinstance(edge, EdgeBuilder):
            edge = edge.build()
        self._edges.append(edge)
        return self
    
    def connect(self, source: str, target: str, condition: Optional[str] = None) -> 'WorkflowBuilder':
        """
        快速连接两个节点
        
        Args:
            source: 源节点ID
            target: 目标节点ID
            condition: 可选的条件表达式
        """
        edge_builder = self.edge(source, target)
        if condition:
            edge_builder.condition(condition)
        self.add_edge(edge_builder)
        return self
    
    def work_id(self, work_id: str) -> 'WorkflowBuilder':
        """
        设置工作流ID
        
        Args:
            work_id: 工作流ID
        """
        self._work_id = work_id
        return self
    
    def work_name(self, work_name: str) -> 'WorkflowBuilder':
        """
        设置工作流名称
        
        Args:
            work_name: 工作流名称
        """
        self._work_name = work_name
        return self
    
    def metadata(self, **kwargs) -> 'WorkflowBuilder':
        """
        设置元数据
        
        Args:
            **kwargs: 元数据键值对
        """
        self._metadata.update(kwargs)
        return self
    
    def build(self) -> Workflow:
        """构建工作流对象"""
        return Workflow(
            work_id=self._work_id,
            work_name=self._work_name,
            nodes=self._nodes,
            edges=self._edges,
            metadata=self._metadata
        )
    
    def to_json(self, indent: int = 2) -> str:
        """
        转换为JSON字符串
        
        Args:
            indent: 缩进空格数
        
        Returns:
            JSON字符串
        """
        import json
        workflow = self.build()
        return json.dumps(workflow.to_dict(), indent=indent, ensure_ascii=False)
    
    def save(self, filepath: str, indent: int = 2) -> None:
        """
        保存为JSON文件
        
        Args:
            filepath: 文件路径
            indent: 缩进空格数
        """
        import json
        workflow = self.build()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(workflow.to_dict(), f, indent=indent, ensure_ascii=False)


# 便捷函数

def create_workflow() -> WorkflowBuilder:
    """创建工作流构建器"""
    return WorkflowBuilder()


def create_node(node_id: Optional[str] = None) -> NodeBuilder:
    """创建节点构建器"""
    return NodeBuilder(node_id)


def create_edge(source: str, target: str, edge_id: Optional[str] = None) -> EdgeBuilder:
    """创建边构建器"""
    return EdgeBuilder(source, target, edge_id)


def load_workflow(filepath: str) -> Workflow:
    """
    从JSON文件加载工作流
    
    Args:
        filepath: JSON文件路径
    
    Returns:
        Workflow对象
    """
    import json
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return Workflow.from_dict(data)


def load_workflow_from_json(json_str: str) -> Workflow:
    """
    从JSON字符串加载工作流
    
    Args:
        json_str: JSON字符串
    
    Returns:
        Workflow对象
    """
    import json
    data = json.loads(json_str)
    return Workflow.from_dict(data)

