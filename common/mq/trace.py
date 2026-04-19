"""
链路追踪和结构化日志基础设施。
为每个请求生成唯一的 trace_id，贯穿整个调用链路。
"""

import uuid
import logging
from datetime import datetime
from typing import Optional


class TraceContext:
    """
    链路追踪上下文。
    在请求入口创建，贯穿整个调用链路。
    """

    def __init__(
        self,
        trace_id: Optional[str] = None,
        user_id: str = "anonymous",
        request_id: Optional[str] = None
    ):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.user_id = user_id
        self.request_id = request_id or str(uuid.uuid4())[:8]
        self.start_time = datetime.now()

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "request_id": self.request_id,
        }

    def to_log_dict(self) -> dict:
        """返回适合注入到日志上下文的字典"""
        return {
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "request_id": self.request_id,
            "timestamp": self.start_time.isoformat(),
        }


class LogFormatter(logging.Formatter):
    """
    统一日志格式：时间 | 级别 | trace_id | user_id | 消息
    """

    def format(self, record):
        trace_id = getattr(record, "trace_id", "-")
        user_id = getattr(record, "user_id", "-")
        request_id = getattr(record, "request_id", "-")

        base = super().format(record)

        return (
            f"{self.formatTime(record)} | "
            f"{record.levelname:<8} | "
            f"[{trace_id[:8]}] | "
            f"[{user_id}] | "
            f"[{request_id}] | "
            f"{record.getMessage()}"
        )


def setup_trace_logging(service_name: str):
    """
    初始化带 trace_id 的结构化日志。
    所有日志会自动带上 trace_id, user_id, service_name。
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    formatter = LogFormatter(
        fmt="%(asctime)s | %(levelname)-8s | [%(trace_id)s] | [%(user_id)s] | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    for handler in logger.handlers[:]:
        handler.setFormatter(formatter)

    return logger
