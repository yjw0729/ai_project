import os
import uuid
import json
import base64
import logging
import threading
import asyncio
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

from common.llm.doc_parser import (
    parse_doc_file,
    constraints_from_fields,
    build_params_example,
)
from common.llm.ai_case_generator import generate_api_test_cases
from common.llm.api_doc_analyzer import FlowchartAnalyzer
from utils.read_config_path.read_ai_config import load_ai_config
from common.llm.llm_client import OpenAILLMClient
from api.http_ai_generate_cases import _load_stub_cases, _save_cases_to_db, _get_or_create_api_config
from common.data_structures.review_data import ReviewData
from common.db_mapper.review_record_mapper import ReviewRecordMapper

# 复用 http_test_case_generate.py 中的文档解析和预分析能力
from api.http_test_case_generate import (
    parse_document_structure,
    DOC_PRE_ANALYSIS_PROMPT,
    _parse_pre_analysis_result,
)

doc_parser_opt = Blueprint("doc_parser_opt", __name__)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _json_error(msg: str, code: int = 400):
    return jsonify({"code": code, "msg": msg, "data": None}), code


def _get_tasks_db_path():
    """获取任务数据库路径"""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "task.db")


def _init_tasks_db():
    """初始化任务数据库"""
    import sqlite3
    db_path = _get_tasks_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            task_type TEXT,
            status TEXT DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            params TEXT,
            interface_ids TEXT,
            result TEXT,
            error_message TEXT,
            created_at TEXT,
            updated_at TEXT,
            completed_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            knowledge_type TEXT,
            content TEXT,
            file_path TEXT,
            created_at TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(task_id)
        )
    """)
    conn.commit()
    conn.close()


@doc_parser_opt.route("/ai/parse_doc", methods=["POST"])
def parse_doc():
    """
    上传文档（docx/pdf），解析表格生成字段列表与约束。
    返回: fields, constraints, params_example
    """
    logger = current_app.logger or logging.getLogger(__name__)
    if "file" not in request.files:
        return _json_error("缺少文件字段 file")
    file = request.files["file"]
    if file.filename == "":
        return _json_error("文件名为空")

    filename = secure_filename(file.filename)
    saved_path = os.path.join(UPLOAD_DIR, filename)
    file.save(saved_path)
    logger.info("【parse_doc 入参】filename=%s", filename)

    try:
        parsed = parse_doc_file(saved_path, location_hint="body.data")
        fields = parsed.get("fields") or []
        constraints = constraints_from_fields(fields)
        params_example = build_params_example(fields)
        data = {
            "fields": fields,
            "constraints": constraints,
            "params_example": params_example,
            "file": filename,
        }
        return jsonify({"code": 200, "msg": "success", "data": data})
    except Exception as e:
        logger.exception("文档解析失败")
        return _json_error(f"文档解析失败: {e}", code=500)


@doc_parser_opt.route("/ai/generate_testcases_from_doc", methods=["POST"])
def generate_testcases_from_doc():
    """
    上传多种知识（图片+文本+文档）并创建用例生成任务。

    入参（form-data / JSON）：
    - texts: 纯文本内容，支持多个（form-data多个同名字段，或JSON数组）
    - documents: 文档文件，支持多个（form-data多个同名字段）
    - images: base64编码的图片列表（JSON数组）
    - api_name, http_method, path（必填）
    - api_desc, max_cases, persist（可选）
    - module: 所属模块（可选）
    - system: 所属系统（可选）

    响应：{ task_id, status: "pending" }
    后续通过 GET /api/tasks/{task_id} 轮询状态
    """
    import sqlite3
    logger = current_app.logger or logging.getLogger(__name__)

    # 解析请求
    if request.content_type and 'application/json' in request.content_type:
        # JSON 模式
        payload = request.get_json() or {}
        knowledge = {
            'images': payload.get('images') or [],
            'texts': payload.get('texts') or [],
            'documents': []  # JSON模式不支持直接传文件
        }
        # 兼容 knowledge 包装结构
        if payload.get('knowledge'):
            kg = payload['knowledge']
            knowledge['images'] = kg.get('images') or knowledge['images']
            knowledge['texts'] = kg.get('texts') or knowledge['texts']
    else:
        # form-data / multipart 模式 - 前端友好格式
        payload = request.form.to_dict()
        files = request.files

        # texts: 直接从 form-data 获取多个同名字段
        texts = request.form.getlist('texts')

        # documents: 直接从 form-data 获取多个文档文件
        doc_files = files.getlist('documents')

        # images: 从 form-data 获取多个图片文件，转为 base64
        img_b64_list = []
        img_files = files.getlist('images')
        for img_file in img_files:
            if hasattr(img_file, 'filename') and img_file.filename:
                img_bytes = img_file.read()
                b64 = base64.b64encode(img_bytes).decode('utf-8')
                # 推断 MIME 类型，拼 data-URI 前缀
                ext = os.path.splitext(img_file.filename)[1].lower()
                mime_map = {
                    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                    '.png': 'image/png', '.gif': 'image/gif',
                    '.webp': 'image/webp', '.bmp': 'image/bmp',
                }
                mime = mime_map.get(ext, 'application/octet-stream')
                img_b64_list.append(f'data:{mime};base64,{b64}')

        # texts 中也可能直接传了 base64 图片（兼容旧逻辑）
        # texts 中也可能传了纯文本
        # 合并：优先用 images 字段的图片，texts 保持为纯文本
        knowledge = {
            'images': img_b64_list,
            'texts': texts,
            'documents': doc_files
        }

    logger.info("【generate_testcases_from_doc 入参】api_name=%s, knowledge_types=%s",
                payload.get('api_name'),
                {k: len(v) if isinstance(v, list) else v for k, v in knowledge.items()})

    # 必填字段检查
    required = ["api_name", "http_method", "path"]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        return _json_error(f"缺少必填字段: {','.join(missing)}")

    # 至少有一种知识输入
    has_images = bool(knowledge.get('images'))
    has_texts = bool(knowledge.get('texts'))
    has_docs = bool(knowledge.get('documents'))
    if not (has_images or has_texts or has_docs):
        return _json_error("至少需要提供一种知识：images、texts 或 documents")

    # 生成任务ID
    task_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    # 初始化数据库
    _init_tasks_db()

    # 保存任务记录 - 添加超时设置避免数据库锁定
    conn = sqlite3.connect(_get_tasks_db_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 保存知识内容
        saved_doc_paths = []
        for img_b64 in (knowledge.get('images') or []):
            cursor.execute("""
                INSERT INTO task_knowledge (task_id, knowledge_type, content, created_at)
                VALUES (?, ?, ?, ?)
            """, (task_id, 'image', img_b64, now))

        for text in (knowledge.get('texts') or []):
            cursor.execute("""
                INSERT INTO task_knowledge (task_id, knowledge_type, content, created_at)
                VALUES (?, ?, ?, ?)
            """, (task_id, 'text', text, now))

        # 保存文档文件
        for doc_file in (knowledge.get('documents') or []):
            if hasattr(doc_file, 'filename') and doc_file.filename:
                filename = secure_filename(doc_file.filename)
                stored_name = f"{task_id}_{filename}"
                file_path = os.path.join(UPLOAD_DIR, stored_name)
                doc_file.save(file_path)
                saved_doc_paths.append(file_path)
                cursor.execute("""
                    INSERT INTO task_knowledge (task_id, knowledge_type, file_path, created_at)
                    VALUES (?, ?, ?, ?)
                """, (task_id, 'document', file_path, now))

        # 创建任务记录
        task_params = {
            'api_name': payload.get('api_name'),
            'api_desc': payload.get('api_desc'),
            'http_method': payload.get('http_method'),
            'path': payload.get('path'),
            'module': payload.get('module'),
            'system': payload.get('system'),
            'max_cases': payload.get('max_cases'),
            'persist': payload.get('persist', False) if isinstance(payload.get('persist'), bool) else str(payload.get('persist', 'false')).lower() == 'true',
            'knowledge_summary': {
                'images_count': len(knowledge.get('images') or []),
                'texts_count': len(knowledge.get('texts') or []),
                'documents_count': len(saved_doc_paths),
            }
        }

        cursor.execute("""
            INSERT INTO tasks (task_id, task_type, status, progress, params, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (task_id, 'case_generation', 'pending', 0, json.dumps(task_params), now, now))

        conn.commit()
        conn.close()

        logger.info("【创建用例生成任务】task_id=%s, 知识类型: 图片=%s, 文本=%s, 文档=%s",
                    task_id, has_images, has_texts, len(saved_doc_paths))

        # 保存知识内容供后台线程使用（序列化到临时文件）
        task_context = {
            'task_id': task_id,
            'api_name': payload.get('api_name'),
            'api_desc': payload.get('api_desc'),
            'http_method': payload.get('http_method'),
            'path': payload.get('path'),
            'module': payload.get('module'),
            'system': payload.get('system'),
            'max_cases': payload.get('max_cases'),
            'persist': task_params.get('persist'),
            'saved_doc_paths': saved_doc_paths,
        }
        context_path = os.path.join(UPLOAD_DIR, f"{task_id}_context.json")
        with open(context_path, 'w', encoding='utf-8') as f:
            json.dump(task_context, f, ensure_ascii=False)

        # 启动后台线程处理用例生成
        thread = threading.Thread(
            target=_process_case_generation_task,
            args=(task_id,),
            daemon=True
        )
        thread.start()
        logger.info("【后台任务已启动】task_id=%s", task_id)

        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                "task_id": task_id,
                "status": "pending",
                "message": "任务已创建，请通过 GET /api/tasks/{task_id} 轮询状态"
            }
        })
    except sqlite3.OperationalError as e:
        conn.rollback()
        if conn:
            conn.close()
        logger.error(f"数据库操作失败: {e}")
        return _json_error(f"数据库操作失败，请重试: {e}", code=500)
    except Exception as e:
        conn.rollback()
        if conn:
            conn.close()
        logger.exception("创建任务时发生未知错误")
        return _json_error(f"创建任务失败: {e}", code=500)


