"""
TaskService：任务管理服务（双写模式）。

设计原则：
- MySQL：持久化存储，完整历史记录
- Redis：快速读写，用于实时状态查询和服务恢复
- 写入时同时更新两者，查询时优先读Redis（快）

使用场景：
- 用例生成任务：创建 → 入队 → 执行中 → 完成/失败
- 测试执行任务：创建 → 入队 → 执行中 → 进度更新 → 完成/失败
- 文档索引任务：创建 → 入队 → 执行中 → 完成/失败
"""

import json
import uuid
import structlog
from datetime import datetime
from typing import Optional, Dict, Any, List

logger = structlog.get_logger()


class TaskStatus:
    """任务状态常量"""
    PENDING = "pending"       # 等待中
    QUEUED = "queued"         # 已入队列
    RUNNING = "running"       # 执行中
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"         # 失败
    CANCELLED = "cancelled"   # 已取消
    RETRYING = "retrying"     # 重试中


class TaskService:
    """
    任务管理服务。

    提供方法：
    - create_task: 创建新任务（双写 MySQL + Redis）
    - update_status: 更新任务状态（双写）
    - get_status: 查询任务状态（优先 Redis，降级 MySQL）
    - get_user_tasks: 获取用户所有任务
    - cancel_task: 取消任务
    """

    def __init__(self, redis_client, task_mapper):
        self.redis = redis_client
        self.mapper = task_mapper

    def create_task(
        self,
        user_id: str,
        task_type: str,
        payload: Dict[str, Any],
        description: str = "",
        priority: int = 5,
        trace_id: str = "",
        max_retries: int = 3,
    ) -> str:
        task_id = str(uuid.uuid4())

        self.mapper.create({
            "task_id": task_id,
            "user_id": user_id,
            "task_type": task_type,
            "description": description,
            "priority": priority,
            "payload": payload,
            "trace_id": trace_id,
            "max_retries": max_retries,
        })

        redis_key = f"task:{user_id}:{task_id}"
        self.redis.hset(redis_key, mapping={
            "status": TaskStatus.PENDING,
            "task_type": task_type,
            "created_time": datetime.now().isoformat(),
            "progress": "0",
            "trace_id": trace_id,
        })
        self.redis.expire(redis_key, 86400)

        self.redis.zadd(f"user_tasks:{user_id}", {task_id: datetime.now().timestamp()})
        self.redis.sadd("tasks:pending", task_id)

        logger.info("任务已创建",
            task_id=task_id,
            user_id=user_id,
            task_type=task_type,
            description=description
        )

        return task_id

    def update_status(
        self,
        task_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        progress: Optional[str] = None,
        error_message: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> bool:
        mysql_ok = self.mapper.update_status(
            task_id=task_id,
            status=status,
            result=result,
            error_message=error_message,
            progress=progress,
        )

        if not mysql_ok:
            logger.warning("MySQL更新失败，任务可能不存在", task_id=task_id)

        redis_key = self._find_task_redis_key(task_id)
        if redis_key:
            redis_update = {
                "status": status,
                "updated_time": datetime.now().isoformat(),
            }
            if progress:
                redis_update["progress"] = progress
            if result:
                redis_update["result_summary"] = json.dumps(result)
            if error_message:
                redis_update["error"] = error_message
            self.redis.hset(redis_key, mapping=redis_update)

            if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                self.redis.srem("tasks:pending", task_id)
                self.redis.srem("tasks:running", task_id)

        return mysql_ok

    def get_status(self, task_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        redis_key = f"task:{user_id}:{task_id}"
        redis_data = self.redis.hgetall(redis_key)

        if redis_data and redis_data.get("status"):
            return {
                "task_id": task_id,
                "user_id": user_id,
                "status": redis_data.get("status", TaskStatus.PENDING),
                "task_type": redis_data.get("task_type"),
                "progress": redis_data.get("progress", "0"),
                "trace_id": redis_data.get("trace_id"),
                "result_summary": json.loads(redis_data.get("result_summary", "{}")) if redis_data.get("result_summary") else None,
                "error": redis_data.get("error"),
                "created_time": redis_data.get("created_time"),
                "updated_time": redis_data.get("updated_time"),
            }

        mysql_data = self.mapper.get_by_task_id(task_id)
        if mysql_data and mysql_data.get("user_id") == user_id:
            redis_key = f"task:{user_id}:{task_id}"
            self.redis.hset(redis_key, mapping={
                "status": mysql_data.get("status", TaskStatus.PENDING),
                "task_type": mysql_data.get("task_type"),
                "progress": mysql_data.get("progress", "0"),
                "trace_id": mysql_data.get("trace_id", ""),
                "created_time": str(mysql_data.get("created_time", "")),
            })
            self.redis.expire(redis_key, 86400)
            return mysql_data

        return None

    def get_user_tasks(
        self,
        user_id: str,
        status_filter: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        task_ids = self.redis.zrevrange(f"user_tasks:{user_id}", 0, limit - 1)

        tasks = []
        for task_id in task_ids:
            task = self.get_status(task_id, user_id)
            if task:
                if status_filter is None or task["status"] in status_filter:
                    tasks.append(task)

        return tasks

    def cancel_task(self, task_id: str, user_id: str) -> bool:
        current = self.get_status(task_id, user_id)
        if not current:
            return False

        cancellable = (TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.RETRYING)
        if current["status"] not in cancellable:
            logger.warning("任务无法取消（状态不允许）",
                task_id=task_id,
                current_status=current["status"]
            )
            return False

        self.update_status(task_id, TaskStatus.CANCELLED, progress="cancelled")
        logger.info("任务已取消", task_id=task_id, user_id=user_id)
        return True

    def get_pending_tasks(self, limit: int = 100) -> List[Dict[str, Any]]:
        task_ids = self.redis.smembers("tasks:pending")
        tasks = []
        for task_id in list(task_ids)[:limit]:
            record = self.mapper.get_by_task_id(task_id)
            if record:
                tasks.append(record)
        return tasks

    def _find_task_redis_key(self, task_id: str) -> Optional[str]:
        record = self.mapper.get_by_task_id(task_id)
        if record:
            return f"task:{record['user_id']}:{task_id}"
        return None
