# common/db_enitiy/review_record.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, Enum, DateTime, JSON
from datetime import datetime
import enum

# 生成ORM基类
Base = declarative_base()


class ReviewRecordStatus(enum.Enum):
    """审核记录状态枚举"""
    PENDING = "pending"  # 待审核
    APPROVED = "approved"  # 已通过
    REJECTED = "rejected"  # 已拒绝


class ReviewRecordType(enum.Enum):
    """审核记录类型枚举"""
    INTERFACE = "interface"  # 接口
    PAGE = "page"  # 页面


class ReviewRecord(Base):
    """审核记录表实体类 - 每个接口/页面一条记录"""
    __tablename__ = 'crosstest_review_record'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')

    # 文档关联 - 同一文档下的多条记录使用相同的doc_id
    doc_id = Column(String(64), nullable=False, comment='文档UUID')

    # 文档基本信息（冗余存储，便于查询）
    document_title = Column(String(200), nullable=False, comment='文档标题')
    business_module = Column(String(100), comment='业务模块')
    project_background = Column(Text, comment='项目背景')
    business_summary = Column(Text, comment='业务摘要')

    # 记录类型：接口或页面
    record_type = Column(
        Enum('interface', 'page'),
        nullable=False,
        default='interface',
        comment='记录类型: interface-接口, page-页面'
    )

    # 接口/页面详细信息
    interface_name = Column(String(200), comment='接口名称')
    interface_method = Column(String(10), comment='接口方法 GET/POST等')
    interface_path = Column(String(500), comment='接口路径')
    interface_description = Column(Text, comment='接口描述')
    request_params = Column(Text, comment='请求参数说明')
    request_json_sample = Column(Text, comment='请求参数JSON示例')
    response_json_sample = Column(Text, comment='响应参数JSON示例')
    response_params = Column(Text, comment='响应参数说明')
    process_flow = Column(Text, comment='处理流程说明')
    flow_chart_desc = Column(Text, comment='流程图描述')

    # 详细流程分析（从flow_chart_analysis中提取的当前接口/页面对应部分）
    detail_flow_analysis = Column(Text, comment='详细流程分析')

    # 原始数据（JSON格式存储完整信息）
    interface_data = Column(JSON, comment='接口完整数据 JSON')
    flow_chart_analysis = Column(JSON, comment='流程图分析 JSON数组')
    image_analysis = Column(JSON, comment='图片分析结果 JSON数组')
    api_section = Column(Text, comment='API部分原始内容')
    document_content = Column(Text, comment='完整文档内容')

    # 审核状态
    status = Column(
        Enum('pending', 'approved', 'rejected'),
        nullable=False,
        default='pending',
        comment='审核状态: pending-待审核, approved-已通过, rejected-已拒绝'
    )

    # 生成结果
    xmind_file_path = Column(String(500), comment='生成的XMind文件路径')
    test_case_count = Column(Integer, default=0, comment='生成的测试用例数量')

    # 审核信息
    creator = Column(String(50), nullable=False, comment='创建人')
    reviewer = Column(String(50), comment='审核人')
    review_comment = Column(Text, comment='审核意见')

    # 时间戳
    created_time = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    def __repr__(self):
        return f"<ReviewRecord(doc_id='{self.doc_id}', interface='{self.interface_name}', status='{self.status}')>"

    def to_dict(self):
        """转换为字典"""
        result = {}
        for key, value in self.__dict__.items():
            if not key.startswith('_'):
                result[key] = value
        return result

    def to_json(self):
        """转换为JSON友好的字典"""
        result = self.to_dict()
        for key, value in result.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, enum.Enum):
                result[key] = value.value
        return result

    def to_review_data_dict(self):
        """转换为ReviewData格式的字典（用于API返回）"""
        return {
            "doc_id": self.doc_id,
            "document_title": self.document_title,
            "business_module": self.business_module,
            "project_background": self.project_background,
            "business_summary": self.business_summary,
            "interface_name": self.interface_name,
            "interface_method": self.interface_method,
            "interface_path": self.interface_path,
            "detail_flow_analysis": self.detail_flow_analysis,
            "status": self.status.value if isinstance(self.status, enum.Enum) else self.status,
            "created_at": self.created_time.isoformat() if self.created_time else None,
            "updated_at": self.updated_time.isoformat() if self.updated_time else None
        }

    @classmethod
    def from_review_data(cls, review_data, interface_info: dict = None, flow_analysis: str = "",
                        interface_images: list = None, general_images: list = None, creator: str = "system"):
        """
        从ReviewData对象创建ReviewRecord（单个接口/页面）

        参数：
        - review_data: ReviewData对象
        - interface_info: 接口信息字典（如果有）
        - flow_analysis: 匹配的流程分析文本
        - interface_images: 该接口专有的图片分析结果列表
        - general_images: 文档级别的知识图片列表
        - creator: 创建人
        """
        # 默认值处理
        if interface_images is None:
            interface_images = []
        if general_images is None:
            general_images = []

        # 如果提供了接口信息，使用接口信息
        if interface_info:
            # 接口记录：只包含该接口匹配到的图片
            return cls(
                doc_id=review_data.doc_id,
                document_title=review_data.document_title,
                business_module=review_data.business_module,
                project_background=review_data.project_background,
                business_summary=review_data.business_summary,
                record_type='interface',
                interface_name=interface_info.get('name', ''),
                interface_method=interface_info.get('method', ''),
                interface_path=interface_info.get('path', ''),
                interface_description=interface_info.get('description', ''),
                request_params=interface_info.get('request_params', ''),
                request_json_sample=interface_info.get('request_json', ''),
                response_json_sample=interface_info.get('response_json', ''),
                response_params=interface_info.get('response_params', ''),
                process_flow=interface_info.get('process_flow', ''),
                flow_chart_desc=interface_info.get('flow_chart_desc', ''),
                detail_flow_analysis=flow_analysis,
                interface_data=interface_info,
                flow_chart_analysis=review_data.flow_chart_analysis,
                image_analysis=interface_images,  # 只保存该接口的图片
                api_section=review_data.api_section,
                document_content=review_data.document_content,
                status=review_data.status,
                creator=creator
            )
        else:
            # 文档级别记录：包含所有流程图，但只包含知识图片
            # 合并：flow_chart_analysis + 知识图片
            merged_flow_analysis = list(review_data.flow_chart_analysis) if review_data.flow_chart_analysis else []
            for img in general_images:
                if img.get('success'):
                    merged_flow_analysis.append({
                        "source": "image",
                        "source_type": "general_knowledge",  # 标记为知识图片
                        "filename": img.get("filename", ""),
                        "analysis": img.get("analysis", "")
                    })

            return cls(
                doc_id=review_data.doc_id,
                document_title=review_data.document_title,
                business_module=review_data.business_module,
                project_background=review_data.project_background,
                business_summary=review_data.business_summary,
                flow_chart_analysis=merged_flow_analysis,
                image_analysis=general_images,  # 只保存知识图片
                api_section=review_data.api_section,
                document_content=review_data.document_content,
                status=review_data.status,
                creator=creator
            )