@doc_parser_opt.route("/ai/tasks/<task_id>/review", methods=["POST"])
def approve_and_generate_task(task_id: str):
    """
    Phase 2 触发接口：审批任务并启动用例生成后台线程。

    入参（JSON body，可选）：
    - reviewer: 审核人姓名
    - comment: 审核意见

    要求：
    1. task 存在于 tasks 表且 status == 'pending_review'
    2. review_record 存在且 status == 'pending'

    成功后：
    - review_record.status → 'approved'
    - tasks.status → 'running'（由 Phase2 线程更新）
    - 启动 _process_case_generation_phase2 后台线程
    """
    import sqlite3
    logger = current_app.logger or logging.getLogger(__name__)

    payload = request.get_json() or {}
    reviewer = payload.get('reviewer', 'system')
    comment = payload.get('comment', '')

    logger.info("[Review API] 审批触发 Phase2, task_id=%s, reviewer=%s", task_id, reviewer)

    # 1. 验证任务存在且处于 pending_review 状态
    conn = sqlite3.connect(_get_tasks_db_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT task_id, status FROM tasks WHERE task_id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return _json_error(f"任务不存在: {task_id}", code=404)

    if row['status'] != 'pending_review':
        return _json_error(
            f"任务状态不是 pending_review，当前状态: {row['status']}。请先完成 Phase 1 识别。",
            code=400
        )

    # 2. 更新 review_record 状态为 approved
    try:
        review_mapper = ReviewRecordMapper()
        review_mapper.update_status(
            doc_id=task_id,
            status='approved',
            reviewer=reviewer,
            review_comment=comment,
        )
        logger.info("[Review API] review_record 已更新为 approved, doc_id=%s", task_id)
    except Exception as up_err:
        logger.error("[Review API] 更新审核记录失败: %s", up_err)
        return _json_error(f"更新审核记录失败: {up_err}", code=500)

    # 3. 更新任务状态为 'completed'（案例生成中），Phase2 线程会继续更新
    _update_task_status(task_id, 'completed', progress=5)

    # 4. 启动 Phase 2 后台线程
    thread = threading.Thread(
        target=_process_case_generation_phase2,
        args=(task_id,),
        daemon=True,
    )
    thread.start()
    logger.info("[Review API] Phase2 线程已启动, task_id=%s", task_id)

    return jsonify({
        "code": 200,
        "msg": "success",
        "data": {
            "task_id": task_id,
            "status": "approved",
            "message": "审批通过，Phase 2 用例生成线程已启动"
        }
    })


@doc_parser_opt.route("/ai/image_to_base64", methods=["GET", "POST"])
def image_to_base64_api():
    """
    上传图片文件，返回 Base64 编码字符串。
    用于辅助 generate_testcases_from_doc 接口的 images 参数准备。

    入参（form-data / GET）：
    - file: 图片文件（POST 必填，支持 jpg/png/gif/webp/bmp 等格式）
    - path: 图片文件路径（GET 模式可通过 path 参数传入本地文件路径）

    响应：
    - base64: Base64 编码字符串（已含前缀如 data:image/png;base64,）
    - filename: 原始文件名
    - size: 文件大小（字节）
    """
    logger = current_app.logger or logging.getLogger(__name__)

    # GET 模式：通过本地文件路径读取
    if request.method == "GET":
        file_path = request.args.get("path", "")
        if not file_path:
            return _json_error("GET 模式请提供图片路径参数 path")

        if not os.path.isabs(file_path):
            # 相对路径拼到项目根目录
            file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), file_path)

        if not os.path.exists(file_path):
            return _json_error(f"文件不存在: {file_path}")

        filename = os.path.basename(file_path)
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
        except Exception as e:
            return _json_error(f"读取文件失败: {e}")

        return _encode_and_respond(filename, file_bytes, logger)

    # POST 模式：上传文件
    if "file" not in request.files:
        return _json_error("缺少文件字段 file")

    file = request.files["file"]
    if file.filename == "":
        return _json_error("文件名为空")

    try:
        file_bytes = file.read()
        return _encode_and_respond(file.filename, file_bytes, logger)
    except Exception as e:
        logger.exception("图片转 Base64 失败")
        return _json_error(f"图片转 Base64 失败: {e}", code=500)


