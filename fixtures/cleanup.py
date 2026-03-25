"""
清理相关 fixtures。

提供测试环境清理和资源回收 fixtures。
"""

import logging
import os
import shutil
from typing import Any, Callable, Dict, List

import pytest
import requests

logger = logging.getLogger(__name__)


@pytest.fixture
def cleanup_actions() -> List[Callable[[], None]]:
    """
    清理动作管理器。

    提供一个列表用于注册清理动作，测试结束后逆序执行。

    Returns:
        List[Callable[[], None]]: 清理动作列表

    Example:
        def test_example(cleanup_actions):
            # 创建临时文件
            temp_file = create_temp_file()

            # 注册清理动作
            cleanup_actions.append(lambda: os.remove(temp_file))
    """
    actions: List[Callable[[], None]] = []
    yield actions

    # 逆序执行清理动作
    for action in reversed(actions):
        try:
            action()
            logger.debug("清理动作执行成功")
        except Exception as e:
            logger.warning(f"清理动作执行失败: {e}")


@pytest.fixture
def temp_dir_cleanup(tmp_path) -> List[str]:
    """
    临时目录清理管理器。

    测试结束后自动清理创建的临时目录。

    Args:
        tmp_path: pytest 提供的临时目录 fixture

    Returns:
        List[str]: 创建的临时目录列表

    Example:
        def test_example(temp_dir_cleanup):
            temp_dir = tmp_path / "test_data"
            temp_dir.mkdir()
            temp_dir_cleanup.append(str(temp_dir))
    """
    created_dirs: List[str] = []
    yield created_dirs

    for dir_path in reversed(created_dirs):
        try:
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)
                logger.debug(f"临时目录已清理: {dir_path}")
        except Exception as e:
            logger.warning(f"清理临时目录失败 {dir_path}: {e}")


@pytest.fixture
def file_cleanup() -> List[str]:
    """
    文件清理管理器。

    测试结束后清理注册的文件。

    Returns:
        List[str]: 文件路径列表

    Example:
        def test_example(file_cleanup):
            with open("test.txt", "w") as f:
                f.write("test")
            file_cleanup.append("test.txt")
    """
    files: List[str] = []
    yield files

    for file_path in reversed(files):
        try:
            if os.path.exists(file_path):
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    logger.debug(f"文件已删除: {file_path}")
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                    logger.debug(f"目录已删除: {file_path}")
        except Exception as e:
            logger.warning(f"清理文件失败 {file_path}: {e}")


@pytest.fixture
def api_client_cleanup(api_client: requests.Session) -> None:
    """
    API 客户端清理。

    测试结束后关闭 API 客户端会话。

    Args:
        api_client: API 客户端会话
    """
    yield
    try:
        api_client.close()
        logger.debug("API 客户端会话已关闭")
    except Exception as e:
        logger.warning(f"关闭 API 客户端失败: {e}")


class CleanupManager:
    """
    清理管理器。

    支持多种清理操作，包括文件、目录、网络请求等。
    """

    def __init__(self):
        """初始化清理管理器"""
        self._cleanup_actions: List[Callable[[], None]] = []

    def register(self, action: Callable[[], None]) -> None:
        """
        注册清理动作。

        Args:
            action: 清理动作函数
        """
        self._cleanup_actions.append(action)
        logger.debug("已注册清理动作")

    def cleanup(self) -> None:
        """执行所有清理动作"""
        for action in reversed(self._cleanup_actions):
            try:
                action()
                logger.debug("清理动作执行成功")
            except Exception as e:
                logger.warning(f"清理动作执行失败: {e}")
        self._cleanup_actions.clear()

    def add_file(self, file_path: str) -> None:
        """添加文件清理"""
        self.register(lambda: os.path.exists(file_path) and os.remove(file_path))

    def add_directory(self, dir_path: str) -> None:
        """添加目录清理"""
        self.register(lambda: os.path.exists(dir_path) and shutil.rmtree(dir_path))

    def add_api_call(self, method: str, url: str, **kwargs: Any) -> None:
        """添加 API 调用清理（如登出）"""
        def cleanup_call():
            try:
                requests.request(method, url, **kwargs)
                logger.debug(f"清理 API 调用完成: {method} {url}")
            except Exception as e:
                logger.warning(f"清理 API 调用失败: {e}")

        self.register(cleanup_call)


@pytest.fixture
def cleanup_manager() -> CleanupManager:
    """
    创建清理管理器实例。

    Returns:
        CleanupManager: 清理管理器实例
    """
    manager = CleanupManager()
    yield manager
    manager.cleanup()


@pytest.fixture
def test_environment_cleanup() -> Dict[str, Any]:
    """
    测试环境清理状态。

    提供一个字典用于记录需要清理的资源。

    Returns:
        Dict[str, Any]: 清理状态字典

    Example:
        def test_example(test_environment_cleanup):
            test_environment_cleanup["created_files"] = []
            test_environment_cleanup["created_dirs"] = []
    """
    state = {
        "created_files": [],
        "created_dirs": [],
        "api_calls": [],
        "db_operations": []
    }
    yield state

    # 清理文件
    for file_path in state.get("created_files", []):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"测试文件已清理: {file_path}")
        except Exception as e:
            logger.warning(f"清理测试文件失败: {e}")

    # 清理目录
    for dir_path in state.get("created_dirs", []):
        try:
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)
                logger.debug(f"测试目录已清理: {dir_path}")
        except Exception as e:
            logger.warning(f"清理测试目录失败: {e}")

    # 执行 API 清理调用
    for call_config in state.get("api_calls", []):
        try:
            method = call_config.get("method", "POST")
            url = call_config.get("url", "")
            requests.request(method, url)
            logger.debug(f"清理 API 调用完成: {method} {url}")
        except Exception as e:
            logger.warning(f"清理 API 调用失败: {e}")


@pytest.fixture
def session_scope_cleanup(request):
    """
    会话级别的清理。

    在整个测试会话结束后执行清理操作。

    Args:
        request: pytest request 对象
    """
    finalizers: List[Callable[[], None]] = []

    def add_finalizer(func: Callable[[], None]) -> None:
        """添加会话结束时的清理函数"""
        finalizers.append(func)
        request.addfinalizer(func)

    yield add_finalizer

    # 注意：实际的清理由 request.addfinalizer 处理
    logger.debug(f"注册了 {len(finalizers)} 个会话级清理函数")