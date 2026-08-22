# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName
@className CredentialManager
@describe 凭证管理CLI工具 - 方便管理API鉴权凭证
"""

import json

from aegis_runner.engine.core.credential_store import (
    credential_store,
    add_bearer_credential,
    add_api_key_credential,
    add_basic_auth_credential,
    add_oauth2_credential,
    AuthType
)


def init_default_credentials():
    """初始化默认凭证（示例）"""
    print("\n" + "="*60)
    print("初始化默认凭证")
    print("="*60)
    
    # 1. 添加测试环境凭证
    add_bearer_credential(
        credential_id="test_api_bearer",
        name="测试环境API - Bearer Token",
        token="${TEST_API_TOKEN}",  # 支持变量引用
        description="测试环境的Bearer Token鉴权",
        expires_in_days=30
    )
    
    # 2. 添加生产环境凭证
    add_bearer_credential(
        credential_id="prod_api_bearer",
        name="生产环境API - Bearer Token",
        token="${PROD_API_TOKEN}",
        description="生产环境的Bearer Token鉴权",
        expires_in_days=90
    )
    
    # 3. 添加第三方API Key凭证
    add_api_key_credential(
        credential_id="third_party_api_key",
        name="第三方服务 - API Key",
        key_name="X-API-Key",
        key_value="${THIRD_PARTY_API_KEY}",
        description="第三方服务的API Key鉴权"
    )
    
    # 4. 添加数据库管理API的Basic Auth
    add_basic_auth_credential(
        credential_id="db_admin_basic",
        name="数据库管理API - Basic Auth",
        username="${DB_ADMIN_USER}",
        password="${DB_ADMIN_PASS}",
        description="数据库管理接口的Basic Auth鉴权"
    )
    
    # 5. 添加OAuth2凭证
    add_oauth2_credential(
        credential_id="oauth2_service",
        name="OAuth2服务 - Access Token",
        access_token="${OAUTH2_ACCESS_TOKEN}",
        token_type="Bearer",
        refresh_token="${OAUTH2_REFRESH_TOKEN}",
        description="OAuth2服务的访问令牌",
        expires_in_days=7
    )
    
    # 6. 添加自定义Header鉴权
    credential_store.add_credential(
        credential_id="custom_header_auth",
        name="自定义Header鉴权",
        auth_type=AuthType.CUSTOM.value,
        config={
            "headers": {
                "X-Custom-Auth": "${CUSTOM_AUTH_TOKEN}",
                "X-Request-ID": "${REQUEST_ID}",
                "X-Client-ID": "workflow_engine_v1"
            }
        },
        description="使用自定义Header的鉴权方式"
    )
    
    print("✅ 已添加6个默认凭证")


def list_all_credentials():
    """列出所有凭证"""
    print("\n" + "="*60)
    print("凭证列表")
    print("="*60)
    
    credentials = credential_store.list_credentials(enabled_only=False)
    
    for i, cred in enumerate(credentials, 1):
        status_icon = "✅" if cred.enabled else "❌"
        if cred.is_expired():
            status_icon = "⏰"
        
        print(f"\n{i}. {status_icon} {cred.name}")
        print(f"   ID: {cred.credential_id}")
        print(f"   类型: {cred.auth_type}")
        print(f"   描述: {cred.description}")
        print(f"   创建时间: {cred.created_at}")
        if cred.expires_at:
            print(f"   过期时间: {cred.expires_at}")
        if cred.tags:
            print(f"   标签: {', '.join(cred.tags)}")


def show_credential_details(credential_id: str):
    """显示凭证详情"""
    print("\n" + "="*60)
    print(f"凭证详情: {credential_id}")
    print("="*60)
    
    credential = credential_store.get_credential(credential_id)
    if not credential:
        print(f"❌ 凭证不存在: {credential_id}")
        return
    
    print(f"名称: {credential.name}")
    print(f"ID: {credential.credential_id}")
    print(f"类型: {credential.auth_type}")
    print(f"描述: {credential.description}")
    print(f"状态: {'✅ 启用' if credential.enabled else '❌ 禁用'}")
    print(f"创建时间: {credential.created_at}")
    print(f"更新时间: {credential.updated_at}")
    
    if credential.expires_at:
        print(f"过期时间: {credential.expires_at}")
        if credential.is_expired():
            print("⚠️ 状态: 已过期")
    
    if credential.tags:
        print(f"标签: {', '.join(credential.tags)}")
    
    # 显示配置（脱敏）
    print(f"\n配置（已加密）:")
    config_keys = list(credential.config.keys())
    sensitive_keys = [k for k in config_keys if not k.startswith('_')]
    print(f"  包含字段: {', '.join(sensitive_keys)}")


def test_credential(credential_id: str, test_url: str):
    """测试凭证是否有效"""
    print("\n" + "="*60)
    print(f"测试凭证: {credential_id}")
    print("="*60)
    
    from aegis_runner.engine.clients.http_client import HttpClient
    
    # 创建HTTP客户端并使用凭证
    client = HttpClient(credential_id=credential_id)
    
    try:
        # 发送测试请求
        response = client.get(test_url)
        
        print(f"✅ 凭证测试成功")
        print(f"   测试URL: {test_url}")
        print(f"   响应状态: {response.status_code}")
        print(f"   响应时间: {response.response_time:.3f}秒")
        
        return True
    except Exception as e:
        print(f"❌ 凭证测试失败")
        print(f"   错误: {str(e)}")
        return False


def export_credentials_config(file_path: str):
    """导出凭证配置"""
    print("\n" + "="*60)
    print(f"导出凭证配置")
    print("="*60)
    
    credential_store.export_credentials(file_path, include_sensitive=False)
    print(f"✅ 凭证配置已导出到: {file_path}")
    print(f"⚠️ 敏感信息已隐藏，仅导出结构")


def import_credentials_config(file_path: str):
    """导入凭证配置"""
    print("\n" + "="*60)
    print(f"导入凭证配置")
    print("="*60)
    
    credential_store.import_credentials(file_path, overwrite=False)
    print(f"✅ 凭证配置已导入")


def check_expired():
    """检查过期凭证"""
    print("\n" + "="*60)
    print("检查过期凭证")
    print("="*60)
    
    expired = credential_store.check_expired_credentials()
    
    if not expired:
        print("✅ 没有过期的凭证")
    else:
        print(f"⚠️ 发现{len(expired)}个过期凭证:")
        for cred in expired:
            print(f"   - {cred.credential_id} ({cred.name})")
            print(f"     过期时间: {cred.expires_at}")


def show_audit_log(credential_id: str = None, limit: int = 20):
    """显示审计日志"""
    print("\n" + "="*60)
    print("审计日志")
    print("="*60)
    
    logs = credential_store.get_audit_log(credential_id=credential_id, limit=limit)
    
    if not logs:
        print("暂无审计日志")
        return
    
    for i, log in enumerate(logs, 1):
        print(f"\n{i}. {log['action']}")
        print(f"   凭证ID: {log['credential_id']}")
        print(f"   时间: {log['timestamp']}")
        if log['details']:
            print(f"   详情: {log['details']}")


def interactive_menu():
    """交互式菜单"""
    while True:
        print("\n" + "="*60)
        print("凭证管理工具 - 主菜单")
        print("="*60)
        print("1. 初始化默认凭证")
        print("2. 列出所有凭证")
        print("3. 查看凭证详情")
        print("4. 测试凭证")
        print("5. 检查过期凭证")
        print("6. 查看审计日志")
        print("7. 导出凭证配置")
        print("8. 导入凭证配置")
        print("9. 查看统计信息")
        print("0. 退出")
        print("="*60)
        
        choice = input("\n请选择操作 (0-9): ").strip()
        
        if choice == "1":
            init_default_credentials()
        elif choice == "2":
            list_all_credentials()
        elif choice == "3":
            cred_id = input("请输入凭证ID: ").strip()
            show_credential_details(cred_id)
        elif choice == "4":
            cred_id = input("请输入凭证ID: ").strip()
            test_url = input("请输入测试URL: ").strip()
            test_credential(cred_id, test_url)
        elif choice == "5":
            check_expired()
        elif choice == "6":
            show_audit_log()
        elif choice == "7":
            file_path = input("请输入导出文件路径: ").strip() or "credentials_export.json"
            export_credentials_config(file_path)
        elif choice == "8":
            file_path = input("请输入导入文件路径: ").strip()
            if os.path.exists(file_path):
                import_credentials_config(file_path)
            else:
                print(f"❌ 文件不存在: {file_path}")
        elif choice == "9":
            credential_store.print_statistics()
        elif choice == "0":
            print("\n👋 再见！")
            break
        else:
            print("❌ 无效的选择，请重试")


def main():
    """主程序"""
    print("\n" + "🔐 "*20)
    print("          企业级凭证管理工具")
    print("🔐 "*20)
    
    # 初始化一些示例凭证
    init_default_credentials()
    
    # 显示统计信息
    credential_store.print_statistics()
    
    # 列出所有凭证
    list_all_credentials()
    
    # 检查过期凭证
    check_expired()
    
    # 显示审计日志
    show_audit_log(limit=10)
    
    print("\n" + "💡 "*20)
    print("提示: 运行此脚本并添加 --interactive 参数进入交互模式")
    print("💡 "*20)
    
    # 如果命令行参数包含 --interactive，进入交互模式
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_menu()


if __name__ == "__main__":
    main()
