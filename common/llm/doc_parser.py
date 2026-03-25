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
        # 方法1: 查找"请求示例"后跟 API 格式（POST/GET + URL + Content-Type + JSON）
        section_pattern = r'(?:请求示例|入参示例)[：:\s]*\n*([\s\S]*?)(?=1\.\d+.*?出参|出参示例|响应示例|$)'
        section_match = re.search(section_pattern, full_text, re.IGNORECASE | re.MULTILINE)
        if section_match:
            section_text = section_match.group(1).strip()
            # 在这段文本中查找 API 格式的 JSON
            api_json_match = re.search(
                r'(?:POST|GET|PUT|DELETE|PATCH)\s+[^\n]+\nContent-Type:\s*application/json\s*\n+(\{[\s\S]*?\})',
                section_text,
                re.IGNORECASE | re.MULTILINE
            )
            if api_json_match:
                json_str = api_json_match.group(1).strip()
                try:
                    params_example = json.loads(json_str)
                    print(f"[DEBUG] 从API格式匹配到JSON: {json_str[:200]}...")
                except json.JSONDecodeError:
                    # JSON 格式不规范时，保存原始文本供后续处理
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
                    try:
                        params_example = json.loads(json_str)
                        print(f"[DEBUG] 清理后匹配到JSON: {json_str[:200]}...")
                    except:
                        # 保存原始文本，标记为待处理
                        params_example = {"_raw_json_text": json_str}
                        print(f"[DEBUG] JSON格式不规范，保存原始文本: {json_str[:200]}...")

        # 方法2: 直接从 full_text 中查找 API 格式的 JSON
        if not params_example:
            api_json_pattern = r'(?:POST|GET|PUT|DELETE|PATCH)\s+[^\n]+\nContent-Type:\s*application/json\s*\n+(\{[\s\S]*?\})'
            api_match = re.search(api_json_pattern, full_text, re.IGNORECASE | re.MULTILINE)
            if api_match:
                json_str = api_match.group(1).strip()
                try:
                    params_example = json.loads(json_str)
                    print(f"[DEBUG] 从API格式匹配到JSON(方法2): {json_str[:200]}...")
                except json.JSONDecodeError:
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
                    try:
                        params_example = json.loads(json_str)
                    except:
                        # 保存原始文本，标记为待处理
                        params_example = {"_raw_json_text": json_str}
                        print(f"[DEBUG] JSON格式不规范，保存原始文本(方法2): {json_str[:200]}...")

        # 方法3: 如果还没找到，尝试通用的 JSON 匹配模式
        if not params_example:
            json_patterns = [
                r'\{[\s\S]{50,3000}\}(?=\s*\n\s*(?:1\.\d|出参|响应|$))',
            ]
            for pattern in json_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE)
                if match:
                    json_str = match.group(0).strip()
                    try:
                        params_example = json.loads(json_str)
                        print(f"[DEBUG] 从通用模式匹配到JSON: {json_str[:200]}...")
                        break
                    except json.JSONDecodeError:
                        # 可能是嵌套JSON字符串格式，尝试修复
                        try:
                            # 处理 action_context 等字段包含嵌套JSON字符串的情况
                            # 将 "action_context": "{ ... }" 转换为 "action_context": { ... }
                            fixed = _fix_nested_json(json_str)
                            if fixed:
                                params_example = json.loads(fixed)
                                print(f"[DEBUG] 修复嵌套JSON后成功: {fixed[:200]}...")
                                break
                        except Exception as e:
                            print(f"[DEBUG] 修复嵌套JSON失败: {e}")
                            continue

    return {"fields": fields, "tables": tables, "params_example": params_example, "text": full_text}


