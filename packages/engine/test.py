import json
from pathlib import Path

from packages.engine.workflow_engine import WorkflowExecutor


task = {
	"task_id": "57926a6b-3d24-42e7-abce-a8fd961935b1",
	"parent_task_id": "00ad54a7-f8da-4ef0-b9c2-7e11c627e08a",
	"task_type": "workflow",
	"priority": "normal",
	"payload": {
		"workflow": {
			"nodes": [
				{
					"data": {
						"assertion": {},
						"extractions": [
							{
								"default": "NULL",
								"var_name": "company_id",
								"source_path": "body[0].id"
							},
							{
								"default": "NULL",
								"var_name": "company_code",
								"source_path": "body[0].business_code"
							},
							{
								"default": "NULL",
								"var_name": "company_name",
								"source_path": "body[0].name"
							}
						],
						"config": {
							"connection": {
								"host": "${data_host}",
								"port": "${data_port}",
								"user": "${data_user}",
								"charset": "utf8mb4",
								"database": "spotter_supplier",
								"password": "${data_password}",
								"read_timeout": 30,
								"write_timeout": 30,
								"connect_timeout": 10
							},
							"query_type": "fetchone",
							"params": [
								"HFX3XL"
							],
							"operation": "select",
							"sql": "SELECT id, business_code, name FROM spotter_supplier.supplier WHERE business_code =%s",

						}
					},
					"stepName": "获取供应商信息",
					"id": "922163847979008",
					"type": "mysql"
				},
				{
					"data": {
						"assertion": {},
						"extractions": [
							{
								"default": "NULL",
								"var_name": "storage_code",
								"source_path": "body[0].storage_code"
							},
							{
								"default": "NULL",
								"var_name": "storage_name",
								"source_path": "body[0].storage_name"
							}
						],
						"config": {
							"connection": {
								"host": "${data_host}",
								"port": "${data_port}",
								"user": "${data_user}",
								"charset": "utf8mb4",
								"database": "spotter_warehouse",
								"password": "${data_password}",
								"read_timeout": 30,
								"write_timeout": 30,
								"connect_timeout": 10
							},
							"query_type": "fetchmany",
							"params": [
								"US",
								"US",
								1
							],
							"operation": "select",
							"sql": "select storage_code,storage_name from spotter_warehouse.warehouse_storage_info where country = %s and (platform_region = %s  or platform_region = 'default') and storage_type = %s and status =1 and approve_status =1"
						}
					},
					"stepName": "获取仓库信息",
					"id": "922163847979009",
					"type": "mysql"
				},
				{
					"data": {
						"assertion": {},
						"extractions": [
							{
								"default": "NULL",
								"var_name": "account_code",
								"source_path": "body[0].account_code"
							},
							{
								"default": "NULL",
								"var_name": "account_name",
								"source_path": "body[0].account_name"
							},
							{
								"default": "NULL",
								"var_name": "account_id",
								"source_path": "body[0].account_id"
							},
							{
								"default": "NULL",
								"var_name": "vendor_id",
								"source_path": "body[0].vendor_id"
							},
							{
								"default": "NULL",
								"var_name": "vendor_code",
								"source_path": "body[0].vendor_code"
							}
						],
						"config": {
							"connection": {
								"host": "${data_host}",
								"port": "${data_port}",
								"user": "${data_user}",
								"charset": "utf8mb4",
								"database": "spotter_cooperation",
								"password": "${data_password}",
								"read_timeout": 30,
								"write_timeout": 30,
								"connect_timeout": 10
							},
							"query_type": "fetchmany",
							"params": [
								"US",
								1
							],
							"operation": "select",
							"sql": "select a.account_code,a.registered_business_name,v.account_id,v.id,v.vendor_code from spotter_cooperation.cp_amazon_vendor v left join spotter_cooperation.cp_amazon_account a on v.account_id = a.id where v.deleted_at is null and v.platform_region = %s and v.vendor_code_type = %s and a.account_code is not null"
						}
					},
					"stepName": "获取VC账号信息",
					"id": "922163847979010",
					"type": "mysql"
				},
				{
					"data": {
						"assertion": {},
						"extractions": [
							{
								"default": "NULL",
								"var_name": "account_commission_rate",
								"source_path": "body[0].account_commission_rate"
							}
						],
						"config": {
							"connection": {
								"host": "${data_host}",
								"port": "${data_port}",
								"user": "${data_user}",
								"charset": "utf8mb4",
								"database": "spotter_cooperation",
								"password": "${data_password}",
								"read_timeout": 30,
								"write_timeout": 30,
								"connect_timeout": 10
							},
							"query_type": "fetchmany",
							"params": [
								"${vendor_code}"
							],
							"operation": "select",
							"sql": "select account_commission_rate from spotter_cooperation.cp_amazon_vendor_agreement where vendor_code = %s and ((effective_time_ms <= 1753080826000 and expired_time_ms >= 1753080826000) or (effective_time_ms <= 1753080826000 and expired_time_ms is null))"
						}
					},
					"stepName": "获取account_commission_rate",
					"id": "922163847979011",
					"type": "mysql"
				},
				{
					"data": {
						"assertion": {},
						"extractions": [],
						"config": {
							"loop_type": "while_loop",
							"max_iterations": 1,
							"condition": "1 == 1",
							"index_variable": "index",
							"output_variable": "loop_result",
							"count": 10,
							"sub_nodes": [
								{
									"x": 0,
									"y": 0,
									"id": "sub-node-1770171467641-00zekim1k",
									"name": "生成随机字符串作为storage_code",
									"type": "mysql",
									"config": {
										"sql": "SELECT UPPER(SUBSTRING(MD5(RAND()) FROM 1 FOR 8)) AS storage_code",

										"operation": "select",
										"connection": {
											"host": "${data_host}",
											"port": "${data_port}",
											"user": "${data_user}",
											"charset": "utf8mb4",
											"database": "spotter_warehouse",
											"password": "${data_password}",
											"read_timeout": 30,
											"write_timeout": 30,
											"connect_timeout": 10
										},
										"query_type": "fetchone",
										"extractions": [
											{
												"default": "NULL",
												"var_name": "storage_code",
												"source_path": "body[0].storage_code"
											}
										]
									},
									"description": "数据库操作"
								},
								{
									"x": 0,
									"y": 0,
									"id": "sub-node-1770173475822-a5hb9ze31",
									"name": "生成随机字符串作为storage_name",
									"type": "mysql",
									"config": {
										"sql": "SELECT CONCAT('test_storage_', %s) AS storage_name",
										"params": [
											"${storage_code}"
										],
										"operation": "select",
										"connection": {
											"host": "${data_host}",
											"port": "${data_port}",
											"user": "${data_user}",
											"charset": "utf8mb4",
											"database": "spotter_warehouse",
											"password": "${data_password}",
											"read_timeout": 30,
											"write_timeout": 30,
											"connect_timeout": 10
										},
										"query_type": "fetchone",
										"extractions": [
											{
												"default": "NULL",
												"var_name": "storage_name",
												"source_path": "body[0].storage_name"
											}
										]
									},
									"description": "数据库操作"
								},
								{
									"x": 0,
									"y": 0,
									"id": "sub-node-1770170837331-qn9yrhw5o",
									"name": "插库写入对应仓库信息",
									"type": "mysql",
									"config": {
										"sql": "INSERT INTO spotter_warehouse.warehouse_storage_info( storage_name, storage_en_name, storage_region, storage_code, company_id, country, state, city,add_time, contact, mobile, postcode, email, storage_type, wms_storage_type, status, approve_status, created_at, updated_at, platform, platform_region, address1, address2, address3, time_zone, df_email_time_list, features, fulfill_storage_code)VALUES(%s, NULL, %s, %s, 54, %s, NULL, 'test', 1749091570470, 'Cynthia 张倩', '17723945384', '23432', 'cynthia.zhang@spotterio.com', %s, NULL, 1, 1, '2025-06-05 02:46:11', '2025-06-07 05:44:23', %s, %s, '江北区xx写字楼2楼', NULL, NULL, 'CET', '[\\\"15:30\\\"]', 'null', %s)",
										"params": [
											"${storage_name}",
											"US",
											"${storage_code}",
											"US",
											1,
											"US",
											"US",
											"${storage_code}"
										],
										"operation": "insert",
										"connection": {
											"host": "${data_host}",
											"port": "${data_port}",
											"user": "${data_user}",
											"charset": "utf8mb4",
											"database": "spotter_warehouse",
											"password": "${data_password}",
											"read_timeout": 30,
											"write_timeout": 30,
											"connect_timeout": 10
										},
										"query_type": "fetchmany"
									},
									"description": "数据库操作"
								},
								{
									"x": 0,
									"y": 0,
									"id": "sub-node-1770170677840-jg3u7z53u",
									"name": "获取仓库信息",
									"type": "mysql",
									"config": {
										"sql": "select storage_code,storage_name from spotter_warehouse.warehouse_storage_info where country = %s and (platform_region = %s  or platform_region = 'default') and storage_type = %s and status =1 and approve_status =1",
										"params": [
											"US",
											"US",
											1
										],
										"operation": "select",
										"connection": {
											"host": "${data_host}",
											"port": "${data_port}",
											"user": "${data_user}",
											"charset": "utf8mb4",
											"database": "spotter_warehouse",
											"password": "${data_password}",
											"read_timeout": 30,
											"write_timeout": 30,
											"connect_timeout": 10
										},
										"query_type": "fetchone",
										"extractions": [
											{
												"default": "NULL",
												"var_name": "storage_code",
												"source_path": "body[0].storage_code"
											},
											{
												"default": "NULL",
												"var_name": "storage_name",
												"source_path": "body[0].storage_name"
											}
										]
									},
									"description": "数据库操作"
								}
							],
							"item_variable": "item"
						}
					},
					"stepName": "插库写入仓库信息并提取参数",
					"id": "922163847979012",
					"type": "loop"
				},
				{
					"data": {
						"assertion": {},
						"extractions": [
							{
								"default": "NULL",
								"var_name": "coop",
								"source_path": "body[0].coop"
							}
						],
						"config": {
							"connection": {
								"host": "${data_host}",
								"port": "${data_port}",
								"user": "${data_user}",
								"charset": "utf8mb4",
								"database": "spotter_cooperation",
								"password": "${data_password}",
								"read_timeout": 30,
								"write_timeout": 30,
								"connect_timeout": 10
							},
							"query_type": "fetchone",
							"params": [
								"${account_commission_rate}"
							],
							"operation": "select",
							"sql": "select %s / 100 as coop"
						}
					},
					"stepName": "获取coop",
					"id": "922163847979013",
					"type": "mysql"
				}
			],
			"edges": [
				{
					"id": "e1",
					"source": "922163847979008",
					"target": "922163847979009"
				},
				{
					"id": "e2",
					"source": "922163847979010",
					"target": "922163847979011"
				},
				{
					"id": "e3",
					"source": "922163847979009",
					"target": "922163847979012"
				},
				{
					"id": "e4",
					"source": "922163847979012",
					"target": "922163847979010"
				},
				{
					"id": "e5",
					"source": "922163847979011",
					"target": "922163847979013"
				}
			],
			"workflowName": "成功生成一条订单类型为PO预账单_云仓_US",
			"workflowId": "2562755455508482"
		},
		"environment": None,
		"variables": {
			"data_port": 30070,
			"dubbo_url": "http://spotter-snap-rpc.dev.spotter.ink/rpc/invoke",
			"xxljobuser": "cynthia.zhang@spotterio.com",
			"data_host": "mysql.dev.spotter.ink",
			"url": "http://api.dev.spotterio.com",
			"data_password": "root",
			"mq_url": "http://api.dev.spotterio.com",
			"password": "MTExMTEx",
			"xxljobpassword": "111111",
			"data_user": "root",
			"header_type": "plut",
			"xxjob_url": "https://developer.dev.spotterio.com/xxl-job",
			"email": "cynthia.zhang@spotterio.com"
		},
		"runId": "923521057644545",
		"reportId": "923521057644544"
	},
	"metadata": {
		"created_at": "2026-02-04T14:55:56.596029",
		"created_by": "system",
		"retry_count": 0,
		"max_retries": 3,
		"timeout": 300
	}
}
task

wf = task["payload"]["workflow"]
# 适配字段：stepName -> name
for n in wf.get("nodes", []):
    if "name" not in n:
        n["name"] = n.get("stepName") or n.get("id")

workflow_data = {
    "work_id": wf.get("workflowId") or task.get("task_id"),
    "work_name": wf.get("workflowName"),
    "nodes": wf.get("nodes", []),
    "edges": wf.get("edges", []),
    # 关键：把变量放到顶层 variables，执行器会自动注入到 context
    "variables": task["payload"].get("variables", {}),
}
print(workflow_data)

executor = WorkflowExecutor(
    workflow_data,
    hook_file="/Users/jan/PycharmProjects/aegis-runner/hooks.py",
)
result = executor.execute()
print(result.to_dict())
print(result.status)
