"""
Test Worker：测试执行任务消费者。

从 RabbitMQ 消费测试执行任务，执行 pytest 用例，支持：
- 并发执行（ThreadPoolExecutor）
- 实时进度推送（通过 Redis Pub/Sub）
- 任务取消（检查 Redis 取消标记）
- 失败重试（指数退避）
"""

import json
import time
import signal
import sys
import os
import structlog

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from platform_service.service.mq_client import MQConsumer
from platform_service.service.task_service import TaskService, TaskStatus
from shared.common_proto.mq_messages import TEST_EXECUTE_QUEUE

logger = structlog.get_logger()


class TestWorker(MQConsumer):
    """
    测试执行 Worker。
    消费 test.execute 队列，执行测试用例。
    """

    def __init__(self, config: dict, task_service: TaskService, notification_service=None):
        super().__init__(
            config=config,
            queue_name=TEST_EXECUTE_QUEUE.queue,
            prefetch_count=TEST_EXECUTE_QUEUE.prefetch_count,
        )
        self.task_service = task_service
        self.notification_service = notification_service

    def _handle_message(self, message: dict) -> bool:
        task_id = message.get("task_id")
        user_id = message.get("user_id")
        payload = message.get("payload", {})
        retry_count = message.get("retry_count", 0)

        try:
            logger.info("开始执行测试任务",
                task_id=task_id,
                user_id=user_id,
                retry=retry_count,
                case_count=len(payload.get("case_ids", []))
            )

            self.task_service.update_status(task_id, TaskStatus.RUNNING, progress="0")

            test_cases = self._load_cases(payload.get("case_ids", []))
            total = len(test_cases)

            if not test_cases:
                self.task_service.update_status(
                    task_id, TaskStatus.FAILED,
                    error_message="未找到测试用例"
                )
                return True

            results = self._execute_cases(
                task_id=task_id,
                user_id=user_id,
                test_cases=test_cases,
                env_id=payload.get("env_id"),
                concurrency=payload.get("concurrency", 5),
                mode=payload.get("mode", "parallel"),
            )

            summary = self._generate_summary(results)

            self.task_service.update_status(
                task_id, TaskStatus.COMPLETED,
                result=summary,
                progress="100"
            )

            if self.notification_service:
                self.notification_service.send_completed(user_id, task_id, summary)

            logger.info("测试任务完成",
                task_id=task_id,
                total=summary["total"],
                passed=summary["passed"],
                failed=summary["failed"]
            )
            return True

        except Exception as e:
            logger.error("测试任务执行异常",
                task_id=task_id,
                error=str(e),
                exc_info=True
            )

            if retry_count < TEST_EXECUTE_QUEUE.max_retries:
                self._retry_task(message, str(e), retry_count)
            else:
                self.task_service.update_status(
                    task_id, TaskStatus.FAILED,
                    error_message=str(e)
                )
                if self.notification_service:
                    self.notification_service.send_failed(user_id, task_id, str(e))

            return True

    def _load_cases(self, case_ids: list) -> list:
        from common.db_mapper.test_case_mapper import TestCaseMapper

        mapper = TestCaseMapper()
        cases = []
        for cid in case_ids:
            entity = mapper.get_by_id(cid)
            if entity:
                case = {
                    "id": entity.id,
                    "name": getattr(entity, "name", ""),
                    "description": getattr(entity, "description", ""),
                    "priority": getattr(entity, "priority", "P2"),
                    "tags": json.loads(getattr(entity, "tags", "[]") or "[]"),
                    "test_data": json.loads(getattr(entity, "test_data", "{}") or "{}"),
                    "expected_results": json.loads(getattr(entity, "expected_results", "[]") or "[]"),
                }
                cases.append(case)
        return cases

    def _execute_cases(self, task_id, user_id, test_cases, env_id, concurrency, mode):
        from common.test_executor import APITestRunner

        env_config = self._load_env_config(env_id)
        runner = APITestRunner(
            env_config=env_config,
            concurrency=concurrency,
        )

        results = []
        total = len(test_cases)

        for i, case in enumerate(test_cases):
            if self._is_cancelled(task_id):
                logger.info("任务已取消，停止执行", task_id=task_id)
                runner.cleanup()
                self.task_service.update_status(task_id, TaskStatus.CANCELLED)
                break

            result = runner.execute_single(case)
            results.append(result)

            execution_id = f"{user_id}:{task_id}"
            self._save_result(execution_id, case["id"], result)

            progress = f"{i + 1}/{total}"
            progress_pct = int((i + 1) / total * 90)
            self.task_service.update_status(task_id, TaskStatus.RUNNING, progress=f"{progress_pct}%")

            if self.notification_service:
                self.notification_service.send_progress(user_id, task_id, {
                    "case_id": case["id"],
                    "case_name": result.case_name,
                    "status": result.status,
                    "duration_ms": round(result.duration_ms, 1),
                    "progress": progress,
                    "progress_pct": progress_pct,
                })

        runner.cleanup()
        return results

    def _load_env_config(self, env_id: int) -> dict:
        if not env_id:
            return {}
        try:
            from common.db_mapper.environment_config_mapper import EnvironmentConfigMapper
            mapper = EnvironmentConfigMapper()
            env = mapper.get_by_id(env_id)
            return env.to_json() if env and hasattr(env, "to_json") else {}
        except Exception:
            return {}

    def _generate_summary(self, results: list) -> dict:
        passed = sum(1 for r in results if r.status == "passed")
        failed = sum(1 for r in results if r.status == "failed")
        errors = sum(1 for r in results if r.status == "error")
        total_duration = sum(r.duration_ms for r in results)

        return {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "error": errors,
            "success_rate": round(passed / max(len(results), 1) * 100, 2),
            "total_duration_ms": round(total_duration, 1),
        }

    def _is_cancelled(self, task_id: str) -> bool:
        """检查任务是否被取消"""
        try:
            import redis
            redis_client = redis.Redis(
                host="localhost",
                port=6379,
                password="pytest_sxp_2026",
                decode_responses=True,
                socket_connect_timeout=2,
            )
            cancel_key = f"task:cancelled:{task_id}"
            return redis_client.exists(cancel_key) > 0
        except Exception:
            return False

    def _save_result(self, execution_id: str, case_id: int, result):
        """保存执行结果到 Redis（隔离存储）"""
        try:
            import redis
            redis_client = redis.Redis(
                host="localhost",
                port=6379,
                password="pytest_sxp_2026",
                decode_responses=True,
                socket_connect_timeout=2,
            )
            redis_key = f"exec_result:{execution_id}"
            result_dict = {
                "case_id": case_id,
                "case_name": result.case_name,
                "status": result.status,
                "duration_ms": round(result.duration_ms, 1),
                "response_time_ms": getattr(result, "response_time_ms", 0),
                "error": getattr(result, "error", None),
                "status_code": getattr(result, "status_code", None),
            }
            redis_client.hset(redis_key, case_id, json.dumps(result_dict))
            redis_client.expire(redis_key, 86400)  # 24小时过期
        except Exception:
            pass  # Redis不可用时静默忽略

    def _retry_task(self, message: dict, error: str, retry_count: int):
        delay = 30 * (2 ** retry_count)
        logger.warning("任务失败，准备重试",
            task_id=message.get("task_id"),
            retry=retry_count + 1,
            delay=delay,
            error=error
        )
        self.task_service.update_status(
            message.get("task_id"),
            TaskStatus.RETRYING,
            error_message=f"重试中({retry_count + 1}): {error}"
        )
        time.sleep(delay)
        from platform_service.service.mq_client import get_mq_client
        new_message = {**message, "retry_count": retry_count + 1}
        get_mq_client().publish(TEST_EXECUTE_QUEUE.routing_key, new_message)


def main():
    import redis

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )

    logger.info("Test Worker启动中...")

    redis_client = redis.Redis(
        host="localhost",
        port=6379,
        password="pytest_sxp_2026",
        decode_responses=True
    )

    from common.db_mapper.task_execution_mapper import TaskExecutionMapper
    task_service = TaskService(redis_client, TaskExecutionMapper())

    notification_service = None

    worker = TestWorker(
        config={
            "host": "localhost",
            "port": 5672,
            "username": "admin",
            "password": "pytest_sxp_2026",
            "virtual_host": "/",
        },
        task_service=task_service,
        notification_service=notification_service,
    )

    def shutdown(signum, frame):
        logger.info("收到关闭信号...")
        worker.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    worker.connect()
    worker.start()


if __name__ == "__main__":
    main()
