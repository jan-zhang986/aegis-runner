# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-12-18
@describe 回调数据模型 - 工作流执行结果回调

使用 dataclass 定义清晰的数据结构，方便维护和使用
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class WorkflowStatus(str, Enum):
    """工作流执行状态"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"


class StepStatus(str, Enum):
    """步骤执行状态"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class StepResult:
    """步骤执行结果"""
    step_id: str
    step_name: str
    step_type: str
    order_num: int
    status: StepStatus
    start_time: Optional[int] = None  # 时间戳（毫秒）
    end_time: Optional[int] = None
    duration_ms: int = 0
    request_data: Dict[str, Any] = field(default_factory=dict)
    response_data: Dict[str, Any] = field(default_factory=dict)
    assertion: List[Dict[str, Any]] = field(default_factory=list)
    extract_vars: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（驼峰命名）"""
        return {
            "stepId": self.step_id,
            "stepName": self.step_name,
            "stepType": self.step_type,
            "orderNum": self.order_num,
            "status": self.status.value if isinstance(self.status, StepStatus) else self.status,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "durationMs": self.duration_ms,
            "requestData": self.request_data,
            "responseData": self.response_data,
            "assertionLogs": self.assertion,
            "extractVars": self.extract_vars,
            "errorMessage": self.error_message,
            "description": self.description
        }


@dataclass
class WorkflowResult:
    """工作流执行结果"""
    run_id: str
    task_id: str
    workflow_id: Optional[str] = None
    workflow_name: Optional[str] = None
    status: WorkflowStatus = WorkflowStatus.PENDING
    start_time: Optional[int] = None  # 时间戳（毫秒）
    end_time: Optional[int] = None
    duration_ms: int = 0
    total_steps: int = 0
    passed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    environment_name: str = ""
    steps: List[StepResult] = field(default_factory=list)
    error_message: Optional[str] = None
    result_summary: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（驼峰命名）"""
        return {
            "runId": self.run_id,
            "taskId": self.task_id,
            "workflowId": self.workflow_id,
            "workflowName": self.workflow_name,
            "status": self.status.value if isinstance(self.status, WorkflowStatus) else self.status,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "durationMs": self.duration_ms,
            "totalSteps": self.total_steps,
            "passedCount": self.passed_count,
            "failedCount": self.failed_count,
            "skippedCount": self.skipped_count,
            "environmentName": self.environment_name,
            "steps": [s.to_dict() for s in self.steps] if self.steps else [],
            "errorMessage": self.error_message,
            "resultSummary": self.result_summary
        }


@dataclass
class SingleWorkflowCallback:
    """
    工作流完成回调数据
    
    每个工作流执行完成后，发送此回调到用例平台。
    用例平台可以根据 reportId 自行聚合统计。
    """
    run_id: str                          # 运行ID（用例平台提供，对应单个工作流）
    task_id: str                         # Spotter 任务ID
    parent_task_id: Optional[str]        # 父任务ID（批量执行时的 tracerId）
    report_id: Optional[str]             # 报告ID（用例平台提供，用于聚合统计）
    success: bool                        # 是否成功
    status: WorkflowStatus               # 执行状态
    result: WorkflowResult               # 执行结果详情
    message: str = ""                    # 消息
    error: Optional[str] = None          # 错误信息
    completed_at: str = ""               # 完成时间 ISO 格式
    
    def __post_init__(self):
        if not self.completed_at:
            self.completed_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（驼峰命名）"""
        return {
            "runId": self.run_id,
            "taskId": self.task_id,
            "parentTaskId": self.parent_task_id,
            "reportId": self.report_id,
            "success": self.success,
            "status": self.status.value if isinstance(self.status, WorkflowStatus) else self.status,
            "result": self.result.to_dict() if self.result else {},
            "message": self.message,
            "error": self.error,
            "completedAt": self.completed_at
        }


# ============ 工厂方法 ============

def create_workflow_result_from_dict(data: Dict[str, Any], task_id: str = "") -> WorkflowResult:
    """从字典创建 WorkflowResult 对象"""
    # 处理步骤
    steps = []
    for step_data in data.get("steps", []):
        step = StepResult(
            step_id=step_data.get("stepId", ""),
            step_name=step_data.get("stepName", ""),
            step_type=step_data.get("stepType", ""),
            order_num=step_data.get("orderNum", 0),
            status=StepStatus(step_data.get("status", "PENDING")),
            start_time=step_data.get("startTime"),
            end_time=step_data.get("endTime"),
            duration_ms=step_data.get("durationMs", 0),
            request_data=step_data.get("requestData", {}),
            response_data=step_data.get("responseData", {}),
            assertion=step_data.get("assertion", []),
            extract_vars=step_data.get("extractVars", {}),
            error_message=step_data.get("errorMessage"),
            description=step_data.get("description", "")
        )
        steps.append(step)
    
    # 解析状态
    status_str = data.get("status", "PENDING")
    try:
        status = WorkflowStatus(status_str)
    except ValueError:
        status = WorkflowStatus.PENDING
    
    return WorkflowResult(
        run_id=data.get("runId", ""),
        task_id=task_id or data.get("taskId", ""),
        workflow_id=data.get("workflowId"),
        workflow_name=data.get("workflowName"),
        status=status,
        start_time=data.get("startTime"),
        end_time=data.get("endTime"),
        duration_ms=data.get("durationMs", 0),
        total_steps=data.get("totalSteps", 0),
        passed_count=data.get("passedCount", 0),
        failed_count=data.get("failedCount", 0),
        skipped_count=data.get("skippedCount", 0),
        environment_name=data.get("environmentName", ""),
        steps=steps,
        error_message=data.get("errorMessage"),
        result_summary=data.get("resultSummary", {}).get("summary", "") if isinstance(data.get("resultSummary"), dict) else str(data.get("resultSummary", ""))
    )


def create_single_callback(
    run_id: str,
    task_id: str,
    parent_task_id: str,
    report_id: str,
    success: bool,
    result_dict: Dict[str, Any],
    message: str = "",
    error: str = None
) -> SingleWorkflowCallback:
    """创建工作流回调对象"""
    # 解析状态
    status_str = result_dict.get("status", "FAILED" if not success else "SUCCESS")
    try:
        status = WorkflowStatus(status_str)
    except ValueError:
        status = WorkflowStatus.FAILED if not success else WorkflowStatus.SUCCESS
    
    result = create_workflow_result_from_dict(result_dict, task_id)
    
    return SingleWorkflowCallback(
        run_id=run_id,
        task_id=task_id,
        parent_task_id=parent_task_id,
        report_id=report_id,
        success=success,
        status=status,
        result=result,
        message=message,
        error=error
    )
