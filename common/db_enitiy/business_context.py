"""
业务上下文实体
用于存储业务逻辑上下文信息，供用例生成使用
"""

from datetime import datetime
from typing import Any, Dict

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, BigInteger
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class BusinessContext(Base):
    """业务上下文实体"""
    __tablename__ = "crosstest_business_context"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment="上下文名称")
    description = Column(Text, comment="上下文描述")

    # 来源信息
    source_type = Column(String(50), comment="来源类型: text/pdf/docx/image/markdown/vector_db")
    source_name = Column(String(255), comment="原始文件名")
    source_size = Column(BigInteger, comment="原始文件大小(字节)")

    # 内容信息
    content = Column(Text, comment="提取的文本内容")
    content_hash = Column(String(64), comment="内容MD5哈希")
    total_chars = Column(Integer, default=0, comment="总字符数")

    # 关联信息
    api_config_id = Column(Integer, comment="关联的API配置ID")
    module = Column(String(100), comment="所属模块")

    # 状态
    is_active = Column(Boolean, default=True, comment="是否启用")
    is_deprecated = Column(Boolean, default=False, comment="是否废弃")

    # 时间戳
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    creator = Column(String(100), comment="创建人")

    def __repr__(self):
        return f"<BusinessContext(id={self.id}, name='{self.name}', source_type='{self.source_type}')>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "source_type": self.source_type,
            "source_name": self.source_name,
            "source_size": self.source_size,
            "content": self.content,
            "content_hash": self.content_hash,
            "total_chars": self.total_chars,
            "api_config_id": self.api_config_id,
            "module": self.module,
            "is_active": self.is_active,
            "is_deprecated": self.is_deprecated,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "creator": self.creator,
        }
