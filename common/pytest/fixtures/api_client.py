"""
API 客户端相关 fixtures。

提供 API 请求客户端的创建和配置 fixtures。
"""

import logging
import os
from typing import Any, Dict, Optional

import requests
import pytest

logger = logging.getLogger(__name__)


def _load_config() -> Dict[str, Any]:
    """加载配置文件。"""
    import json

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_path = os.path.join(base_dir, "app", "ai_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@pytest.fixture
def config() -> Dict[str, Any]:
    """
    加载应用配置。

    Returns:
        Dict[str, Any]: 配置字典，包含 base_url, api_key 等信息
    """
    return _load_config()


@pytest.fixture
def api_client(config: Optional[Dict[str, Any]] = None) -> requests.Session:
    """
    创建并配置 API 客户端会话。

    Args:
        config: 可选的配置字典，如果提供则使用其中的配置

    Returns:
        requests.Session: 配置好的请求会话对象
    """
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Accept": "application/json"
    })

    if config and isinstance(config, dict):
        base_url = config.get("base_url")
        if base_url:
            session.base_url = base_url
            logger.debug(f"API客户端已配置base_url: {base_url}")

    logger.info("API客户端会话已创建")
    return session


@pytest.fixture
def api_client_with_auth(
    api_client: requests.Session,
    config: Dict[str, Any]
) -> requests.Session:
    """
    创建带有认证的 API 客户端。

    Args:
        api_client: 基础 API 客户端
        config: 包含认证信息的配置

    Returns:
        requests.Session: 带有认证头部的会话对象
    """
    api_key = config.get("api_key")
    if api_key:
        api_client.headers.update({"Authorization": f"Bearer {api_key}"})
        logger.info("API客户端已添加认证信息")

    return api_client


@pytest.fixture
def base_url(config: Dict[str, Any]) -> str:
    """
    获取 API 基础 URL。

    Args:
        config: 配置字典

    Returns:
        str: 基础 URL 地址
    """
    return config.get("base_url", "")


@pytest.fixture
def timeout() -> int:
    """
    获取默认请求超时时间。

    Returns:
        int: 超时时间（秒）
    """
    return 30


@pytest.fixture
def default_headers() -> Dict[str, str]:
    """
    获取默认请求头。

    Returns:
        Dict[str, str]: 默认请求头字典
    """
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "pytest-api-client/1.0"
    }


class APIClient:
    """
    API 客户端封装类。

    提供更高级的 API 调用方法，支持多种 HTTP 方法。
    """

    def __init__(self, session: requests.Session, base_url: str = ""):
        """
        初始化 API 客户端。

        Args:
            session: requests.Session 实例
            base_url: 基础 URL 地址
        """
        self.session = session
        self.base_url = base_url

    def request(
        self,
        method: str,
        path: str,
        **kwargs: Any
    ) -> requests.Response:
        """
        发起 API 请求。

        Args:
            method: HTTP 方法（GET, POST, PUT, DELETE 等）
            path: 请求路径
            **kwargs: 其他传递给 requests 的参数

        Returns:
            requests.Response: 响应对象
        """
        url = f"{self.base_url}{path}" if not path.startswith("http") else path
        return self.session.request(method, url, **kwargs)

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        """GET 请求"""
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        """POST 请求"""
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> requests.Response:
        """PUT 请求"""
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> requests.Response:
        """DELETE 请求"""
        return self.request("DELETE", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> requests.Response:
        """PATCH 请求"""
        return self.request("PATCH", path, **kwargs)


@pytest.fixture
def api_helper(api_client: requests.Session, base_url: str) -> APIClient:
    """
    创建 API 客户端辅助类实例。

    Args:
        api_client: requests 会话对象
        base_url: 基础 URL

    Returns:
        APIClient: API 客户端辅助类实例
    """
    return APIClient(api_client, base_url)