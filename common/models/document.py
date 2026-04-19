"""
Document 文档模型

定义技术文档/需求文档的数据结构。
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, Any
import json


class DocumentType(str, Enum):
    """文档类型枚举"""
    TECH_SPEC = 'tech_spec'             # 技术规格文档
    API_DOC = 'api_doc'                 # API接口文档
    PRD = 'prd'                          # 产品需求文档
    DESIGN = 'design'                    # 设计文档
    TEST_PLAN = 'test_plan'             # 测试计划文档
    OTHER = 'other'                      # 其他文档


@dataclass
class Document:
    """文档数据模型"""
    doc_name: str
    doc_type: DocumentType
    id: Optional[int] = None
    task_id: Optional[str] = None
    doc_content: Optional[str] = None
    is_current: bool = True
    is_history: bool = False
    version: Optional[str] = None
    is_latest: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None

    def __post_init__(self):
        if isinstance(self.doc_type, str):
            self.doc_type = DocumentType(self.doc_type)

    def to_dict(self) -> dict:
        """转换为字典"""
        data = asdict(self)
        data['doc_type'] = self.doc_type.value if isinstance(self.doc_type, DocumentType) else self.doc_type
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Document':
        """从字典创建实例"""
        return cls(
            id=data.get('id'),
            task_id=data.get('task_id'),
            doc_name=data['doc_name'],
            doc_type=data['doc_type'],
            doc_content=data.get('doc_content'),
            is_current=data.get('is_current', True),
            is_history=data.get('is_history', False),
            version=data.get('version'),
            is_latest=data.get('is_latest', True),
            created_at=data.get('created_at', datetime.now()),
            approved_at=data.get('approved_at'),
            approved_by=data.get('approved_by'),
        )

    def archive(self):
        """归档文档"""
        self.is_history = True
        self.is_latest = False

    def approve(self, approved_by: str):
        """审批通过"""
        self.approved_at = datetime.now()
        self.approved_by = approved_by
