# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName src.core.processors.base
@className SleepProcessor
@describe 休眠处理器 - 用于在流程中暂停指定时间
"""

import time
import asyncio
import threading
from typing import Any, Dict
from aegis_runner.engine.context import ExecutionContext
from aegis_runner.engine.core.processors import BaseProcessor
from aegis_runner.engine.core.simple_logger import logger
from aegis_runner.engine.core.elegant_processor_registry import register_processor, ProcessorCategory


@register_processor(
    processor_type="sleep",
    category=ProcessorCategory.CORE,
    description="休眠处理器，支持多种休眠模式避免线程阻塞问题",
    tags={"sleep", "delay", "wait", "core", "non-blocking", "async"},
    enabled=True,
    priority=60,
    version="1.1.0",
    author="Aegis Team"
)
class SleepProcessor(BaseProcessor):
    """休眠处理器 - 用于在流程中暂停指定时间"""

    def __init__(self):
        super().__init__()
    
    def _get_config_schema_name(self) -> str:
        """获取配置模式名称"""
        return "sleep"
    
    def _validate_specific_config(self, config: Dict[str, Any]) -> bool:
        """休眠处理器特定的配置验证"""
        duration = config.get("duration", 0)
        
        # 验证休眠时间
        if not isinstance(duration, (int, float)):
            from aegis_runner.engine.core.exceptions import ValidationError, ErrorContext
            context = ErrorContext(processor_type=self.__class__.__name__)
            raise ValidationError(
                message=f"休眠时间必须是数字类型，当前类型: {type(duration)}",
                context=context
            )
        
        if duration < 0:
            from aegis_runner.engine.core.exceptions import ValidationError, ErrorContext
            context = ErrorContext(processor_type=self.__class__.__name__)
            raise ValidationError(
                message=f"休眠时间不能为负数，当前值: {duration}",
                context=context
            )
        
        # 检查最大休眠时间限制（防止过长的休眠）
        max_duration = config.get("max_duration", 3600)  # 默认最大1小时
        if duration > max_duration:
            from aegis_runner.engine.core.exceptions import ValidationError, ErrorContext
            context = ErrorContext(processor_type=self.__class__.__name__)
            raise ValidationError(
                message=f"休眠时间超过最大限制 {max_duration} 秒，当前值: {duration}",
                context=context
            )
        
        return True

    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> Dict[str, Any]:
        """
        执行休眠操作
        
        Args:
            node_info: 节点信息
            context: 执行上下文
            predecessor_results: 前置节点结果
            
        Returns:
            休眠结果信息
        """
        config = node_info.get("data", {}).get("config", {})
        
        # 获取休眠时间（支持动态渲染）
        duration_str = config.get("duration", "0")
        try:
            # 尝试渲染字符串变量
            if isinstance(duration_str, str):
                duration = float(context.render_string(duration_str))
            else:
                duration = float(duration_str)
        except (ValueError, TypeError) as e:
            logger.error(f"[SleepProcessor] 无法解析休眠时间: {duration_str}, 错误: {e}")
            raise ValueError(f"无法解析休眠时间: {duration_str}")
        
        # 获取可选参数
        reason = config.get("reason", "流程暂停")
        unit = config.get("unit", "seconds")  # seconds, milliseconds
        sleep_mode = config.get("mode", "blocking")  # blocking, non_blocking, async
        
        # 转换时间单位
        if unit == "milliseconds":
            actual_duration = duration / 1000.0
        else:  # seconds
            actual_duration = duration
        
        # 记录休眠开始
        start_time = time.time()
        formatted_reason = context.render_string(reason)
        
        logger.info(f"[SleepProcessor] 开始休眠: {actual_duration:.3f}秒, 模式: {sleep_mode}, 原因: {formatted_reason}")
        
        # 根据模式执行不同的休眠策略
        # 注意：工作流引擎在 Worker 端使用线程池执行，所以 time.sleep() 只会阻塞线程池中的线程
        # 不会阻塞 Worker 的事件循环，Worker 可以继续处理其他任务
        try:
            if sleep_mode == "blocking":
                # 阻塞式休眠（直接使用 time.sleep，最简单直接）
                # 在 Worker 线程池中执行，不会阻塞事件循环
                actual_sleep_time = self._blocking_sleep(actual_duration)
            elif sleep_mode == "non_blocking":
                # 非阻塞式休眠（使用线程，但仍需等待完成）
                # 注意：由于处理器必须等待休眠完成才能返回，所以仍会阻塞当前线程
                # 但在 Worker 线程池中执行，不会阻塞事件循环
                logger.debug("[SleepProcessor] non_blocking 模式：使用线程休眠，不会阻塞 Worker 事件循环")
                actual_sleep_time = self._non_blocking_sleep(actual_duration)
            elif sleep_mode == "async":
                # 异步休眠（使用 asyncio，但仍需等待完成）
                # 注意：由于处理器是同步的，所以仍会阻塞当前线程
                # 但在 Worker 线程池中执行，不会阻塞事件循环
                logger.debug("[SleepProcessor] async 模式：使用 asyncio 休眠，不会阻塞 Worker 事件循环")
                actual_sleep_time = self._async_sleep(actual_duration)
            else:
                logger.warning(f"[SleepProcessor] 未知的休眠模式: {sleep_mode}, 使用默认阻塞模式")
                actual_sleep_time = self._blocking_sleep(actual_duration)
                
        except KeyboardInterrupt:
            logger.warning(f"[SleepProcessor] 休眠被用户中断")
            raise
        except Exception as e:
            logger.error(f"[SleepProcessor] 休眠过程中发生错误: {e}")
            raise
        
        # 计算实际休眠时间
        end_time = time.time()
        total_elapsed = end_time - start_time
        
        # 记录休眠完成
        logger.info(f"[SleepProcessor] 休眠完成: 请求时间 {actual_duration:.3f}秒, 实际休眠 {actual_sleep_time:.3f}秒, 总耗时 {total_elapsed:.3f}秒")
        
        # 返回结果
        result = {
            "status": "completed",
            "mode": sleep_mode,
            "requested_duration": actual_duration,
            "actual_sleep_time": actual_sleep_time,
            "total_elapsed_time": total_elapsed,
            "reason": formatted_reason,
            "unit": unit,
            "start_time": start_time,
            "end_time": end_time,
            "node_id": node_info.get('id')
        }
        
        # 记录详细的休眠信息
        sleep_details = f"""
