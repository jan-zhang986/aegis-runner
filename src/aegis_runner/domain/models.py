# -*- coding: utf-8 -*-
"""
Aegis Runner Domain Models & Schemas
"""
from typing import Optional, Dict, Any, List, Text
from pydantic import BaseModel, Field
from datetime import datetime


class WorkflowDebugExecuteRequest(BaseModel):
    """工作流执行请求"""
    run_id: Optional[Text] = Field(..., alias="runId", description="运行id")
    workflow: Dict[str, Any] = Field(..., description="工作流定义（包含 nodes 和 edges）")
    global_variables: Optional[Dict[str, Any]] = Field(None, alias="globalVariables", description="初始变量")
    enable_streaming: Optional[bool] = Field(False, alias="enableStreaming", description="是否启用流式执行")

    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }


class StepResultModel(BaseModel):
    """步骤执行结果模型"""
    node_id: str = Field(..., alias="nodeId", description="节点ID")
    node_type: str = Field(..., alias="nodeType", description="节点类型")
    status: str = Field(..., description="状态: pending/running/success/failed/skipped")
    start_time: Optional[str] = Field(None, alias="startTime", description="开始时间")
    end_time: Optional[str] = Field(None, alias="endTime", description="结束时间")
    duration: Optional[float] = Field(None, description="执行时长（秒）")
    output: Optional[Any] = Field(None, description="输出结果")
    error: Optional[str] = Field(None, description="错误信息")
    error_details: Optional[Dict[str, Any]] = Field(None, alias="errorDetails", description="错误详情")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")

    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }


class WorkflowExecuteResponse(BaseModel):
    """工作流执行响应"""
    workflow_id: str = Field(..., alias="workflowId", description="工作流ID")
    status: str = Field(..., description="状态: pending/running/success/failed/cancelled")
    start_time: Optional[str] = Field(None, alias="startTime", description="开始时间")
    end_time: Optional[str] = Field(None, alias="endTime", description="结束时间")
    duration: Optional[float] = Field(None, description="执行时长（秒）")
    steps: List[StepResultModel] = Field(default_factory=list, description="步骤执行结果列表")
    variables: Dict[str, Any] = Field(default_factory=dict, description="变量")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    success_rate: Optional[float] = Field(None, alias="successRate", description="成功率")
    total_steps: int = Field(0, alias="totalSteps", description="总步骤数")
    successful_steps: int = Field(0, alias="successfulSteps", description="成功步骤数")
    failed_steps: int = Field(0, alias="failedSteps", description="失败步骤数")
    skipped_steps: int = Field(0, alias="skippedSteps", description="跳过步骤数")

    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }


class BatchWorkflowItem(BaseModel):
    """批量工作流执行项"""
    workflow: Dict[str, Any] = Field(..., description="工作流定义（包含 nodes 和 edges）")
    variables: Optional[Dict[str, Any]] = Field(None, description="初始变量")
    run_id: Optional[str] = Field(None, alias="runId", description="运行ID（用例平台提供，回调时原样返回）")

    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }


class BatchWorkflowExecuteRequest(BaseModel):
    """批量工作流执行请求"""
    workflows: List[BatchWorkflowItem] = Field(..., description="工作流列表")
    priority: Optional[str] = Field("normal", description="优先级：urgent/high/normal")
    max_batch_size: Optional[int] = Field(1000, alias="maxBatchSize", description="单次批量处理的最大数量")
    report_id: Optional[str] = Field(None, alias="reportId", description="reportId（用例平台提供）")

    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }


class ResultSummaryModel(BaseModel):
    """结果摘要模型"""
    summary: str = Field(..., description="摘要信息")

    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }


class ResponseData(BaseModel):
    """响应数据模型"""
    body: Optional[Any] = Field(None, alias="body", description="响应数据")
    extract_vars: Optional[Dict[str, Any]] = Field(None, alias="extractVars", description="提取的变量")
    assertion_logs: Optional[List[Dict[str, Any]]] = Field(None, alias="assertion", description="断言日志列表")

    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }


class StepCallbackModel(BaseModel):
    """步骤回调模型"""
    step_id: str = Field(..., alias="stepId", description="步骤ID")
    step_name: str = Field(..., alias="stepName", description="步骤名称")
    step_type: str = Field(..., alias="stepType", description="步骤类型")
    order_num: int = Field(..., alias="orderNum", description="步骤顺序号")
    status: str = Field(..., description="步骤状态：SUCCESS/FAILED/SKIPPED/PENDING")
    start_time: Optional[int] = Field(None, alias="startTime", description="开始时间")
    end_time: Optional[int] = Field(None, alias="endTime", description="结束时间")
    duration_ms: float = Field(0, alias="durationMs", description="执行时长（毫秒）")
    request_data: Optional[Dict[str, Any]] = Field(None, alias="requestData", description="请求数据")
    response_data: Optional[ResponseData] = Field(None, alias="responseData", description="响应数据")
    assertion: Optional[List[Dict[str, Any]]] = Field(None, alias="assertion", description="断言日志列表")
    extract_vars: Optional[Dict[str, Any]] = Field(None, alias="extractVars", description="提取的变量")
    description: Optional[str] = Field(None, description="步骤描述")

    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }


class LogModel(BaseModel):
    """日志模型"""
    run_step_id: Optional[str] = Field(None, alias="runStepId", description="运行步骤ID")
    step_id: Optional[str] = Field(None, alias="stepId", description="步骤ID")
    level: str = Field(..., description="日志级别：INFO/WARN/ERROR/DEBUG")
    content: str = Field(..., description="日志内容")
    log_time: int = Field(..., alias="logTime", description="日志时间")

    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }


class WorkflowRunResultCallbackModel(BaseModel):
    """工作流执行结果回调模型"""
    report_id: Optional[str] = Field(None, alias="reportId", description="报告ID")
    run_id: str = Field(..., alias="runId", description="运行ID")
    status: str = Field(..., description="执行状态：SUCCESS/FAILED/RUNNING/PENDING/CANCELLED")
    start_time: Optional[int] = Field(None, alias="startTime", description="开始时间")
    end_time: Optional[int] = Field(None, alias="endTime", description="结束时间")
    duration_ms: int = Field(0, alias="durationMs", description="执行时长（毫秒）")
    total_steps: int = Field(0, alias="totalSteps", description="总步骤数")
    passed_count: int = Field(0, alias="passedCount", description="成功步骤数")
    failed_count: int = Field(0, alias="failedCount", description="失败步骤数")
    skipped_count: int = Field(0, alias="skippedCount", description="跳过步骤数")
    pending_count: int = Field(0, alias="pendingCount", description="待执行步骤数")
    result_summary: Optional[ResultSummaryModel] = Field(None, alias="resultSummary", description="结果摘要")
    environment_name: Optional[str] = Field(None, alias="environmentName", description="环境名称")
    steps: List[StepCallbackModel] = Field(default_factory=list, description="步骤执行结果列表")
    logs: List[LogModel] = Field(default_factory=list, description="日志列表")

    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }
