from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum
import uuid


class DocumentType(Enum):
    '''文档类型枚举'''
    API_DOC = "api_documentation"
    TEST_CASE = "test_case"
    DESIGN_DOC = "design_document"
    PRODUCT_REQ = "product_requirement"
    TECH_SPEC = "technical_specification"
    BUG_REPORT = "bug_report"


class BusinessModule(Enum):
    '''业务模块枚举'''
    CROSS_BORDER_OPENING = "cross_border_opening"      # 跨境-开户
    CROSS_BORDER_TRADING = "cross_border_trading"      # 跨境-交易
    INTERNET_OPENING = "internet_opening"              # 互联网-开户
    INTERNET_TRADING = "internet_trading"              # 互联网-交易


@dataclass
class Document:
    """文档基类"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    source_type: str = "unknown"
    source_uri: str = ""
    doc_type: Optional[DocumentType] = None
    business_module: Optional[BusinessModule] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        '''转换为字典'''
        return {
            "id": self.id,
            "content": self.content,
            "source_type": self.source_type,
            "source_uri": self.source_uri,
            "doc_type": self.doc_type,
            "business_module": self.business_module,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

@dataclass
class DocumentChunk(Document):
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_doc_id: str = ""
    chunk_index: int = 0
    start_pos: int = 0
    end_pos: int = 0
    vector: Optional[List[float]] = None

    def to_index_dict(self) -> Dict[str, Any]:
        '''转换为索引字典'''
        data = self.to_dict()
        data.update({
            "chunk_id": self.chunk_id,
            "parent_doc_id": self.parent_doc_id,
            "chunk_index": self.chunk_index,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos
        })
        return data

@dataclass
class CollectionStats:
    """集合统计信息"""
    collection_name: str
    total_chunks: int
    vector_dim: int
    index_type: str
    index_params: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)