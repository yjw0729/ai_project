"""
Task poller for database-backed task queue.
"""

import sqlite3
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from common.models.task import Task, TaskStatus, TaskType


class TaskPoller:
    """Polls pending tasks from the database and manages task lifecycle."""

    def __init__(
        self,
        db_path: str,
        poll_interval: float = 0.1,
        on_task_callback: Optional[Callable[[Task], None]] = None,
    ):
        self.db_path = db_path
        self.poll_interval = poll_interval
        self.on_task_callback = on_task_callback
        self._running = False
        self._lock = threading.Lock()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=30)

    def is_running(self) -> bool:
        return self._running

    def start(self):
        self._running = True

    def stop(self):
        self._running = False

    def create_task(
        self,
        task_type: str,
        params: Optional[Dict[str, Any]] = None,
        document_id: Optional[int] = None,
        interface_ids: Optional[List[int]] = None,
    ) -> str:
        import json

        task_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        conn = self._conn()
        conn.execute(
            """
            INSERT INTO tasks
            (task_id, task_type, status, params, document_id, interface_ids,
             progress, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                task_id,
                task_type,
                TaskStatus.PENDING.value,
                json.dumps(params or {}),
                document_id,
                json.dumps(interface_ids) if interface_ids else None,
                now,
                now,
            ),
        )
        conn.commit()
        conn.close()
        return task_id

    def get_task(self, task_id: str) -> Optional[Task]:
        conn = self._conn()
        cur = conn.execute(
            """
            SELECT task_id, task_type, status, params, document_id, interface_ids,
                   result, error_message, progress, created_at, updated_at, completed_at
            FROM tasks WHERE task_id = ?
            """,
            (task_id,),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        columns = [
            'task_id', 'task_type', 'status', 'params', 'document_id', 'interface_ids',
            'result', 'error_message', 'progress', 'created_at', 'updated_at', 'completed_at',
        ]
        return Task.from_row(row, columns)

    def get_task_list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        import math

        conn = self._conn()
        base_query = "FROM tasks"
        params: List[Any] = []

        if status:
            base_query += " WHERE status = ?"
            params.append(status)

        cur = conn.execute(f"SELECT COUNT(*) {base_query}", params)
        total = cur.fetchone()[0]

        offset = (page - 1) * page_size
        cur = conn.execute(
            f"""
            SELECT task_id, task_type, status, params, document_id, interface_ids,
                   result, error_message, progress, created_at, updated_at, completed_at
            {base_query}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        )
        rows = cur.fetchall()
        conn.close()

        columns = [
            'task_id', 'task_type', 'status', 'params', 'document_id', 'interface_ids',
            'result', 'error_message', 'progress', 'created_at', 'updated_at', 'completed_at',
        ]
        tasks = [Task.from_row(r, columns).to_dict() for r in rows]
        return {
            'tasks': tasks,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': math.ceil(total / page_size) if total else 0,
        }

    def poll_pending_task(self) -> Optional[Task]:
        import json

        conn = self._conn()
        now = datetime.now().isoformat()
        cur = conn.execute(
            """
            SELECT task_id, task_type, status, params, document_id, interface_ids,
                   result, error_message, progress, created_at, updated_at, completed_at
            FROM tasks
            WHERE status = ?
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (TaskStatus.PENDING.value,),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None

        columns = [
            'task_id', 'task_type', 'status', 'params', 'document_id', 'interface_ids',
            'result', 'error_message', 'progress', 'created_at', 'updated_at', 'completed_at',
        ]
        task = Task.from_row(row, columns)

        # Atomically mark as PROCESSING
        conn2 = self._conn()
        conn2.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
            (TaskStatus.PROCESSING.value, now, task.task_id),
        )
        conn2.commit()
        conn2.close()

        task.status = TaskStatus.PROCESSING
        return task

    def update_task_status(
        self,
        task_id: str,
        status: str,
        progress: Optional[int] = None,
        result: Optional[Any] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        import json

        conn = self._conn()
        now = datetime.now().isoformat()
        completed_at = now if status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value) else None

        fields = ["status = ?", "updated_at = ?"]
        values: List[Any] = [status, now]

        if progress is not None:
            fields.append("progress = ?")
            values.append(progress)
        if result is not None:
            fields.append("result = ?")
            values.append(json.dumps(result))
        if error_message is not None:
            fields.append("error_message = ?")
            values.append(error_message)
        if completed_at:
            fields.append("completed_at = ?")
            values.append(completed_at)

        values.append(task_id)
        conn.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE task_id = ?", values)
        conn.commit()
        changes = conn.total_changes
        conn.close()
        return changes > 0

    # ------------------------------------------------------------------
    # Required interface methods (for common.worker compatibility)
    # ------------------------------------------------------------------

    def poll(self) -> Optional[Task]:
        """
        Alias for poll_pending_task — fetch and claim the next pending task.

        Returns:
            A Task instance if one is available and successfully claimed,
            otherwise None.
        """
        return self.poll_pending_task()

    def claim_task(self, task_id: str) -> bool:
        """
        Atomically claim a specific task for execution.

        Returns:
            True if the task was successfully claimed (it was PENDING);
            False if it was already claimed or does not exist.
        """
        with self._lock:
            conn = self._conn()
            now = datetime.now().isoformat()
            try:
                cur = conn.execute(
                    "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ? AND status = ?",
                    (TaskStatus.PROCESSING.value, now, task_id, TaskStatus.PENDING.value),
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    def get_pending_tasks(self, limit: int = 10) -> List[Task]:
        """
        Retrieve pending/processing tasks without claiming them.

        Args:
            limit: Maximum number of tasks to return.

        Returns:
            List of Task objects (may be empty).
        """
        conn = self._conn()
        cur = conn.execute(
            """
            SELECT task_id, task_type, status, params, document_id, interface_ids,
                   result, error_message, progress, created_at, updated_at, completed_at
            FROM tasks
            WHERE status IN (?, ?)
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (TaskStatus.PENDING.value, TaskStatus.PROCESSING.value, limit),
        )
        rows = cur.fetchall()
        conn.close()

        columns = [
            "task_id", "task_type", "status", "params", "document_id", "interface_ids",
            "result", "error_message", "progress", "created_at", "updated_at", "completed_at",
        ]
        return [Task.from_row(r, columns) for r in rows]
