# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName
@className ExecutionModels
@describe 执行相关对象模型
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ExecutionStatus(Enum):
    """执行状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    """步骤状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """步骤执行结果"""
    node_id: str
    node_type: str
    status: StepStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    output: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    logs: Optional[str] = None  # 包含整个节点所有执行日志的详细消息（字符串格式）
    
    def __post_init__(self):
        if self.start_time and self.end_time:
            self.duration = (self.end_time - self.start_time).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "status": self.status.value,
            "metadata": self.metadata
        }
        
        if self.start_time:
            result["start_time"] = self.start_time.isoformat()
        if self.end_time:
            result["end_time"] = self.end_time.isoformat()
        if self.duration is not None:
            result["duration"] = self.duration
        if self.output is not None:
            result["output"] = self.output
        if self.error:
            result["error"] = self.error
        if self.logs:
            result["logs"] = self.logs
            
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StepResult':
        """从字典创建"""
        start_time = None
        if data.get("start_time"):
            start_time = datetime.fromisoformat(data["start_time"])
        
        end_time = None
        if data.get("end_time"):
            end_time = datetime.fromisoformat(data["end_time"])
        
        return cls(
            node_id=data["node_id"],
            node_type=data["node_type"],
            status=StepStatus(data["status"]),
            start_time=start_time,
            end_time=end_time,
            duration=data.get("duration"),
            output=data.get("output"),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
            logs=data.get("logs")
        )


@dataclass
class ExecutionResult:
    """执行结果"""
    workflow_id: str
    status: ExecutionStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    steps: List[StepResult] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.start_time and self.end_time:
            self.duration = (self.end_time - self.start_time).total_seconds()
    
    def add_step(self, step: StepResult) -> None:
        """添加步骤结果"""
        self.steps.append(step)
    
    def get_step(self, node_id: str) -> Optional[StepResult]:
        """获取步骤结果"""
        for step in self.steps:
            if step.node_id == node_id:
                return step
        return None
    
    def get_successful_steps(self) -> List[StepResult]:
        """获取成功的步骤"""
        return [step for step in self.steps if step.status == StepStatus.SUCCESS]
    
    def get_failed_steps(self) -> List[StepResult]:
        """获取失败的步骤"""
        return [step for step in self.steps if step.status == StepStatus.FAILED]
    
    def get_skipped_steps(self) -> List[StepResult]:
        """获取跳过的步骤"""
        return [step for step in self.steps if step.status == StepStatus.SKIPPED]
    
    def get_total_duration(self) -> float:
        """获取总执行时间"""
        if self.duration is not None:
            return self.duration
        
        if not self.steps:
            return 0.0
        
        total = 0.0
        for step in self.steps:
            if step.duration is not None:
                total += step.duration
        return total
    
    def get_success_rate(self) -> float:
        """获取成功率"""
        if not self.steps:
            return 0.0
        
        successful = len(self.get_successful_steps())
        return successful / len(self.steps)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "steps": [step.to_dict() for step in self.steps],
            "variables": self.variables,
            "metadata": self.metadata
        }
        
        if self.start_time:
            result["start_time"] = self.start_time.isoformat()
        if self.end_time:
            result["end_time"] = self.end_time.isoformat()
        if self.duration is not None:
            result["duration"] = self.duration
            
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionResult':
        """从字典创建"""
        start_time = None
        if data.get("start_time"):
            start_time = datetime.fromisoformat(data["start_time"])
        
        end_time = None
        if data.get("end_time"):
            end_time = datetime.fromisoformat(data["end_time"])
        
        steps = [StepResult.from_dict(step_data) for step_data in data.get("steps", [])]
        
        return cls(
            workflow_id=data["workflow_id"],
            status=ExecutionStatus(data["status"]),
            start_time=start_time,
            end_time=end_time,
            duration=data.get("duration"),
            steps=steps,
            variables=data.get("variables", {}),
            metadata=data.get("metadata", {})
        )


@dataclass
class ExecutionContextData:
    """执行上下文数据对象"""
    variables: Dict[str, Any] = field(default_factory=dict)
    node_results: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def set_variable(self, key: str, value: Any) -> None:
        """设置变量"""
        self.variables[key] = value
    
    def get_variable(self, key: str, default: Any = None) -> Any:
        """获取变量"""
        return self.variables.get(key, default)
    
    def set_node_result(self, node_id: str, result: Any) -> None:
        """设置节点结果"""
        self.node_results[node_id] = result
    
    def get_node_result(self, node_id: str, default: Any = None) -> Any:
        """获取节点结果"""
        return self.node_results.get(node_id, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "variables": self.variables,
            "node_results": self.node_results,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionContext':
        """从字典创建"""
        return cls(
            variables=data.get("variables", {}),
            node_results=data.get("node_results", {}),
            metadata=data.get("metadata", {})
        )
