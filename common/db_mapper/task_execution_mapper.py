"""
TaskExecution 任务记录表的数据访问层。
支持任务的全生命周期管理。
"""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from common.datacase_function.contect_db import db_session


class TaskExecutionMapper:
    """TaskExecution表的数据访问类"""

    def __init__(self, db_key: str = "default"):
        self.db_key = db_key

    @contextmanager
    def session_scope(self):
        with db_session(self.db_key) as session:
            yield session

    def create(self, task_data: Dict[str, Any]) -> int:
        with self.session_scope() as session:
            from common.db_enitiy.task_execution import TaskExecution

            entity = TaskExecution(
                task_id=task_data["task_id"],
                user_id=task_data["user_id"],
                task_type=task_data["task_type"],
                description=task_data.get("description", ""),
                priority=task_data.get("priority", 5),
                payload=json.dumps(task_data.get("payload", {})),
                status="pending",
                trace_id=task_data.get("trace_id", ""),
                created_by=task_data.get("user_id", "anonymous"),
                updated_by=task_data.get("user_id", "anonymous"),
            )

            session.add(entity)
            session.flush()
            return entity.id

    def get_by_task_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self.session_scope() as session:
            from common.db_enitiy.task_execution import TaskExecution
            entity = session.query(TaskExecution).filter(
                TaskExecution.task_id == task_id
            ).first()

            if entity:
                return self._entity_to_dict(entity)
            return None

    def get_by_user(
        self,
        user_id: str,
        status_filter: Optional[List[str]] = None,
        task_type_filter: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        with self.session_scope() as session:
            from common.db_enitiy.task_execution import TaskExecution
            query = session.query(TaskExecution).filter(
                TaskExecution.user_id == user_id
            )

            if status_filter:
                query = query.filter(TaskExecution.status.in_(status_filter))
            if task_type_filter:
                query = query.filter(TaskExecution.task_type.in_(task_type_filter))

            entities = query.order_by(TaskExecution.created_time.desc()).limit(limit).all()
            return [self._entity_to_dict(e) for e in entities]

    def update_status(
        self,
        task_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        progress: Optional[str] = None,
    ) -> bool:
        with self.session_scope() as session:
            from common.db_enitiy.task_execution import TaskExecution
            entity = session.query(TaskExecution).filter(
                TaskExecution.task_id == task_id
            ).first()

            if not entity:
                return False

            entity.status = status

            if status == "queued":
                entity.queued_time = datetime.now()
            elif status == "running":
                entity.started_time = datetime.now()
            elif status in ("completed", "failed", "cancelled"):
                entity.finished_time = datetime.now()

            if result is not None:
                entity.result = json.dumps(result)

            if error_code is not None:
                entity.error_code = error_code

            if error_message is not None:
                entity.error_message = error_message

            if progress is not None:
                entity.progress = progress

            entity.updated_by = "system"

            session.flush()
            return True

    def increment_retry(self, task_id: str) -> int:
        with self.session_scope() as session:
            from common.db_enitiy.task_execution import TaskExecution
            entity = session.query(TaskExecution).filter(
                TaskExecution.task_id == task_id
            ).first()

            if entity:
                entity.retry_count = (entity.retry_count or 0) + 1
                session.flush()
                return entity.retry_count
            return 0

    def get_retry_count(self, task_id: str) -> int:
        record = self.get_by_task_id(task_id)
        return (record or {}).get("retry_count", 0) if record else 0

    def _entity_to_dict(self, entity) -> Dict[str, Any]:
        result = {}
        for col in ["id", "task_id", "user_id", "task_type", "description",
                    "priority", "payload", "status", "result", "error_code", "error_message",
                    "retry_count", "max_retries", "trace_id", "created_time",
                    "queued_time", "started_time", "finished_time", "progress",
                    "created_by", "updated_by"]:
            if hasattr(entity, col):
                value = getattr(entity, col)
                if col in ("payload", "result") and value:
                    try:
                        value = json.loads(value) if isinstance(value, str) else value
                    except Exception:
                        pass
                result[col] = value
        return result