def _encode_and_respond(filename: str, file_bytes: bytes, logger):
    """将图片字节编码为 Base64 并返回响应"""
    b64_data = base64.b64encode(file_bytes).decode("utf-8")

    ext = os.path.splitext(filename)[1].lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    mime_type = mime_map.get(ext, "application/octet-stream")
    data_uri = f"data:{mime_type};base64,{b64_data}"

    logger.info("【image_to_base64】filename=%s, size=%d bytes", filename, len(file_bytes))

    return jsonify({
        "code": 200,
        "msg": "success",
        "data": {
            "base64": data_uri,
            "base64_raw": b64_data,
            "filename": filename,
            "size": len(file_bytes),
            "mime_type": mime_type,
        }
    })


def _update_task_status(task_id: str, status: str, progress: int = None,
                        result: dict = None, error_message: str = None):
    """更新任务状态到数据库"""
    import sqlite3
    db_path = _get_tasks_db_path()
    now = datetime.now().isoformat()

    try:
        conn = sqlite3.connect(db_path, timeout=30)
        cursor = conn.cursor()

        # 构建更新语句
        updates = ["status = ?", "updated_at = ?"]
        values = [status, now]

        if progress is not None:
            updates.append("progress = ?")
            values.append(progress)

        if result is not None:
            updates.append("result = ?")
            values.append(json.dumps(result, ensure_ascii=False))

        if error_message is not None:
            updates.append("error_message = ?")
            values.append(error_message)

        if status in ('completed', 'failed', 'cancelled'):
            updates.append("completed_at = ?")
            values.append(now)

        values.append(task_id)
        cursor.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE task_id = ?", values)

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.getLogger(__name__).error(f"更新任务状态失败: {task_id}, {e}")
        return False


def _extract_doc_fields(parsed_doc: dict) -> dict:
    """
    从 parse_doc_file 返回的解析结果中进一步提取结构化字段：
    - request_params: 请求参数说明文本
    - request_json_sample: 请求JSON示例（从 params_example 或文档文本提取）
    - response_params: 响应参数说明文本
    - response_json_sample: 响应JSON示例（从文档文本提取）
    - process_flow: 处理流程描述
    """
    import re
    import json

    fields = parsed_doc.get("fields") or []
    tables = parsed_doc.get("tables") or []
    params_example = parsed_doc.get("params_example") or {}

    # 1. 构建 request_params 文本（从 fields 构建）
    request_params_parts = []
    for f in fields:
        parts = []
        name = f.get("name") or f.get("display_name") or ""
        if not name:
            continue
        parts.append(f"字段名:{name}")
        raw_type = f.get("raw_type") or f.get("type") or ""
        if raw_type:
            parts.append(f"类型:{raw_type}")
        required = f.get("required", "")
        if required and required != "unknown":
            parts.append(f"必填:{required}")
        desc = f.get("desc") or ""
        if desc:
            parts.append(f"说明:{desc}")
        request_params_parts.append("；".join(parts))

    request_params = "\n".join(request_params_parts)

    # 2. request_json_sample：优先用 params_example，否则从文档文本匹配
    request_json_sample = params_example if params_example else {}

    # ====== 新增：直接从文档文本中提取请求JSON示例 ======
    # 如果 params_example 为空，尝试从文档中匹配
    if not request_json_sample and doc_text:
        req_json_patterns = [
            # 匹配 ```json 代码块包裹的 JSON
            r'(?:POST|GET|PUT|DELETE|PATCH)\s+[/\w\-\{\}]+\s*\nContent-Type:\s*application/json\s*\n\s*```(?:json)?\s*(\{[\s\S]*?\})\s*```',
            # 匹配入参示例后面的 JSON
            r'(?:入参示例|请求示例|请求体示例|入参|请求体)[：:]\s*\n```(?:json)?\s*(\{[\s\S]*?\})\s*```',
            # 匹配任何位置的大括号 JSON 对象（简单模式）
            r'\{[\s\S]{20,5000}?"[a-z_]+"[\s\S]*?\}(?=\s*\n\s*(?:1\.\d|出参|响应|$))',
        ]
        for pattern in req_json_patterns:
            match = re.search(pattern, doc_text, re.IGNORECASE | re.MULTILINE)
            if match:
                json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', match.group(1).strip())
                try:
                    # 验证是否是有效 JSON
                    parsed = json.loads(json_str)
                    if isinstance(parsed, dict) and len(parsed) > 0:
                        request_json_sample = parsed
                        logger.info(f"[JSON提取] 从文档中匹配到请求JSON示例: {str(parsed)[:200]}...")
                        break
                except json.JSONDecodeError:
                    continue

    # 3-5. 尝试从文档文本中提取响应参数、响应JSON、处理流程
    # 先从表格中提取"出参"相关的表
    response_params = ""
    response_json_sample = {}
    process_flow = ""

    for tbl in tables:
        if not tbl or len(tbl) < 2:
            continue
        header_row = tbl[0]
        header_text = "|".join([h.strip().lower() for h in header_row])

        # 判断是入参表还是出参表
        is_response = any(kw in header_text for kw in ["出参", "响应", "返回", "output", "response"])
        is_request = any(kw in header_text for kw in ["入参", "请求", "input", "request", "字段"])

        if is_response:
            # 提取出参表作为 response_params
            resp_parts = []
            # 跳过表头，处理数据行
            for row in tbl[1:]:
                row_map = {}
                for h, v in zip(header_row, row):
                    row_map[h.strip()] = (v or "").strip()
                name = row_map.get("字段名称") or row_map.get("字段名") or row_map.get("name") or ""
                if not name:
                    continue
                parts = [f"字段名:{name}"]
                for col in ["参数类型", "type"]:
                    if row_map.get(col):
                        parts.append(f"类型:{row_map[col]}")
                        break
                for col in ["是否必填", "required"]:
                    val = row_map.get(col, "")
                    if val:
                        parts.append(f"必填:{val}")
                        break
                for col in ["备注", "说明", "desc"]:
                    val = row_map.get(col, "")
                    if val:
                        parts.append(f"说明:{val}")
                        break
                resp_parts.append("；".join(parts))
            if resp_parts:
                response_params = (response_params + "\n" + "\n".join(resp_parts)).strip()

    # 从文档全文本中提取 response_json_sample
    # 优先用传入的 text，否则从 tables 重建文本
    doc_text = parsed_doc.get("text", "")
    if not doc_text and tables:
        # 从表格重建文本（用于 JSON 匹配）
        doc_text = "\n".join(
            "\n".join(" | ".join(row) for row in tbl)
            for tbl in tables
        )

    # 匹配响应JSON示例
    if doc_text:
        resp_json_patterns = [
            r'(?:出参示例|出参|响应示例|响应体示例|响应JSON|返回示例)[：:]\s*\n?```(?:json)?\s*(\{[\s\S]*?\})\s*```',
            r'(?:出参示例|出参|响应示例|响应体示例|响应JSON|返回示例)[：:]\s*\n?(\{[\s\S]*?\})',
        ]
        for pattern in resp_json_patterns:
            match = re.search(pattern, doc_text, re.IGNORECASE | re.MULTILINE)
            if match:
                json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', match.group(1).strip())
                try:
                    response_json_sample = json.loads(json_str)
                    break
                except json.JSONDecodeError:
                    continue

        # 匹配处理流程
        flow_patterns = [
            r'(?:流程|处理流程|业务流程|调用流程|接口流程)[：:]\s*(.{10,500}?)(?=\n\n|\n(?:1\.\d|##|$))',
            r'流程[：:]\s*\n?((?:\d+[.、][^\n]+\n?){1,10})',
        ]
        for pattern in flow_patterns:
            match = re.search(pattern, doc_text, re.IGNORECASE | re.MULTILINE)
            if match:
                process_flow = match.group(1).strip()
                break

    return {
        "request_params": request_params,
        "request_json_sample": request_json_sample,
        "response_params": response_params,
        "response_json_sample": response_json_sample,
        "process_flow": process_flow,
    }


