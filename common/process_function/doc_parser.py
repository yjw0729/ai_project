import os
import re
from typing import List, Dict, Any, Optional
import docs
import pdfplumber

def _parse_type_and_length(type_str: str) -> Dict[str, Any]:
    """
    将类似 String(32) / int(11) / decimal(10,2) 解析为类型与长度/精度。
    """
    if not type_str:
        return {"type": "", "maxLength": None, "precision": None, "scale": None}
    s = type_str.strip()
    m = re.match(r"([A-Za-z]+)\s*\(([\d, ]+)\)", s)
    if not m:
        return {"type": s.lower(), "maxLength": None, "precision": None, "scale": None}
    base = m.group(1).lower()
    nums = [int(x.strip()) for x in m.group(2).split(",") if x.strip().isdigit()]
    info = {"type": base, "maxLength": None, "precision": None, "scale": None}
    if base in ["string", "varchar", "char"] and nums:
        info["maxLength"] = nums[0]
    elif base in ["int", "integer"] and nums:
        info["maxLength"] = nums[0]
    elif base in ["decimal", "number", "numeric"] and len(nums) >= 2:
        info["precision"] = nums[0]
        info["scale"] = nums[1]
    return info


def _parse_required(val: str) -> str:
    if not val:
        return "unknown"
    v = val.strip().upper()
    if v == "Y":
        return "required"
    if v == "N":
        return "optional"
    if v == "C":
        return "conditional"
    return "unknown"


def _row_to_field(row: Dict[str, str], location_prefix: str = "") -> Dict[str, Any]:
    """
    将一行表格转换为标准字段描述。
    期望列名：字段名称/参数名称/参数类型/是否必填/备注
    """
    name = row.get("字段名称") or row.get("字段名") or row.get("name") or ""
    param_name = row.get("参数名称") or row.get("param") or row.get("label") or ""
    type_str = row.get("参数类型") or row.get("type") or ""
    required_raw = row.get("是否必填") or row.get("required") or ""
    desc = row.get("备注") or row.get("说明") or row.get("desc") or ""

    type_info = _parse_type_and_length(type_str)
    required_norm = _parse_required(required_raw)
    location = location_prefix or "body"

    field = {
        "name": name or param_name,
        "display_name": param_name or name,
        "location": location,
        "type": type_info.get("type") or "",
        "maxLength": type_info.get("maxLength"),
        "precision": type_info.get("precision"),
        "scale": type_info.get("scale"),
        "required": required_norm,
        "raw_required": required_raw,
        "raw_type": type_str,
        "desc": desc,
    }
    return field


def parse_doc_tables(tables: List[List[List[str]]], location_hint: str = "body") -> List[Dict[str, Any]]:
    """
    解析提取好的表格内容。
    tables: 每个表格是二维数组 rows×cols，第一行是表头。
    """
    fields: List[Dict[str, Any]] = []
    for tbl in tables:
        if not tbl or len(tbl) < 2:
            continue
        headers = [h.strip() for h in tbl[0]]
        for row in tbl[1:]:
            row_map = {}
            for h, v in zip(headers, row):
                row_map[h.strip()] = (v or "").strip()
            field = _row_to_field(row_map, location_prefix=location_hint)
            if field.get("name"):
                fields.append(field)
    return fields


