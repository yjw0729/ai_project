"""
Task data models.

Exports: Task, TaskStatus, TaskType
"""

from enum import Enum
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRY = "retry"


class TaskType(str, Enum):
    DOCUMENT_PARSE = "document_parse"
    CASE_GENERATE = "case_generate"
    ASSERTION_GENERATE = "assertion_generate"
    PAGE_CASE_GENERATE = "page_case_generate"
    ITERATION_PARSE = "iteration_parse"
    # Aliases matching string values seen in tests
    TEST_CASE_GENERATION = "test_case_generation"
    API_TEST = "api_test"
    RAG_INGESTION = "rag_ingestion"


# Reverse mapping so string values in data can resolve to enum members
_TASK_TYPE_ALIASES: Dict[str, TaskType] = {
    "document_parse": TaskType.DOCUMENT_PARSE,
    "case_generate": TaskType.CASE_GENERATE,
    "assertion_generate": TaskType.ASSERTION_GENERATE,
    "page_case_generate": TaskType.PAGE_CASE_GENERATE,
    "iteration_parse": TaskType.ITERATION_PARSE,
}


def _parse_task_type(value: Union[str, TaskType]) -> TaskType:
    if isinstance(value, TaskType):
        return value
    lower = str(value).lower()
    for member in TaskType:
        if member.value == lower:
            return member
    return _TASK_TYPE_ALIASES.get(lower, TaskType.DOCUMENT_PARSE)


def _parse_task_status(value: Union[str, TaskStatus]) -> TaskStatus:
    if isinstance(value, TaskStatus):
        return value
    lower = str(value).lower()
    for member in TaskStatus:
        if member.value == lower:
            return member
    return TaskStatus.PENDING


@dataclass
class Task:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: Union[TaskType, str] = field(default=TaskType.DOCUMENT_PARSE)
    status: Union[TaskStatus, str] = field(default=TaskStatus.PENDING)
    params: Union[Dict[str, Any], str] = field(default_factory=dict)
    progress: int = 0
    result: Optional[Any] = None
    error_message: Optional[str] = None
    document_id: Optional[int] = None
    interface_ids: Optional[List[int]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        self.task_type = _parse_task_type(self.task_type)
        self.status = _parse_task_status(self.status)
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
        # Normalise params to dict
        if isinstance(self.params, str):
            self.params = json.loads(self.params) if self.params else {}
        # Normalise interface_ids to list of int
        if isinstance(self.interface_ids, str):
            self.interface_ids = json.loads(self.interface_ids) if self.interface_ids else []
        if self.interface_ids and isinstance(self.interface_ids[0], str):
            self.interface_ids = [int(x) for x in self.interface_ids]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        return cls(
            task_id=data.get('task_id', str(uuid.uuid4())),
            task_type=data.get('task_type', 'document_parse'),
            status=data.get('status', 'pending'),
            params=data.get('params', {}),
            progress=data.get('progress', 0),
            result=data.get('result'),
            error_message=data.get('error_message'),
            document_id=data.get('document_id'),
            interface_ids=data.get('interface_ids'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
            completed_at=data.get('completed_at'),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'task_type': self.task_type.value if isinstance(self.task_type, TaskType) else self.task_type,
            'status': self.status.value if isinstance(self.status, TaskStatus) else self.status,
            'params': json.dumps(self.params) if isinstance(self.params, dict) else self.params,
            'progress': self.progress,
            'result': self.result,
            'error_message': self.error_message,
            'document_id': self.document_id,
            'interface_ids': json.dumps(self.interface_ids) if isinstance(self.interface_ids, list) else self.interface_ids,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_row(cls, row: tuple, columns: List[str]) -> 'Task':
        data = dict(zip(columns, row))
        if isinstance(data.get('params'), str):
            data['params'] = json.loads(data['params']) if data['params'] else {}
        if isinstance(data.get('interface_ids'), str):
            ids = data.get('interface_ids', '')
            data['interface_ids'] = json.loads(ids) if ids else []
        return cls.from_dict(data)

    def update_progress(self, value: int):
        self.progress = max(0, min(100, value))
        self.updated_at = datetime.now()
        if self.progress >= 100:
            self.status = TaskStatus.COMPLETED
            self.completed_at = datetime.now()

    def mark_failed(self, message: str):
        self.status = TaskStatus.FAILED
        self.error_message = message
        self.completed_at = datetime.now()
        self.updated_at = datetime.now()

    # Backward-compat aliases for existing worker code that uses id/payload/error
    @property
    def id(self) -> str:
        return self.task_id

    @id.setter
    def id(self, value: str):
        self.task_id = value

    @property
    def payload(self) -> Union[Dict[str, Any], str]:
        return self.params

    @payload.setter
    def payload(self, value: Union[Dict[str, Any], str]):
        self.params = value

    @property
    def error(self) -> Optional[str]:
        return self.error_message

    @error.setter
    def error(self, value: str):
        self.error_message = value

    # progress as int (some code reads it as str "0")
    @property
    def progress_int(self) -> int:
        return self.progress
