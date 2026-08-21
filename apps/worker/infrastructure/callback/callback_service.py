# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-12-18
@describe 回调服务 - 工作流执行完成后通知用例平台

每个工作流执行完成后，实时回调通知用例平台。
用例平台可以根据 reportId 自行聚合统计。
"""
import json
import asyncio
import aiohttp
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from apps.worker.infrastructure.callback.callback_models import (
    SingleWorkflowCallback,
    create_single_callback
)

# 导入新的回调模型
try:
    from packages.contracts.workflow_models import (
        WorkflowRunResultCallbackModel,
        ResultSummaryModel,
        StepCallbackModel,
        LogModel,
        ResponseData
    )
except ImportError:
    # 如果导入失败，定义占位符
    WorkflowRunResultCallbackModel = None
    ResultSummaryModel = None
    StepCallbackModel = None
    LogModel = None
    ResponseData = None

# 尝试导入日志模块
try:
    from packages.shared.logging.log_component import LOGGER
except ImportError:
    import logging
    class LoggerWrapper:
        def __init__(self):
            self.logger = logging.getLogger(__name__)
            logging.basicConfig(level=logging.INFO)
    LOGGER = LoggerWrapper()


@dataclass
class CallbackResult:
    """回调结果"""
    success: bool
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 0
    duration_ms: int = 0


class WorkflowCallbackService:
    """
    工作流回调服务
    
    从配置文件读取回调地址，每个工作流执行完成后发送结果到用例平台
    """
    
    _config: Dict[str, Any] = None
    
    @classmethod
    def load_config(cls) -> Dict[str, Any]:
        """加载回调配置"""
        if cls._config is not None:
            return cls._config
        
        try:
            import yaml

            from packages.shared.settings.runtime import get_callback_workflow_config

            cls._config = get_callback_workflow_config()
            # 方案 B：工作流结果只发 Kafka，不再打 HTTP 回调地址
            LOGGER.logger.info(f"加载工作流结果配置: result_topic={cls._config.get('result_topic', 'workflow-run-result')}")
            return cls._config
            
        except Exception as e:
            LOGGER.logger.warning(f"加载回调配置失败: {e}")
            cls._config = {}
            return cls._config
    
    @classmethod
    def get_batch_size(cls) -> int:
        """获取分批大小（每批节点数量）"""
        config = cls.load_config()
        return config.get('batch_size', 50)  # 默认每批50个节点
    
    @classmethod
    def is_batch_enabled(cls) -> bool:
        """检查是否启用分批发送"""
        config = cls.load_config()
        return config.get('enable_batch', True)  # 默认启用分批
    
    @classmethod
    def get_callback_url(cls) -> Optional[str]:
        """获取回调地址"""
        config = cls.load_config()
        return config.get('url') or None
    
    @classmethod
    def is_enabled(cls) -> bool:
        """检查是否启用回调"""
        url = cls.get_callback_url()
        return bool(url and url.strip())

    @classmethod
    def get_result_topic(cls) -> Optional[str]:
        """获取工作流结果 Kafka topic（方案 B），与后端 WORKFLOW_RUN_RESULT_TOPIC 一致"""
        config = cls.load_config()
        return config.get('result_topic') or 'workflow-run-result'

    @classmethod
    def use_kafka_result(cls) -> bool:
        """是否将工作流结果发往 Kafka（方案 B）"""
        config = cls.load_config()
        return config.get('use_kafka_result', True)

    # Kafka 消息安全阈值（留 100KB 余量给 key、header 等开销）
    _KAFKA_MAX_PAYLOAD_BYTES = 900 * 1024

    @classmethod
    def _truncate_payload_if_needed(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查 payload 序列化大小，超限时逐步截断 logs 和 responseData.body。
        返回截断后的 payload（原地修改）。
        """
        raw = json.dumps(payload, ensure_ascii=False)
        if len(raw.encode('utf-8')) <= cls._KAFKA_MAX_PAYLOAD_BYTES:
            return payload

        run_id = payload.get('runId', '')
        original_size = len(raw.encode('utf-8'))
        LOGGER.logger.warning(
            f"Kafka 消息超限: runId={run_id}, size={original_size} bytes, "
            f"threshold={cls._KAFKA_MAX_PAYLOAD_BYTES} bytes, 开始截断降级"
        )

        # 第一轮：截断 logs[].content（最大膨胀来源）
        logs = payload.get('logs') or []
        for log_entry in logs:
            content = log_entry.get('content', '')
            if len(content) > 5000:
                log_entry['content'] = content[:5000] + f'\n... [Kafka 降级截断，原长度 {len(content)} 字符]'

        raw = json.dumps(payload, ensure_ascii=False)
        if len(raw.encode('utf-8')) <= cls._KAFKA_MAX_PAYLOAD_BYTES:
            LOGGER.logger.info(f"截断 logs 后消息大小: {len(raw.encode('utf-8'))} bytes, 已降至阈值内")
            return payload

        # 第二轮：截断 steps[].responseData.body（大 SQL 查询结果）
        steps = payload.get('steps') or []
        for step in steps:
            resp = step.get('responseData') or {}
            body = resp.get('body')
            if body is not None:
                body_json = json.dumps(body, ensure_ascii=False)
                if len(body_json) > 3000:
                    resp['body'] = {'_truncated': True, 'preview': body_json[:2000], 'originalSize': len(body_json)}

        raw = json.dumps(payload, ensure_ascii=False)
        if len(raw.encode('utf-8')) <= cls._KAFKA_MAX_PAYLOAD_BYTES:
            LOGGER.logger.info(f"截断 responseData.body 后消息大小: {len(raw.encode('utf-8'))} bytes, 已降至阈值内")
            return payload

        # 第三轮：进一步截断 logs 到 1000 字符
        for log_entry in logs:
            content = log_entry.get('content', '')
            if len(content) > 1000:
                log_entry['content'] = content[:1000] + f'\n... [Kafka 深度截断，原长度 {len(content)} 字符]'

        final_size = len(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
        LOGGER.logger.info(f"深度截断后消息大小: {final_size} bytes (原始: {original_size} bytes)")
        return payload

    @classmethod
    async def _send_workflow_result_to_kafka(cls, callback_model: 'WorkflowRunResultCallbackModel') -> bool:
        """将工作流执行结果发送到 Kafka（方案 B），单条消息，key=reportId。"""
        if not callback_model:
            return False
        try:
            from packages.shared.infrastructure.kafka_producer import get_kafka_producer
            producer = await get_kafka_producer()
            topic = cls.get_result_topic()
            payload = callback_model.model_dump(by_alias=True, exclude_none=False)
            payload = cls._truncate_payload_if_needed(payload)
            key = (callback_model.report_id or callback_model.run_id or "").strip() or None
            return await producer.send_workflow_result(topic, key, payload)
        except Exception as e:
            LOGGER.logger.error(f"发送工作流结果到 Kafka 失败: runId={getattr(callback_model, 'run_id', '')}, error={e}", exc_info=True)
            return False

    @classmethod
    async def _send_request(cls, url: str, payload: Dict[str, Any]) -> CallbackResult:
        """
        发送HTTP请求
        
        Args:
            url: 请求地址
            payload: 请求数据
            
        Returns:
            CallbackResult: 回调结果
        """
        config = cls.load_config()
        timeout = config.get('timeout', 30)
        retry_count = config.get('retry_count', 3)
        retry_delay = config.get('retry_delay', 1)
        custom_headers = config.get('headers', {})
        
        start_time = datetime.now()
        attempts = 0
        last_error = None
        
        # 请求头
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Aegis-Runner/1.0",
            "X-Callback-Timestamp": datetime.now().isoformat()
        }
        if custom_headers:
            headers.update(custom_headers)
        
        # 重试循环
        for attempt in range(retry_count):
            attempts = attempt + 1
            try:
                LOGGER.logger.info(f"发送回调 (尝试 {attempts}/{retry_count}): {url}")
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=timeout)
                    ) as response:
                        response_body = await response.text()
                        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                        
                        if response.status in [200, 201, 202, 204]:
                            LOGGER.logger.info(f"回调成功: status={response.status}, duration={duration_ms}ms")
                            return CallbackResult(
                                success=True,
                                status_code=response.status,
                                response_body=response_body,
                                attempts=attempts,
                                duration_ms=duration_ms
                            )
                        else:
                            last_error = f"HTTP {response.status}: {response_body[:200]}"
                            LOGGER.logger.warning(f"回调返回非成功状态: {last_error}")
                            
            except aiohttp.ClientError as e:
                last_error = f"网络错误: {str(e)}"
                LOGGER.logger.warning(f"回调请求失败: {last_error}")
            except asyncio.TimeoutError:
                last_error = f"请求超时 ({timeout}s)"
                LOGGER.logger.warning(f"回调请求超时")
            except Exception as e:
                last_error = f"未知错误: {str(e)}"
                LOGGER.logger.error(f"回调请求异常: {last_error}", exc_info=True)
            
            # 重试前等待
            if attempt < retry_count - 1:
                LOGGER.logger.info(f"等待 {retry_delay}s 后重试...")
                await asyncio.sleep(retry_delay)
        
        # 所有重试失败
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        LOGGER.logger.error(f"回调最终失败: attempts={attempts}, error={last_error}")
        return CallbackResult(
            success=False,
            error=last_error,
            attempts=attempts,
            duration_ms=duration_ms
        )
    
    @classmethod
    async def send_callback(cls, callback: SingleWorkflowCallback) -> CallbackResult:
        """
        发送工作流完成回调（旧格式，保留以兼容）
        
        Args:
            callback: 工作流回调数据
            
        Returns:
            CallbackResult: 回调结果
        """
        url = cls.get_callback_url()
        if not url:
            LOGGER.logger.debug("未配置回调地址，跳过回调")
            return CallbackResult(success=True, error="未配置回调地址")
        
        payload = callback.to_dict()
        LOGGER.logger.info(f"发送工作流回调: runId={callback.run_id}, reportId={callback.report_id}")
        return await cls._send_request(url, payload)
    
    @classmethod
    async def send_workflow_result_callback(cls, callback_model: 'WorkflowRunResultCallbackModel') -> CallbackResult:
        """
        发送工作流执行结果
        """
        url = cls.get_callback_url()
        if not url:
            LOGGER.logger.debug("未配置回调地址，跳过回调")
            return CallbackResult(success=True, error="未配置回调地址")

        if cls.is_batch_enabled():
            return await cls._send_batch_callback(
                callback_model=callback_model,
                url=url,
                batch_size=cls.get_batch_size(),
            )

        payload = callback_model.model_dump(by_alias=True, exclude_none=False)
        return await cls._send_request(url, payload)
    
    @classmethod
    async def _send_batch_callback(cls, callback_model: 'WorkflowRunResultCallbackModel', url: str, batch_size: int) -> CallbackResult:
        """
        分批发送工作流执行结果回调
        
        Args:
            callback_model: 工作流执行结果回调模型对象
            url: 回调地址
            batch_size: 每批节点数量
            
        Returns:
            CallbackResult: 回调结果
        """
        steps = callback_model.steps or []
        logs = callback_model.logs or []
        
        # 计算总批次数（基于 steps 数量，logs 会对应分配到各批次）
        total_steps = len(steps)
        total_batches = (total_steps + batch_size - 1) // batch_size if total_steps > 0 else 1
        
        # 如果没有 steps，基于 logs 计算批次数
        if total_steps == 0 and logs:
            total_batches = (len(logs) + batch_size - 1) // batch_size
        
        LOGGER.logger.info(f"开始分批发送: runId={callback_model.run_id}, totalBatches={total_batches}, steps={len(steps)}, logs={len(logs)}")
        
        # 构建 logs 的索引映射（按 runStepId 或 stepId 关联到对应的 step）
        logs_by_step = {}
        for log in logs:
            step_id = getattr(log, 'run_step_id', None) or getattr(log, 'step_id', None)
            if step_id:
                if step_id not in logs_by_step:
                    logs_by_step[step_id] = []
                logs_by_step[step_id].append(log)
        
        # 分批发送 steps 和对应的 logs
        last_error = None
        all_success = True
        
        for batch_num in range(1, total_batches + 1):
            # 获取当前批次的 steps
            start_idx = (batch_num - 1) * batch_size
            end_idx = min(start_idx + batch_size, len(steps))
            batch_steps = steps[start_idx:end_idx] if steps else []
            
            # 获取当前批次 steps 对应的 logs
            batch_logs = []
            for step in batch_steps:
                step_id = getattr(step, 'step_id', None) or getattr(step, 'stepId', None)
                if step_id and step_id in logs_by_step:
                    batch_logs.extend(logs_by_step[step_id])
            
            # 如果当前批次没有 steps，尝试获取对应索引范围的 logs（用于只有 logs 没有 steps 的情况）
            if not batch_steps and logs:
                start_idx_logs = (batch_num - 1) * batch_size
                end_idx_logs = min(start_idx_logs + batch_size, len(logs))
                batch_logs = logs[start_idx_logs:end_idx_logs]
            
            # 构建批次回调数据
            batch_payload = callback_model.model_dump(by_alias=True, exclude_none=False)
            batch_payload['steps'] = [step.model_dump(by_alias=True) if hasattr(step, 'model_dump') else step for step in batch_steps]
            batch_payload['logs'] = [log.model_dump(by_alias=True) if hasattr(log, 'model_dump') else log for log in batch_logs]
            
            # 添加批次信息
            batch_payload['batchIndex'] = batch_num
            batch_payload['totalBatches'] = total_batches
            batch_payload['isFirstBatch'] = (batch_num == 1)
            batch_payload['isLastBatch'] = (batch_num == total_batches)
            
            # 如果不是第一批，只发送增量数据（但保留 runId 和 status 用于标识）
            if batch_num > 1:
                # 移除基础信息字段，只保留 runId、status 和批次数据
                # 注意：runId 和 status 必须保留，用于后端识别和合并
                batch_payload.pop('startTime', None)
                batch_payload.pop('endTime', None)
                batch_payload.pop('durationMs', None)
                batch_payload.pop('totalSteps', None)
                batch_payload.pop('passedCount', None)
                batch_payload.pop('failedCount', None)
                batch_payload.pop('skippedCount', None)
                batch_payload.pop('pendingCount', None)
                batch_payload.pop('resultSummary', None)
                batch_payload.pop('environmentName', None)
            
            # 发送当前批次
            LOGGER.logger.info(f"发送批次 {batch_num}/{total_batches}: runId={callback_model.run_id}, steps={len(batch_steps)}, logs={len(batch_logs)}")
            result = await cls._send_request(url, batch_payload)
            
            if not result.success:
                all_success = False
                last_error = result.error
                LOGGER.logger.warning(f"批次 {batch_num}/{total_batches} 发送失败: {result.error}")
                # 继续发送后续批次，不中断
            else:
                LOGGER.logger.info(f"批次 {batch_num}/{total_batches} 发送成功")
            
            # 批次间稍作延迟，避免后端压力过大
            if batch_num < total_batches:
                await asyncio.sleep(0.1)
        
        # 返回最终结果
        if all_success:
            LOGGER.logger.info(f"所有批次发送完成: runId={callback_model.run_id}, totalBatches={total_batches}")
            return CallbackResult(
                success=True,
                status_code=200,
                attempts=total_batches,
                duration_ms=0  # 总耗时由各批次累加，这里不计算
            )
        else:
            LOGGER.logger.error(f"分批发送部分失败: runId={callback_model.run_id}, lastError={last_error}")
            return CallbackResult(
                success=False,
                error=f"分批发送部分失败: {last_error}",
                attempts=total_batches
            )


