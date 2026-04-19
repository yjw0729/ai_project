"""
Task processor that dispatches tasks to registered handlers.
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from common.models.task import Task, TaskStatus, TaskType

logger = logging.getLogger(__name__)


class TaskProcessor:
    """
    Processes a Task based on its type and updates the database.

    Compatible with the interface expected by common.worker.
    """

    def __init__(self, worker_id: int, db_path: str = "./db/task.db"):
        self.worker_id = worker_id
        self.db_path = db_path
        self._lock = threading.Lock()
        self._handlers: Dict[str, Callable[..., Dict[str, Any]]] = {
            "document_parse": self._handle_document_parse,
            "case_generate": self._handle_case_generate,
            "iteration_parse": self._handle_iteration_parse,
            "page_case_generate": self._handle_page_case_generate,
        }
        self._processing_tasks: Dict[str, datetime] = {}

    def register_handler(self, task_type: str, handler: Callable[..., Dict[str, Any]]):
        self._handlers[task_type] = handler

    def is_processing(self, task_id: str) -> bool:
        return task_id in self._processing_tasks

    def process(self, task: Task) -> Dict[str, Any]:
        """
        Dispatch a task to the appropriate handler based on its type.

        Args:
            task: The Task object to process.

        Returns:
            A result dict describing the outcome.
        """
        task_id = task.id
        task_type = task.task_type
        params = task.payload or {}

        self._processing_tasks[task_id] = datetime.now()

        try:
            # Map TaskType enum to handler key
            handler_key_map = {
                TaskType.DOCUMENT_PARSING: "document_parse",
                TaskType.TEST_CASE_GENERATION: "case_generate",
            }
            handler_key = handler_key_map.get(task_type, task_type.value if hasattr(task_type, "value") else str(task_type))
            handler = self._handlers.get(handler_key)

            if not handler:
                return {
                    "success": False,
                    "error": f"未注册的任务类型: {handler_key}",
                    "task_id": task_id,
                }

            # Convert Task to dict format for handler compatibility
            task_dict = {
                "task_id": task_id,
                "task_type": handler_key,
                "params": params,
            }
            result = handler(task_dict)

            self.update_task_status(task_id, TaskStatus.COMPLETED, result=result)
            return {
                "success": True,
                "result": result,
                "task_id": task_id,
            }

        except Exception as e:
            logger.error(f"Worker-{self.worker_id} task {task_id} failed: {e}", exc_info=True)
            self.update_task_status(task_id, TaskStatus.FAILED, error=str(e))
            return {
                "success": False,
                "error": str(e),
                "task_id": task_id,
            }
        finally:
            self._processing_tasks.pop(task_id, None)

    def process_test_case_generation(self, task: Task) -> Dict[str, Any]:
        """Handle test-case generation tasks."""
        generator = self._services.get("case_generator")
        interface_info = task.payload.get("interface_info", {})
        options = task.payload.get("options", {})
        if generator:
            cases = generator.generate(
                interface_info=interface_info,
                options=options,
            )
        else:
            cases = []
        return {
            "test_cases": cases,
            "count": len(cases),
        }

    def process_api_test(self, task: Task) -> Dict[str, Any]:
        """Handle API test execution tasks."""
        return {
            "task_id": task.id,
            "executed_count": 0,
            "status": "skipped",
            "message": "API test execution not yet implemented",
        }

    def process_document_parsing(self, task: Task) -> Dict[str, Any]:
        """Handle document parsing tasks."""
        parser = self._services.get("document_parser")
        if parser:
            return parser.parse(
                doc_content=task.payload.get("doc_content", ""),
                doc_type=task.payload.get("doc_type", "api_doc"),
                use_llm=task.payload.get("use_llm", False),
            )
        return {
            "interfaces": [],
            "interface_count": 0,
        }

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        progress: Optional[str] = None,
    ) -> None:
        """
        Persist a task status change to the database.

        Args:
            task_id: The task identifier.
            status: The new TaskStatus.
            result: Optional result payload to store as JSON.
            error: Optional error message.
            progress: Optional progress string (e.g. "50").
        """
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()

            try:
                result_json = json.dumps(result) if result is not None else None
                progress_val = int(progress) if progress is not None else None
                completed_at = datetime.now().isoformat() if status in (
                    TaskStatus.COMPLETED, TaskStatus.FAILED
                ) else None

                cursor.execute(
                    """
                    UPDATE tasks
                    SET status = ?,
                        result = ?,
                        error_message = ?,
                        progress = ?,
                        updated_at = ?,
                        completed_at = ?
                    WHERE task_id = ?
                    """,
                    (
                        status.value,
                        result_json,
                        error,
                        progress_val,
                        datetime.now().isoformat(),
                        completed_at,
                        task_id,
                    ),
                )
                conn.commit()

                if cursor.rowcount == 0:
                    cursor.execute(
                        """
                        INSERT INTO tasks
                            (task_id, task_type, status, params, result, error_message,
                             progress, created_at, updated_at, completed_at)
                        VALUES (?, ?, ?, '{}', ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            task_id,
                            "",
                            status.value,
                            result_json,
                            error,
                            progress_val,
                            datetime.now().isoformat(),
                            datetime.now().isoformat(),
                            completed_at,
                        ),
                    )
                    conn.commit()

            except Exception as e:
                logger.error(f"Failed to update task {task_id} status: {e}")
                conn.rollback()
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @property
    def _services(self) -> Dict[str, Any]:
        return {}

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _handle_document_parse(self, task: Dict[str, Any]) -> Dict[str, Any]:
        parser = self._services.get("document_parser")
        if parser:
            return parser.parse(
                doc_content=task["params"].get("doc_content", ""),
                doc_type=task["params"].get("doc_type", "api_doc"),
                use_llm=task["params"].get("use_llm", False),
            )
        return {
            "interfaces": [],
            "interface_count": 0,
        }

    def _handle_case_generate(self, task: Dict[str, Any]) -> Dict[str, Any]:
        generator = self._services.get("case_generator")
        interface_info = task["params"].get("interface_info", {})
        options = task["params"].get("options", {})
        if generator:
            cases = generator.generate(
                interface_info=interface_info,
                options=options,
            )
        else:
            cases = []
        return {
            "test_cases": cases,
            "count": len(cases),
        }

    def _handle_iteration_parse(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "increment_content": "",
        }

    def _handle_page_case_generate(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "page_name": task["params"].get("page_name", ""),
        }

