"""
认证相关 fixtures。

提供认证 Token 获取和管理 fixtures。
"""

import logging
from typing import Any, Dict, Optional

import requests
import pytest

logger = logging.getLogger(__name__)


@pytest.fixture
def auth_token(api_client: requests.Session, config: Dict[str, Any]) -> str:
    """
    获取认证 Token。

    根据配置中的认证信息获取访问令牌。
    如果配置中有 token 则直接返回，否则尝试调用登录接口获取。

    Args:
        api_client: API 客户端会话
        config: 应用配置字典

    Returns:
        str: 认证 Token 字符串
    """
    # 首先检查配置中是否已有 token
    existing_token = config.get("auth_token") or config.get("token")
    if existing_token:
        logger.info("从配置中获取到已有 Token")
        return existing_token

    # 检查是否有登录接口配置
    login_path = config.get("login_path", "/api/v1/login")
    auth_config = config.get("auth", {})

    if auth_config:
        try:
            response = api_client.post(login_path, json=auth_config)
            if response.status_code == 200:
                data = response.json()
                token = data.get("token") or data.get("access_token")
                if token:
                    logger.info("成功通过登录接口获取 Token")
                    return token
        except Exception as e:
            logger.warning(f"获取 Token 失败: {e}")

    # 如果无法获取 Token，返回空字符串
    logger.warning("未能获取有效的认证 Token")
    return ""


@pytest.fixture
def auth_headers(auth_token: str) -> Dict[str, str]:
    """
    获取认证请求头。

    Args:
        auth_token: 认证 Token

    Returns:
        Dict[str, str]: 包含认证信息的请求头
    """
    if auth_token:
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    return {"Content-Type": "application/json"}


@pytest.fixture
def authenticated_client(
    api_client: requests.Session,
    auth_token: str
) -> requests.Session:
    """
    创建已认证的 API 客户端。

    Args:
        api_client: 基础 API 客户端
        auth_token: 认证 Token

    Returns:
        requests.Session: 带有认证信息的会话对象
    """
    if auth_token:
        api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
        logger.info("已为 API 客户端添加认证信息")

    return api_client


@pytest.fixture
def api_key(config: Dict[str, Any]) -> Optional[str]:
    """
    获取 API Key。

    Args:
        config: 应用配置

    Returns:
        Optional[str]: API Key 字符串，如果不存在则返回 None
    """
    return config.get("api_key")


@pytest.fixture
def api_credentials(config: Dict[str, Any]) -> Dict[str, str]:
    """
    获取 API 凭证信息。

    Args:
        config: 应用配置

    Returns:
        Dict[str, str]: 包含 api_key 和 base_url 的字典
    """
    return {
        "api_key": config.get("api_key", ""),
        "base_url": config.get("base_url", ""),
        "model": config.get("model", "")
    }


class AuthManager:
    """
    认证管理器。

    提供 Token 刷新、过期检测等认证管理功能。
    """

    def __init__(self, token: str = ""):
        """
        初始化认证管理器。

        Args:
            token: 初始 Token
        """
        self._token = token

    @property
    def token(self) -> str:
        """获取当前 Token"""
        return self._token

    @token.setter
    def token(self, value: str) -> None:
        """设置新 Token"""
        self._token = value
        logger.info("Token 已更新")

    def is_valid(self) -> bool:
        """
        检查 Token 是否有效。

        Returns:
            bool: Token 是否有效
        """
        return bool(self._token)

    def refresh(self, new_token: str) -> None:
        """
        刷新 Token。

        Args:
            new_token: 新的 Token 字符串
        """
        self.token = new_token

    def clear(self) -> None:
        """清除 Token"""
        self._token = ""
        logger.info("Token 已清除")


@pytest.fixture
def auth_manager(auth_token: str) -> AuthManager:
    """
    创建认证管理器实例。

    Args:
        auth_token: 初始 Token

    Returns:
        AuthManager: 认证管理器实例
    """
    return AuthManager(auth_token)