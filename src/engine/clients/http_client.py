# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-10-13
@packageName
@className HttpClient
@describe HTTP客户端 - 独立的HTTP请求能力
"""
from enum import Enum

from typing import Dict, Any, Optional, Union, List, Callable

import io
import json
import time
import uuid
from typing import Union, Text
import httpx
from httpx import Request, Response, RequestError, HTTPError
from pydantic import BaseModel, Field, HttpUrl
from dataclasses import dataclass
from src.engine.core.simple_logger import logger

Name = Text
Url = Text
BaseUrl = Union[HttpUrl, Text]
VariablesMapping = Dict[Text, Any]
FunctionsMapping = Dict[Text, Callable]
Headers = Dict[Text, Text]
Cookies = Dict[Text, Text]

class MethodEnum(Text, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    PATCH = "PATCH"

class AddressData(BaseModel):
    client_ip: Text = "N/A"
    client_port: int = 0
    server_ip: Text = "N/A"
    server_port: int = 0


class ResponseData(BaseModel):
    status_code: int
    headers: Dict
    cookies: Cookies
    encoding: Union[Text, None] = None
    content_type: Text
    body: Union[Text, bytes, List, Dict, None]

class RequestData(BaseModel):
    method: MethodEnum = MethodEnum.GET
    url: Url
    headers: Headers = {}
    cookies: Cookies = {}
    body: Union[Text, bytes, List, Dict, None] = {}

class ReqRespData(BaseModel):
    request: RequestData
    response: ResponseData

class RequestStat(BaseModel):
    content_size: float = 0
    response_time_ms: float = 0
    elapsed_ms: float = 0

class SessionData(BaseModel):
    """request session data, including request, response, validators and stat data"""

    success: bool = False
    # in most cases, req_resp only contains one request & response
    # while when 30X redirect occurs, req_resp will contain multiple request & response
    req_resp: List[Union[ReqRespData]] = []
    stat: RequestStat = RequestStat()
    address: AddressData = AddressData()
    validators: Dict = {}


@dataclass
class HttpRequestConfig:
    """
    面向 Processor/业务层的 HTTP 请求配置对象。
    由强类型节点配置渲染后构造，用于调用 HttpClient。
    files: form_key -> (content_bytes, optional_filename)，用于 multipart/form-data 文件上传
    """
    method: str
    url: str
    headers: Dict[str, str]
    params: Optional[Dict[str, Any]] = None
    data: Any = None
    json: Any = None
    cookies: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = None
    # multipart 文件: form_key -> (bytes, optional_filename)
    files: Optional[Dict[str, tuple]] = None

class Http:
    REQUEST = "request"
    RESPONSE = 'response'
    GETSOCKNAME = 'getsockname'
    TIMEOUT = 'timeout'
    STREAM = 'stream'
    CONTENT_LENGTH = "content-length"

def _build_multipart_body(files: Dict[str, tuple], extra_form: Any = None) -> tuple:
    """构建 multipart/form-data 请求体为 bytes，返回 (body_bytes, content_type)。"""
    boundary = "----formboundary" + uuid.uuid4().hex[:16]
    boundary_b = boundary.encode("ascii")
    crlf = b"\r\n"
    parts = []
    for form_key, content_and_name in files.items():
        if isinstance(content_and_name, (list, tuple)) and len(content_and_name) >= 2:
            content_bytes, filename = content_and_name[0], content_and_name[1]
        else:
            content_bytes, filename = content_and_name, "file"
        if hasattr(content_bytes, "read"):
            content_bytes = content_bytes.read()
        if not isinstance(content_bytes, bytes):
            content_bytes = b""
        filename_str = filename.decode("utf-8") if isinstance(filename, bytes) else (filename or "file")
        disp = f'form-data; name="{form_key}"; filename="{filename_str}"'.encode("utf-8")
        parts.append(b"--" + boundary_b + crlf)
        parts.append(b"Content-Disposition: " + disp + crlf)
        parts.append(b"Content-Type: application/octet-stream" + crlf)
        parts.append(crlf)
        parts.append(content_bytes + crlf)
    if extra_form and isinstance(extra_form, dict):
        for k, v in extra_form.items():
            val = str(v).encode("utf-8") if not isinstance(v, bytes) else v
            parts.append(b"--" + boundary_b + crlf)
            parts.append(f'Content-Disposition: form-data; name="{k}"'.encode("utf-8") + crlf)
            parts.append(crlf)
            parts.append(val + crlf)
    parts.append(b"--" + boundary_b + b"--" + crlf)
    body_bytes = b"".join(parts)
    content_type = f"multipart/form-data; boundary={boundary}"
    return body_bytes, content_type


def lower_dict_keys(origin_dict):
    """convert keys in dict to lower case

    Args:
        origin_dict (dict): mapping data structure

    Returns:
        dict: mapping with all keys lowered.

    Examples:
        >>> origin_dict = {
            "Name": "",
            "Request": "",
            "URL": "",
            "METHOD": "",
            "Headers": "",
            "Data": ""
        }
        >>> lower_dict_keys(origin_dict)
            {
                "name": "",
                "request": "",
                "url": "",
                "method": "",
                "headers": "",
                "data": ""
            }

    """
    if not origin_dict or not isinstance(origin_dict, dict):
        return origin_dict

    return {key.lower(): value for key, value in origin_dict.items()}


def omit_long_data(body, omit_len=512):
    """omit too long str/bytes"""
    if not isinstance(body, (str, bytes)):
        return body

    body_len = len(body)
    if body_len <= omit_len:
        return body

    omitted_body = body[0:omit_len]

    appendix_str = f" ... OMITTED {body_len - omit_len} CHARACTORS ..."
    if isinstance(body, bytes):
        appendix_str = appendix_str.encode("utf-8")

    return omitted_body + appendix_str




class ApiResponse(Response):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error = None
    
    def raise_for_status(self):
        if hasattr(self, "error") and self.error:
            raise self.error
        try:
            super(ApiResponse, self).raise_for_status()
        except HTTPError as e:
            raise e


def get_req_resp_record(resp_obj: Response) -> ReqRespData:
    """Get request and response info from Response() object."""
    request_headers = dict(resp_obj.request.headers)
    request_cookies = dict(resp_obj.cookies) if hasattr(resp_obj, 'cookies') else {}

    request_body = resp_obj.request.content
    if request_body is not None:
        try:
            if isinstance(request_body, bytes):
                request_body = request_body.decode('utf-8')
            request_body = json.loads(request_body)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            request_body = "OMITTED"

    request_data = RequestData(
        method=resp_obj.request.method,
        url=str(resp_obj.request.url),
        headers=request_headers,
        cookies=request_cookies,
        body=request_body,
    )


    resp_headers = dict(resp_obj.headers)
    content_type = lower_dict_keys(resp_headers).get("content-type", "")

    if "image" in content_type:
        response_body = resp_obj.content
    else:
        try:
            response_body = resp_obj.json()
        except (ValueError, json.JSONDecodeError):
            response_body = omit_long_data(resp_obj.text)

    response_data = ResponseData(
        status_code=resp_obj.status_code,
        cookies=dict(resp_obj.cookies) if hasattr(resp_obj, 'cookies') else {},
        encoding=resp_obj.encoding,
        headers=resp_headers,
        content_type=content_type,
        body=response_body,
    )


    return ReqRespData(request=request_data, response=response_data)


def _get_socket_info(response, method_name):
    """Get client or server IP and port."""
    try:
        # httpx doesn't expose socket info in the same way as requests
        # Return default values for now
        return ('0.0.0.0', 0)
    except Exception as e:
        logger.error(f"Error getting socket info: {e}")
        return ('0.0.0.0', 0)


class HttpSession:
    """Class for performing HTTP requests and holding session cookies using httpx."""

    def __init__(self):
        self.data = SessionData()
        self.client = httpx.Client()

    def update_last_req_resp_record(self, resp_obj):
        """Update request and response info from Response() object."""
        self.data.req_resp.append(get_req_resp_record(resp_obj))

    def request(self, method, url, **kwargs):
        """Constructs and sends a :py:class:`httpx.Request`."""
        kwargs.setdefault('timeout', 120)
        kwargs.setdefault('follow_redirects', True)

        start_time = time.time()
        response = self._send_request_safe_mode(method, url, **kwargs)
        response_time_ms = round((time.time() - start_time) * 1000, 2)

        client_ip, client_port = _get_socket_info(response, Http.GETSOCKNAME)
        server_ip, server_port = _get_socket_info(response, Http.GETSOCKNAME)

        self.data.address.client_ip = client_ip
        self.data.address.client_port = client_port
        self.data.address.server_ip = server_ip
        self.data.address.server_port = server_port

        content_size = int(response.headers.get(Http.CONTENT_LENGTH, 0))
        self.data.stat.response_time_ms = response_time_ms
        self.data.stat.elapsed_ms = response_time_ms  # httpx doesn't have elapsed attribute
        self.data.stat.content_size = content_size

        # httpx doesn't have history in the same way, so we just use the current response
        self.data.req_resp = [get_req_resp_record(response)]

        response.raise_for_status()
        return response

    def _send_request_safe_mode(self, method: Union[Text], url: Union[Text], **kwargs):
        """Send a HTTP request and catch exceptions due to connection problems."""
        try:
            return self.client.request(method, url, **kwargs)
        except (RequestError, HTTPError) as ex:
            # 创建一个简单的错误响应
            class ErrorResponse:
                def __init__(self, error, method, url):
                    self.error = error
                    self.status_code = 0
                    self.request = Request(method, url)
                    self.headers = {}
                    self.cookies = {}
                    self.encoding = None
                    self.content = b""
                    self.text = ""
                
                def json(self):
                    return {"error": str(self.error)}
                
                def raise_for_status(self):
                    if self.error:
                        raise self.error
            
            return ErrorResponse(ex, method, url)
    
    def close(self):
        """Close the httpx client."""
        if hasattr(self, 'client'):
            self.client.close()


class HTTPResponse:
    """HTTP响应包装类"""
    
    def __init__(self, status_code: int, headers: dict, body: any, 
                 response_time: float = 0.0, url: str = "", method: str = ""):
        self.status_code = status_code
        self.headers = headers
        self.body = body
        self.response_time = response_time
        self.url = url
        self.method = method
        self._json_data = None
    
    def json(self):
        """返回JSON格式的响应体"""
        if self._json_data is None:
            if isinstance(self.body, (dict, list)):
                self._json_data = self.body
            else:
                try:
                    import json
                    self._json_data = json.loads(self.body) if isinstance(self.body, str) else self.body
                except (json.JSONDecodeError, TypeError):
                    self._json_data = self.body
        return self._json_data
    
    def text(self):
        """返回文本格式的响应体"""
        if isinstance(self.body, str):
            return self.body
        elif isinstance(self.body, (dict, list)):
            import json
            return json.dumps(self.body, ensure_ascii=False)
        else:
            return str(self.body)
    
    def is_success(self):
        """判断请求是否成功"""
        return 200 <= self.status_code < 300


class HttpClient:
    """HTTP客户端类 - 提供简化的HTTP请求接口"""
    
    def __init__(self, base_url: str = "", timeout: int = 30, 
                 default_headers: dict = None, auth_type: str = None, 
                 auth_token: str = None, auth_config: dict = None,
                 credential_id: str = None):
        """
        初始化HTTP客户端
        
        Args:
            base_url: 基础URL
            timeout: 超时时间
            default_headers: 默认请求头
            auth_type: 鉴权类型（简单模式）
            auth_token: 鉴权Token（简单模式）
            auth_config: 完整鉴权配置（企业级模式）
            credential_id: 凭证ID（从凭证中心获取）
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.default_headers = default_headers or {}
        self.auth_type = auth_type
        self.auth_token = auth_token
        self.auth_config = auth_config or {}
        self.credential_id = credential_id
        self.session = HttpSession()
        
        # 设置默认请求头
        if self.default_headers:
            self.session.headers.update(self.default_headers)
        
        # 设置认证（按优先级）
        if credential_id:
            # 优先级1: 从凭证中心获取
            self._apply_credential_auth(credential_id)
        elif auth_config:
            # 优先级2: 使用完整的auth_config
            self._apply_auth_config(auth_config)
        elif auth_type and auth_token:
            # 优先级3: 使用简单的auth_type和auth_token
            self.set_auth(auth_type, token=auth_token)
    
    def _apply_credential_auth(self, credential_id: str):
        """
        从凭证中心获取并应用鉴权配置
        
        Args:
            credential_id: 凭证ID
        """
        try:
            from src.engine.core.credential_store import credential_store
            
            auth_headers = credential_store.get_auth_headers(credential_id, context=None)
            if auth_headers:
                self.session.client.headers.update(auth_headers)
                logger.info(f"[HttpClient] ✅ 已应用凭证鉴权: {credential_id}")
            else:
                logger.warning(f"[HttpClient] ⚠️ 凭证未找到或无效: {credential_id}")
        except Exception as e:
            logger.error(f"[HttpClient] ❌ 应用凭证失败: {str(e)}")
    
    def _apply_auth_config(self, auth_config: Dict[str, Any]):
        """
        应用完整的鉴权配置
        
        Args:
            auth_config: 鉴权配置字典
        """
        auth_type = auth_config.get("type", "").lower()
        
        if auth_type == "bearer":
            token = auth_config.get("token", "")
            self.session.client.headers['Authorization'] = f'Bearer {token}'
            logger.info("[HttpClient] ✅ 已应用Bearer Token鉴权")
        
        elif auth_type == "api_key":
            key_name = auth_config.get("key_name", "X-API-Key")
            key_value = auth_config.get("key_value", "")
            in_location = auth_config.get("in", "header")
            
            if in_location == "header":
                self.session.client.headers[key_name] = key_value
                logger.info(f"[HttpClient] ✅ 已应用API Key鉴权: {key_name}")
        
        elif auth_type == "basic":
            username = auth_config.get("username", "")
            password = auth_config.get("password", "")
            from httpx import BasicAuth
            self.session.client.auth = BasicAuth(username, password)
            logger.info("[HttpClient] ✅ 已应用Basic Auth鉴权")
        
        elif auth_type == "oauth2":
            access_token = auth_config.get("access_token", "")
            token_type = auth_config.get("token_type", "Bearer")
            self.session.client.headers['Authorization'] = f'{token_type} {access_token}'
            logger.info("[HttpClient] ✅ 已应用OAuth2鉴权")
        
        elif auth_type == "custom":
            headers = auth_config.get("headers", {})
            self.session.client.headers.update(headers)
            logger.info(f"[HttpClient] ✅ 已应用自定义Header鉴权: {len(headers)}个Header")
        
        else:
            logger.warning(f"[HttpClient] ⚠️ 不支持的鉴权类型: {auth_type}")
    
    def set_auth(self, auth_type: str, token: str = None, username: str = None, password: str = None):
        """设置认证信息（简单模式，向后兼容）"""
        self.auth_type = auth_type
        if auth_type.lower() == 'bearer' and token:
            self.session.client.headers['Authorization'] = f'Bearer {token}'
        elif auth_type.lower() == 'basic' and username and password:
            from httpx import BasicAuth
            self.session.client.auth = BasicAuth(username, password)
        elif auth_type.lower() == 'api_key' and token:
            self.session.client.headers['X-API-Key'] = token
    
    def _build_url(self, path: str) -> str:
        """构建完整的URL"""
        if path.startswith('http'):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"
    
    def _prepare_headers(self, headers: dict = None) -> dict:
        """准备请求头"""
        final_headers = self.default_headers.copy()
        if headers:
            final_headers.update(headers)
        return final_headers
    
    def _make_request(self, method: str, path: str, **kwargs) -> HTTPResponse:
        """发送HTTP请求"""
        url = self._build_url(path)
        
        # 准备请求参数
        request_kwargs = {
            'timeout': self.timeout,
            'follow_redirects': True
        }
        
        # 合并请求头
        if 'headers' in kwargs:
            kwargs['headers'] = self._prepare_headers(kwargs['headers'])
        else:
            kwargs['headers'] = self._prepare_headers()
        
        request_kwargs.update(kwargs)
        
        # 记录请求开始时间
        start_time = time.time()
        
        try:
            # 发送请求
            response = self.session.request(method, url, **request_kwargs)
            response_time = time.time() - start_time
            
            # 解析响应体
            try:
                if 'application/json' in response.headers.get('content-type', ''):
                    body = response.json()
                else:
                    body = response.text
            except (ValueError, json.JSONDecodeError):
                body = response.text
            
            # 创建响应对象
            http_response = HTTPResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=body,
                response_time=response_time,
                url=str(response.url),
                method=method
            )
            
            return http_response
            
        except Exception as e:
            # logger.error(f"HTTP请求失败: {str(e)}")
            # 返回错误响应
            return HTTPResponse(
                status_code=0,
                headers={},
                body={"error": str(e)},
                response_time=time.time() - start_time,
                url=url,
                method=method
            )

    def execute_request(self, request: HttpRequestConfig) -> HTTPResponse:
        """
        使用 HttpRequestConfig 对象执行 HTTP 请求。
        该方法面向 Processor 层，避免在业务代码中散落过多 kwargs 细节。
        当存在 files 时以 multipart/form-data 发送，不再使用 json。
        """
        kwargs: Dict[str, Any] = {
            "headers": request.headers,
        }

        if request.params is not None:
            kwargs["params"] = request.params
        if request.cookies is not None:
            kwargs["cookies"] = request.cookies
        if request.timeout is not None:
            kwargs["timeout"] = request.timeout

        if request.files:
            # 手动构建 multipart/form-data 为 bytes，用 data= 发送，避免 httpx files= 的流式请求触发 "streaming request content" 错误
            body_bytes, content_type = _build_multipart_body(request.files, request.data)
            kwargs["content"] = body_bytes
            if "headers" not in kwargs:
                kwargs["headers"] = request.headers
            kwargs["headers"] = dict(kwargs["headers"])
            kwargs["headers"]["Content-Type"] = content_type
        else:
            if request.json is not None:
                kwargs["json"] = request.json
            elif request.data is not None:
                kwargs["data"] = request.data

        return self._make_request(request.method.upper(), request.url, **kwargs)
    
    def get(self, path: str, params: dict = None, headers: dict = None, **kwargs) -> HTTPResponse:
        """发送GET请求"""
        if params:
            kwargs['params'] = params
        return self._make_request('GET', path, headers=headers, **kwargs)
    
    def post(self, path: str, json: dict = None, data: any = None, 
             headers: dict = None, **kwargs) -> HTTPResponse:
        """发送POST请求"""
        if json is not None:
            kwargs['json'] = json
        elif data is not None:
            kwargs['data'] = data
        return self._make_request('POST', path, headers=headers, **kwargs)
    
    def put(self, path: str, json: dict = None, data: any = None, 
            headers: dict = None, **kwargs) -> HTTPResponse:
        """发送PUT请求"""
        if json is not None:
            kwargs['json'] = json
        elif data is not None:
            kwargs['data'] = data
        return self._make_request('PUT', path, headers=headers, **kwargs)
    
    def delete(self, path: str, headers: dict = None, **kwargs) -> HTTPResponse:
        """发送DELETE请求"""
        return self._make_request('DELETE', path, headers=headers, **kwargs)
    
    def patch(self, path: str, json: dict = None, data: any = None, 
              headers: dict = None, **kwargs) -> HTTPResponse:
        """发送PATCH请求"""
        if json is not None:
            kwargs['json'] = json
        elif data is not None:
            kwargs['data'] = data
        return self._make_request('PATCH', path, headers=headers, **kwargs)
    
    def head(self, path: str, headers: dict = None, **kwargs) -> HTTPResponse:
        """发送HEAD请求"""
        return self._make_request('HEAD', path, headers=headers, **kwargs)
    
    def options(self, path: str, headers: dict = None, **kwargs) -> HTTPResponse:
        """发送OPTIONS请求"""
        return self._make_request('OPTIONS', path, headers=headers, **kwargs)


