from datetime import datetime
from typing import List, Dict, Any


class ReviewData:
    """
    审核数据结构 - Phase 1（识别）和 Phase 2（生成）之间的数据载体。
    """
    def __init__(self, doc_id: str, document_title: str, business_module: str = ""):
        self.doc_id = doc_id
        self.document_title = document_title
        self.business_module = business_module
        self.project_background = ""
        self.business_summary = ""
        self.interface_list = []
        self.flow_chart_analysis = []
        self.status = "pending"
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.document_content = ""
        self.api_section = ""
        self.image_analysis = []
        self.functional_modules = []
        self.business_flows = []
        self.business_rules = []
        self.inferred_interfaces = []
        self.document_type = ""

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
