#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
接口文档解析器
从 Word 文档中解析接口名称、请求参数、响应参数（字段名、必填、枚举、说明）
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ApiParam:
    """单个接口参数"""
    name: str
    required: bool = False
    description: str = ""
    enum_values: List[str] = field(default_factory=list)
    param_type: str = ""


@dataclass
class ApiInterface:
    """接口信息"""
    name: str
    request_params: List[ApiParam] = field(default_factory=list)
    response_params: List[ApiParam] = field(default_factory=list)


def extract_content_from_docx(file_path: str) -> Tuple[str, List[List[str]]]:
    """
    从 docx 提取纯文本和表格内容。
    返回: (全文, 表格列表，每个表格为行列表，每行为单元格字符串列表)
    """
    try:
        from docx import Document
        doc = Document(file_path)
        paragraphs = []
        for p in doc.paragraphs:
            t = p.text.strip()
            if t:
                paragraphs.append(t)
        text = "\n".join(paragraphs)

        tables = []
        for table in doc.tables:
            rows = []
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                rows.append(cells)
            if rows:
                tables.append(rows)
        return text, tables
    except Exception as e:
        logger.warning(f"extract_content_from_docx failed: {e}")
        return "", []


def _normalize_header(header: str) -> str:
    h = header.strip().lower()
    if "参数" in header and "名" in header or "name" in h or "field" in h:
        return "name"
    if "必填" in header or "required" in h or "必须" in header:
        return "required"
    if "类型" in header or "type" in h:
        return "type"
    if "说明" in header or "描述" in header or "description" in h or "备注" in header:
        return "desc"
    if "枚举" in header or "enum" in h or "取值" in header:
        return "enum"
    if "默认" in header or "default" in h:
        return "default"
    return ""


def _parse_table_to_params(rows: List[List[str]]) -> List[ApiParam]:
    """将表格行解析为 ApiParam 列表"""
    if len(rows) < 2:
        return []
    first_row = [c for c in rows[0] if c]
    first_text = " ".join(first_row).strip().lower()
    # 若第一行像章节标题（如“请求参数”），用第二行当表头
    if len(rows) >= 3 and (
        len(first_row) <= 2
        or ("请求" in first_text and "参数" in first_text)
        or ("响应" in first_text and "参数" in first_text)
    ):
        header_row = [c for c in rows[1] if c]
        data_rows = rows[2:]
    else:
        header_row = first_row
        data_rows = rows[1:]
    if not header_row:
        return []
    col_map = {}
    for i, cell in enumerate(header_row):
        key = _normalize_header(cell)
        if key:
            col_map[key] = i
    name_col = col_map.get("name", 0)
    required_col = col_map.get("required", -1)
    desc_col = col_map.get("desc", -1)
    type_col = col_map.get("type", -1)
    enum_col = col_map.get("enum", -1)

    params = []
    for row in data_rows:
        if not row:
            continue
        name = row[name_col] if name_col < len(row) else ""
        name = name.strip()
        if not name or name.startswith("-") or name == "参数名":
            continue
        required = False
        if required_col >= 0 and required_col < len(row):
            req_val = row[required_col].strip()
            required = req_val in ("是", "必填", "Y", "Yes", "true", "1", "必选")
        desc = row[desc_col].strip() if desc_col >= 0 and desc_col < len(row) else ""
        ptype = row[type_col].strip() if type_col >= 0 and type_col < len(row) else ""
        enum_str = row[enum_col].strip() if enum_col >= 0 and enum_col < len(row) else ""
        enum_values = []
        if enum_str:
            for part in re.split(r"[,，;；、\s]+", enum_str):
                part = part.strip()
                if part:
                    enum_values.append(part)
        params.append(ApiParam(
            name=name,
            required=required,
            description=desc,
            enum_values=enum_values,
            param_type=ptype
        ))
    return params


