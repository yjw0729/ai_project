"""
pytest Fixtures 入口配置。

该模块汇总所有 fixtures，提供统一的导入入口。
使用时无需关心 fixtures 的具体来源。

使用示例：
    # 在测试文件中直接使用
    def test_example(api_client, auth_token, db_session, cleanup_actions):
        response = api_client.get("/api/example")
        assert response.status_code == 200
"""

from fixtures.api_client import (
    APIClient,
    api_client,
    api_client_with_auth,
    api_helper,
    base_url,
    config,
    default_headers,
    timeout,
)
from fixtures.auth import (
    auth_headers,
    auth_manager,
    auth_token,
    api_credentials,
    api_key,
    authenticated_client,
)
from fixtures.cleanup import (
    cleanup_actions,
    cleanup_manager,
    file_cleanup,
    api_client_cleanup,
    session_scope_cleanup,
    temp_dir_cleanup,
    test_environment_cleanup,
)
from fixtures.database import (
    DatabaseHelper,
    db_config,
    db_helper,
    db_keys,
    db_session,
    db_session_default,
    db_session_factory,
    db_session_for_cleanup,
    test_connection,
    transaction,
)
import pytest
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@pytest.fixture
def resilient_api_client():
    """返回带有重试逻辑的 requests Session

    配置了自动重试策略：
    - 状态码 500/502/503/504 时重试
    - 连接错误时重试
    - 最多重试 3 次
    """
    session = requests.Session()

    retry_strategy = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session

# 导出所有 fixtures
__all__ = [
    # API Client
    "config",
    "api_client",
    "api_client_with_auth",
    "resilient_api_client",
    "base_url",
    "timeout",
    "default_headers",
    "APIClient",
    "api_helper",
    # Auth
    "auth_token",
    "auth_headers",
    "authenticated_client",
    "api_key",
    "api_credentials",
    "auth_manager",
    # Database
    "db_session_factory",
    "db_session",
    "db_session_default",
    "db_config",
    "test_connection",
    "db_keys",
    "DatabaseHelper",
    "db_helper",
    "transaction",
    "db_session_for_cleanup",
    # Cleanup
    "cleanup_actions",
    "temp_dir_cleanup",
    "file_cleanup",
    "api_client_cleanup",
    "cleanup_manager",
    "test_environment_cleanup",
    "session_scope_cleanup",
]
