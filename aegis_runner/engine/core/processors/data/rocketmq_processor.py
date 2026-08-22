# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-06-13
@packageName src.core.processors.data
@className RocketmqProcessor
@describe RocketMQ 消息发送处理器
"""

import requests
import json
import os
import time
from typing import Optional, Dict, Any, List

from aegis_runner.engine.clients.rocketmq_client import SpotterRocketMQClient
from aegis_runner.engine.core.processors import render_recursive
from aegis_runner.engine.core.interfaces.processor_interface import ProcessorInterface
from aegis_runner.engine.core.simple_logger import logger
from aegis_runner.engine.core.exceptions import ValidationError, ExecutionError, ErrorCategory
from aegis_runner.engine.core.elegant_processor_registry import register_processor, ProcessorCategory
from aegis_runner.engine.models.response import ResponseBuilder


@register_processor(
    processor_type="rocketmq",
    category=ProcessorCategory.DATA,
    description="RocketMQ消息队列处理器，支持消息发送和接收",
    tags={"message", "queue", "rocketmq", "data"},
    enabled=True,
    priority=55,
    dependencies=["requests"],
    version="1.0.0",
    author="Jan"
)
class RocketmqProcessor(ProcessorInterface):
    """
    RocketMQ 消息发送处理器
    
    功能：
    - 支持 RocketMQ 消息发送
    - 支持动态参数渲染
    - 支持多种环境配置
    - 支持自定义请求头
    - 支持消息标签和键值
    - 支持结果验证
    """
    
    def __init__(self):
        """初始化处理器"""
        pass
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        验证配置
        
        必需配置：
        - topic: 消息主题
        - message_body: 消息内容
        
        可选配置：
        - environment: 环境 (dev/test/prod，默认dev)
        - custom_url: 自定义服务地址（可通过工作流变量 ${rocketmq_url} 设置）
        - custom_token: 自定义认证 token（可通过工作流变量 ${rocketmq_token} 设置）
        - site_tenant: 站点租户 (默认default)
        - tag: 消息标签 (默认*)
        - key: 消息键值 (默认*)
        - custom_headers: 自定义请求头
        - timeout: 超时时间（秒，默认30）
        - output_variable: 保存结果的变量名
        """
        # 可选校验：仅提示，不阻断
        required_fields = ['topic', 'message_body']
        for field in required_fields:
            if field not in config:
                logger.warning(f"[RocketmqProcessor] 缺少建议配置: {field}，将尝试在执行阶段从前置结果或变量中获取")
        
        # 验证 topic
        topic = config.get('topic')
        if topic is not None and (not isinstance(topic, str) or not topic.strip()):
            logger.warning("[RocketmqProcessor] topic 建议为非空字符串")
        
        # 验证 message_body
        message_body = config.get('message_body')
        if message_body in (None, ""):
            logger.warning("[RocketmqProcessor] message_body 为空，将尝试使用前置节点输出")
        
        # 验证环境
        environment = config.get('environment', 'dev')
        valid_environments = ['dev', 'test', 'prod']
        if environment not in valid_environments:
            logger.warning(f"[RocketmqProcessor] environment 应为 {valid_environments} 之一，当前为 {environment}")
        
        # 验证超时时间
        timeout = config.get('timeout', 30)
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            logger.warning("[RocketmqProcessor] timeout 建议为大于 0 的数字")
        
        return True
    
    def execute(self, node_info: Dict[str, Any], context: Any, 
                predecessor_results: Dict[str, Any]) -> Any:
        """
        执行 RocketMQ 消息发送
        
        Args:
            node_info: 节点信息
            context: 执行上下文
            predecessor_results: 前置节点结果
            
        Returns:
            发送结果
        """
        start_time = time.time()
        logger.info("[RocketmqProcessor] 开始执行 RocketMQ 消息发送")
        
        # 1. 获取配置
        config = node_info.get("data", {}).get("config", {})
        
        # 2. 可选校验（仅记录警告，不阻断）
        try:
            self.validate_config(config)
        except Exception as _:
            # 理论上 validate_config 不再抛错；兜底不阻断
            pass
        
        # 3. 渲染配置中的变量（全量递归渲染）
        config = render_recursive(config, context)
        
        # 4. 记录详细的 RocketMQ 请求信息
        topic = config.get('topic', '')
        tag = config.get('tag', '*')
        key = config.get('key', '*')
        site_tenant = config.get('site_tenant', 'default')
        message_body = config.get('message_body', '')
        
        # 格式化消息体用于显示，不做截断
        if isinstance(message_body, dict):
            message_body_display = json.dumps(message_body, indent=2, ensure_ascii=False)
        else:
            message_body_display = str(message_body)
        
        request_details_lines = [
            "================== RocketMQ Request Details ==================",
            f"Topic        : {topic}",
            f"Tag          : {tag}",
            f"Key          : {key}",
            f"Site Tenant  : {site_tenant}",
            f"MQ URL       : {config.get('mq_url', 'N/A')}",
            f"Message Body : {message_body_display}",
            f"Node ID      : {node_info.get('id', 'N/A')}",
        ]
        
        # 全局变量
        if hasattr(context, 'get_all_variables'):
            variables = context.get_all_variables()
            if variables:
                request_details_lines.append("Variables    :")
                # 完整显示所有变量，不做截断
                for key, value in variables.items():
                    if isinstance(value, (dict, list)):
                        value_str = json.dumps(value, indent=2, ensure_ascii=False)
                    else:
                        value_str = str(value)
                    request_details_lines.append(f"  {key}: {value_str}")
            else:
                request_details_lines.append("Variables    : None")
        
        request_details_lines.append("=============================================================")
        logger.info("\n".join(request_details_lines))
        
        # 5. 执行 RocketMQ 发送
        try:
            result = self._send_rocketmq_message(config, predecessor_results)
            duration = time.time() - start_time
            
            # 6. 保存结果到上下文
            output_var = config.get('output_variable')
            if output_var:
                context.set_variable(output_var, result)
                logger.info(f"[RocketmqProcessor] 结果已保存到变量: {output_var}")
            
            # 7. 记录详细的 RocketMQ 响应信息
            original_response = result.get("result", {})
            status_emoji = "✅ 成功" if result.get("status") == "success" else "❌ 失败"
            
            # 格式化响应用于显示
            if isinstance(original_response, dict):
                response_display = json.dumps(original_response, indent=2, ensure_ascii=False)
            else:
                response_display = str(original_response)
            
            response_details = f"""
================== RocketMQ Response Details ==================
Status       : {status_emoji}
Msg ID       : {result.get("msg_id", "N/A")}
Topic        : {result.get("topic", topic)}
Tag          : {result.get("tag", tag)}
Key          : {result.get("key", key)}
Response     : {response_display}
Duration     : {duration:.3f}s
=============================================================
"""
            logger.info(response_details)
            
            # 使用标准响应格式
            if result.get("status") == "success":
                # 获取原始 response（从 _send_rocketmq_message 返回的 result 字段中）
                original_response = result.get("result", {})
                
                # 从result中获取message_body（已经过处理，可能从前置结果获取或已转换为JSON字符串）
                message_body = result.get("message_body", "")
                if not message_body:
                    # 如果result中没有，尝试从config中获取
                    message_body = config.get('message_body', '')
                    if isinstance(message_body, dict):
                        message_body = json.dumps(message_body, ensure_ascii=False)
                    elif not isinstance(message_body, str):
                        message_body = str(message_body)
                
                # 使用原始 response 作为 body
                return ResponseBuilder.success(
                    processor_type="rocketmq",
                    body=original_response,  # 直接返回原始 response
                    message="消息发送成功",
                    status_code=200,
                    metadata={
                        "topic": result.get("topic", ""),
                        "tag": result.get("tag", "*"),
                        "key": result.get("key", "*"),
                        "message_body": message_body  # 添加消息体
                    },
                    duration=duration
                ).to_dict()
            else:
                return ResponseBuilder.error(
                    processor_type="rocketmq",
                    error=result.get("message", "RocketMQ 消息发送失败"),
                    error_code="MQ_SEND_ERROR",
                    status_code=500,
                    error_details=result,
                    duration=duration
                ).to_dict()
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"[RocketmqProcessor] RocketMQ 消息发送失败: {e}")
            return ResponseBuilder.error(
                processor_type="rocketmq",
                error=f"RocketMQ 消息发送失败: {str(e)}",
                error_code="MQ_ERROR",
                status_code=500,
                duration=duration
            ).to_dict()

    @classmethod
    def _send_rocketmq_message(cls, config: Dict[str, Any],
                              predecessor_results: Dict[str, Any]) -> Any:
        """
        发送 RocketMQ 消息

        Args:
            config: 配置参数
            predecessor_results: 前置节点结果

        Returns:
            发送结果
        """
        # 获取消息内容
        message_body = config.get('message_body', '')

        # 如果消息体为空，尝试从前置结果获取
        if not message_body and predecessor_results:
            first_result = list(predecessor_results.values())[0]
            if isinstance(first_result, dict):
                message_body = json.dumps(first_result, ensure_ascii=False)
            else:
                message_body = str(first_result)

        if not message_body:
            raise ValueError("message_body 不能为空，且无前置节点结果")

        # 如果是字典，转换为JSON字符串
        if isinstance(message_body, dict):
            message_body = json.dumps(message_body, ensure_ascii=False)

        # 获取其他配置
        topic = config.get('topic')
        site_tenant = config.get('site_tenant', 'default')
        tag = config.get('tag', '*')
        key = config.get('key', '*')
        timeout = config.get('timeout', 30)

        logger.info(f"[RocketMQProcessor] 发送消息到主题: {topic}")
        logger.debug(f"[RocketMQProcessor] 消息内容: {message_body}")

        try:
            # 从配置中获取自定义 URL 和 token（支持工作流变量渲染）
            url = config.get('mq_url')

            # 创建SDK实例（支持从工作流变量获取 URL 和 token）
            mq = SpotterRocketMQClient(
                base_url=url,
            )

            # 设置站点信息
            if site_tenant != "default":
                mq.set_site_tenant(site_tenant)

            # 发送消息
            result = mq.send_message(
                topic=topic,
                message_body=message_body,
                tag=tag,
                key=key,
            )

            # 构建标准化返回结果
            # 判断逻辑：优先检查success字段，如果没有则检查error字段
            # 注意：不依赖code字段，因为即使code是500，消息也可能发送成功
            success = result.get("success")
            if success is None:
                if "error" in result:
                    success = False
                else:
                    success = True
            
            if success:
                return {
                    "status": "success",
                    "msg_id": result.get("msg_id"),
                    "topic": topic,
                    "tag": tag,
                    "key": key,
                    "message_body": message_body,
                    "result": result,
                    "status_code": result.get("status_code"),
                    "data": result.get("data"),
                    "message": "RocketMQ 消息发送成功"
                }
            else:
                return {
                    "status": "error",
                    "topic": topic,
                    "message_body": message_body,
                    "error": result.get("error"),
                    "status_code": result.get("status_code"),
                    "message": f"RocketMQ 消息发送失败: {result.get('error')}"
                }

        except Exception as e:
            error_msg = f"RocketMQ 发送异常: {str(e)}"
            logger.error(f"[RocketmqProcessor] {error_msg}")
            raise Exception(error_msg)

    # ========== 元数据方法 ==========
    
    def get_processor_type(self) -> str:
        """获取处理器类型"""
        return "rocketmq"
    
    def get_processor_name(self) -> str:
        """获取处理器名称"""
        return "RocketmqProcessor"
    
    def get_processor_description(self) -> str:
        """获取处理器描述"""
        return "RocketMQ 消息发送处理器"
    
    def get_required_config_keys(self) -> list:
        """获取必需的配置键"""
        return ['topic', 'message_body']
    
    def get_optional_config_keys(self) -> list:
        """获取可选的配置键"""
        return ['environment', 'custom_url', 'custom_token', 'site_tenant', 'tag', 'key', 'custom_headers', 'timeout', 'output_variable']