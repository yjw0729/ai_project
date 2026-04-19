"""
跨服务共享的 RabbitMQ 消息格式定义。
定义所有消息队列的主题、路由键、消息体格式。
"""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel

from common.mq.schemas import TaskType


class MQMessage(BaseModel):
    """统一MQ消息格式"""
    message_id: str           # 消息唯一ID（UUID）
    trace_id: str            # 链路追踪ID
    user_id: str             # 用户ID
    task_id: str             # 任务记录ID
    task_type: TaskType      # 任务类型
    payload: Dict[str, Any]  # 任务参数
    created_at: datetime
    retry_count: int = 0
    max_retries: int = 3


class MQQueueConfig(BaseModel):
    """MQ队列配置"""
    exchange: str
    queue: str
    routing_key: str
    prefetch_count: int = 2
    max_retries: int = 3
    retry_delay: int = 30  # 秒


# ========== 各队列配置 ==========

LLM_GENERATE_QUEUE = MQQueueConfig(
    exchange="llm",
    queue="llm.generate",
    routing_key="llm.generate",
    prefetch_count=2,     # LLM API 并发控制
    max_retries=3,
    retry_delay=30,
)

TEST_EXECUTE_QUEUE = MQQueueConfig(
    exchange="test",
    queue="test.execute",
    routing_key="test.execute",
    prefetch_count=1,    # 测试执行资源重，串行
    max_retries=0,       # 测试不重试
)

RAG_INDEX_QUEUE = MQQueueConfig(
    exchange="rag",
    queue="rag.index",
    routing_key="rag.index",
    prefetch_count=3,
    max_retries=2,
    retry_delay=10,
)

REPORT_GENERATE_QUEUE = MQQueueConfig(
    exchange="report",
    queue="report.generate",
    routing_key="report.generate",
    prefetch_count=5,
    max_retries=1,
    retry_delay=5,
)


# ========== 消息构建工具 ==========

def build_llm_generate_message(
    task_id: str,
    user_id: str,
    payload: Dict[str, Any],
    trace_id: str = ""
) -> MQMessage:
    """构建用例生成消息"""
    import uuid
    return MQMessage(
        message_id=str(uuid.uuid4()),
        trace_id=trace_id or str(uuid.uuid4()),
        user_id=user_id,
        task_id=task_id,
        task_type=TaskType.LLM_GENERATE,
        payload=payload,
        created_at=datetime.now(),
        max_retries=LLM_GENERATE_QUEUE.max_retries,
    )


def build_test_execute_message(
    task_id: str,
    user_id: str,
    payload: Dict[str, Any],
    trace_id: str = ""
) -> MQMessage:
    """构建测试执行消息"""
    import uuid
    return MQMessage(
        message_id=str(uuid.uuid4()),
        trace_id=trace_id or str(uuid.uuid4()),
        user_id=user_id,
        task_id=task_id,
        task_type=TaskType.TEST_EXECUTE,
        payload=payload,
        created_at=datetime.now(),
        max_retries=TEST_EXECUTE_QUEUE.max_retries,
    )
