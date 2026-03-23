"""
common-proto 共享协议包。

包含：
- schemas: 共享数据模型（Pydantic）
- mq_messages: MQ消息格式定义
- trace: 链路追踪基础设施
"""

from shared.common_proto.schemas import (
    TaskStatus,
    TaskType,
    TestCasePriority,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskStatusResponse,
    ExecuteTestRequest,
    ExecuteTestResponse,
    TestResultSummary,
    TestCaseExecutionResult,
    GenerateCasesRequest,
    GenerateCasesResponse,
    APIResponse,
    PaginatedResponse,
)

from shared.common_proto.mq_messages import (
    MQMessage,
    MQQueueConfig,
    LLM_GENERATE_QUEUE,
    TEST_EXECUTE_QUEUE,
    RAG_INDEX_QUEUE,
    REPORT_GENERATE_QUEUE,
    build_llm_generate_message,
    build_test_execute_message,
)

from shared.common_proto.trace import (
    TraceContext,
    LogFormatter,
    setup_trace_logging,
)

__all__ = [
    # schemas
    "TaskStatus",
    "TaskType",
    "TestCasePriority",
    "TaskCreateRequest",
    "TaskCreateResponse",
    "TaskStatusResponse",
    "ExecuteTestRequest",
    "ExecuteTestResponse",
    "TestResultSummary",
    "TestCaseExecutionResult",
    "GenerateCasesRequest",
    "GenerateCasesResponse",
    "APIResponse",
    "PaginatedResponse",
    # mq_messages
    "MQMessage",
    "MQQueueConfig",
    "LLM_GENERATE_QUEUE",
    "TEST_EXECUTE_QUEUE",
    "RAG_INDEX_QUEUE",
    "REPORT_GENERATE_QUEUE",
    "build_llm_generate_message",
    "build_test_execute_message",
    # trace
    "TraceContext",
    "LogFormatter",
    "setup_trace_logging",
]
