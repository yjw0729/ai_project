"""
Worker pool for concurrent task execution.
"""

import os
import threading
import traceback
from concurrent.futures import Future, ThreadPoolExecutor
from multiprocessing import Process, Queue as MPQueue
from typing import Any, Callable, Dict, Iterable, List, Optional


def get_optimal_worker_count() -> int:
    """Return the recommended number of worker processes: cpu_count * 2 + 1."""
    return os.cpu_count() * 2 + 1


class _TaskFuture:
    """A Future-like wrapper that stores task results keyed by task_id."""

    def __init__(self, task_id: str, future: Future):
        self._task_id = task_id
        self._future = future
        self._result: Dict[str, Any] = {}

    def result(self, timeout: float = None) -> Dict[str, Any]:
        try:
            val = self._future.result(timeout=timeout)
            return {"success": True, "result": val}
        except Exception as e:
            return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


# =============================================================================
# Process-based WorkerPool — used by workers/run_worker.py
# =============================================================================

class WorkerPool:
    """
    Process-based worker pool that distributes tasks across multiple processes.

    Compatible with the interface expected by workers/run_worker.py.
    """

    def __init__(
        self,
        worker_count: int,
        threads_per_worker: int = 4,
        poll_interval: float = 1.0,
        db_path: str = "./db/task.db",
        redis_config: Optional[Dict[str, Any]] = None,
    ):
        self.worker_count = worker_count
        self.threads_per_worker = threads_per_worker
        self.poll_interval = poll_interval
        self.db_path = db_path
        self.redis_config: Dict[str, Any] = redis_config or {}

        self.task_queue: MPQueue = MPQueue()
        self.result_queue: MPQueue = MPQueue()
        self.workers: List[Process] = []
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Spawn all worker processes and start them."""
        if self._running:
            return

        self._running = True
        for i in range(self.worker_count):
            p = Process(
                target=_worker_loop,
                args=(
                    i,
                    self.task_queue,
                    self.result_queue,
                    self.threads_per_worker,
                    self.poll_interval,
                    self.db_path,
                    self.redis_config,
                ),
                name=f"WorkerProcess-{i}",
            )
            p.start()
            self.workers.append(p)

    def stop(self, wait: bool = True, timeout: float = 10.0) -> None:
        """Gracefully stop all worker processes."""
        if not self._running:
            return

        self._running = False

        for _ in self.workers:
            self.task_queue.put(None)

        for p in self.workers:
            p.join(timeout=timeout)
            if p.is_alive():
                p.terminate()

        self.workers.clear()

    def is_running(self) -> bool:
        return self._running

    def is_alive(self) -> bool:
        """Return True if at least one worker process is still alive."""
        return any(p.is_alive() for p in self.workers)

    # ------------------------------------------------------------------
    # Task submission
    # ------------------------------------------------------------------

    def submit_task(self, task_id: str) -> None:
        """Enqueue a task ID for processing by an available worker."""
        self.task_queue.put(task_id)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Return current pool statistics."""
        alive_count = sum(1 for p in self.workers if p.is_alive())
        return {
            "worker_count": self.worker_count,
            "alive_count": alive_count,
            "dead_count": self.worker_count - alive_count,
            "running": self._running,
            "queue_size": self.task_queue.qsize() if self._running else 0,
        }


# ------------------------------------------------------------------
# Worker process entry point (module-level so it can be pickled)
# ------------------------------------------------------------------

def _worker_loop(
    worker_id: int,
    task_queue: MPQueue,
    result_queue: MPQueue,
    threads_per_worker: int,
    poll_interval: float,
    db_path: str,
    redis_config: Dict[str, Any],
) -> None:
    """
    The main loop run inside each worker process.
    Polls the task queue and delegates to TaskProcessor.
    """
    from common.worker.task_processor import TaskProcessor

    processor = TaskProcessor(worker_id=worker_id, db_path=db_path)

    while True:
        try:
            task_id = task_queue.get(timeout=poll_interval)
        except Exception:
            continue

        if task_id is None:
            break

        try:
            from common.worker.task_poller import TaskPoller
            poller = TaskPoller(db_path=db_path, poll_interval=poll_interval)
            tasks = poller.get_pending_tasks(limit=100)
            task_obj = next((t for t in tasks if t.id == task_id), None)

            if task_obj is None:
                result_queue.put({"task_id": task_id, "status": "not_found"})
                continue

            result = processor.process(task_obj)
            result_queue.put({"task_id": task_id, "status": "processed", "result": result})
        except Exception as e:
            result_queue.put({"task_id": task_id, "status": "error", "error": str(e)})


# =============================================================================
# Legacy thread-pool-based WorkerPool (kept for compatibility)
# =============================================================================

class _LegacyWorkerPool:
    """Legacy thread-pool-based worker pool (deprecated, kept for compatibility)."""

    def __init__(self, max_workers: int = 4):
        self._max_workers = max_workers
        self._executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=max_workers)
        self._running = False
        self._submitted = 0
        self._completed = 0
        self._lock = threading.Lock()

    def is_running(self) -> bool:
        return self._running

    def start(self):
        self._running = True

    def stop(self, wait: bool = True):
        self._running = False
        if wait:
            self._executor.shutdown(wait=True)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "max_workers": self._max_workers,
                "submitted": self._submitted,
                "completed": self._completed,
                "running": self._running,
            }

    def submit(self, task_id: str, fn: Callable[..., Any], *args, **kwargs) -> _TaskFuture:
        with self._lock:
            self._submitted += 1

        def wrapper():
            with self._lock:
                self._completed += 1
            return fn(*args, **kwargs)

        future = self._executor.submit(wrapper)
        return _TaskFuture(task_id, future)

    def map(self, fn: Callable[..., Any], iterable: Iterable[Any]) -> List[Dict[str, Any]]:
        results = []
        for item in iterable:
            task_id = f"map-{id(item)}"
            future = self.submit(task_id, fn, item)
            results.append(future.result(timeout=30.0))
        return results

    def get_result(self, task_id: str) -> Dict[str, Any]:
        return {"success": False, "error": "Task result not found in memory store"}
