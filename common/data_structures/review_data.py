from datetime import datetime
from typing import List, Dict, Any


class ReviewData:
    """
    审核数据结构 - Phase 1（识别）和 Phase 2（生成）之间的数据载体。

    注意：此类与 api/http_test_case_generate.py 中原有的 ReviewData 类完全兼容，
    通过将此类提取为 shared 模块来消除循环导入。
    """
    def __init__(self, doc_id: str, document_title: str, business_module: str = ""):
        self.doc_id = doc_id
        self.document_title = document_title
        self.business_module = business_module
        self.project_background = ""
        self.business_summary = ""          # 服务内容摘要
        self.interface_list = []           # list[dict] - 接口列表
        self.flow_chart_analysis = []     # list[dict] - 流程图分析结果
        self.status = "pending"           # pending | approved | rejected
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.document_content = ""        # 原始文档内容
        self.api_section = ""            # API 部分原始内容
        self.image_analysis = []         # list[dict] - 图片分析结果
        # 需求文档专用字段
        self.functional_modules = []      # 功能模块列表
        self.business_flows = []         # 业务流程列表
        self.business_rules = []          # 业务规则列表
        self.inferred_interfaces = []    # 推断的接口列表
        self.document_type = ""           # api_doc | product_design

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "document_title": self.document_title,
            "business_module": self.business_module,
            "project_background": self.project_background,
            "business_summary": self.business_summary,
            "interface_list": self.interface_list,
            "flow_chart_analysis": self.flow_chart_analysis,
            "image_analysis": self.image_analysis,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "functional_modules": self.functional_modules,
            "business_flows": self.business_flows,
            "business_rules": self.business_rules,
            "inferred_interfaces": self.inferred_interfaces,
            "document_type": self.document_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ReviewData':
        review = cls(
            doc_id=data.get("doc_id", ""),
            document_title=data.get("document_title", ""),
            business_module=data.get("business_module", "")
        )
        review.project_background = data.get("project_background", "")
        review.business_summary = data.get("business_summary", "")
        review.interface_list = data.get("interface_list", [])
        review.flow_chart_analysis = data.get("flow_chart_analysis", [])
        review.status = data.get("status", "pending")
        review.created_at = data.get("created_at", datetime.now().isoformat())
        review.updated_at = data.get("updated_at", datetime.now().isoformat())
        review.document_content = data.get("document_content", "")
        review.api_section = data.get("api_section", "")
        review.image_analysis = data.get("image_analysis", [])
        review.functional_modules = data.get("functional_modules", [])
        review.business_flows = data.get("business_flows", [])
        review.business_rules = data.get("business_rules", [])
        review.inferred_interfaces = data.get("inferred_interfaces", [])
        review.document_type = data.get("document_type", "")
        return review