================== Sleep Details ==================
mode              : {sleep_mode}
requested_duration: {actual_duration:.3f} {unit}
actual_sleep_time : {actual_sleep_time:.3f} seconds
total_elapsed_time: {total_elapsed:.3f} seconds
reason            : {formatted_reason}
start_time        : {start_time:.3f}
end_time          : {end_time:.3f}
node_id           : {node_info.get('id')}
=================================================
"""
        logger.info(sleep_details)
        
        return result
    
    def _blocking_sleep(self, duration: float) -> float:
        """阻塞式休眠"""
        time.sleep(duration)
        return duration
    
    def _non_blocking_sleep(self, duration: float) -> float:
        """
        非阻塞式休眠（使用线程）
        
        注意：在 Worker 线程池中执行时，此方法只会阻塞线程池中的线程，
        不会阻塞 Worker 的事件循环，Worker 可以继续处理其他任务。
        """
        def sleep_worker():
            time.sleep(duration)
        
        # 创建并启动线程
        sleep_thread = threading.Thread(target=sleep_worker, daemon=True)
        sleep_thread.start()
        
        # 等待线程完成（必须等待，否则处理器会立即返回，工作流会继续执行）
        # 注意：这仍然会阻塞主线程，但使用线程可以在某些场景下提供更好的控制
        sleep_thread.join()
        
        return duration
    
    def _async_sleep(self, duration: float) -> float:
        """
        异步休眠（使用 asyncio）
        
        注意：在 Worker 线程池中执行时，此方法只会阻塞线程池中的线程，
        不会阻塞 Worker 的事件循环，Worker 可以继续处理其他任务。
        """
        try:
            # 尝试使用asyncio
            try:
                loop = asyncio.get_running_loop()
                # 如果事件循环正在运行，说明在异步环境中
                # 但由于处理器是同步的，我们需要在新线程中运行
                async def async_sleep():
                    await asyncio.sleep(duration)
                
                # 在新线程中运行异步代码
                def run_async():
                    asyncio.run(async_sleep())
                
                thread = threading.Thread(target=run_async, daemon=True)
                thread.start()
                # 必须等待，否则处理器会立即返回
                thread.join()
            except RuntimeError:
                # 没有运行中的事件循环，直接运行
                asyncio.run(asyncio.sleep(duration))
            
            return duration
        except Exception as e:
            logger.warning(f"[SleepProcessor] 异步休眠失败，回退到阻塞模式: {e}")
            return self._blocking_sleep(duration)

    def get_processor_description(self) -> str:
        """获取处理器描述"""
        return "休眠处理器 - 支持多种休眠模式：阻塞式、非阻塞式、异步式，避免多任务环境中的线程阻塞问题"
