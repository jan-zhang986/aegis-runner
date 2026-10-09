# -*- coding: utf-8 -*-
"""
Aegis 常用测试 Fixtures
提供环境配置注入、轻量 HTTP 客户端与证据记录辅助。
"""
import os
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

try:
    import pytest
except ImportError:
    pytest = None



class AegisHttpClient:
    """轻量 HTTP 测试客户端，具备自动步骤打屏与响应证据附加能力"""

    def __init__(self, base_url: str = "", default_headers: Optional[Dict[str, str]] = None):
        self.base_url = base_url.rstrip("/")
        self.default_headers = default_headers or {}

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
    ):
        url = f"{self.base_url}/{path.lstrip('/')}"
        if params:
            import urllib.parse
            query_str = urllib.parse.urlencode(params)
            url = f"{url}?{query_str}"

        req_headers = {**self.default_headers, **(headers or {})}
        body = None
        if json_data is not None:
            body = json.dumps(json_data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=body, headers=req_headers, method=method.upper())
        
        status_code = 0
        resp_data = None
        error_msg = None

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status_code = response.status
                raw = response.read().decode("utf-8")
                try:
                    resp_data = json.loads(raw)
                except Exception:
                    resp_data = raw
        except urllib.error.HTTPError as e:
            status_code = e.code
            raw = e.read().decode("utf-8")
            try:
                resp_data = json.loads(raw)
            except Exception:
                resp_data = raw
        except Exception as e:
            error_msg = str(e)

        # 动态将调用证据记录到当前测试步骤中
        try:
            import aegis as _aegis_mod
            _aegis_mod.aegis.attach_evidence("http_call", {
                "method": method.upper(),
                "url": url,
                "status_code": status_code,
                "error": error_msg,
            })
        except Exception:
            pass


        class ResponseWrapper:
            def __init__(self, status, data, err):
                self.status_code = status
                self._data = data
                self.error = err

            def json(self):
                if isinstance(self._data, dict):
                    return self._data
                raise ValueError(f"Response is not JSON: {self._data}")

            @property
            def text(self):
                return json.dumps(self._data) if isinstance(self._data, dict) else str(self._data)

        return ResponseWrapper(status_code, resp_data, error_msg)

    def get(self, path: str, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs):
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs):
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs):
        return self.request("DELETE", path, **kwargs)


if pytest:
    @pytest.fixture
    def aegis_api_client():
        """测试用例可直接注入的 HTTP 客户端 fixture"""
        base_url = os.getenv("AEGIS_TARGET_BASE_URL", "http://127.0.0.1:8080")
        return AegisHttpClient(base_url=base_url)
