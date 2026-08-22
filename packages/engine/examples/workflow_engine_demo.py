import pprint

from packages.engine.workflow_engine import WorkflowExecutor
from packages.engine.src.core.simple_logger import logger


def build_demo_workflow():
    """构建示例工作流（从原 workflow_engine.py __main__ 迁移而来）"""
    return {
        "nodes": [
            {
                "id": "login",
                "type": "http_request",
                "data": {
                    "config": {
                        "method": "POST",
                        "url": "${sevc_url}/spotter-items-web/sevc/catalog/offer/history/list",
                        "body": {
                            "pageSize": 5,
                            "currentPage": 1,
                            "catalogOfferId": 909955534295
                        },
                        "headers": {
                            "x-app": "sevc",
                            "Content-Type": "application/json",
                            "x-site-tenant": "DEFAULT",
                            "Authentication-Token": "${get_token($email,$password,$url,$header_type)}"
                        }
                    },
                    "assertion": {
                        "rules": [
                            {"source": "status_code", "operator": "equals", "target": 200},
                            {"source": "body.data.pageSize", "operator": "equals", "target": 5}
                        ]
                    },
                    "extractions": [
                        {
                            "source_path": "body.data.data",
                            "var_name": "userId"
                        }
                    ]
                }
            },
            {
                "id": "dubbo调用",
                "type": "dubbo",
                "data": {
                    "config": {
                        "url": "${dubbo_url}",
                        "application_name": "spotter-order",
                        "interface_name": "com.spotter.order.api.IOrderAmzItemService",
                        "method_name": "listByAmzCodeList",
                        "param_types": ["java.util.List"],
                        "params": [["P04AB1CUL4"]],
                        "site_tenant": "US_AMZ"
                    },
                    "assertion": {
                        "rules": [
                            {
                                "source": "body.data[0].companyName",
                                "operator": "string_equals",
                                "target": "${companyName}",
                                "message": "不是宇宙中心断言失败。"
                            }
                        ]
                    },
                    "extractions": [
                        {
                            "var_name": "orderType",
                            "source_path": "body.data[0].orderType"
                        },
                        {
                            "var_name": "companyName",
                            "source_path": "body.data[0].companyName"
                        },
                        {
                            "var_name": "dubbo_message",
                            "source_path": "body.message"
                        }
                    ]
                }
            },
            {
                "id": "check_dubbo_success",
                "type": "condition",
                "data": {
                    "config": {
                        "expression": "'${dubbo_message}' == 'success'"
                    }
                }
            },
            {
                "id": "loop_process",
                "type": "loop",
                "data": {
                    "config": {
                        "loop_type": "foreach_loop",
                        "items": "${dubbo调用.body.data}",
                        "item_variable": "order_item",
                        "index_variable": "order_index",
                        "delay": 0.1,
                        "sub_nodes": [
                            {
                                "type": "log_message",
                                "data": {
                                    "config": {
                                        "message": "处理订单 ${order_index}: ${order_item.orderType} - ${order_item.companyName}"
                                    }
                                }
                            }
                        ],
                        "output_variable": "loop_result"
                    }
                }
            },
            {
                "id": "sql_query",
                "type": "mysql",
                "data": {
                    "config": {
                        "sql": "SELECT * FROM aegis_runner.user WHERE name like '%Y%' ",
                        "operation": "select",
                        "connection": {
                            "host": "mysql.tst.spotter.ink",
                            "port": 31070,
                            "user": "root",
                            "password": "root",
                            "database": "aegis_runner"
                        }
                    },
                    "assertion": {
                        "rules": [
                            {
                                "source": "body.data[0].name",
                                "operator": "string_equals",
                                "target": "Yuki",
                                "message": "期望用户名为张三！实际查询不是张三或无数据。"
                            }
                        ]
                    },
                    "extractions": [
                        {
                            "var_name": "email",
                            "source_path": "body.data[0].email"
                        }
                    ]
                }
            },
            {
                "id": "send_mq_message",
                "type": "rocketmq",
                "data": {
                    "config": {
                        "topic": "SUPPLY_LINK_RET",
                        "message_body": '{"type":"normal","eventId":"KEPtFogQ5hWE2Pkw","payloads":[{"ssku":"ssku6623462","status":5,"amzPoNo":"AmzOrderNol077D","outNums":6,"syncFlag":false,"companyId":54,"innerPack":1,"orderCode":"AmzOrderNol077D","transType":"SP","outboundNo":"VCOUTBOUNDno7625558","saOrderCode":"SAno8884792","outboundDate":1761126325103,"outboundType":1,"orderTotalNums":6,"outStorageCode":"CNSZSN91752A","outboundDateMs":1761126325103,"channelOrderCode":"AmzOrderNol077D","vcpoShipmentCode":"VCOUTBOUNDno7625558","fulfillmentOrderNo":"FoNoFZTTD"}],"eventName":"OutboundFinanceEvent","retryTimes":0,"sourceService":"spotter-warehouse","eventClassPath":"com.spotter.warehouse.event.OutboundFinanceEvent","eventTriggerMs":1724211900815,"destinationService":[],"targetListenerClassPath":""}',
                        "mq_url": "http://api.dev.spotterio.com/spotter-utility-web/mock/sendMQMessage",
                        "site_tenant": "DEFAULT",
                        "tag": "*",
                        "key": "*"
                    },
                    "assertion": {
                        "rules": [
                            {
                                "source": "status_code",
                                "operator": "string_equals",
                                "target": 500,
                                "message": "MQ消息发送失败"
                            }
                        ]
                    },
                    "extractions": [
                        {
                            "var_name": "error_code",
                            "source_path": "error_code"
                        }
                    ]
                }
            },
            {
                "id": "log_not_user_1",
                "type": "log_message",
                "data": {
                    "config": {
                        "message": "检测到用户ID (${userId}) 不是 1，跳过获取详情。MQ消息ID: ${mq_msg_id}"
                    }
                }
            },
            {
                "id": "final_log",
                "type": "log_message",
                "data": {
                    "config": {
                        "message": "流程结束。"
                    }
                }
            }
        ],
        "edges": [
            {"id": "e1", "source": "login", "target": "dubbo调用"},
            {"id": "e2", "source": "dubbo调用", "target": "check_dubbo_success"},
            {"id": "e3", "source": "check_dubbo_success", "target": "loop_process", "source_handle": "true"},
            {"id": "e4", "source": "check_dubbo_success", "target": "sql_query", "source_handle": "false"},
            {"id": "e5", "source": "loop_process", "target": "send_mq_message"},
            {"id": "e6", "source": "sql_query", "target": "send_mq_message"},
            {"id": "e7", "source": "send_mq_message", "target": "log_not_user_1"},
            {"id": "e8", "source": "log_not_user_1", "target": "final_log"},
        ]
    }


