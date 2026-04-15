# common/db_entity/__init__.py
# 所有实体类共享同一个 Base，避免跨文件外键解析失败
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