# ============ 便捷函数 ============

async def send_single_workflow_callback(
    run_id: str,
    task_id: str,
    parent_task_id: str,
    report_id: str,
    success: bool,
    result_dict: Dict[str, Any],
    message: str = "",
    error: str = None
) -> CallbackResult:
    """
    发送工作流完成回调（新格式）
    
    使用 WorkflowRunResultCallbackModel 对象进行数据验证和构建
    
    Args:
        run_id: 运行ID（用例平台提供，对应单个工作流）
        task_id: Spotter 任务ID
        parent_task_id: 父任务ID（批量执行时的 tracerId）
        report_id: 报告ID（用例平台提供，用于聚合统计）
        success: 是否成功
        result_dict: 执行结果字典（包含 runId, status, steps, logs 等）
        message: 消息（已废弃，保留以兼容）
        error: 错误信息（已废弃，保留以兼容）
        
    Returns:
        CallbackResult: 回调结果
    """
    if not WorkflowRunResultCallbackModel:
        LOGGER.logger.error("WorkflowRunResultCallbackModel 未导入，无法使用新格式回调")
        return CallbackResult(success=False, error="WorkflowRunResultCallbackModel 未导入")
    
    try:
        # 准备回调数据
        callback_data = result_dict.copy()
        
        # 确保 runId 存在
        if not callback_data.get("runId"):
            callback_data["runId"] = run_id
        
        # 确保 status 存在（必填字段）
        if not callback_data.get("status"):
            # 根据 success 参数设置 status
            callback_data["status"] = "SUCCESS" if success else "FAILED"
        
        # 添加 reportId
        if report_id:
            callback_data["reportId"] = report_id
        
        # 处理 resultSummary：如果是字典，转换为 ResultSummaryModel
        if callback_data.get("resultSummary") and isinstance(callback_data["resultSummary"], dict):
            if ResultSummaryModel:
                callback_data["resultSummary"] = ResultSummaryModel(**callback_data["resultSummary"])
        
        # 处理 steps：转换为 StepCallbackModel 列表
        if callback_data.get("steps") and StepCallbackModel:
            steps = []
            for step_dict in callback_data["steps"]:
                try:
                    # 处理 responseData：如果是字典或列表，转换为 ResponseData 对象
                    response_data = step_dict.get("responseData")
                    if response_data is not None and ResponseData:
                        # 如果 responseData 已经是 ResponseData 格式（字典），直接使用
                        if isinstance(response_data, dict) and ("body" in response_data or "extractVars" in response_data or "assertion" in response_data):
                            # 已经是 ResponseData 格式
                            pass
                        else:
                            # 如果是原始格式（直接是响应数据），转换为 ResponseData 格式
                            step_dict = step_dict.copy()
                            step_dict["responseData"] = {
                                "body": response_data
                            }
                            # 移除 None 值
                            if step_dict["responseData"]["body"] is None:
                                step_dict["responseData"] = None
                    
                    step_model = StepCallbackModel(**step_dict)
                    steps.append(step_model)
                except Exception as e:
                    LOGGER.logger.warning(f"步骤数据转换失败，跳过: {e}, step={step_dict}")
                    # 如果转换失败，尝试修复 responseData 格式后重试
                    try:
                        step_dict_copy = step_dict.copy()
                        response_data = step_dict_copy.get("responseData")
                        if response_data is not None and not isinstance(response_data, dict):
                            # 如果不是字典，转换为 ResponseData 格式
                            step_dict_copy["responseData"] = {"body": response_data}
                            step_model = StepCallbackModel(**step_dict_copy)
                            steps.append(step_model)
                        else:
                            # 如果转换失败，直接使用原始字典
                            steps.append(step_dict)
                    except Exception:
                        # 最终失败，使用原始字典
                        steps.append(step_dict)
            callback_data["steps"] = steps
        
        # 处理 logs：转换为 LogModel 列表
        if callback_data.get("logs") and LogModel:
            logs = []
            for log_dict in callback_data["logs"]:
                try:
                    log_model = LogModel(**log_dict)
                    logs.append(log_model)
                except Exception as e:
                    LOGGER.logger.warning(f"日志数据转换失败，跳过: {e}, log={log_dict}")
                    # 如果转换失败，直接使用原始字典
                    logs.append(log_dict)
            callback_data["logs"] = logs
        
        # 创建 WorkflowRunResultCallbackModel 对象（会自动验证数据）
        callback_model = WorkflowRunResultCallbackModel(**callback_data)
        
        # 发送回调
        return await WorkflowCallbackService.send_workflow_result_callback(callback_model)
        
    except Exception as e:
        LOGGER.logger.error(f"构建工作流回调模型失败: {e}", exc_info=True)
        return CallbackResult(success=False, error=f"构建回调模型失败: {str(e)}")


# 保留旧函数名以兼容
async def send_workflow_callback(
    run_id: str,
    task_id: str,
    success: bool,
    result: Dict[str, Any],
    message: str = "",
    error: str = None
) -> CallbackResult:
    """
    发送工作流执行结果回调（兼容旧接口）
    """
    return await send_single_workflow_callback(
        run_id=run_id,
        task_id=task_id,
        parent_task_id="",
        report_id="",
        success=success,
        result_dict=result,
        message=message,
        error=error
    )