def _resize_base64_image(b64_data: str, max_width: int = 1280, quality: int = 85) -> str:
    """
    对 base64 图片进行压缩缩放。

    处理流程：
    1. 解析 data-URI 前缀（如 data:image/png;base64,）
    2. 解码为字节
    3. 用 PIL/Pillow 缩放到 max_width 范围内（保持宽高比）
    4. 重新编码为 JPEG（节省体积）或 PNG
    5. 重新拼接回 data-URI 并返回

    如果 Pillow 不可用、或图片本身已在尺寸范围内，直接原样返回。
    """
    try:
        import re
        # 解析前缀
        prefix = ""
        body = b64_data
        m = re.match(r'(data:([^;]+);base64,)', b64_data)
        if m:
            prefix = m.group(1)
            body = b64_data[len(prefix):]

        raw_bytes = base64.b64decode(body)

        from io import BytesIO
        from PIL import Image

        img = Image.open(BytesIO(raw_bytes))
        original_w, original_h = img.size

        if original_w <= max_width and original_h <= max_width:
            # 图片已经足够小，不压缩
            return b64_data

        # 等比缩放
        ratio = min(max_width / original_w, max_width / original_h)
        new_w = int(original_w * ratio)
        new_h = int(original_h * ratio)
        img_resized = img.resize((new_w, new_h), Image.LANCZOS)

        buf = BytesIO()
        orig_fmt = img.format or "JPEG"
        save_fmt = "JPEG" if orig_fmt in ("JPEG", "JPG", "", None) else orig_fmt
        if save_fmt == "JPEG":
            img_resized = img_resized.convert("RGB")

        img_resized.save(buf, format=save_fmt, quality=quality, optimize=True)
        compressed_bytes = buf.getvalue()

        new_b64 = base64.b64encode(compressed_bytes).decode("utf-8")
        # 自动使用 JPEG（压缩率更高）
        new_prefix = prefix.replace(
            prefix.split(":")[1].split(";")[0], "image/jpeg"
        ) if prefix else "data:image/jpeg;base64,"
        return f"{new_prefix}{new_b64}"

    except Exception as e:
        # 任何处理失败都降级为原图
        return b64_data


