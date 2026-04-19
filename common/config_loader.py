"""
配置文件加载器

统一管理所有配置文件的加载，支持默认值和热重载。
"""
import json
import os
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ConfigLoader:
    """
    配置加载器单例。

    自动从 app/ 目录加载配置文件，
    支持默认值，避免配置文件缺失时崩溃。
    """

    _instance: Optional["ConfigLoader"] = None
    _config: Dict[str, Any] = {}
    _base_dir: str = ""

    def __new__(cls) -> "ConfigLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cls._instance._load_all()
        return cls._instance

    def _load_all(self) -> None:
        """加载所有配置文件"""
        self._config = {
            "api_auto_test": self._load_json("app/api_auto_test_config.json"),
        }

    def _load_json(self, rel_path: str) -> Dict[str, Any]:
        """加载 JSON 配置文件"""
        path = os.path.join(self._base_dir, rel_path)
        if not os.path.exists(path):
            logger.warning("配置文件不存在: %s", path)
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("加载配置文件失败 %s: %s", path, e)
            return {}

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点号路径，如 'test_execution.retry_times'"""
        if "." not in key:
            return self._config.get(key, default)

        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    @property
    def retry_times(self) -> int:
        """获取失败重试次数（从 api_auto_test 配置）"""
        return self.get("api_auto_test.test_execution.retry_times", 2)

    @property
    def default_timeout(self) -> int:
        """获取默认超时时间（秒）"""
        return self.get("api_auto_test.test_execution.default_timeout", 30)

    @property
    def max_concurrency(self) -> int:
        """获取最大并发数"""
        return self.get("api_auto_test.test_execution.max_concurrency", 20)

    @property
    def fail_fast(self) -> bool:
        """是否失败快速停止"""
        return self.get("api_auto_test.test_execution.fail_fast", False)

    @property
    def allure_results_dir(self) -> str:
        """Allure 结果目录"""
        return self.get("api_auto_test.storage.allure_results_dir", "outputs/allure-results")

    @property
    def generated_tests_dir(self) -> str:
        """生成的测试文件目录"""
        return self.get("api_auto_test.storage.generated_tests_dir", "outputs/generated_tests")

    @property
    def report_dir(self) -> str:
        """报告输出目录"""
        return self.get("api_auto_test.storage.report_dir", "outputs/reports")

    def get_abs_path(self, rel_path: str) -> str:
        """将相对路径转换为基于项目根目录的绝对路径"""
        return os.path.join(self._base_dir, rel_path)

    def reload(self) -> None:
        """重新加载所有配置"""
        self._load_all()
        logger.info("配置已重新加载")


# 全局单例
_config_loader: Optional[ConfigLoader] = None


def get_config() -> ConfigLoader:
    """获取配置加载器单例"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader
