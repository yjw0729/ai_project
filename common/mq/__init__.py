"""
common/mq/ - 消息队列共享协议模块。

从 shared/common_proto/ 迁移而来，作为项目的统一 MQ 基础设施。
"""

from common.mq.schemas import (
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

from common.mq.mq_messages import (
    MQMessage,
    MQQueueConfig,
    LLM_GENERATE_QUEUE,
    TEST_EXECUTE_QUEUE,
    RAG_INDEX_QUEUE,
    REPORT_GENERATE_QUEUE,
    build_llm_generate_message,
    build_test_execute_message,
)

from common.mq.trace import (
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