def _find_interface_name_from_text(text: str, default: str = "接口") -> str:
    """从正文中推断接口名称"""
    lines = text.split("\n")
    for line in lines[:30]:
        line = line.strip()
        if not line:
            continue
        if "接口" in line and len(line) < 50:
            return line
        if "接口" in line:
            return line[:50]
    return default


def _find_params_in_text(text: str, section_keywords: List[str]) -> List[ApiParam]:
    """在纯文本中查找参数（简单启发式）"""
    params = []
    # 匹配 字段名(fieldName) 或 **fieldName** 或 参数：xxx
    pattern = re.compile(
        r"(?:(?:参数名|字段名|参数)\s*[：:]\s*)?"
        r"([a-zA-Z_][a-zA-Z0-9_]*)\s*"
        r"(?:[（(][^）)]*[）)])?\s*"
        r"(?:\s*[：:]\s*(.*?))?(?=\n|$)",
        re.MULTILINE | re.DOTALL
    )
    for m in pattern.finditer(text):
        name, rest = m.group(1), (m.group(2) or "").strip()
        if len(name) < 2:
            continue
        required = "必填" in rest or "必选" in rest
        desc = rest
        enum_values = []
        if "枚举" in rest or "取值" in rest:
            for part in re.split(r"[,，;；、\s]+", rest):
                if part and not part.startswith("枚举") and not part.startswith("取值"):
                    enum_values.append(part.strip())
        params.append(ApiParam(name=name, required=required, description=desc, enum_values=enum_values))
    return params


def parse_api_doc_from_docx(
    file_path: str,
    root_title: Optional[str] = None,
) -> Tuple[str, List[ApiInterface]]:
    """
    从接口说明 Word 文档解析出接口列表及请求/响应参数。

    Returns:
        (root_title, [ApiInterface, ...])
    """
    text, tables = extract_content_from_docx(file_path)
    interfaces: List[ApiInterface] = []
    root = root_title or _find_interface_name_from_text(text, "接口文档")

    # 1) 用表格解析：通常一个表格对应“请求参数”或“响应参数”
    request_keywords = ["请求参数", "请求体", "入参", "request", "input"]
    response_keywords = ["响应参数", "返回参数", "出参", "response", "output"]

    next_table_is_response = False
    for table_rows in tables:
        if not table_rows:
            continue
        first_row_text = " ".join(str(c) for c in table_rows[0])
        first_row_lower = first_row_text.lower()
        is_request = any(k in first_row_text or k in first_row_lower for k in request_keywords)
        is_response = any(k in first_row_text or k in first_row_lower for k in response_keywords)
        params = _parse_table_to_params(table_rows)
        if not params:
            # 可能是表头行写的是“请求参数”等，尝试把第一行当表头
            if len(table_rows) >= 2 and (is_request or is_response):
                params = _parse_table_to_params(table_rows)
            if not params:
                continue
        if not interfaces:
            interfaces.append(ApiInterface(name=root, request_params=[], response_params=[]))
        if next_table_is_response:
            interfaces[-1].response_params = params
            next_table_is_response = False
        elif is_response:
            interfaces[-1].response_params = params
        elif is_request:
            interfaces[-1].request_params = params
        else:
            if not interfaces[-1].request_params:
                interfaces[-1].request_params = params
            else:
                interfaces[-1].response_params = params

    # 2) 若没有从表格解析到任何参数，尝试从正文解析
    if not interfaces or (not interfaces[0].request_params and not interfaces[0].response_params):
        params = _find_params_in_text(text, request_keywords)
        if params or not interfaces:
            if not interfaces:
                interfaces = [ApiInterface(name=root, request_params=params, response_params=[])]
            else:
                interfaces[0].request_params = params or interfaces[0].request_params

    if not interfaces:
        interfaces = [ApiInterface(name=root, request_params=[], response_params=[])]

    return root, interfaces


