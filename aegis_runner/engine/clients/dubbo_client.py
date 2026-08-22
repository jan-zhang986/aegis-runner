import time
import requests



class DubboClient:
    def __init__(self, url=None, timeout=30):
        self.url = url
        self.timeout = timeout
        self.default_headers = {"Content-Type": "application/json"}
        self.application_name = None
        self.interface_name = None
        self.method_name = None
        self.param_types = None
        self.params = None
        self.site_tenant = None
        self.dubbo_tag = None
        self.headers = {}
    
    # 链式设值方法
    def set_url(self, url):
        self.url = url
        return self

    def set_application_name(self, application_name):
        self.application_name = application_name
        return self

    def set_interface_name(self, interface_name):
        self.interface_name = interface_name
        return self

    def set_method_name(self, method_name):
        self.method_name = method_name
        return self

    def set_param_types(self, param_types):
        self.param_types = param_types
        return self

    def set_params(self, params):
        self.params = params
        return self

    def set_site_tenant(self, site_tenant):
        self.site_tenant = site_tenant
        return self

    def set_dubbo_tag(self, dubbo_tag):
        self.dubbo_tag = dubbo_tag
        return self

    def set_headers(self, headers):
        if isinstance(headers, dict):
            self.headers.update(headers)
        return self

    def set_timeout(self, timeout):
        self.timeout = timeout
        return self

    def reset(self):
        self.application_name = None
        self.interface_name = None
        self.method_name = None
        self.param_types = None
        self.params = None
        self.site_tenant = None
        self.dubbo_tag = None
        self.headers = {}
        self.timeout = 30
        return self

    def invoke(self):
        """
        支持：
        1. 链式set_xxx后调用invoke()
        2. 直接invoke(全部参数)
        3. 任意混合，invoke优先生效，其次set_xxx，其次__init__
        """


        payload = {
            "applicationName": self.application_name,
            "interfaceName": self.interface_name,
            "methodName": self.method_name,
            "paramTypes": self.param_types or [],
            "params": self.params or [],
            "siteTenant": self.site_tenant,
            "dubboTag": self.dubbo_tag,
        }
        # 移除空
        payload = {k: v for k, v in payload.items() if v is not None}
        try:
            return{"body": requests.post(
                self.url,
                json=payload,
                headers=self.headers,
                timeout=30
            ).json()}

        except requests.exceptions.Timeout:
            raise Exception(f"请求超时（{3 }秒）")
        except requests.exceptions.ConnectionError:
            raise Exception("连接错误，请检查网络和服务地址")
        except requests.exceptions.RequestException as e:
            raise Exception(f"请求异常：{str(e)}")
        except Exception as e:
            raise Exception(f"未知错误：{str(e)}")







if __name__ == '__main__':
    print(DubboClient(url="http://spotter-snap-rpc.tst.spotter.ink/rpc/invoke-async")
          .set_application_name("spotter-supplier")
          .set_method_name('findOneByCriteria')
          .set_interface_name('com.spotter.supplier.api.SupplierService')
          .set_param_types(["java.lang.Long"])
          .set_site_tenant('US_AMZ')
          .set_params([1])
          .invoke())



