import json
import re
import time
from typing import Dict, Any, Tuple, Optional

import httpx

from src.engine.context import ExecutionContext
from src.engine.core.processors import BaseProcessor
from src.engine.core.simple_logger import logger
from src.engine.clients.http_client import HttpClient, HttpRequestConfig
from src.engine.core.elegant_processor_registry import register_processor, ProcessorCategory
from src.engine.core.processors import render_recursive
from src.engine.models.response import ResponseBuilder


# 执行时若全局变量存在以下 key，会自动写入请求头（覆盖节点内同名 header）
HEADER_KEYS_FROM_VARIABLES = (
    "x-tag-header",
    "x-site-tenant",
    "x-tenant-id",
    "x-app",
)


@register_processor(
    processor_type="http_request",
    category=ProcessorCategory.API,
    description="HTTP请求处理器，支持GET、POST、PUT、DELETE等操作",
    tags={"http", "api", "network", "request"},
    enabled=True,
    priority=100,
    version="1.0.0",
    author="Aegis Team"
)
class HttpProcessor(BaseProcessor):
    def __init__(self, workflow_auth_config: dict = None):
        """
        初始化HTTP处理器
        
        Args:
            workflow_auth_config: 工作流级别的鉴权配置
        """
        super().__init__()
        self.workflow_auth_config = workflow_auth_config or {}
    
    def _get_config_schema_name(self) -> str:
        """获取配置模式名称"""
        return "http_request"
    
    def _validate_specific_config(self, config: Dict[str, Any]) -> bool:
        """HTTP特定的配置验证"""
        # 检查URL是否包含变量模板
        url = config.get("url", "")
        if "${" in url and "}" in url:
            # URL包含变量模板，这是允许的
            pass
        elif not url.startswith(("http://", "https://")):
            logger.error(f"[HttpProcessor] URL格式不正确: {url}")
            return False
        
        # 检查headers是否为字典类型
        headers = config.get("headers", {})
        if not isinstance(headers, dict):
            logger.error(f"[HttpProcessor] headers必须是字典类型")
            return False
        
        return True
    
    def execute(self, node_info: dict, context: ExecutionContext, predecessor_results: dict) -> dict:
        start_time = time.time()
        
        # 优先使用强类型 HttpConfig
        config_obj = self.get_typed_config(node_info)
        config = None
        if config_obj:
            config = config_obj
        else:
            config = node_info.get("data", {}).get("config", {})
        
        # 全量递归渲染
        config = render_recursive(config, context)
        
        # 1. 处理URL和路径参数
        url = getattr(config, 'url', "") if hasattr(config, 'url') else config.get('url', "")
        url = context.render_string(url)
        
        # 处理路径参数 {userId} -> 123
        path_params = getattr(config, 'path_params', None) if hasattr(config, 'path_params') else config.get('path_params')
        if path_params:
            for key, value in path_params.items():
                rendered_value = context.render_string(str(value))
                url = url.replace(f"{{{key}}}", rendered_value)
        
        # 2. 处理查询参数 (params)
        params = getattr(config, 'params', None) if hasattr(config, 'params') else config.get('params')
        if params:
            params = {k: context.render_string(str(v)) for k, v in params.items()}
        
        # 3. 获取请求方法
        method = (getattr(config, 'method', "GET") if hasattr(config, 'method') else config.get('method', "GET")).upper()
        
        # 4. 渲染请求头
        headers = getattr(config, 'headers', None) if hasattr(config, 'headers') else config.get('headers', None)
        if headers is None:
            headers = {}
        headers = {k: context.render_string(v) for k, v in headers.items()}
        # 若全局变量中存在指定 key，则写入请求头（覆盖节点内同名 header）
        if hasattr(context, 'get_variable'):
            for hk in HEADER_KEYS_FROM_VARIABLES:
                val = context.get_variable(hk)
                if val is not None:
                    headers[hk] = str(val)
        
        # 5. 处理 Cookies
        cookies = getattr(config, 'cookies', None) if hasattr(config, 'cookies') else config.get('cookies')
        if cookies:
            cookies = {k: context.render_string(str(v)) for k, v in cookies.items()}
        
        # 6. 处理 Body 数据（支持多种类型）
        json_data = getattr(config, 'json', None) if hasattr(config, 'json') else config.get('json')
        form_data = getattr(config, 'data', None) if hasattr(config, 'data') else config.get('data')
        body_data = getattr(config, 'body', None) if hasattr(config, 'body') else config.get('body')
        files_data = getattr(config, 'files', None) if hasattr(config, 'files') else config.get('files')
        upload_data = getattr(config, 'upload', None) if hasattr(config, 'upload') else config.get('upload')
        
        # upload 是 files 的别名
        if upload_data and not files_data:
            files_data = upload_data
        # 兼容：后端可能下传 bodyType=form-data 且 body={ formKey: fileId }，按 upload 处理
        body_type = config.get("bodyType") or config.get("paramType") if isinstance(config, dict) else (getattr(config, "bodyType", None) or getattr(config, "paramType", None))
        if not files_data and body_type in ("upload", "form-data") and isinstance(body_data, dict) and body_data and all(isinstance(v, str) for v in body_data.values()):
            files_data = body_data

        # 渲染各种数据类型
        rendered_json = None
        rendered_data = None
        rendered_body = None
        rendered_files = None
        
        if json_data:
            # JSON 数据
            if isinstance(json_data, dict):
                rendered_json = {}
                for key, value in json_data.items():
                    if isinstance(value, str):
                        rendered_json[key] = context.render_string(value)
                    else:
                        rendered_json[key] = value
            else:
                rendered_json = json_data
        
        if form_data:
            # 表单数据
            if isinstance(form_data, dict):
                rendered_data = {}
                for key, value in form_data.items():
                    if isinstance(value, str):
                        rendered_data[key] = context.render_string(value)
                    else:
                        rendered_data[key] = value
            else:
                rendered_data = form_data
        
        if body_data:
            # 原始 body 数据：支持 str / dict / list（JSON 数组）
            if isinstance(body_data, str):
                rendered_body = context.render_string(body_data)
            elif isinstance(body_data, dict):
                # 兼容旧版本：如果 body 是 dict，当作 json 处理
                if not rendered_json:
                    rendered_json = {}
                    for key, value in body_data.items():
                        if isinstance(value, str):
                            rendered_json[key] = context.render_string(value)
                        else:
                            rendered_json[key] = value
            elif isinstance(body_data, list):
                # body 为 list（JSON 数组）时按 JSON 发送，避免 data= 传入 list 导致 httpx 报错
                if not rendered_json:
                    rendered_json = body_data
            else:
                rendered_body = body_data
        
        if files_data:
            # 文件数据：form_key -> fileId（字符串），需渲染后按 fileId 从平台下载再上传
            rendered_files = {}
            for k, v in (files_data if isinstance(files_data, dict) else {}).items():
                rendered_files[k] = context.render_string(str(v)) if hasattr(context, 'render_string') else str(v)
        else:
            rendered_files = None

        # 7. 获取高级配置
        timeout = getattr(config, 'timeout', 120) if hasattr(config, 'timeout') else config.get('timeout', 120)
        verify_ssl = getattr(config, 'verify_ssl', True) if hasattr(config, 'verify_ssl') else config.get('verify_ssl', True)
        verify = getattr(config, 'verify', None) if hasattr(config, 'verify') else config.get('verify')
        if verify is not None:
            verify_ssl = verify
        allow_redirects = getattr(config, 'allow_redirects', True) if hasattr(config, 'allow_redirects') else config.get('allow_redirects', True)
        
        # 记录详细的HTTP请求信息
        # 构建请求详情字符串
        request_details_lines = [
            "================== HTTP Request Details ==================",
            f"Method      : {method}",
            f"URL         : {url}",
        ]
        
        # 查询参数
        if params:
            request_details_lines.append("Params      :")
            params_json = json.dumps(params, indent=4, ensure_ascii=False)
            request_details_lines.extend(["  " + line for line in params_json.split("\n")])
        else:
            request_details_lines.append("Params      : None")
        
        # 请求头
        request_details_lines.append("Headers     :")
        headers_json = json.dumps(headers, indent=4, ensure_ascii=False)
        request_details_lines.extend(["  " + line for line in headers_json.split("\n")])
        
        # Cookies
        if cookies:
            request_details_lines.append("Cookies     :")
            cookies_json = json.dumps(cookies, indent=4, ensure_ascii=False)
            request_details_lines.extend(["  " + line for line in cookies_json.split("\n")])
        else:
            request_details_lines.append("Cookies     : None")
        
        # Body 数据
        if rendered_json:
            request_details_lines.append("Body (JSON) :")
            body_json = json.dumps(rendered_json, indent=4, ensure_ascii=False)
            request_details_lines.extend(["  " + line for line in body_json.split("\n")])
        elif rendered_data:
            # 表单字段
            request_details_lines.append("Body (FORM):")
            form_json = json.dumps(rendered_data, indent=4, ensure_ascii=False)
            request_details_lines.extend(["  " + line for line in form_json.split("\n")])
            # 如果同时存在文件，额外打印文件字段，避免误以为没有上传文件
            if rendered_files:
                request_details_lines.append(f"Body (FILES): {list(rendered_files.keys())}")
        elif rendered_body:
            # 不做截断，完整显示 body
            body_preview = str(rendered_body)
            request_details_lines.append(f"Body (RAW)  : {body_preview}")
        elif rendered_files:
            request_details_lines.append(f"Body (FILES): {list(rendered_files.keys())}")
        else:
            request_details_lines.append("Body        : None")
        
        # 其他配置
        request_details_lines.extend([
            f"Timeout     : {timeout}s",
            f"Verify SSL  : {verify_ssl}",
        ])
        
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
        
        request_details_lines.append("========================================================")
        request_details = "\n".join(request_details_lines)
        logger.info(request_details)
        
        # 获取鉴权配置（多层级优先级）
        auth_config = self._get_auth_config(config if isinstance(config, dict) else config.__dict__, context)
        credential_id = (getattr(config, 'credential_id', None) or getattr(config, 'credential', None)) if hasattr(config, 'credential_id') else (config.get('credential_id') or config.get('credential'))
        
        # 创建HTTP客户端（支持鉴权）
        http_client = HttpClient(
            base_url="",
            timeout=timeout,
            auth_config=auth_config,
            credential_id=credential_id
        )
        
        # 记录鉴权信息（脱敏）
        if credential_id:
            logger.info(f"[HTTP] 🔐 使用凭证鉴权: {credential_id}")
        elif auth_config:
            auth_type = auth_config.get("type", "unknown")
            logger.info(f"[HTTP] 🔐 使用{auth_type}鉴权")

        # 若有 upload/files：按 fileId 从平台下载，得到 form_key -> (bytes, filename)
        resolved_files = None
        if rendered_files:
            resolved_files = {}
            for form_key, file_id in rendered_files.items():
                if not form_key or not str(file_id).strip():
                    continue
                content, filename = self._download_file_by_id(context, str(file_id).strip(), timeout=timeout)
                resolved_files[form_key] = (content, filename or "file")

        # 构建 HttpRequestConfig 对象，聚合所有请求参数
        request_config = HttpRequestConfig(
            method=method,
            url=url,
            headers=headers,
            params=params,
            cookies=cookies,
            json=None if resolved_files else rendered_json,
            data=rendered_body if rendered_body is not None else rendered_data,
            timeout=timeout,
            files=resolved_files,
        )
        
        # 构建请求元数据字典（用于记录和调试）
        request_metadata = {
            "method": request_config.method,
            "url": request_config.url,
            "headers": request_config.headers,
        }
        
        # 添加可选字段
        if request_config.params:
            request_metadata["params"] = request_config.params
        if request_config.cookies:
            request_metadata["cookies"] = request_config.cookies
        if request_config.json is not None:
            request_metadata["json"] = request_config.json
        elif request_config.data is not None:
            request_metadata["data"] = request_config.data
        if request_config.timeout:
            request_metadata["timeout"] = request_config.timeout
        if request_config.files:
            request_metadata["files"] = list(request_config.files.keys())

        try:
            response = http_client.execute_request(request_config)

        except Exception as e:
            logger.error(f"HTTP请求失败: {str(e)}")
            raise
        
        # 获取响应体
        try:
            response_body = response.json()
        except (ValueError, json.JSONDecodeError):
            response_body = response.text()
        
        # 记录详细的HTTP响应信息
        status_emoji = "✅ 200" if response.status_code == 200 else f"❌ {response.status_code}" if response.status_code >= 400 else f"⚠️ {response.status_code}"
        
        # 检查是否有URL重定向
        response_url_info = ""
        if hasattr(response, 'url') and response.url and response.url != url:
            response_url_info = f"实际URL  : {response.url}\n"
        
        # 检查Content-Type
        content_type = response.headers.get('content-type', '').lower()
        content_type_warning = ""
        if 'application/json' not in content_type and response.status_code == 200:
            content_type_warning = f"⚠️  警告: 期望JSON响应，但收到 {content_type}，可能返回了HTML页面\n"
        
        # 格式化 body 显示，不做截断
        if isinstance(response_body, dict):
            body_display = json.dumps(response_body, indent=4, ensure_ascii=False)
        else:
            body_display = str(response_body)
        
        response_details = f"""
================== HTTP Response Details ==================
status_code : {status_emoji}
{response_url_info}{content_type_warning}headers     : {json.dumps(response.headers, indent=4, ensure_ascii=False)}
body        : {body_display}
duration    : {response.response_time:.3f}s
=========================HTTP Response Status code {response.status_code}================================
"""
        logger.info(response_details)
        
        # 使用标准响应格式，包含请求元数据
        # 注意：已移除 variables 参数，避免每个节点都携带所有变量导致内存溢出
        duration = time.time() - start_time
        return ResponseBuilder.from_http_response(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response_body,
            duration=duration,
            request=request_metadata
        ).to_dict()

    def _download_file_by_id(self, context: ExecutionContext, file_id: str, timeout: int = 60) -> Tuple[bytes, Optional[str]]:
        """
        根据 fileId 从平台下载接口拉取文件，供 multipart 上传使用。
        依赖 context 变量：PLATFORM_BASE_URL（必填），PLATFORM_FILE_DOWNLOAD_TOKEN（可选，Bearer 鉴权）。
        """
        base_url = None
        if hasattr(context, 'get_variable'):
            base_url = context.get_variable('PLATFORM_BASE_URL')
        if not base_url or not str(base_url).strip():
            base_url = "http://aegis-ones-web.spotter.ink"
        url = str(base_url).rstrip('/') + '/metadata/definition/file/download/' + str(file_id).strip()
        headers = {}
        if hasattr(context, 'get_variable'):
            token = context.get_variable('PLATFORM_FILE_DOWNLOAD_TOKEN')
            if token:
                headers['Authorization'] = f'Bearer {token}'
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url, headers=headers or None)
                resp.raise_for_status()
                content = resp.content
                filename = None
                cd = resp.headers.get('content-disposition') or resp.headers.get('Content-Disposition')
                if cd and 'filename=' in cd:
                    m = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^";\n]+)', cd, re.I)
                    if not m:
                        m = re.search(r'filename=([^;\n]+)', cd, re.I)
                    if m:
                        filename = m.group(1).strip().strip('"\'')
                return (content, filename)
        except httpx.HTTPStatusError as e:
            logger.error(f"[HTTP] 平台文件下载失败 fileId={file_id} status={e.response.status_code}")
            raise RuntimeError(f"平台文件下载失败 (fileId={file_id}): HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"[HTTP] 平台文件下载请求异常 fileId={file_id}: {e}")
            raise RuntimeError(f"平台文件下载请求失败 (fileId={file_id}): {e}") from e
    
    def _get_auth_config(self, node_config: dict, context: ExecutionContext) -> dict:
        """
        获取鉴权配置（多层级优先级）
        
        优先级（从高到低）：
        1. 节点级别的auth配置
        2. 工作流级别的auth配置  
        3. 环境变量中的auth配置
        
        Args:
            node_config: 节点配置
            context: 执行上下文
            
        Returns:
            dict: 鉴权配置
        """
        # 优先级1: 节点级别的auth
        node_auth = node_config.get("auth") or node_config.get("auth_config")
        if node_auth:
            logger.info("[HTTP] 🔐 使用节点级别鉴权配置")
            # 处理变量替换
            if isinstance(node_auth, dict):
                processed_auth = {}
                for key, value in node_auth.items():
                    if isinstance(value, str):
                        processed_auth[key] = context.render_string(value)
                    elif isinstance(value, dict):
                        processed_auth[key] = {
                            k: context.render_string(v) if isinstance(v, str) else v
                            for k, v in value.items()
                        }
                    else:
                        processed_auth[key] = value
                return processed_auth
            return node_auth
        
        # 优先级2: 工作流级别的auth
        if self.workflow_auth_config:
            logger.info("[HTTP] 🔐 使用工作流级别鉴权配置")
            # 处理变量替换
            processed_auth = {}
            for key, value in self.workflow_auth_config.items():
                if isinstance(value, str):
                    processed_auth[key] = context.render_string(value)
                else:
                    processed_auth[key] = value
            return processed_auth
        
        # 优先级3: 环境变量（从context中获取）
        env_auth_type = context.get_variables.get("DEFAULT_AUTH_TYPE")
        env_auth_token = context.get_variables.get("DEFAULT_AUTH_TOKEN")
        
        if env_auth_type and env_auth_token:
            logger.info("[HTTP] 🔐 使用环境变量鉴权配置")
            return {
                "type": env_auth_type,
                "token": env_auth_token
            }
        
        # 无鉴权配置
        return {}