def _analyze_images_with_llm(images: list, api_context: str = "") -> list:
    """
    使用多模态LLM分析上传的图片。

    参数：
    - images: Base64编码的图片列表
    - api_context: 接口上下文信息（接口名称、描述等）

    返回：
    - list: 图片分析结果列表，每个元素包含 {filename, analysis, success, source}
    """
    import dashscope
    from dashscope import MultiModalConversation

    logger = logging.getLogger(__name__)

    if not images:
        logger.info("[Phase1] 无图片需要分析")
        return []

    logger.info("[Phase1] 开始分析 %d 张图片", len(images))

    # 设置API Key
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        logger.warning("[Phase1] 未设置DASHSCOPE_API_KEY环境变量")
        return [{
            "filename": f"image_{i+1}",
            "analysis": "图片分析失败: 未设置DASHSCOPE_API_KEY",
            "success": False,
            "source": "flowchart"
        } for i in range(len(images))]

    dashscope.api_key = api_key
    logger.info("[Phase1] 使用 qwen3.5-plus 多模态模型分析图片")

    # 详细的流程图分析提示词（与 http_test_case_generate.py 保持一致）
    FLOWCHART_PROMPT = """请分析这张系统交互流程图或泳道图，提取以下信息：
1. 涉及的系统和组件（有哪些参与方）
2. 各系统之间的交互顺序和调用关系
3. 图中所标明的的业务流程步骤包括正向流程和异常的流程，
4. 关键的数据流向
5. 是否有分支、循环、并行等特殊逻辑，如果存在那么将这些逻辑查找狐出来

使用资深产品设计工程师的角度，用结构化的方式描述这个图内的业务流程，
如果图片不包含流程图信息，请说明"未识别到流程图"。"""

    image_analysis_results = []

    for idx, img_b64 in enumerate(images):
        try:
            logger.info("[Phase1] 分析图片 %d/%d", idx + 1, len(images))

            # ====== 大图片自动压缩 ======
            processed_b64 = _resize_base64_image(img_b64, max_width=1280, quality=85)
            if processed_b64 != img_b64:
                try:
                    old_len = len(img_b64)
                    new_len = len(processed_b64)
                    ratio = new_len / old_len if old_len else 1
                    logger.info("[Phase1] 图片 %d 已压缩: %d → %d 字节 (%.0f%%)",
                                idx + 1, old_len, new_len, ratio * 100)
                except Exception:
                    pass
                img_b64 = processed_b64

            # 构建消息
            # 检查 img_b64 是否已有 data-URI 前缀
            img_prefix = "data:image/png;base64,"
            img_body = img_b64
            if img_b64.startswith("data:"):
                # 已有前缀，直接使用
                img_body = img_b64
            else:
                img_body = f"{img_prefix}{img_b64}"

            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "image": img_body
                        },
                        {
                            "text": FLOWCHART_PROMPT
                        }
                    ]
                }
            ]

            # 调用 qwen3.5-plus 多模态模型
            response = MultiModalConversation.call(
                model='qwen3.5-plus',
                messages=messages
            )

            if response.status_code == 200:
                result_content = response.output.choices[0].message.content
                analysis_text = ""
                for item in result_content:
                    if 'text' in item:
                        analysis_text += item['text']

                image_analysis_results.append({
                    "filename": f"image_{idx + 1}",
                    "analysis": analysis_text,
                    "success": True,
                    "source": "flowchart"
                })
                logger.info("[Phase1] 图片 %d 分析成功", idx + 1)
            else:
                logger.warning("[Phase1] 图片 %d 分析失败: %s - %s",
                             idx + 1, response.code, response.message)
                image_analysis_results.append({
                    "filename": f"image_{idx + 1}",
                    "analysis": f"图片分析失败: {response.code} - {response.message}",
                    "success": False,
                    "source": "flowchart"
                })

        except Exception as img_err:
            logger.warning("[Phase1] 图片 %d 分析失败: %s", idx + 1, img_err)
            image_analysis_results.append({
                "filename": f"image_{idx + 1}",
                "analysis": f"图片分析失败: {str(img_err)}",
                "success": False,
                "source": "flowchart"
            })

    logger.info("[Phase1] 图片分析完成: 成功=%d, 失败=%d",
                sum(1 for r in image_analysis_results if r["success"]),
                sum(1 for r in image_analysis_results if not r["success"]))

    return image_analysis_results


def _read_document_text(file_path: str) -> str:
    """根据文件类型正确读取文档内容，支持 .docx, .pdf, .txt, .md 等格式"""
    import docx
    ext = os.path.splitext(file_path)[1].lower()

    if ext in [".docx", ".doc"]:
        try:
            doc = docx.Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs]
            tables_content = []
            for table in doc.tables:
                for row in table.rows:
                    row_text = [cell.text.strip() for cell in row.cells]
                    tables_content.append(' | '.join(row_text))
            content = '\n'.join(paragraphs)
            if tables_content:
                content += '\n\n表格内容:\n' + '\n'.join(tables_content)
            return content
        except Exception as e:
            raise RuntimeError(f"解析 docx 文档失败: {e}")

    elif ext == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                text_parts = []
                for page_num, page in enumerate(pdf.pages, 1):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(f"--- 第 {page_num} 页 ---\n{page_text}")
                    except Exception:
                        continue
                return '\n\n'.join(text_parts)
        except Exception as e:
            raise RuntimeError(f"解析 PDF 文档失败: {e}")

    else:
        # 文本文件直接读取
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()


