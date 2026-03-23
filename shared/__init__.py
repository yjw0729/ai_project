"""
shared/__init__.py
shared/ 跨服务共享包。

本目录包含所有服务共享的基础设施：

├── common-proto/   # 共享协议定义（schemas, MQ消息格式, trace_id）
└── llm-sdk/        # LLM客户端SDK
"""

from shared.common_proto import (
    TaskStatus,
    TaskType,
    TaskStatusResponse,
    MQMessage,
    LLM_GENERATE_QUEUE,
    TEST_EXECUTE_QUEUE,
    build_llm_generate_message,
    build_test_execute_message,
    TraceContext,
)

__version__ = "1.0.0"

__all__ = [
    "__version__",
    "TaskStatus",
    "TaskType",
    "TaskStatusResponse",
    "MQMessage",
    "LLM_GENERATE_QUEUE",
    "TEST_EXECUTE_QUEUE",
    "build_llm_generate_message",
    "build_test_execute_message",
    "TraceContext",
]
