import json
from typing import Optional, Dict, Any

import requests


class SpotterRocketMQClient:
    """MQ消息发送SDK"""

    def __init__(self, base_url: str = None):
        """
        初始化SDK
        Args:
            base_url: 自定义服务地址（优先使用）
            token: 自定义认证 token（优先使用）
        """
        self.base_url = base_url
        # 优先使用传入的 token，其次使用默认值
        self.token = 'tM3yI4rA'

        # 默认请求头
        self.default_headers = {
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Pragma': 'no-cache',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'x-site-tenant': 'default',
            'Content-Type': 'application/json'
        }

    def set_site_tenant(self, site_tenant: str):
        """设置站点信息"""
        self.default_headers['x-site-tenant'] = site_tenant
        return self

    def send_message(self,
                     topic: str,
                     message_body: str,
                     tag: str = "*",
                     key: Optional[str] = "*",
                   ) -> Dict[str, Any]:
        """
        发送消息到MQ

        Args:
            topic: 消息主题
            message_body: 消息内容 如果是json  需要json.dumps()
            tag: 消息标签，默认为 "*"
            key: 消息键值，可选
            custom_headers: 自定义请求头，可选

        Returns:
            Dict: 包含MsgId的响应数据

        Raises:
            requests.RequestException: 请求异常
            ValueError: 参数错误
        """
        if not topic:
            raise ValueError("topic 不能为空")
        if not message_body:
            raise ValueError("message_body 不能为空")

        # 构建请求数据
        payload = {
            "token": self.token,
            "topic": topic,
            "messageBody": message_body,
            "tag": tag
        }

        # 如果提供了key参数，则添加到payload中
        if key is not None:
            payload["key"] = key

        # 合并自定义请求头
        headers = self.default_headers.copy()

        try:
            # 发送POST请求
            response = requests.post(
                self.base_url +"/spotter-utility-web/mock/sendMQMessage",
                headers=headers,
                data=json.dumps(payload),
                verify=False,
                timeout=30
            )

            # 检查响应状态
            response.raise_for_status()

            # 解析JSON响应
            result = response.json()
            return result

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "status_code": getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            }
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON解析错误: {str(e)}",
                "raw_response": response.text if 'response' in locals() else None
            }

#
# if __name__ == '__main__':
#     msg = {"data":{"carrier":"SGWJP","orderStatus":"","referenceNo":"kkkyyyyy028","trackingNumber":["tracking-star-001","tracking-star-002","tracking-star-003","tracking-star-004","tracking-star-005","tracking-star-006"],"thirdPartyOutboundNo":"PO-SPOTTER-251024-0028"},"bizId":"FOPO1302506260235YYYK028","success":True,"taskCode":"jbt_query_outbound","featuresMap":{"isCloudWarehouse":"1","requestMessageId":"7F00000100074EEC777768FCC3DE2FE3"}}
#     url = "http://api.tst.spotterio.com/spotter-utility-web/mock/sendMQMessage"
#     print(SpotterRocketMQClient(url).send_message(
#         "SUPPLY_LINK_RET",
#         json.dumps(msg),
#         "jbt_query_outbound",
#         "*"
#     ))
#
#
#     pass