def _build_review_data_from_task(task_id: str, context: dict, images: list, texts: list,
                                  saved_doc_paths: list) -> ReviewData:
    """
    Phase 1（识别）：从任务上下文构建 ReviewData 对象。

    doc_id == task_id — 这是两阶段的连接键。

    复用 http_test_case_generate.py 中的阶段0文档分析能力：
    1. parse_document_structure() - 结构化解析文档
    2. 预分析 LLM - 识别接口清单和出入参
    3. 整合图片分析结果

    增强：调用多模态LLM分析上传的图片。
    """
    from api.http_rag_document import get_rag_service

    logger = logging.getLogger(__name__)

    api_name = context.get('api_name', '未命名接口')
    http_method = context.get('http_method', 'GET').upper()
    path = context.get('path', '')
    api_desc = context.get('api_desc', '')
    module = context.get('module', '')

    # ====== 1. 合并所有文本为 document_content ======
    combined_texts = list(texts) if texts else []

    for doc_path in (saved_doc_paths or []):
        if os.path.exists(doc_path):
            try:
                doc_content = _read_document_text(doc_path)
                combined_texts.append(doc_content)
            except Exception as e:
                logger.warning(f"读取文档失败 {doc_path}: {e}")
                combined_texts.append(f"[文档文件: {doc_path}]")

    document_content = "\n\n".join(combined_texts)

    # ====== 2. 使用多模态LLM分析图片 ======
    api_context = f"{api_name} {http_method} {path} {api_desc}"
    image_analysis_results = _analyze_images_with_llm(images, api_context)

    # ====== 3. 调用阶段0文档分析能力 ======
    review_data = ReviewData(
        doc_id=task_id,
        document_title=api_name,
        business_module=module,
    )
    review_data.document_content = document_content
    review_data.image_analysis = image_analysis_results
    review_data.status = "pending"

    # 如果没有文档内容，只用 context 信息构建单接口记录
    if not document_content.strip():
        logger.info("[Phase1] 无文档内容，使用 context 构建单接口记录")
        interface_dict = _build_single_interface_dict(
            api_name=api_name,
            http_method=http_method,
            path=path,
            api_desc=api_desc,
            image_analysis_results=image_analysis_results
        )
        review_data.interface_list = [interface_dict]
        review_data.project_background = ""
        review_data.business_summary = ""
        return review_data

    # ====== 3.1 调用 parse_document_structure() 解析文档结构 ======
    logger.info("[Phase1] 开始解析文档结构...")
    try:
        doc_structure = parse_document_structure(document_content)
        logger.info(f"[Phase1] 文档结构解析完成: basic_knowledge={len(doc_structure.get('basic_knowledge', ''))}字符, "
                    f"service_content={len(doc_structure.get('service_content', ''))}字符, "
                    f"api_section={len(doc_structure.get('api_section', ''))}字符")
        review_data.api_section = doc_structure.get("api_section", "")
    except Exception as e:
        logger.warning(f"[Phase1] 文档结构解析失败: {e}")
        doc_structure = {
            "basic_knowledge": "",
            "service_content": "",
            "template_config": "",
            "api_section": document_content
        }
        review_data.api_section = document_content

    # ====== 3.2 调用预分析 LLM 识别接口清单 ======
    logger.info("[Phase1] 开始调用预分析 LLM 识别接口...")
    rag = None
    try:
        rag = get_rag_service()
        if not rag:
            logger.error("[Phase1] RAG服务未初始化")
            raise RuntimeError("RAG服务未初始化")

        # 构建预分析输入
        full_content = f"""
【基础知识】
{doc_structure.get('basic_knowledge', '')}

【服务内容】
{doc_structure.get('service_content', '')}

【模板配置】
{doc_structure.get('template_config', '')}

【核心API应用】
{doc_structure.get('api_section', '')}
"""
        # qwen-plus 128K 上下文，预留 8K 输出，可输入约 120K 字符
        max_chars = 120000
        pre_analysis_prompt = DOC_PRE_ANALYSIS_PROMPT.format(
            content=full_content[:max_chars]
        )

        logger.info(f"[Phase1] 预分析输入长度: {len(pre_analysis_prompt)} 字符")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            pre_result = loop.run_until_complete(
                rag._generate_answer(
                    prompt=pre_analysis_prompt,
                    temperature=0.1,
                    max_tokens=16000,
                )
            )
        finally:
            loop.close()

        logger.info(f"[Phase1] 预分析输出长度: {len(pre_result)} 字符")

        # 解析预分析结果
        project_info = _parse_pre_analysis_result(pre_result)

        logger.info(f"[Phase1] 预解析结果: 项目背景={project_info.get('project_background', '')[:50] if project_info.get('project_background') else '空'}...")
        logger.info(f"[Phase1] 接口数量={project_info.get('interface_count', 0)}, "
                    f"页面数量={project_info.get('page_count', 0)}, "
                    f"接口列表长度={len(project_info.get('interface_list', []))}")

        # 填充 ReviewData
        review_data.project_background = project_info.get('project_background', '')
        review_data.business_summary = doc_structure.get('service_content', '')
        review_data.flow_chart_analysis = project_info.get('flow_charts', [])

        # 获取识别出的接口列表
        interface_list_from_doc = project_info.get('interface_list', [])

    except RuntimeError:
        # RAG服务初始化失败是严重错误，重新抛出，让外层更新任务状态为 failed
        logger.error(f"[Phase1] RAG服务初始化失败，任务将标记为失败")
        raise
    except Exception as e:
        logger.warning(f"[Phase1] 预分析 LLM 调用失败: {e}")
        project_info = {
            'project_background': '',
            'interface_count': 0,
            'interface_list': [],
            'flow_charts': []
        }
        interface_list_from_doc = []

    # ====== 4. 合并 context API 与文档识别的接口 ======
    # 如果 context 中的 API 不在文档识别的列表中，补充进去
    context_api_exists = any(
        iface.get('path', '').strip('/') == path.strip('/') and
        iface.get('method', '').upper() == http_method.upper()
        for iface in interface_list_from_doc
    )

    if not context_api_exists and path:
        logger.info(f"[Phase1] context API '{api_name}' 不在文档识别列表中，补充添加")
        context_interface = _build_single_interface_dict(
            api_name=api_name,
            http_method=http_method,
            path=path,
            api_desc=api_desc,
            image_analysis_results=image_analysis_results
        )
        interface_list_from_doc.append(context_interface)

    # ====== 5. 整合图片分析结果到接口列表 ======
    # 为每个接口匹配图片分析结果
    final_interface_list = _merge_image_analysis_to_interfaces(
        interface_list=interface_list_from_doc,
        image_analysis_results=image_analysis_results
    )

    review_data.interface_list = final_interface_list

    # 添加图片分析结果到流程图列表
    for analysis in image_analysis_results:
        if analysis.get("success"):
            review_data.flow_chart_analysis.append({
                "source": "image",
                "filename": analysis.get("filename", ""),
                "analysis": analysis.get("analysis", "")
            })

    logger.info("[Phase1] ReviewData 构建完成: doc_id=%s, 接口数=%d, 文本数=%d, 图片分析数=%d",
                task_id, len(review_data.interface_list), len(combined_texts), len(image_analysis_results))

    # 打印每个接口的详细信息（用于调试）
    for idx, iface in enumerate(review_data.interface_list, 1):
        logger.info(f"[Phase1] 接口 {idx}: {iface.get('name', '未命名')} "
                    f"| 方法: {iface.get('method', '')} "
                    f"| 路径: {iface.get('path', '')} "
                    f"| 入参: {len(str(iface.get('request_params', '')))}字符 "
                    f"| 出参: {len(str(iface.get('response_params', '')))}字符")

    return review_data


def _build_single_interface_dict(api_name: str, http_method: str, path: str,
                                 api_desc: str, image_analysis_results: list) -> dict:
    """
    构建单个接口字典（用于 context API 或无文档时的兜底）
    """
    flow_chart_desc = ""
    detail_flow_analysis = ""
    if image_analysis_results:
        success_results = [r for r in image_analysis_results if r["success"]]
        if success_results:
            flow_chart_desc = "\n".join([
                f"【{r['filename']}】{r['analysis']}"
                for r in success_results
            ])
            detail_flow_analysis = "\n".join([
                f"图片 {r['filename']} 分析:\n{r['analysis']}"
                for r in success_results
            ])

    return {
        'name': api_name,
        'method': http_method,
        'path': path,
        'description': api_desc,
        'request_params': '',
        'request_json': '{}',
        'response_json': '{}',
        'response_params': '',
        'process_flow': '',
        'flow_chart_desc': flow_chart_desc,
        'detail_flow_analysis': detail_flow_analysis,
        'image_analysis': image_analysis_results,
    }


