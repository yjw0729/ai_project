# workers/start_workers.py
"""
Worker 进程统一启动脚本。

支持启动不同类型的 Worker：
- test_worker: 测试执行 Worker
- llm_worker: LLM 生成 Worker（未来）
- rag_worker: RAG 索引 Worker（未来）

Usage:
    python workers/start_workers.py test
    python workers/start_workers.py llm
    python workers/start_workers.py rag
    python workers/start_workers.py all
"""

import sys
import os
import argparse
import signal
import structlog

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = structlog.get_logger()


def setup_logging():
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def create_redis_client():
    import redis
    return redis.Redis(
        host="localhost",
        port=6379,
        password="pytest_sxp_2026",
        decode_responses=True
    )


def start_test_worker():
    """启动 Test Worker"""
    from workers.mq_consumer import TestWorker
    from platform_service.service.task_service import TaskService
    from common.db.mapper import TaskExecutionMapper

    logger.info("启动 Test Worker...")

    redis_client = create_redis_client()
    task_service = TaskService(redis_client, TaskExecutionMapper())

    worker = TestWorker(
        config={
            "host": "localhost",
            "port": 5672,
            "username": "admin",
            "password": "pytest_sxp_2026",
            "virtual_host": "/",
        },
        task_service=task_service,
        notification_service=None,
    )

    # 信号处理
    def signal_handler(signum, frame):
        logger.info("收到停止信号，正在关闭 Worker...")
        worker.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    worker.connect()
    worker.start()


def start_llm_worker():
    """LLM Worker（预留，后续实现）"""
    logger.warning("LLM Worker 尚未实现")


def start_rag_worker():
    """RAG Worker（预留，后续实现）"""
    logger.warning("RAG Worker 尚未实现")


def main():
    parser = argparse.ArgumentParser(description="Worker 启动脚本")
    parser.add_argument(
        "worker_type",
        nargs="?",
        default="test",
        choices=["test", "llm", "rag", "all"],
        help="Worker 类型: test(默认), llm, rag, all"
    )
    args = parser.parse_args()

    setup_logging()

    if args.worker_type == "test":
        start_test_worker()
    elif args.worker_type == "llm":
        start_llm_worker()
    elif args.worker_type == "rag":
        start_rag_worker()
    elif args.worker_type == "all":
        start_test_worker()


if __name__ == "__main__":
    main()