def parse_doc_file(file_path: str, location_hint: str = "body") -> Dict[str, Any]:
    """
    解析 docx/pdf 文件中的表格，返回 {fields: [...], params_example: {...}}
    - docx: 使用 python-docx 读取表格和段落文本
    - pdf: 使用 pdfplumber 读取表格（简单模式）
    - 尝试从文档中提取JSON示例（如"1.1.3入参示例"等标题下的JSON）
    """
    import json
    ext = os.path.splitext(file_path)[1].lower()
    tables: List[List[List[str]]] = []
    params_example: Optional[Dict[str, Any]] = None
    full_text = ""

    if ext in [".docx", ".doc"]:
        try:
            import docx
        except ImportError:
            raise RuntimeError("缺少依赖 python-docx，请先安装")
        doc = docx.Document(file_path)
        for tbl in doc.tables:
            rows = []
            for row in tbl.rows:
                rows.append([cell.text.strip() for cell in row.cells])
            if rows:
                tables.append(rows)
        # 提取所有段落文本，用于查找JSON示例
        full_text = "\n".join([p.text for p in doc.paragraphs])
    elif ext == ".pdf":
        try:
            import pdfplumber
        except ImportError:
            raise RuntimeError("缺少依赖 pdfplumber，请先安装")
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                try:
                    tbls = page.extract_tables()
                    for t in tbls:
                        if t:
                            tables.append(t)
                    full_text += page.extract_text() or ""
                except Exception:
                    continue
    else:
        raise RuntimeError(f"不支持的文件类型: {ext}")

    fields = parse_doc_tables(tables, location_hint=location_hint)

    # 尝试从文档文本中提取JSON示例（查找"入参示例"、"请求示例"等关键词后的JSON）
    if full_text:
        # 方法1: 查找"1.1.3入参示例"和"1.1.4出参"之间的内容
        section_pattern = r'(?:1\.\d+\.\d+.*?入参示例|入参示例|请求示例|请求体示例|参数示例)[：:]\s*\n?([\s\S]*?)(?=1\.\d+\.\d+.*?出参|出参示例|响应示例|$)'
        section_match = re.search(section_pattern, full_text, re.IGNORECASE | re.MULTILINE)
        if section_match:
            section_text = section_match.group(1).strip()
            # 从这段文本中提取JSON
            json_in_section = re.search(r'(\{[\s\S]*?\})', section_text)
            if json_in_section:
                json_str = json_in_section.group(1).strip()
                try:
                    params_example = json.loads(json_str)
                except json.JSONDecodeError:
                    # 尝试清理可能的格式问题
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
                    try:
                        params_example = json.loads(json_str)
                    except:
                        pass

        # 方法2: 如果方法1没找到，尝试直接匹配JSON块
        if not params_example:
            json_patterns = [
                r'(?:入参示例|请求示例|请求体示例|参数示例)[：:]\s*\n?(\{[\s\S]*?\})',
                r'(?:入参示例|请求示例|请求体示例|参数示例)[：:]\s*\n?```(?:json)?\s*(\{[\s\S]*?\})\s*```',
            ]
            for pattern in json_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE)
                if match:
                    json_str = match.group(1).strip()
                    try:
                        params_example = json.loads(json_str)
                        break
                    except json.JSONDecodeError:
                        # 尝试清理可能的格式问题
                        json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)  # 移除控制字符
                        try:
                            params_example = json.loads(json_str)
                            break
                        except:
                            continue

    return {"fields": fields, "tables": tables, "params_example": params_example}


def constraints_from_fields(fields: List[Dict[str, Any]]) -> str:
    """
    将字段列表转换为约束文本，供 LLM prompt 使用。
    """
    lines = []
    for f in fields:
        parts = [
            f"字段:{f.get('name')}",
            f"位置:{f.get('location')}",
            f"类型:{f.get('raw_type') or f.get('type')}",
            f"必填:{f.get('required')}",
        ]
        if f.get("maxLength"):
            parts.append(f"最大长度:{f['maxLength']}")
        if f.get("precision") and f.get("scale"):
            parts.append(f"精度:{f['precision']},{f['scale']}")
        if f.get("desc"):
            parts.append(f"备注:{f['desc']}")
        lines.append("；".join(parts))
    return "\n".join(lines)


def build_params_example(fields: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    基于字段生成简单的 params 示例，只放置空值/示例。
    这里按 location 归类，简单放到 body 下。
    """
    body: Dict[str, Any] = {}
    for f in fields:
        name = f.get("name") or ""
        if not name:
            continue
        # 简单填充示例
        example_val: Any = ""
        t = (f.get("type") or "").lower()
        if t in ["int", "integer", "number", "numeric", "decimal"]:
            example_val = 0
        elif t in ["boolean", "bool"]:
            example_val = False
        else:
            example_val = ""
        body[name] = example_val
    return body