def _merge_image_analysis_to_interfaces(interface_list: list, image_analysis_results: list) -> list:
    """
    将图片分析结果合并到接口列表中

    策略：
    1. 如果图片分析结果与某个接口名称相关联，将分析结果添加到该接口
    2. 如果是通用流程图，添加到第一个接口
    3. 所有图片分析结果都需要有归宿
    """
    import re

    matched_interfaces = set()  # 已匹配图片的接口索引
    result = []

    for idx, iface in enumerate(interface_list):
        iface_dict = dict(iface)  # 复制一份
        iface_name = iface.get('name', '').lower()
        iface_path = iface.get('path', '').lower()

        # 收集该接口匹配的图片分析
        matched_images = []
        for img in image_analysis_results:
            if not img.get('success'):
                continue
            img_analysis = img.get('analysis', '')
            img_lower = img_analysis.lower()

            # 检查图片是否与该接口相关
            is_relevant = False

            # 1. 接口名称在图片分析中
            if iface_name and iface_name in img_lower:
                is_relevant = True

            # 2. 接口路径关键词在图片分析中
            if iface_path:
                path_keywords = [w for w in re.split(r'[/_\-]', iface_path) if len(w) > 2]
                for kw in path_keywords:
                    if kw in img_lower:
                        is_relevant = True
                        break

            if is_relevant:
                matched_images.append(img)
                matched_interfaces.add(idx)

        # 添加匹配的图片分析到接口
        if matched_images:
            flow_chart_desc = iface_dict.get('flow_chart_desc', '') or ""
            detail_flow_analysis = iface_dict.get('detail_flow_analysis', '') or ""

            for img in matched_images:
                filename = img.get('filename', '')
                analysis = img.get('analysis', '')
                flow_chart_desc += f"\n【{filename}】{analysis}"
                detail_flow_analysis += f"\n图片 {filename} 分析:\n{analysis}"

            iface_dict['flow_chart_desc'] = flow_chart_desc.strip()
            iface_dict['detail_flow_analysis'] = detail_flow_analysis.strip()
            iface_dict['image_analysis'] = matched_images

        result.append(iface_dict)

    # 处理未匹配的图片（通用流程图），添加到第一个接口
    unmatched_images = [img for img in image_analysis_results
                       if img.get('success') and img.get('filename', '') not in
                       [matched_img.get('filename', '') for matched_img in
                        [img for iface in result for img in iface.get('image_analysis', [])]]]

    if unmatched_images and result:
        first_iface = result[0]
        flow_chart_desc = first_iface.get('flow_chart_desc', '') or ""
        detail_flow_analysis = first_iface.get('detail_flow_analysis', '') or ""

        for img in unmatched_images:
            filename = img.get('filename', '')
            analysis = img.get('analysis', '')
            flow_chart_desc += f"\n【{filename}】{analysis}"
            detail_flow_analysis += f"\n图片 {filename} 分析:\n{analysis}"

        first_iface['flow_chart_desc'] = flow_chart_desc.strip()
        first_iface['detail_flow_analysis'] = detail_flow_analysis.strip()
        existing_images = first_iface.get('image_analysis', [])
        first_iface['image_analysis'] = existing_images + unmatched_images

    return result


