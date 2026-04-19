"""
数据库相关 fixtures。

提供数据库连接、会话管理和数据库操作 fixtures。
"""

import logging
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

import pytest
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _import_db_session():
    """导入数据库会话管理器。"""
    try:
        from common.db.datacase.contect_db import db_session
        return db_session
    except ImportError as e:
        logger.warning(f"无法导入 db_session: {e}")
        return None


@pytest.fixture(scope="session")
def db_session_factory():
    """
    获取数据库会话工厂函数。

    Returns:
        可调用函数: db_session 上下文管理器
    """
    db_session = _import_db_session()
    if db_session is None:
        pytest.skip("数据库会话模块不可用")
    return db_session


@pytest.fixture(scope="function")
def db_session(db_session_factory) -> Generator[Session, None, None]:
    """
    提供数据库会话。

    使用上下文管理器管理数据库会话，自动处理提交和回滚。

    Args:
        db_session_factory: 数据库会话工厂函数

    Yields:
        Session: SQLAlchemy 会话对象

    Example:
        def test_example(db_session):
            result = db_session.execute("SELECT 1")
    """
    with db_session_factory() as session:
        yield session
        logger.debug("数据库会话已关闭")


@pytest.fixture(scope="function")
def db_session_default(db_session_factory) -> Generator[Session, None, None]:
    """
    使用默认数据源的数据库会话。

    Args:
        db_session_factory: 数据库会话工厂函数

    Yields:
        Session: SQLAlchemy 会话对象
    """
    with db_session_factory(db_key="default") as session:
        yield session


@pytest.fixture(scope="session")
def db_config() -> Dict[str, Any]:
    """
    获取数据库配置信息。

    Returns:
        Dict[str, Any]: 数据库配置字典
    """
    import json
    import os

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_path = os.path.join(base_dir, "app", "db_config.json")

    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@pytest.fixture
def test_connection(db_session: Session) -> bool:
    """
    测试数据库连接是否正常。

    Args:
        db_session: 数据库会话

    Returns:
        bool: 连接是否正常
    """
    try:
        result = db_session.execute("SELECT 1")
        return result.fetchone()[0] == 1
    except Exception as e:
        logger.error(f"数据库连接测试失败: {e}")
        return False


@pytest.fixture
def db_keys(db_config: Dict[str, Any]) -> List[str]:
    """
    获取所有配置的数据库键。

    Args:
        db_config: 数据库配置字典

    Returns:
        List[str]: 数据库键列表
    """
    return list(db_config.keys())


class DatabaseHelper:
    """
    数据库操作辅助类。

    提供常用的数据库操作方法。
    """

    def __init__(self, session: Session):
        """
        初始化数据库辅助类。

        Args:
            session: SQLAlchemy 会话对象
        """
        self.session = session

    def execute_query(self, query: str, params: Optional[Dict] = None) -> List[Any]:
        """
        执行查询语句。

        Args:
            query: SQL 查询语句
            params: 查询参数

        Returns:
            List[Any]: 查询结果列表
        """
        result = self.session.execute(query, params or {})
        return result.fetchall()

    def execute_update(self, query: str, params: Optional[Dict] = None) -> int:
        """
        执行更新语句。

        Args:
            query: SQL 更新语句
            params: 更新参数

        Returns:
            int: 影响的行数
        """
        result = self.session.execute(query, params or {})
        self.session.commit()
        return result.rowcount

    def insert(self, table: str, data: Dict[str, Any]) -> Any:
        """
        插入数据。

        Args:
            table: 表名
            data: 要插入的数据字典

        Returns:
            插入的记录 ID
        """
        columns = ", ".join(data.keys())
        placeholders = ", ".join([f":{key}" for key in data.keys()])
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        result = self.session.execute(query, data)
        self.session.commit()
        return result.lastrowid

    def delete(self, table: str, where: str, params: Optional[Dict] = None) -> int:
        """
        删除数据。

        Args:
            table: 表名
            where: WHERE 条件
            params: 查询参数

        Returns:
            int: 删除的行数
        """
        query = f"DELETE FROM {table} WHERE {where}"
        result = self.session.execute(query, params or {})
        self.session.commit()
        return result.rowcount


@pytest.fixture
def db_helper(db_session: Session) -> DatabaseHelper:
    """
    创建数据库操作辅助类实例。

    Args:
        db_session: 数据库会话

    Returns:
        DatabaseHelper: 数据库辅助类实例
    """
    return DatabaseHelper(db_session)


@pytest.fixture
def transaction(db_session: Session) -> Generator[Session, None, None]:
    """
    提供事务上下文。

    在测试结束后自动回滚事务，保证测试隔离性。

    Args:
        db_session: 数据库会话

    Yields:
        Session: 事务中的会话对象
    """
    transaction = db_session.begin_nested()
    yield db_session
    transaction.rollback()
    logger.debug("事务已回滚")


@pytest.fixture(scope="function")
def db_session_for_cleanup(db_session_factory) -> Generator[Session, None, None]:
    """
    用于清理操作的数据库会话。

    在测试结束后会提交更改。

    Args:
        db_session_factory: 数据库会话工厂函数

    Yields:
        Session: SQLAlchemy 会话对象
    """
    with db_session_factory() as session:
        yield session
        try:
            session.commit()
            logger.debug("数据库更改已提交")
        except Exception as e:
            session.rollback()
            logger.error(f"提交失败，已回滚: {e}")