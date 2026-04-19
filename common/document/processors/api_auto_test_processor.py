"""
API自动化测试文档处理器 - RAG向量层
"""

import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

from common.llm.api_doc_analyzer import APIDocAnalyzer, FlowchartAnalyzer
from common.document.processors.api_doc_processor import APIDocumentProcessor

logger = logging.getLogger(__name__)


class APITestDocProcessor:
    """
    API自动化测试文档处理器。

    支持处理：
    - OpenAPI 3.0 / Swagger 2.0 文档（.json / .yaml）
    - 接口说明Word文档（.docx）
    - 流程图图片（.png / .jpg）
    - 流程描述文本

    文档上传后解析 → 接口信息提取 → 存入临时存储 → 供生成用例使用
    """

    # 支持的文件类型
    SUPPORTED_OPENAPI_EXTENSIONS = {".json", ".yaml", ".yml"}
    SUPPORTED_DOCX_EXTENSIONS = {".docx"}
    SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}

    def __init__(self, upload_dir: str = "uploads/api_auto_test"):
        self.upload_dir = upload_dir
        self.api_analyzer = APIDocAnalyzer()
        self.flowchart_analyzer = FlowchartAnalyzer()
        self.api_doc_processor = APIDocumentProcessor()

        os.makedirs(self.upload_dir, exist_ok=True)

    def process_upload(
        self,
        file_path: str,
        doc_type: str,
        system_name: Optional[str] = None,
        flowchart_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        处理上传的文档。
        doc_type: openapi | api_doc | flowchart
        """
        logger.info("【APITestDocProcessor】开始处理文档: path=%s, type=%s", file_path, doc_type)

        doc_id = str(uuid.uuid4())
        file_ext = os.path.splitext(file_path)[1].lower()

        result = {
            "doc_id": doc_id,
            "doc_type": doc_type,
            "system_name": system_name or "",
            "file_path": file_path,
            "parsed_interfaces": [],
            "flowchart_nodes": [],
            "flow_data": {},
            "error": None,
        }

        try:
            if doc_type == "openapi":
                interfaces = self._process_openapi(file_path)
                result["parsed_interfaces"] = interfaces
                logger.info("【APITestDocProcessor】OpenAPI解析完成: %d 个接口", len(interfaces))

            elif doc_type == "api_doc":
                interfaces = self._process_interface_doc(file_path)
                result["parsed_interfaces"] = interfaces
                logger.info("【APITestDocProcessor】接口文档解析完成: %d 个接口", len(interfaces))

            elif doc_type == "flowchart":
                if file_ext in self.SUPPORTED_IMAGE_EXTENSIONS:
                    flow_data = self._process_flowchart_image(file_path, flowchart_description)
                else:
                    flow_data = self._process_flowchart_text(file_path)
                result["flow_data"] = flow_data
                result["flowchart_nodes"] = flow_data.get("nodes", [])
                logger.info("【APITestDocProcessor】流程图解析完成: %d 个节点", len(result["flowchart_nodes"]))

            else:
                result["error"] = f"不支持的文档类型: {doc_type}"

        except Exception as e:
            logger.error("【APITestDocProcessor】处理文档异常: %s", str(e), exc_info=True)
            result["error"] = str(e)

        return result

    def _process_openapi(self, file_path: str) -> List[Dict[str, Any]]:
        """处理OpenAPI文档"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 先用现有的APIDocumentProcessor解析
        endpoints = self.api_doc_processor.process(content)

        interfaces = []
        for ep in endpoints:
            params_dict = {}
            for p in (ep.get("parameters") or []):
                params_dict[p.get("name", "")] = {
                    "type": p.get("param_type", "string"),
                    "required": p.get("required", False),
                    "description": p.get("description", ""),
                    "example": p.get("example"),
                }

            interfaces.append({
                "interface_name": ep.get("path", ""),
                "description": ep.get("description", ""),
                "method": ep.get("method", "GET"),
                "path": ep.get("path", ""),
                "request_params": params_dict,
                "response_params": ep.get("response", {}),
                "scenarios": ep.get("tags", []),
            })

        # 如果解析数量少，尝试LLM增强
        if len(interfaces) == 0:
            interfaces = self.api_analyzer.analyze_openapi(content)

        return interfaces

    def _process_interface_doc(self, file_path: str) -> List[Dict[str, Any]]:
        """处理接口说明Word文档"""
        # 提取文本内容
        doc_text = self._extract_docx_text(file_path)

        # 使用LLM分析接口文档
        interfaces = self.api_analyzer.analyze_interface_doc(doc_text, doc_type="docx")

        return interfaces

    def _extract_docx_text(self, file_path: str) -> str:
        """从Word文档中提取文本"""
        try:
            from docx import Document
            doc = Document(file_path)
            paragraphs = []
            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append(para.text)
            # 提取表格内容
            for table in doc.tables:
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if cells:
                        paragraphs.append(" | ".join(cells))
            return "\n".join(paragraphs)
        except Exception as e:
            logger.warning("【APITestDocProcessor】提取Word文档失败: %s", str(e))
            return ""

    def _process_flowchart_image(self, image_path: str, description: str = "") -> Dict[str, Any]:
        """处理流程图图片"""
        try:
            import base64
            with open(image_path, 'rb') as f:
                image_base64 = base64.b64encode(f.read()).decode('utf-8')
            flow_data = self.flowchart_analyzer.analyze_image_base64(image_base64, description)
            return flow_data
        except Exception as e:
            logger.error("【APITestDocProcessor】处理流程图图片失败: %s", str(e))
            return {"error": str(e), "nodes": [], "dependencies": []}

    def _process_flowchart_text(self, text_path: str) -> Dict[str, Any]:
        """处理流程描述文本"""
        try:
            with open(text_path, 'r', encoding='utf-8') as f:
                description = f.read()
            flow_data = self.flowchart_analyzer.analyze_text_description(description)
            return flow_data
        except Exception as e:
            logger.error("【APITestDocProcessor】处理流程文本失败: %s", str(e))
            return {"error": str(e), "nodes": [], "dependencies": []}

    def save_parsed_result(self, result: Dict[str, Any]) -> str:
        """保存解析结果到文件"""
        doc_id = result.get("doc_id", str(uuid.uuid4()))
        save_path = os.path.join(self.upload_dir, f"{doc_id}.json")
        os.makedirs(self.upload_dir, exist_ok=True)
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info("【APITestDocProcessor】解析结果已保存: %s", save_path)
        return save_path

    def load_parsed_result(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """加载已保存的解析结果"""
        save_path = os.path.join(self.upload_dir, f"{doc_id}.json")
        if not os.path.exists(save_path):
            return None
        with open(save_path, 'r', encoding='utf-8') as f:
            return json.load(f)
