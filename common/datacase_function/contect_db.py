import json
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from urllib.parse import quote_plus

# 引擎缓存，支持多数据源
_ENGINE_CACHE = {}
_SESSION_FACTORY_CACHE = {}


def _load_db_config():
    """读取 app/db_config.json，返回配置字典。"""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # 项目根目录
    config_path = os.path.join(base_dir, "app", "db_config.json")
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def get_engine(db_key: str = "default"):
    """根据 db_key 获取或创建引擎。"""
    if db_key in _ENGINE_CACHE:
        return _ENGINE_CACHE[db_key]

    configs = _load_db_config()
    conf = configs.get(db_key) or {}
    db_type = conf.get("type", "mysql+pymysql")
    host = conf.get("host", "default")
    port = conf.get("port", 3306)
    db_name = conf.get("db_name", "")
    user = conf.get("user", "")
    password = conf.get("password", "")

    # 改进的数据库连接配置
    engine = create_engine(
        f"{db_type}://{user}:{quote_plus(password)}@{host}:{port}/{db_name}",
        echo=False,
        # 连接池配置
        pool_size=10,              # 连接池大小
        max_overflow=20,           # 最大溢出连接数
        pool_timeout=30,           # 获取连接的超时时间
        pool_recycle=3600,         # 连接回收时间（1小时）
        pool_pre_ping=True,        # 连接前检查连接健康状态

        # 连接超时配置
        connect_args={
            'connect_timeout': 10,     # 连接超时
            'read_timeout': 30,        # 读取超时
            'write_timeout': 30,       # 写入超时
            'autocommit': True,        # 自动提交
        }
    )
    _ENGINE_CACHE[db_key] = engine
    return engine


def get_session_factory(db_key: str = "default"):
    """获取或创建 sessionmaker。"""
    if db_key in _SESSION_FACTORY_CACHE:
        return _SESSION_FACTORY_CACHE[db_key]
    engine = get_engine(db_key)
    factory = sessionmaker(bind=engine)
    _SESSION_FACTORY_CACHE[db_key] = factory
    return factory


def test_connection(db_key: str = "default"):
    """测试数据库连接是否正常"""
    try:
        engine = get_engine(db_key)
        with engine.connect() as conn:
            result = conn.execute("SELECT 1 as test")
            row = result.fetchone()
            return row is not None and row[0] == 1
    except Exception as e:
        print(f"数据库连接测试失败 [{db_key}]: {e}")
        return False


def get_connection_status(db_key: str = "default"):
    """获取数据库连接状态信息"""
    try:
        engine = get_engine(db_key)
        pool = engine.pool

        status = {
            "db_key": db_key,
            "pool_size": getattr(pool, 'size', 0),
            "checked_in": getattr(pool, '_pool', [0, 0, 0])[1] if hasattr(pool, '_pool') else 0,
            "checked_out": getattr(pool, '_pool', [0, 0, 0])[0] if hasattr(pool, '_pool') else 0,
            "invalid": getattr(pool, '_invalid', 0) if hasattr(pool, '_invalid') else 0,
            "test_connection": test_connection(db_key)
        }

        return status
    except Exception as e:
        return {
            "db_key": db_key,
            "error": str(e),
            "test_connection": False
        }


@contextmanager
def db_session(db_key: str = "default"):
    """提供指定数据源的会话上下文。"""
    SessionLocal = get_session_factory(db_key)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()




