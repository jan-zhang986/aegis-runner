# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-10-30
@packageName src.core.processors.job
@className XxlJobProcessor
@describe XXL-Job 任务调度处理器

支持功能：
1. 通过 Handler 名称触发任务（使用 API 接口，无需数据库）
2. 传递任务执行参数
3. 支持多租户
4. 自动登录和认证

参考 aegis-runner 的 JobCenter 实现
使用独立的 XxlJobClient 封装 XXL-Job 操作
"""

import time
import json
from typing import Any, Dict

from src.engine.core.processors import BaseProcessor, render_recursive
from src.engine.core.simple_logger import logger
from src.engine.core.elegant_processor_registry import register_processor, ProcessorCategory
from src.engine.models.response import ResponseBuilder
from src.engine.clients.xxljob_client import XxlJobClient


@register_processor(
    processor_type="xxl_job",
    category=ProcessorCategory.DATA,
    description="XXL-Job 任务调度处理器，支持触发任务执行",
    tags={"xxljob", "job", "scheduler", "task"},
    enabled=True,
    priority=100,
    version="1.0.0",
    author="Aegis Team"
)
class XxlJobProcessor(BaseProcessor):
    """
    XXL-Job 处理器
    
    配置示例：
    {
        "executor_handler": "myJobHandler",
        "executor_param": "{\"key\": \"value\"}",
        "site_tenant": "DEFAULT",
        "address_list": "",
        "output_variable": "xxljob_result"
    }
    
    配置说明：
    - 必需配置：
      * executor_handler: 执行器 Handler 名称
    - 可选配置：
      * executor_param: 任务执行参数（JSON 字符串，可选）
      * site_tenant: 站点租户（默认: DEFAULT）
      * address_list: 执行器地址列表（可选）
      * output_variable: 输出变量名（默认: xxljob_result）
      * xxjob_url: XXL-Job 管理平台 URL（可选，优先从上下文变量 ${xxjob_url} 获取）
    
    注意：
    - xxjob_url 优先从工作流上下文变量 ${xxjob_url} 获取，如果不存在则从配置中获取
    - 账号密码在代码中写死，可通过环境变量覆盖：
      * XXLJOB_USERNAME: 登录用户名（默认: admin）
      * XXLJOB_PASSWORD: 登录密码（默认: 123456）
      * XXLJOB_APP_CODE: 应用代码（默认: developer）
    - 通过 Handler 名称触发任务，使用 API 接口查询任务信息，不再需要数据库连接
    - db_name 参数已废弃，不再使用
    """
    
    def __init__(self):
        super().__init__()
        self.processor_type = "xxljob"
        self.processor_name = "XXL-Job任务调度处理器"
        self.processor_description = "支持触发 XXL-Job 任务执行"
    
    def _get_config_schema_name(self) -> str:
        """获取配置模式名称"""
        return "xxljob"
    
    def _validate_specific_config(self, config: Dict[str, Any]) -> bool:
        """XXL-Job 特定的配置验证"""
        # 检查必需字段
        if not config.get("executor_handler"):
            logger.error("[XxlJobProcessor] executor_handler 不能为空")
            return False
        
        # xxjob_url 可以从上下文获取，不强制在配置中
        return True
    
    def execute(self, node_info: dict, context: Any, predecessor_results: dict) -> Dict[str, Any]:
        """
        执行 XXL-Job 操作
        
        Args:
            node_info: 节点信息
            context: 执行上下文
            predecessor_results: 前置节点结果
            
        Returns:
            执行结果
        """
        xxl_job_client = None
        start_time = time.time()

        try:
            # 获取配置
            config = node_info.get("data", {}).get("config", {})
            
            # 渲染配置中的变量
            config = render_recursive(config, context)
            
            # 验证配置
            if not self._validate_specific_config(config):
                return ResponseBuilder.error(
                    processor_type="xxl_job",
                    error="配置验证失败",
                    error_code="INVALID_CONFIG",
                    status_code=400,
                    duration=time.time() - start_time
                ).to_dict()
            
            # 从配置中获取所有参数（只获取一次，避免重复）
            output_variable = config.get("output_variable", "xxljob_result")
            executor_handler = config.get("executor_handler")
            executor_param = config.get("executor_param", "")
            site_tenant = config.get("site_tenant", "DEFAULT")
            address_list = config.get("address_list", "")
            # tag 优先从节点配置读取，其次从上下文变量 x-tag-header 读取；不再强制默认 aegis
            tag = config.get("x-tag-header")
            if not tag and hasattr(context, "get_variable"):
                try:
                    tag = context.get_variable("x-tag-header")
                except Exception:
                    tag = None

            # 从上下文获取 xxl_job_url（优先从上下文，其次从配置）
            base_url = None
            if hasattr(context, 'get_variable'):
                base_url = context.get_variable("url")
            if not base_url:
                base_url = config.get("url", "")
            
            if not base_url:
                return ResponseBuilder.error(
                    processor_type="xxl_job",
                    error="xxl-job_url 不能为空，请在工作流变量或配置中提供",
                    error_code="MISSING_XXL_JOB_URL",
                    status_code=400,
                    duration=time.time() - start_time
                ).to_dict()
            
            # 创建 XXL-Job 客户端（账号密码在代码中写死）
            xxl_job_client = self._create_xxl_job_client(base_url)
            
            # 记录详细的 XXL-Job 请求信息
            request_details_lines = ["\n================== XXL-Job Request Details ==================",
                                     f"XXL-Job URL  : {base_url}", f"Handler      : {executor_handler}",
                                     f"Site Tenant  : {site_tenant}", f"Executor Param: {executor_param}",
                                     f"Note         : 使用 API 接口查询任务，不再需要数据库",
                                     f"Node ID      : {node_info.get('id', 'N/A')}"]

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
            
            # 执行操作：通过 Handler 名称触发
            result = xxl_job_client.trigger_job_by_handler_with_context(
                executor_handler=executor_handler,
                executor_param=executor_param,
                site_tenant=site_tenant,
                address_list=address_list,
                tag=tag
            )
            
            # 保存结果到上下文变量
            if context and hasattr(context, 'set_variable'):
                context.set_variable(output_variable, result)
            
            duration = time.time() - start_time
            
            # 记录详细的 XXL-Job 响应信息
            status_emoji = "✅ 成功" if result.get("success") else "❌ 失败"
            response_body = result.get("content", result)
            
            # 格式化响应用于显示，不做截断
            if isinstance(response_body, dict):
                response_display = json.dumps(response_body, indent=2, ensure_ascii=False)
            else:
                response_display = str(response_body)
            
            response_details = f"""