def _fix_nested_json(json_str: str) -> str:
    """
    修复嵌套JSON字符串格式的问题。

    文档中可能有这种格式：
    "action_context": "{
        "amount": 50000,
        "currency": "CNY"
    }"

    需要转换为有效的JSON：
    "action_context": {
        "amount": 50000,
        "currency": "CNY"
    }
    """
    import re

    result = json_str

    # 找到所有嵌套 JSON 字符串的模式
    # 例如: "action_context": "{
    #     nested content
    #   }",
    # 这种格式的问题在于，内部的 JSON 对象被当作字符串值处理了

    # 方法1：找到 "field_name": "{ 开头，到 }", 结尾
    # 使用正则匹配多行
    nested_pattern = r'"([^"]+)":\s*"(\{[\s\S]*?\})"(?=\s*[,}\]])'

    def fix_single_nested(match):
        field_name = match.group(1)
        nested_content = match.group(2)

        # 尝试解析内部内容
        inner = nested_content.strip()
        if inner.startswith('{') and inner.endswith('}'):
            # 检查内部是否有未转义的双引号
            try:
                # 首先尝试直接解析
                json.loads(inner)
                return match.group(0)  # 已经是有效的 JSON
            except json.JSONDecodeError:
                pass

            # 尝试转义内部的双引号
            # 找到字段名和值，替换未转义的双引号
            # 这是一个简化处理，假设内部是标准的 JSON 格式

            # 使用字符级处理
            fixed_inner = _escape_json_string(inner)
            try:
                json.loads(fixed_inner)
                return f'"{field_name}": {fixed_inner}'
            except:
                pass

        return match.group(0)

    result = re.sub(nested_pattern, fix_single_nested, result)

    return result


def _escape_json_string(s: str) -> str:
    """
    将 JSON 字符串中的未转义字符转义。

    这个函数处理文档中格式不规范的嵌套 JSON。
    """
    import re

    # 原始字符串可能包含：
    # "field": "{
    #     "nested_field": "value"
    # }"

    # 我们需要：
    # 1. 找到嵌套 JSON 的开始（以 { 开头）
    # 2. 找到嵌套 JSON 的结束（找到对应的最后一个 }）
    # 3. 将内部的未转义双引号转义

    # 简化处理：找到 "field": "{ 模式，提取到下一个 ", 模式
    lines = s.split('\n')
    result_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # 检查是否是嵌套 JSON 字段的开始
        # 例如: "action_context": "{
        if re.match(r'^\s*"[^"]+":\s*"\{', line):
            # 收集多行直到找到结束
            nested_lines = [line]
            i += 1

            # 找到结束行（以 }", 或 }" 结尾）
            while i < len(lines):
                next_line = lines[i]
                nested_lines.append(next_line)

                # 检查是否是结束行
                if re.search(r'^\s*\}",?\s*$', next_line) or re.search(r'\}"\s*,\s*$', next_line):
                    break
                i += 1

            # 合并嵌套行
            nested_str = '\n'.join(nested_lines)

            # 去掉首尾引号并转义
            # 模式: "field": "{
            #        content
            #     }",

            # 找到第一个 ": " 后的 { 和 最后的 }",
            # 中间的内容需要重新构建为有效的 JSON

            # 简单方法：提取 { 到 } 的内容，然后重新构建
            match = re.search(r'"\s*(\{[\s\S]*\})\s*"', nested_str)
            if match:
                inner = match.group(1)
                # 去掉首尾的 { 和 }
                if inner.startswith('{'):
                    inner = inner[1:]
                if inner.endswith('}'):
                    inner = inner[:-1]
                inner = inner.strip()

                # 内部的内容应该已经是有效的 JSON 格式
                # 重新构建
                field_match = re.match(r'^"([^"]+)":\s*', nested_str)
                if field_match:
                    field_name = field_match.group(1)
                    # 假设 inner 是有效的 JSON 对象
                    result_lines.append(f'"{field_name}": {{')
                    result_lines.append(inner.strip(','))
                    result_lines.append('}')
                    i += 1
                    continue

            result_lines.append(line)
        else:
            result_lines.append(line)

        i += 1

    return '\n'.join(result_lines)


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

