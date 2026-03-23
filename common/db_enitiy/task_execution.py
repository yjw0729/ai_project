"""
TaskExecution 任务执行记录实体类。
"""

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.sql import func

Base = declarative_base()


class TaskExecution(Base):
    """任务执行记录表实体类"""
    __tablename__ = 'crosstest_task_execution'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(100), nullable=False, unique=True)
    user_id = Column(String(50), nullable=False)
    task_type = Column(String(50), nullable=False)
    description = Column(String(500))
    priority = Column(Integer, default=5)
    payload = Column(JSON)
    status = Column(String(20), nullable=False, default='pending')
    result = Column(JSON)
    error_code = Column(String(50))
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    trace_id = Column(String(100))
    created_time = Column(DateTime, server_default=func.now())
    queued_time = Column(DateTime)
    started_time = Column(DateTime)
    finished_time = Column(DateTime)
    progress = Column(String(50), default='0')
    created_by = Column(String(50))
    updated_by = Column(String(50))
