"""
跨服务共享的数据模型定义（Pydantic）。
所有服务使用统一的请求/响应格式。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 等待中
    QUEUED = "queued"        # 已入队列
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"       # 失败
    CANCELLED = "cancelled" # 已取消
    RETRYING = "retrying"   # 重试中


class TaskType(str, Enum):
    """任务类型枚举"""
    LLM_GENERATE = "llm.generate"        # 用例生成
    LLM_ANALYZE = "llm.analyze"         # 文档分析
    RAG_INDEX = "rag.index"             # 文档索引
    TEST_EXECUTE = "test.execute"       # 测试执行
    REPORT_GENERATE = "report.generate" # 报告生成


class TestCasePriority(str, Enum):
    """测试用例优先级"""
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


# ========== 任务相关 ==========

class TaskCreateRequest(BaseModel):
    """创建任务的请求"""
    task_type: TaskType
    payload: Dict[str, Any]
    description: Optional[str] = ""
    user_id: Optional[str] = "anonymous"


class TaskCreateResponse(BaseModel):
    """创建任务的响应"""
    task_id: str
    status: TaskStatus
    message: str
    created_at: datetime


class TaskStatusResponse(BaseModel):
    """任务状态查询响应"""
    task_id: str
    status: TaskStatus
    progress: str = "0"
    result_summary: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


# ========== 测试执行相关 ==========

class ExecuteTestRequest(BaseModel):
    """执行测试请求"""
    case_ids: List[int] = Field(..., min_items=1)
    env_id: Optional[int] = None
    concurrency: int = Field(default=5, ge=1, le=50)
    mode: str = Field(default="parallel", pattern="^(parallel|serial)$")
    user_id: Optional[str] = "anonymous"


class ExecuteTestResponse(BaseModel):
    """执行测试响应（异步模式）"""
    task_id: str
    status: TaskStatus
    execution_id: str
    message: str
    progress_url: str = ""


class TestResultSummary(BaseModel):
    """测试结果摘要"""
    total: int
    passed: int
    failed: int
    error: int
    skipped: int
    success_rate: float
    total_duration_ms: float
    avg_duration_ms: float


class TestCaseExecutionResult(BaseModel):
    """单个用例执行结果"""
    case_id: int
    case_name: str
    status: str  # passed, failed, skipped, error
    duration_ms: float
    response_time_ms: int
    assertions: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None
    status_code: Optional[int] = None


# ========== 用例生成相关 ==========

class GenerateCasesRequest(BaseModel):
    """生成测试用例请求"""
    doc_id: str
    system_name: Optional[str] = ""
    options: Dict[str, Any] = Field(default_factory=dict)
    user_id: Optional[str] = "anonymous"


class GenerateCasesResponse(BaseModel):
    """生成测试用例响应（异步模式）"""
    task_id: str
    status: TaskStatus
    doc_id: str
    message: str


# ========== 通用响应 ==========

class APIResponse(BaseModel):
    """统一API响应格式"""
    code: int = 200
    message: str = "success"
    data: Optional[Any] = None


class PaginatedResponse(BaseModel):
    """分页响应"""
    code: int = 200
    message: str = "success"
    data: Dict[str, Any] = Field(default_factory=dict)
    pagination: Dict[str, int] = Field(default_factory=dict)
