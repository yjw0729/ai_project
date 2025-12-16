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
    host = conf.get("host", "localhost")
    port = conf.get("port", 3306)
    db_name = conf.get("db_name", "")
    user = conf.get("user", "")
    password = conf.get("password", "")

    engine = create_engine(
        f"{db_type}://{user}:{quote_plus(password)}@{host}:{port}/{db_name}",
        echo=False,
        pool_size=5,
        max_overflow=10,
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




