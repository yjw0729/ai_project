"""
API自动化测试 - Fixtures管理器
"""

import logging
from typing import Any, Callable, Dict, Optional
import requests

logger = logging.getLogger(__name__)


class FixtureManager:
    """
    Fixtures管理器。

    内置Fixtures：
    - env_config: 加载环境配置
    - api_client: 创建API客户端（requests.Session）
    - auth_token: 获取认证Token
    - test_data: 加载测试数据
    - db_connection: 数据库连接

    支持注册自定义Fixtures。
    """

    BUILTIN_FIXTURES = {
        "env_config": "_load_env_config",
        "api_client": "_create_api_client",
        "auth_token": "_get_auth_token",
        "test_data": "_load_test_data",
        "db_connection": "_get_db_connection",
    }

    def __init__(self):
        self._fixtures: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}

    def register_fixture(self, name: str, factory_func: Callable) -> None:
        """注册自定义fixture工厂函数"""
        self._factories[name] = factory_func
        logger.info("【FixtureManager】已注册自定义fixture: %s", name)

    def get_fixture(self, name: str, **kwargs: Any) -> Any:
        """获取fixture实例（懒加载）"""
        if name not in self._fixtures:
            if name in self._factories:
                self._fixtures[name] = self._factories[name](**kwargs)
            elif name in self.BUILTIN_FIXTURES:
                factory_method = getattr(self, self.BUILTIN_FIXTURES[name], None)
                if factory_method:
                    self._fixtures[name] = factory_method(**kwargs)
                else:
                    raise ValueError(f"内置fixture {name} 的工厂方法未找到")
            else:
                raise ValueError(f"未知的fixture: {name}")
            logger.debug("【FixtureManager】获取fixture: %s", name)

        return self._fixtures[name]

    def set_fixture(self, name: str, instance: Any) -> None:
        """直接设置fixture实例（不经过工厂）"""
        self._fixtures[name] = instance

    def _load_env_config(self, env_id: Optional[int] = None, **kwargs: Any) -> Dict[str, Any]:
        """加载环境配置"""
        if env_id is None:
            return {}
        try:
            from common.db_mapper.environment_config_mapper import EnvironmentConfigMapper
            mapper = EnvironmentConfigMapper()
            env = mapper.get_by_id(env_id)
            if env:
                return env.to_json() if hasattr(env, "to_json") else {}
        except Exception as e:
            logger.warning("【FixtureManager】加载环境配置失败: %s", str(e))
        return {}

    def _create_api_client(self, env_config: Optional[Dict[str, Any]] = None, **kwargs: Any) -> requests.Session:
        """创建API客户端"""
        session = requests.Session()
        if env_config and isinstance(env_config, dict):
            headers = env_config.get("headers", {})
            if headers:
                session.headers.update(headers)
            base_url = env_config.get("base_url", "")
            if base_url:
                session.base_url = base_url
        logger.debug("【FixtureManager】创建API客户端完成")
        return session

    def _get_auth_token(self, env_config: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Optional[str]:
        """获取认证Token（根据环境配置中的认证信息）"""
        if env_config and isinstance(env_config, dict):
            return env_config.get("auth_token") or env_config.get("token")
        return None

    def _load_test_data(self, data_file: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
        """加载测试数据文件"""
        if data_file:
            import json
            import os
            try:
                if os.path.isfile(data_file):
                    with open(data_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
            except Exception as e:
                logger.warning("【FixtureManager】加载测试数据失败: %s", str(e))
        return {}

    def _get_db_connection(self, **kwargs: Any) -> Any:
        """获取数据库连接"""
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from common.db_enitiy.base import Base
            from app.db_config import DB_CONFIG

            engine = create_engine(DB_CONFIG.get("url", ""), pool_pre_ping=True)
            Session = sessionmaker(bind=engine)
            return Session()
        except Exception as e:
            logger.warning("【FixtureManager】获取数据库连接失败: %s", str(e))
            return None

    def cleanup(self) -> None:
        """清理所有fixtures"""
        for name, fixture in self._fixtures.items():
            try:
                if hasattr(fixture, "close"):
                    fixture.close()
                elif hasattr(fixture, "cleanup"):
                    fixture.cleanup()
            except Exception as e:
                logger.warning("【FixtureManager】清理fixture %s 失败: %s", name, str(e))
        self._fixtures.clear()
        logger.info("【FixtureManager】所有fixtures已清理")