================== XXL-Job Response Details ==================
Status       : {status_emoji}
Code         : {result.get('code', 'N/A')}
Message      : {result.get('msg', 'N/A')}
Response     : {response_display}
Duration     : {duration:.3f}s
=============================================================
"""
            logger.info(response_details)
            
            # 根据 XXL-Job 的返回判断成功或失败
            if result.get("success"):
                return ResponseBuilder.success(
                    processor_type="xxl_job",
                    body=result,
                    message="XXL-Job 任务触发成功",
                    status_code=200,
                    metadata={
                        "executor_handler": executor_handler,
                        "xx_job_url": base_url
                    },
                    duration=duration
                ).to_dict()
            else:
                return ResponseBuilder.error(
                    processor_type="xxl_job",
                    error=result.get("msg", "任务触发失败"),
                    error_code="JOB_TRIGGER_FAILED",
                    status_code=result.get("code", 500),
                    duration=duration,
                    body=result
                ).to_dict()
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"[XxlJobProcessor] XXL-Job 操作失败: {str(e)}")
            return ResponseBuilder.error(
                processor_type="xxl_job",
                error=f"XXL-Job 操作失败: {str(e)}",
                error_code="XXL_JOB_ERROR",
                status_code=500,
                duration=duration
            ).to_dict()
        
        finally:
           # 关闭客户端
           xxl_job_client.close()
           pass

    @classmethod
    def _create_xxl_job_client(cls, url: str) -> XxlJobClient:
        """
        创建 XXL-Job 客户端
        
        Args:
            url: XXL-Job 管理平台 URL 目前使用spotter api 网关地址
            
        Returns:
            XxlJobClient 实例
        """
        return XxlJobClient(base_url=url)

    def get_processor_type(self) -> str:
        """获取处理器类型"""
        return self.processor_type
    
    def get_processor_name(self) -> str:
        """获取处理器名称"""
        return self.processor_name
    
    def get_processor_description(self) -> str:
        """获取处理器描述"""
        return self.processor_description
    
    def get_required_config_keys(self) -> list:
        """获取必需的配置键"""
        return ['executor_handler']
    
    def get_optional_config_keys(self) -> list:
        """获取可选的配置键"""
        return [
            'executor_param',      # 任务执行参数（JSON 字符串）
            'site_tenant',         # 站点租户（默认: DEFAULT）
            'address_list',        # 执行器地址列表
            'xxjob_url',          # XXL-Job URL（可选，优先从上下文变量获取）
            'output_variable'      # 输出变量名（默认: xxljob_result）
            # 注意：username, password, app_code 已移除，在代码中写死
            # 注意：db_name 已废弃，不再使用
        ]

