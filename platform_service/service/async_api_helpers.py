"""
异步API辅助函数。

提供：
- TaskService 懒加载
- MQClient 懒加载
- 用户ID提取
- 同步降级执行
"""

import uuid
import structlog
from typing import Optional

logger = structlog.get_logger()

_mq_client = None
_task_service = None


def _get_task_service():
    """获取 TaskService 单例（延迟初始化）"""
    global _task_service
    if _task_service is None:
        try:
            import redis
            redis_client = redis.Redis(
                host="localhost",
                port=6379,
                password="pytest_sxp_2026",
                decode_responses=True,
                socket_connect_timeout=3,
            )
            redis_client.ping()

            from common.db.mapper.task_execution_mapper import TaskExecutionMapper
            from platform_service.service.task_service import TaskService

            _task_service = TaskService(redis_client, TaskExecutionMapper())
            print("[OK] TaskService initialized")
        except Exception as e:
            print(f"[WARN] TaskService init failed: {e}")
            _task_service = None
    return _task_service


def _get_mq_client():
    """获取 MQ 客户端单例"""
    global _mq_client
    if _mq_client is None:
        try:
            from platform_service.service.mq_client import get_mq_client as _get
            _mq_client = _get()
            _mq_client.connect()
        except Exception as e:
            print(f"[WARN] MQ client init failed: {e}")
            _mq_client = None
    return _mq_client


def _get_user_id(req) -> str:
    """从请求中提取用户ID"""
    return req.headers.get("X-User-ID", "anonymous")


def build_async_response(task_id: str, execution_id: str, case_count: int, status: str = "queued", message: str = ""):
    """构建异步API统一响应格式"""
    return {
        "code": 200,
        "message": message or "任务已提交",
        "data": {
            "task_id": task_id,
            "execution_id": execution_id,
            "status": status,
            "case_count": case_count,
            "query_url": f"/api/auto_test/task/{task_id}",
        }
    }
