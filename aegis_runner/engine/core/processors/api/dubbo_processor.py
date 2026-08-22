# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-15
@packageName src.core.processors.api
@className DubboProcessor
@describe Dubbo RPC 服务调用处理器
"""

import requests
import os
import time
from typing import Dict, Any, List, Optional
from aegis_runner.engine.core.interfaces.processor_interface import ProcessorInterface
from aegis_runner.engine.core.processors import BaseProcessor
from aegis_runner.engine.core.simple_logger import logger
from aegis_runner.engine.core.exceptions import ValidationError, ExecutionError, ErrorCategory
from aegis_runner.engine.core.elegant_processor_registry import register_processor, ProcessorCategory
from aegis_runner.engine.clients.dubbo_client import DubboClient
from aegis_runner.engine.core.processors import render_recursive
from aegis_runner.engine.models.response import ResponseBuilder


@register_processor(
    processor_type="dubbo",
    category=ProcessorCategory.API,
    description="Dubbo RPC调用处理器，支持远程服务调用",
    tags={"dubbo", "rpc", "api", "service"},
    enabled=True,
    priority=60,
    dependencies=["requests"],
    version="1.0.0",
    author="Aegis Team"
)
class DubboProcessor(BaseProcessor):
    """
    Dubbo RPC 服务调用处理器
    
    功能：
    - 支持 Dubbo RPC 服务调用
    - 支持同步和异步调用
    - 支持参数类型验证
    - 支持超时设置
    - 支持结果验证
    """
    
    def __init__(self,  workflow_auth_config: dict = None):
        """初始化处理器"""
        super().__init__()
        self.workflow_auth_config = workflow_auth_config or {}

    
    def _get_value(self, config, key, default=None):
        if hasattr(config, key):
            return getattr(config, key)
        if isinstance(config, dict):
            return config.get(key, default)
        return default

    def validate_config(self, config: Any) -> bool:
        """
        验证配置
        必需配置： url/application_name/interface_name/method_name
        """
        required_fields = ['url','application_name', 'interface_name', 'method_name','params','site_tenant','param_types']
        for field in required_fields:
            v = self._get_value(config, field)
            if v is None:
                logger.warning(f"[DubboProcessor] 缺少建议配置: {field}")
        url = self._get_value(config, 'url')
        if url is not None and not isinstance(url, str):
            logger.warning("[DubboProcessor] url 建议为字符串类型")
        if url and not url.startswith(('http://', 'https://')):
            logger.warning("[DubboProcessor] url 建议为有效的 HTTP/HTTPS 地址")
        param_types = self._get_value(config, 'param_types', [])
        params = self._get_value(config, 'params', [])
        if isinstance(param_types, list) and isinstance(params, list):
            if len(param_types) != len(params):
                logger.warning(f"[DubboProcessor] param_types 与 params 数量不匹配: {len(param_types)} vs {len(params)}")
        return True
    
    def execute(self, node_info: dict, context: Any, predecessor_results: dict) -> Any:
        start_time = time.time()
        logger.info("[DubboProcessor] 开始执行 Dubbo RPC 调用")
        
        config = node_info.get("data", {}).get("config") if isinstance(node_info, dict) and "data" in node_info else node_info
        if not config:
            raise ValueError("Dubbo节点配置不能为空！")
        try:
            self.validate_config(config)
        except Exception as _:
            pass
        config = render_recursive(config, context)
        
        # 记录详细的 Dubbo 请求信息
        import json
        application_name = self._get_value(config, 'application_name', 'N/A')
        interface_name = self._get_value(config, 'interface_name', 'N/A')
        method_name = self._get_value(config, 'method_name', 'N/A')
        params = self._get_value(config, 'params', [])
        param_types = self._get_value(config, 'param_types', [])
        site_tenant = self._get_value(config, 'site_tenant', 'N/A')
        dubbo_tag = self._get_value(config, 'dubbo_tag', 'N/A')
        
        request_details_lines = [
            "================== Dubbo Request Details ==================",
            f"Application  : {application_name}",
            f"Interface    : {interface_name}",
            f"Method       : {method_name}",
            f"Site Tenant  : {site_tenant}",
            f"Dubbo Tag    : {dubbo_tag}",
        ]
        
        if params:
            request_details_lines.append("Params       :")
            params_json = json.dumps(params, indent=2, ensure_ascii=False)
            request_details_lines.extend(["  " + line for line in params_json.split("\n")])
        else:
            request_details_lines.append("Params       : None")
        
        if param_types:
            request_details_lines.append("Param Types  :")
            types_json = json.dumps(param_types, indent=2, ensure_ascii=False)
            request_details_lines.extend(["  " + line for line in types_json.split("\n")])
        else:
            request_details_lines.append("Param Types  : None")
        
        request_details_lines.append(f"Node ID      : {node_info.get('id', 'N/A')}")
        
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
        
        try:
            result = self._invoke_dubbo_service(config)
            duration = time.time() - start_time
            
            # 记录详细的 Dubbo 响应信息
            response_body = result.get("body", result)
            status_emoji = "✅ 成功"
            
            # 格式化响应用于显示，不做截断
            if isinstance(response_body, dict):
                response_display = json.dumps(response_body, indent=2, ensure_ascii=False)
            else:
                response_display = str(response_body)
            
            response_details = f"""
