# -*- coding: utf-8 -*-
"""
TestWorker — process-based test execution worker.
"""

import os
import time
import signal
import logging
import threading
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class TestWorker:
    """
    Single test-execution worker backed by a process.

    Can be instantiated directly or managed by a WorkerPool.

    Args:
        worker_id: Unique integer identifier for this worker.
        db_path: Path to the SQLite task database.
        redis_config: Optional dict with Redis connection parameters
            (host, port, password, etc.).
    """

    def __init__(
        self,
        worker_id: int,
        db_path: str = "./db/task.db",
        redis_config: Optional[Dict[str, Any]] = None,
    ):
        self.worker_id = worker_id
        self.db_path = db_path
        self.redis_config: Dict[str, Any] = redis_config or {}

        self._process: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the worker loop in a background thread."""
        if self._running:
            logger.warning(f"TestWorker-{self.worker_id} already running")
            return

        self._stop_event.clear()
        self._running = True
        self._process = threading.Thread(target=self._run_loop, daemon=True)
        self._process.start()
        logger.info(f"TestWorker-{self.worker_id} started (thread={self._process.name})")

    def stop(self) -> None:
        """Signal the worker to stop and wait for the loop to exit."""
        if not self._running:
            return

        self._stop_event.set()
        self._running = False

        if self._process is not None:
            self._process.join(timeout=10.0)

        logger.info(f"TestWorker-{self.worker_id} stopped")

    def is_alive(self) -> bool:
        """Return True if the worker loop is still running."""
        return self._running and (self._process is not None) and self._process.is_alive()

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    def process_task(self, task_id: str) -> Dict[str, Any]:
        """
        Process a single task by ID.

        This is a synchronous placeholder — subclasses or callers can
        override to implement real test execution.

        Args:
            task_id: The identifier of the task to process.

        Returns:
            A result dict with at least a ``status`` key.
        """
        logger.info(f"TestWorker-{self.worker_id} processing task: {task_id}")

        try:
            from common.worker.task_poller import TaskPoller
            from common.worker.task_processor import TaskProcessor

            poller = TaskPoller(db_path=self.db_path, poll_interval=1.0)
            tasks = poller.get_pending_tasks(limit=100)
            task_obj = next((t for t in tasks if t.id == task_id), None)

            if task_obj is None:
                return {"status": "not_found", "task_id": task_id}

            processor = TaskProcessor(worker_id=self.worker_id, db_path=self.db_path)
            result = processor.process(task_obj)
            return {"status": "processed", "task_id": task_id, "result": result}

        except Exception as e:
            logger.error(f"TestWorker-{self.worker_id} error on task {task_id}: {e}")
            return {"status": "error", "task_id": task_id, "error": str(e)}

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Poll for pending tasks and process them until stopped."""
        from common.worker.task_poller import TaskPoller

        poller = TaskPoller(db_path=self.db_path, poll_interval=1.0)
        logger.info(f"TestWorker-{self.worker_id} loop started")

        while not self._stop_event.is_set():
            try:
                task = poller.poll()
                if task is not None:
                    self.process_task(task.id)
            except Exception as e:
                logger.error(f"TestWorker-{self.worker_id} poll error: {e}")
                time.sleep(5.0)

        logger.info(f"TestWorker-{self.worker_id} loop exited")