def api_interfaces_to_xmind_tree(
    root_title: str,
    interfaces: List[ApiInterface],
) -> List[Dict[str, Any]]:
    """
    将 ApiInterface 列表转成 XMind 的 content 树结构（仅数据，不写文件）。
    结构：根 -> 接口名 -> 请求参数/响应参数 -> 字段名 -> 必填 | 枚举 | 枚举值/说明
    """
    import uuid
    from datetime import datetime

    def make_id():
        return f"id_{uuid.uuid4().hex[:8]}"

    def add_param_children(parent: Dict, param: ApiParam) -> None:
        # 子节点1：参数名称（就是字段名本身，这里冗余显示便于理解）
        parent["children"]["attached"].append({
            "id": make_id(),
            "title": f"参数名称: {param.name}",
            "children": {"attached": []},
        })
        # 子节点2：是否必填
        required_text = "是" if param.required else "否"
        parent["children"]["attached"].append({
            "id": make_id(),
            "title": f"是否必填: {required_text}",
            "children": {"attached": []},
        })
        # 子节点3：码值（枚举值）
        if param.enum_values:
            enum_node = {
                "id": make_id(),
                "title": "码值",
                "children": {"attached": []},
            }
            for v in param.enum_values:
                enum_node["children"]["attached"].append({
                    "id": make_id(),
                    "title": v,
                    "children": {"attached": []},
                })
            parent["children"]["attached"].append(enum_node)

    root = {
        "id": "root",
        "title": root_title,
        "children": {"attached": []},
    }

    for iface in interfaces:
        iface_node = {
            "id": make_id(),
            "title": iface.name,
            "children": {"attached": []},
        }
        if iface.request_params:
            req_node = {
                "id": make_id(),
                "title": "请求参数",
                "children": {"attached": []},
            }
            for p in iface.request_params:
                param_node = {
                    "id": make_id(),
                    "title": p.name,
                    "children": {"attached": []},
                }
                add_param_children(param_node, p)
                req_node["children"]["attached"].append(param_node)
            iface_node["children"]["attached"].append(req_node)
        if iface.response_params:
            res_node = {
                "id": make_id(),
                "title": "响应参数",
                "children": {"attached": []},
            }
            for p in iface.response_params:
                param_node = {
                    "id": make_id(),
                    "title": p.name,
                    "children": {"attached": []},
                }
                add_param_children(param_node, p)
                res_node["children"]["attached"].append(param_node)
            iface_node["children"]["attached"].append(res_node)
        root["children"]["attached"].append(iface_node)

    return [{
        "rootTopic": root,
        "topicSelected": 0,
        "view": {"zoomLevel": 100, "showTheme": True},
        "selection": [],
        "lastModified": datetime.now().isoformat(),
    }]


def generate_api_params_xmind(
    root_title: str,
    interfaces: List[ApiInterface],
    output_dir: str,
    filename_prefix: str = "接口参数",
) -> str:
    """
    生成接口出入参的 XMind 文件，返回文件路径。
    样式：根 -> 接口名 -> 请求参数/响应参数 -> 字段名 -> 必填 | 枚举 | 枚举值/说明（无图标）
    """
    import json
    import zipfile
    from pathlib import Path
    from datetime import datetime

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = re.sub(r'[^\w\s\u4e00-\u9fff-]', '', root_title).strip() or "接口"
    xmind_path = output_path / f"{filename_prefix}_{safe_title}_{timestamp}.xmind"

    content_list = api_interfaces_to_xmind_tree(root_title, interfaces)
    content_json = json.dumps(content_list, ensure_ascii=False, indent=2)

    with zipfile.ZipFile(xmind_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content.json", content_json)
        manifest = {
            "version": "1.0",
            "media": {"content/json": {"path": "content.json"}},
        }
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        meta_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<meta>
    <app name="XMind" version="3.7.9"/>
    <created>{datetime.now().isoformat()}</created>
    <creator>API Doc Parser</creator>
    <description>{root_title}</description>
</meta>"""
        zf.writestr("meta.xml", meta_xml)

    return str(xmind_path)
