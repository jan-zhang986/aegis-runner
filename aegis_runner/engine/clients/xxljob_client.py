# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-10-30
@packageName src.clients
@className XxlJobClient
@describe XXL-Job 客户端 XXL-Job 任务触发能力
"""

import json
from typing import Dict, Any, Optional
import requests

from aegis_runner.engine.core.simple_logger import logger


class XxlJobClient:
    """
    """
    
    def __init__(
        self,
        base_url: str,
        username: str = "jan.zhang@spotterio.com",
        password: str = "MTExMTEx",
        app_code: str = "developer",
        auto_login: bool = True
    ):
        """
        初始化 XXL-Job 客户端
        
        Args:
            base_url: API网关 URL
            username: 用户名
            password: 密码
            app_code: 应用代码
            auto_login: 是否自动登录
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.app_code = app_code
        
        self.cookies = None
        self.auth_token = None
        
        if auto_login:
            self.login()
    
    def login(self) -> bool:
        """
        登录 XXL-Job 管理平台
        
        Returns:
            是否登录成功
        """
        try:
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Connection': 'keep-alive',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            }
            
            # 支持不同的登录路径
            path = '/spotter-user-center/sso/login'  # spotter 平台
            payload = {
                "username": self.username,
                "password": self.password,
                "appCode": self.app_code
            }
            resp = requests.post(
                self.base_url + path,
                headers=headers,
                json=payload,
                timeout=10
            )

            if resp.status_code == 200:
                self.cookies = resp.cookies

                # 尝试从 cookie 中获取 token
                # 优先级：spotter_token_test > spotter_token_dev > XXL_JOB_LOGIN_IDENTITY
                if 'spotter_token_test' in self.cookies:
                    self.auth_token = self.cookies.get('spotter_token_test')
                elif 'spotter_token_dev' in self.cookies:
                    self.auth_token = self.cookies.get('spotter_token_dev')
                    print(self.auth_token)
                elif 'XXL_JOB_LOGIN_IDENTITY' in self.cookies:
                    self.auth_token = self.cookies.get('XXL_JOB_LOGIN_IDENTITY')

                # 如果从 cookie 中获取不到，尝试从响应头或响应体中获取
                if not self.auth_token:
                    # 尝试从响应头获取
                    if 'Authentication-Token' in resp.headers:
                        self.auth_token = resp.headers.get('Authentication-Token')
                    # 尝试从响应体获取
                    elif resp.text:
                        try:
                            resp_data = resp.json()
                            if 'token' in resp_data:
                                self.auth_token = resp_data.get('token')
                            elif 'content' in resp_data and isinstance(resp_data.get('content'), dict):
                                content = resp_data.get('content')
                                if 'token' in content:
                                    self.auth_token = content.get('token')
                        except:
                            pass

                logger.info(
                    f"[XxlJobClient] ✅ 登录成功: {self.base_url}, Token={'已获取' if self.auth_token else '未获取'}")
                return True


            
            logger.error(f"[XxlJobClient] ❌ 所有登录路径都失败")
            return False
        
        except Exception as e:
            logger.error(f"[XxlJobClient] ❌ 登录失败: {str(e)}")
            return False

    def query_job_address_handler(
        self,
        job_group: int,
        tag: Optional[str] = None,
        site_tenant: str = "DEFAULT",
    ) -> Optional[str]:
        """
        根据执行器分组 ID 查询执行器地址信息，并按 tag 选择地址。

        对应浏览器中的接口:
        GET /xxl-job-admin/jobgroup/loadById?id={job_group}

        Args:
            job_group: 执行器分组 ID
            tag: 地址 tag（例如 sdklog、cbspay 等），用于匹配 URL 中的 `@tag`
            site_tenant: 站点租户（默认为 DEFAULT）

        Returns:
            选中的单个地址字符串（可能包含 @tag 后缀）；未找到或出错时返回 None
        """
        try:
            path = f"/xxl-job-admin/jobgroup/loadById?id={job_group}"
            headers = {
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
                "x-app": "developer",
                "x-site-tenant": site_tenant,
                "x-spotter-i18n": "zh_Hans",
                "x-sso-version": "v3",
            }

            if self.auth_token:
                headers["Authentication-Token"] = self.auth_token

            logger.info(
                f"[XxlJobClient] 查询执行器分组地址: job_group={job_group}, site_tenant={site_tenant}, tag={tag or '(无)'}"
            )

            resp = requests.get(
                self.base_url + path,
                headers=headers,
                cookies=self.cookies,
                timeout=10,
            )

            result = resp.json()

            # XXL-Job 通常使用 code=200 表示成功
            if result.get("code") != 200:
                logger.error(f"[XxlJobClient] ❌ 查询执行器分组失败: id={job_group}, resp={result}")
                return None

            content = result.get("content") or {}
            registry_list = content.get("registryList") or []

            if not registry_list:
                logger.warning(f"[XxlJobClient] ⚠️ 执行器分组无注册地址: id={job_group}")
                return None

            selected: Optional[str] = None

            # 1. 若传入 tag，则优先匹配包含 @tag 的地址，并返回带 @ 的完整地址
            if tag:
                for addr in registry_list:
                    if f"@{tag}" in addr:
                        selected = addr
                        break

            # 2. 如果没有传 tag，或者没匹配到对应 tag，则返回「没有 tag」的地址
            if not selected:
                for addr in registry_list:
                    if "@" not in addr:
                        selected = addr
                        break

            logger.info(
                f"[XxlJobClient] ✅ 选中执行器地址: id={job_group}, tag={tag or '(无)'}, address={selected}"
            )
            return selected

        except Exception as e:
            logger.error(f"[XxlJobClient] ❌ 查询执行器分组异常: {str(e)}")
            return None



    def query_job_by_handler(
        self,
        executor_handler: str,
        site_tenant: str = "DEFAULT"
    ) -> Optional[Dict[str, Any]]:
        """
        通过 Handler 名称查询任务
        
        Args:
            executor_handler: 执行器 Handler 名称
            site_tenant: 站点租户
        
        Returns:
            任务信息，如果未找到返回 None
        """
        try:
            path = '/xxl-job-admin/jobinfo/queryPage'
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
                'x-app': 'developer',
                'x-site-tenant': site_tenant,
                'x-spotter-i18n': 'zh_Hans',
                'x-sso-version': 'v3',
            }
            
            if self.auth_token:
                headers['Authentication-Token'] = self.auth_token
            
            payload = {
                "current": 1,
                "pageSize": 20,
                "executorHandler": executor_handler
            }
            
            logger.info(f"[XxlJobClient] 通过 API 查询任务: handler={executor_handler}")
            
            resp = requests.post(
                self.base_url + path,
                headers=headers,
                json=payload,
                cookies=self.cookies,
                timeout=10
            )
            
            result = resp.json()
            
            if result.get("code") == 200:
                executor_list = result.get("content", {}).get("list", [])
                if executor_list and len(executor_list) > 0:
                    job = executor_list[0]
                    logger.info(f"[XxlJobClient] ✅ 找到任务: ID={job.get('id')}, Handler={executor_handler}")
                    return job
                else:
                    logger.warning(f"[XxlJobClient] ⚠️ 未找到任务: {executor_handler}")
                    return None
            else:
                logger.error(f"[XxlJobClient] ❌ 查询任务失败: {result}")
                return None
        
        except Exception as e:
            logger.error(f"[XxlJobClient] ❌ 查询任务异常: {str(e)}")
            return None

    def trigger_job_by_id(
        self,
        job_id: int,
        executor_param: str = "",
        site_tenant: str = "DEFAULT",
        address_list: str = ""
    ) -> Dict[str, Any]:
        """
        通过任务 ID 触发任务
        
        Args:
            job_id: 任务 ID
            executor_param: 执行参数（可选）
            site_tenant: 站点租户
            address_list: 执行器地址列表（可选）
        
        Returns:
            执行结果
        """
        try:
            path = '/xxl-job-admin/jobinfo/trigger'
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
                'x-app': 'developer',
                'x-site-tenant': site_tenant,
                'x-spotter-i18n': 'zh_Hans',
                'x-sso-version': 'v3',
            }
            
            if self.auth_token:
                headers['Authentication-Token'] = self.auth_token
            
            # 构建请求体，根据 API 要求
            payload = {
                "id": job_id,
                "siteTenant": site_tenant,
                "addressList": address_list if address_list else ""
            }
            
            # 只有在有执行参数时才添加
            if executor_param:
                payload["executorParam"] = executor_param
            
            logger.info(f"[XxlJobClient] 触发任务: ID={job_id}, SiteTenant={site_tenant}, Param={executor_param or '(空)'}")
            
            resp = requests.post(
                self.base_url + path,
                headers=headers,
                json=payload,
                cookies=self.cookies,
                timeout=10
            )
            
            result = resp.json()
            
            if result.get("code") == 200:
                logger.info(f"[XxlJobClient] ✅ 任务触发成功: ID={job_id}")
                return {
                    "success": True,
                    "code": 200,
                    "msg": "任务触发成功",
                    "content": result
                }
            else:
                logger.error(f"[XxlJobClient] ❌ 任务触发失败: {result}")
                return {
                    "success": False,
                    "code": result.get("code", 500),
                    "msg": result,
                    "content": None
                }
        
        except Exception as e:
            logger.error(f"[XxlJobClient] ❌ 触发任务异常: {str(e)}")
            return {
                "success": False,
                "code": 500,
                "msg": f"触发任务失败: {str(e)}",
                "content": None
            }

    def trigger_job_by_handler(
        self,
        executor_handler: str,
        executor_param: str = "",
        site_tenant: str = "DEFAULT",
        address_list: str = "",
        **kwargs
    ) -> Dict[str, Any]:
        """
        通过 Handler 名称触发任务
        
        Args:
            executor_handler: 执行器 Handler 名称
            executor_param: 执行参数
            site_tenant: 站点租户
            address_list: 执行器地址列表
        
        Returns:
            执行结果
        """
        try:
            # 通过 API 查询任务
            tag = kwargs.get('tag')
            job = self.query_job_by_handler(executor_handler, site_tenant)

            if not job:
                logger.error(f"[XxlJobClient] ❌ 未找到任务: {executor_handler}")
                return {
                    "success": False,
                    "code": 404,
                    "msg": f"未找到任务: {executor_handler}",
                    "content": None
                }
            
            job_id = job.get("id")
            logger.info(f"[XxlJobClient] 找到任务: ID={job_id}")
            job_group = job.get("jobGroup")

            address = self.query_job_address_handler(job_group=job_group, tag=tag, site_tenant=site_tenant)
            
            # 触发任务
            return self.trigger_job_by_id(
                job_id=job_id,
                executor_param=executor_param,
                site_tenant=site_tenant,
                address_list=address
            )
        
        except Exception as e:
            logger.error(f"[XxlJobClient] ❌ 通过 Handler 触发任务失败: {str(e)}")
            return {
                "success": False,
                "code": 500,
                "msg": f"通过 Handler 触发任务失败: {str(e)}",
                "content": None
            }
    
    def trigger_job_by_handler_with_context(
        self,
        executor_handler: str,
        executor_param: str = "",
        site_tenant: str = "DEFAULT",
        address_list: str = "",
        **kwargs
    ) -> Dict[str, Any]:
        """
        通过 Handler 名称触发任务

        Args:
            executor_handler: 执行器 Handler 名称
            executor_param: 执行参数
            site_tenant: 站点租户
            address_list: 执行器地址列表
        
        Returns:
            执行结果
        """
        # 直接使用 API 接口查询和触发，不再需要数据库
        tag = kwargs.get('tag')
        return self.trigger_job_by_handler(
            executor_handler=executor_handler,
            executor_param=executor_param,
            site_tenant=site_tenant,
            address_list=address_list,
            tag=tag,

        )
    def get_job_info(self, job_id: int) -> Optional[Dict[str, Any]]:
        """
        获取任务信息
        
        Args:
            job_id: 任务 ID
        
        Returns:
            任务信息
        """
        try:
            path = f'/xxl-job-admin/jobinfo/info?id={job_id}'
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            }
            
            if self.auth_token:
                headers['Authentication-Token'] = self.auth_token
            
            resp = requests.get(
                self.base_url + path,
                headers=headers,
                cookies=self.cookies,
                timeout=10
            )
            
            result = resp.json()
            
            if result.get("code") == 200:
                return result.get("content")
            else:
                logger.error(f"[XxlJobClient] 获取任务信息失败: {result}")
                return None
        
        except Exception as e:
            logger.error(f"[XxlJobClient] 获取任务信息异常: {str(e)}")
            return None
    
    def close(self):
        """关闭客户端"""
        self.cookies = None
        self.auth_token = None
        logger.info("[XxlJobClient] 客户端关闭")


# 便捷函数
def create_xxl_job_client(
    base_url: str,
    username: str = "admin",
    password: str = "123456",
    app_code: str = "developer"
) -> XxlJobClient:
    """
    创建 XXL-Job 客户端（工厂函数）
    
    Args:
        base_url: XXL-Job 管理平台 URL
        username: 用户名
        password: 密码
        app_code: 应用代码
    
    Returns:
        XxlJobClient 实例
    """
    return XxlJobClient(
        base_url=base_url,
        username=username,
        password=password,
        app_code=app_code
    )


if __name__ == '__main__':
    # 示例调试代码，如需本地调试可取消注释
    # job = XxlJobClient('http://api.dev.spotterio.com')
    # job.login()
    # print(job.query_job_by_handler('pushSettleAccountTrade'))
    # print(job.query_job_address_handler(91, "v2", "US_AMZ"))
    pass




