# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName
@className SubWorkflowProcessor
@describe 子工作流处理器
"""

import json
import os
import time
from typing import Any, Dict, Optional
from datetime import datetime

from ...models.workflow import Workflow
from ...models.execution import ExecutionResult, ExecutionStatus
from ...models.configs import SubWorkflowConfig
from ...core.processors import BaseProcessor
from aegis_runner.engine.core.elegant_processor_registry import register_processor, ProcessorCategory


@register_processor(
    processor_type="sub_workflow",
    category=ProcessorCategory.WORKFLOW,
    description="子工作流处理器，支持工作流的嵌套和调用",
    tags={"workflow", "sub", "nested", "execution"},
    enabled=True,
    priority=50,
    version="1.0.0",
    author="Aegis Team"
)
class SubWorkflowProcessor(BaseProcessor):
    """子工作流处理器"""
    
    def __init__(self):
        super().__init__()
        self.workflow_registry = {}  # 工作流注册表
    
    def register_workflow(self, name: str, workflow_data: Dict[str, Any]) -> None:
        """注册工作流到注册表"""
        self.workflow_registry[name] = workflow_data
    
    def execute(self, node_config: Dict[str, Any], context: Any, predecessor_results: Dict[str, Any]) -> Any:
        """
        执行子工作流
        
        Args:
            node_config: 节点配置
            context: 执行上下文
            predecessor_results: 前置节点结果
            
        Returns:
            子工作流执行结果
        """
        config = SubWorkflowConfig.from_dict(node_config.get("config", {}))
        
        # 加载子工作流
        sub_workflow = self._load_sub_workflow(config)
        if not sub_workflow:
            raise ValueError("无法加载子工作流")
        
        # 创建子工作流执行上下文
        sub_context = self._create_sub_context(context, config, predecessor_results)
        
        # 执行子工作流
        result = self._execute_sub_workflow(sub_workflow, sub_context, config)
        
        # 处理输出映射
        if config.output_mapping:
            self._apply_output_mapping(result, config.output_mapping, context)
        
        return result
    
    def _load_sub_workflow(self, config: SubWorkflowConfig) -> Optional[Workflow]:
        """加载子工作流"""
        # 1. 从注册表获取
        if config.workflow_name and config.workflow_name in self.workflow_registry:
            workflow_data = self.workflow_registry[config.workflow_name]
            return Workflow.from_dict(workflow_data)
        
        # 2. 从文件加载
        if config.workflow_file:
            if not os.path.exists(config.workflow_file):
                raise FileNotFoundError(f"工作流文件不存在: {config.workflow_file}")
            
            with open(config.workflow_file, 'r', encoding='utf-8') as f:
                workflow_data = json.load(f)
            return Workflow.from_dict(workflow_data)
        
        # 3. 从配置数据获取
        if config.workflow_data:
            return Workflow.from_dict(config.workflow_data)
        
        return None
    
    def _create_sub_context(self, parent_context: Any, config: SubWorkflowConfig, predecessor_results: Dict[str, Any]) -> Any:
        """创建子工作流执行上下文"""
        from ...context import ExecutionContext
        sub_context = ExecutionContext()
        
        # 复制父上下文的变量
        sub_context.variables = parent_context.variables.copy()
        sub_context.metadata = parent_context.metadata.copy()
        
        # 应用输入映射
        if config.input_mapping:
            for parent_var, sub_var in config.input_mapping.items():
                value = parent_context.get_variable(parent_var)
                if value is not None:
                    sub_context.set_variable(sub_var, value)
        
        # 应用前置节点结果
        for node_id, result in predecessor_results.items():
            sub_context.set_node_result(node_id, result)
        
        return sub_context
    
    def _execute_sub_workflow(self, sub_workflow: Workflow, sub_context: Any, config: SubWorkflowConfig) -> Dict[str, Any]:
        """执行子工作流"""
        try:
            # 使用现有的WorkflowExecutor执行子工作流
            from ..workflow_engine import WorkflowExecutor
            
            # 创建执行器
            executor = WorkflowExecutor(sub_workflow)
            executor.context = sub_context  # 使用子上下文
            
            # 设置超时
            start_time = time.time()
            
            # 执行子工作流
            execution_result = executor.execute()
            
            # 检查超时
            if config.timeout and time.time() - start_time > config.timeout:
                raise TimeoutError(f"子工作流执行超时: {config.timeout}秒")
            
            # 处理错误
            if execution_result.status == ExecutionStatus.FAILED:
                if config.error_handling == "stop_on_error":
                    raise Exception(f"子工作流执行失败: {execution_result}")
                elif config.error_handling == "continue_on_error":
                    return {"status": "failed", "error": str(execution_result)}
                elif config.error_handling == "retry":
                    # 这里可以实现重试逻辑
                    raise Exception(f"子工作流执行失败，需要重试: {execution_result}")
            
            # 返回执行结果
            return {
                "status": "success",
                "execution_result": execution_result,
                "variables": sub_context.variables,
                "node_results": sub_context.node_results
            }
            
        except Exception as e:
            if config.error_handling == "stop_on_error":
                raise e
            elif config.error_handling == "continue_on_error":
                return {"status": "failed", "error": str(e)}
            else:
                raise e
    
    def _apply_output_mapping(self, result: Dict[str, Any], output_mapping: Dict[str, str], parent_context: Any) -> None:
        """应用输出映射"""
        if "variables" in result:
            for sub_var, parent_var in output_mapping.items():
                value = result["variables"].get(sub_var)
                if value is not None:
                    parent_context.set_variable(parent_var, value)
        
        if "node_results" in result:
            for sub_node_id, parent_node_id in output_mapping.items():
                if sub_node_id in result["node_results"]:
                    value = result["node_results"][sub_node_id]
                    parent_context.set_node_result(parent_node_id, value)


# 创建全局实例
sub_workflow_processor = SubWorkflowProcessor()


def execute_sub_workflow(node_config: Dict[str, Any], context: Any, predecessor_results: Dict[str, Any]) -> Any:
    """执行子工作流的便捷函数"""
    return sub_workflow_processor.execute(node_config, context, predecessor_results)