================== Dubbo Response Details ==================
Status       : {status_emoji}
Response     : {response_display}
Duration     : {duration:.3f}s
=============================================================
"""
            logger.info(response_details)
            
            # 使用标准响应格式
            return ResponseBuilder.success(
                processor_type="dubbo",
                body=result.get("body", result),
                message="Dubbo RPC 调用成功",
                status_code=200,
                metadata={
                    "application_name": self._get_value(config, 'application_name'),
                    "interface_name": self._get_value(config, 'interface_name'),
                    "method_name": self._get_value(config, 'method_name'),
                    "params": self._get_value(config, 'params'),
                    "param_types":self._get_value(config,'param_types'),
                    "site_tenant": self._get_value(config,'site_tenant'),
                    "dubbo_tag": self._get_value(config, 'dubbo_tag')
                },
                duration=duration
                # 注意：已移除 variables 参数，避免每个节点都携带所有变量导致内存溢出
            ).to_dict()
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"[DubboProcessor] Dubbo RPC 调用失败: {e}")
            return ResponseBuilder.error(
                processor_type="dubbo",
                error=f"Dubbo RPC 调用失败: {str(e)}",
                error_code="DUBBO_RPC_ERROR",
                status_code=500,
                duration=duration
                # 注意：已移除 variables 参数，避免每个节点都携带所有变量导致内存溢出
            ).to_dict()
    
    def _invoke_dubbo_service(self, config: Dict[str, Any]) -> Any:
        """
        调用 Dubbo RPC 服务，参数兼容链式与直接入参
        """
        url = self._get_value(config, 'url')
        application_name = self._get_value(config, 'application_name')
        interface_name = self._get_value(config, 'interface_name')
        method_name = self._get_value(config, 'method_name')
        param_types = self._get_value(config, 'param_types', [])
        params = self._get_value(config, 'params', [])
        site_tenant = self._get_value(config, 'site_tenant')
        dubbo_tag = self._get_value(config, 'dubbo_tag')
        headers = self._get_value(config, 'headers', {})
        timeout = self._get_value(config, 'timeout', 30)

        try:
            return (DubboClient(url=url, timeout=timeout).set_application_name(application_name)
                      .set_interface_name(interface_name)
                      .set_method_name(method_name)
                      .set_param_types(param_types)
                      .set_params(params)
                      .set_site_tenant(site_tenant)
                      .set_dubbo_tag(dubbo_tag)
                      ).invoke()

        except Exception as e:
            raise Exception(f"DubboClient调用异常: {str(e)}")
    
    # ========== 元数据方法 ==========
    
    def get_processor_type(self) -> str:
        """获取处理器类型"""
        return "dubbo"
    
    def get_processor_name(self) -> str:
        """获取处理器名称"""
        return "DubboProcessor"
    
    def get_processor_description(self) -> str:
        """获取处理器描述"""
        return "Dubbo RPC 服务调用处理器"
    
    def get_required_config_keys(self) -> list:
        """获取必需的配置键"""
        return ['application_name', 'interface_name', 'method_name']
    
    def get_optional_config_keys(self) -> list:
        """获取可选的配置键"""
        return ['url', 'param_types', 'params', 'site_tenant', 'dubbo_tag', 'timeout', 'headers', 'output_variable']