def run_demo():
    """运行示例工作流"""
    workflow_data = build_demo_workflow()

    executor = WorkflowExecutor(workflow_data)

    # 示意性设置一些上下文变量（敏感信息请使用环境变量或凭证管理）
    executor.context.set_variable("email", "986099850@qq.com")
    executor.context.set_variable("password", "dHR4ZmQxMjM=")
    executor.context.set_variable("url", "http://api.dev.spotterio.com")
    executor.context.set_variable("header_type", "sevc")
    executor.context.set_variable("sevc_url", "http://api.dev.spotterio.com")
    executor.context.set_variable("dubbo_url", "http://spotter-snap-rpc.tst.spotter.ink/rpc/invoke-async")

    execution_result = executor.execute()

    logger.info(f"工作流ID: {execution_result.workflow_id}")
    logger.info(f"执行状态: {execution_result.status.value}")

    if execution_result.start_time and execution_result.end_time:
        execution_result.duration = (execution_result.end_time - execution_result.start_time).total_seconds()
    else:
        execution_result.duration = None

    if execution_result.duration is not None:
        logger.info(f"执行时间: {execution_result.duration:.4f} 秒")
    else:
        logger.info("执行时间: 无法计算")

    logger.info(f"成功率: {execution_result.get_success_rate():.2%}")
    logger.info(f"总步骤数: {len(execution_result.steps)}")
    logger.info(f"成功步骤: {len(execution_result.get_successful_steps())}")
    logger.info(f"失败步骤: {len(execution_result.get_failed_steps())}")
    logger.info(f"跳过步骤: {len(execution_result.get_skipped_steps())}")

    pprint.pprint(execution_result.to_dict())


if __name__ == "__main__":
    run_demo()