def _process_case_generation_phase2(task_id: str):
    """
    Phase 2（生成）：后台线程，在人工审批通过后执行。

    流程：
    1. 从 crosstest_review_record 加载审核通过的记录（status == 'approved'）
    2. 读取知识内容（图片/文本/文档）
    3. 为每个接口调用 generate_api_test_cases()
    4. 保存到 test_cases 表
    5. 更新 review_record.test_case_count
    6. 更新 task 状态为 completed
    """
    import sqlite3
    logger = logging.getLogger(__name__)

    from utils.read_config_path.read_ai_config import load_ai_config_refresh as load_ai_config

    ai_conf = load_ai_config()
    use_llm = ai_conf.get("use_llm", True)
    llm_client = None
    if use_llm:
        api_key = ai_conf.get("api_key")
        if api_key:
            llm_client = OpenAILLMClient(
                api_key=api_key,
                base_url=(ai_conf.get("base_url") or "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/"),
                model=ai_conf.get("model") or "qwen-plus",
                temperature=ai_conf.get("temperature", 0.2),
                max_tokens=ai_conf.get("max_tokens", 16000),
                timeout=ai_conf.get("timeout", 600),
            )
            logger.info("[Phase2] 大模型已启用，model=%s", ai_conf.get("model"))
        else:
            logger.warning("[Phase2] 未配置 api_key，降级为 mock")
    else:
        logger.info("[Phase2] use_llm=False，降级为 mock")

    try:
        logger.info("[Phase2] 开始执行, task_id=%s", task_id)

        review_mapper = ReviewRecordMapper()
        db_records = review_mapper.get_all_by_doc_id(task_id)

        if not db_records:
            logger.error("[Phase2] 未找到审核记录, task_id=%s", task_id)
            _update_task_status(task_id, 'failed', error_message="未找到审核通过的记录")
            return

        _update_task_status(task_id, 'completed', progress=5)  # Phase2 开始：案例生成中

        # 取第一条记录获取文档级别的公共信息
        base_record = db_records[0]

        # 收集所有接口记录
        interface_list = []
        for rec in db_records:
            if rec.get('interface_name'):
                interface_list.append({
                    'name': rec.get('interface_name', ''),
                    'method': rec.get('interface_method', ''),
                    'path': rec.get('interface_path', ''),
                    'description': rec.get('interface_description', ''),
                    'request_params': rec.get('request_params', ''),
                    'request_json_sample': rec.get('request_json_sample', ''),
                    'response_json_sample': rec.get('response_json_sample', ''),
                    'response_params': rec.get('response_params', ''),
                    'process_flow': rec.get('process_flow', ''),
                    'detail_flow_analysis': rec.get('detail_flow_analysis', ''),
                })

        logger.info("[Phase2] 加载接口数=%d, task_id=%s", len(interface_list), task_id)

        # 2. 读取知识内容
        db_path = _get_tasks_db_path()
        conn = sqlite3.connect(db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT knowledge_type, content, file_path FROM task_knowledge WHERE task_id = ?", (task_id,))
        knowledge_rows = cursor.fetchall()
        conn.close()

        images = []
        texts = []
        saved_doc_paths = []
        for row in knowledge_rows:
            kt = row['knowledge_type']
            if kt == 'image':
                images.append(row['content'])
            elif kt == 'text':
                texts.append(row['content'])
            elif kt == 'document' and row['file_path']:
                saved_doc_paths.append(row['file_path'])

        # 3. 从文档获取 params_example（如果尚未填充）
        params_example = {}
        for doc_path in saved_doc_paths:
            if os.path.exists(doc_path):
                try:
                    parsed = parse_doc_file(doc_path)
                    params_example = parsed.get('params_example', {})
                    break
                except Exception:
                    pass

        # 4. 逐接口调用大模型生成用例
        all_generated_cases = []
        total_interfaces = len(interface_list) or 1

        for idx, iface in enumerate(interface_list or [{}]):
            progress_pct = 10 + int(80 * idx / total_interfaces)
            _update_task_status(task_id, 'completed', progress=progress_pct)

            api_name = iface.get('name', '')
            api_desc = iface.get('description', '')
            http_method = iface.get('method', 'GET') or 'GET'
            path = iface.get('path', '')

            # 合并上下文提示
            context_hint_parts = []
            if texts:
                context_hint_parts.append("背景信息:\n" + "\n".join(texts[:5]))
            if iface.get('description'):
                context_hint_parts.append(f"接口描述: {iface['description']}")
            context_hint = "\n\n".join(context_hint_parts)

            logger.info("[Phase2] 生成接口 %d/%d: %s %s", idx + 1, total_interfaces, http_method, path)

            try:
                generated_cases = generate_api_test_cases(
                    api_name=api_name or f"接口{idx+1}",
                    api_desc=api_desc or context_hint,
                    http_method=http_method,
                    path=path,
                    params_example=params_example,
                    constraints=api_desc or context_hint,
                    max_cases=5,
                    llm_client=llm_client,
                )["cases"]
            except Exception as llm_err:
                logger.warning("[Phase2] 大模型调用失败，降级为stub: %s", llm_err)
                generated_cases = _load_stub_cases()["cases"]

            # 补充接口上下文字段
            for case in generated_cases:
                tags = case.get('tags', [])
                if isinstance(tags, str):
                    tags = [tags]
                elif not isinstance(tags, list):
                    tags = []
                if api_name and api_name not in tags:
                    tags.append(api_name)
                case['tags'] = tags

            all_generated_cases.extend(generated_cases)

        _update_task_status(task_id, 'completed', progress=90)

        # 5. 保存到数据库
        if all_generated_cases:
            try:
                _save_cases_to_db(
                    api_name=base_record.get('document_title', 'unknown') if hasattr(base_record, 'get') else 'unknown',
                    creator='system',
                    cases=all_generated_cases,
                    logger=logger,
                    module=base_record.get('business_module', '') if hasattr(base_record, 'get') else '',
                    system=None,
                )
                logger.info("[Phase2] 用例已保存: %d 条", len(all_generated_cases))
            except Exception as save_err:
                logger.error("[Phase2] 保存用例失败: %s", save_err)

        # 6. 更新 review_record 生成结果
        try:
            review_mapper.update_generation_result(
                doc_id=task_id,
                xmind_file_path="",
                test_case_count=len(all_generated_cases),
            )
        except Exception as up_err:
            logger.warning("[Phase2] 更新生成结果失败（不影响主流程）: %s", up_err)

        # 7. 更新任务状态为成功完成
        result_data = {
            'case_count': len(all_generated_cases),
            'document_title': base_record.get('document_title', '') if hasattr(base_record, 'get') else '',
            'interface_count': total_interfaces,
            'generated_at': datetime.now().isoformat(),
        }
        _update_task_status(task_id, 'succeed', progress=100, result=result_data)

        # 8. 清理临时文件
        context_path = os.path.join(UPLOAD_DIR, f"{task_id}_context.json")
        try:
            os.remove(context_path)
        except Exception:
            pass

        logger.info("[Phase2] 完成, task_id=%s, 生成用例数=%d", task_id, len(all_generated_cases))

    except Exception as e:
        logger.exception(f"[Phase2] 异常, task_id={task_id}: {e}")
        _update_task_status(task_id, 'failed', error_message=str(e))


def _process_case_generation_task(task_id: str):
    """
    Phase 1（识别）：解析知识，构建 ReviewData，进入待审核状态。

    原有的 generate_api_test_cases() 调用已移至 Phase 2（在人工审核通过后执行）。
    """
    import sqlite3
    logger = logging.getLogger(__name__)

    try:
        logger.info("[Phase1] 开始处理, task_id=%s", task_id)

        _update_task_status(task_id, 'k_running', progress=0)  # 知识生成中

        # 读取任务上下文
        context_path = os.path.join(UPLOAD_DIR, f"{task_id}_context.json")
        if not os.path.exists(context_path):
            _update_task_status(task_id, 'failed', error_message="任务上下文文件丢失")
            return

        with open(context_path, 'r', encoding='utf-8') as f:
            context = json.load(f)

        # 读取知识内容
        db_path = _get_tasks_db_path()
        conn = sqlite3.connect(db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT knowledge_type, content, file_path FROM task_knowledge WHERE task_id = ?", (task_id,))
        knowledge_rows = cursor.fetchall()
        conn.close()

        images = []
        texts = []
        saved_doc_paths = []
        for row in knowledge_rows:
            kt = row['knowledge_type']
            if kt == 'image':
                images.append(row['content'])
            elif kt == 'text':
                texts.append(row['content'])
            elif kt == 'document' and row['file_path']:
                saved_doc_paths.append(row['file_path'])

        logger.info("[Phase1] 知识加载完成: 图片=%d, 文本=%d, 文档=%d",
                    len(images), len(texts), len(saved_doc_paths))

        _update_task_status(task_id, 'k_running', progress=30)  # 知识生成中

        # 构建 ReviewData
        review_data = _build_review_data_from_task(task_id, context, images, texts, saved_doc_paths)

        _update_task_status(task_id, 'k_running', progress=60)  # 知识生成中

        # 保存到 crosstest_review_record 表
        try:
            review_mapper = ReviewRecordMapper()
            review_mapper.save_from_review_data(review_data, creator="system")
            logger.info("[Phase1] ReviewData 已保存到审核表, doc_id=%s", task_id)
        except Exception as save_err:
            logger.error("[Phase1] 保存审核记录失败: %s", save_err)
            _update_task_status(task_id, 'failed', error_message=f"保存审核记录失败: {save_err}")
            return

        # 进入待审核状态
        _update_task_status(task_id, 'pending_review', progress=100)
        logger.info("[Phase1] 任务进入待审核状态, task_id=%s", task_id)

    except Exception as e:
        logger.exception(f"[Phase1] 异常, task_id={task_id}: {e}")
        _update_task_status(task_id, 'failed', error_message=str(e))


