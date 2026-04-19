"""
Alembic 迁移环境配置

连接 `app/db_config.json` 中的 default 数据源。
"""
from logging.config import fileConfig
import os
import sys

from sqlalchemy import engine_from_config, pool
from alembic import context

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Alembic Config
config = context.config

# 读取项目数据库配置
from common.db.datacase.contect_db import _load_db_config

db_configs = _load_db_config()
db_conf = db_configs.get("default", {})
db_type = db_conf.get("type", "mysql+pymysql")
host = db_conf.get("host", "localhost")
port = db_conf.get("port", 3306)
db_name = db_conf.get("db_name", "")
user = db_conf.get("user", "")
password = db_conf.get("password", "")

from urllib.parse import quote_plus
sqlalchemy_url = (
    f"{db_type}://{user}:{quote_plus(password)}@{host}:{port}/{db_name}"
)
config.set_main_option("sqlalchemy.url", sqlalchemy_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from common.db.entity import Base

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 脚本而非直接执行迁移"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：直接连接数据库执行迁移"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
