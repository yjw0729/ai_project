# common/db_enitiy/review_summary.py
"""
文档审核汇总表实体
每个文档（doc_id）只有一条汇总记录，专用于列表查询，避免扫描含大字段的 crosstest_review_record 表。
"""
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, Enum, DateTime
from datetime import datetime
import enum

Base = declarative_base()


class ReviewSummary(Base):
    """文档审核汇总表 - 每个文档一条记录，只存摘要信息"""
    __tablename__ = 'crosstest_review_summary'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')

    # 文档标识
    doc_id = Column(String(64), nullable=False, unique=True, index=True, comment='文档UUID（唯一）')

    # 基础信息
    document_title  = Column(String(200), nullable=False, comment='文档标题')
    business_module = Column(String(100), comment='业务模块')
    document_type = Column(String(50), comment='文档类型: api_doc-技术设计文档, product_design-需求文档')

    # 统计信息
    interface_count       = Column(Integer, default=0, comment='识别到的接口数量')
    image_count           = Column(Integer, default=0, comment='提取到的图片总数')
    general_image_count   = Column(Integer, default=0, comment='知识类图片数量（未匹配到接口）')
    test_case_count       = Column(Integer, default=0, comment='生成的测试用例数量')

    # 审核状态
    status = Column(
        Enum('pending', 'approved', 'rejected'),
        nullable=False,
        default='pending',
        comment='审核状态: pending-待审核, approved-已通过, rejected-已拒绝'
    )

    # 生成结果
    xmind_file_path = Column(String(500), comment='生成的XMind文件路径')

    # 操作人
    creator  = Column(String(50), nullable=False, default='system', comment='创建人')
    reviewer = Column(String(50), comment='审核人')
    review_comment = Column(Text, comment='审核意见')

    # 时间戳
    created_time = Column(DateTime, default=datetime.now,  comment='创建时间')
    updated_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='最后更新时间')

    def __repr__(self):
        return (f"<ReviewSummary(doc_id='{self.doc_id}', "
                f"title='{self.document_title}', status='{self.status}')>")

    def to_dict(self):
        return {
            'id':                  self.id,
            'doc_id':              self.doc_id,
            'document_title':      self.document_title,
            'business_module':     self.business_module,
            'document_type':      self.document_type,
            'interface_count':     self.interface_count,
            'image_count':         self.image_count,
            'general_image_count': self.general_image_count,
            'test_case_count':     self.test_case_count,
            'status':              self.status.value if isinstance(self.status, enum.Enum) else self.status,
            'xmind_file_path':     self.xmind_file_path,
            'creator':             self.creator,
            'reviewer':            self.reviewer,
            'review_comment':      self.review_comment,
            'created_time':        self.created_time.isoformat() if self.created_time else None,
            'updated_time':        self.updated_time.isoformat() if self.updated_time else None,
        }
