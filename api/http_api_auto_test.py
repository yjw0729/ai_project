"""API自动化测试 - Flask API接口层"""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from flask import Blueprint, request, jsonify, make_response
from werkzeug.utils import secure_filename

from common.rag.processors.api_auto_test_processor import APITestDocProcessor
from common.test_executor import APITestRunner, ReportGenerator
from common.llm.api_test_prompts import TEST_CASE_GENERATION_PROMPT
from common.llm.llm_client import LLMClient

logger = logging.getLogger(__name__)


api_auto_test_bp = Blueprint("api_auto_test", __name__, url_prefix="/api/auto_test")


# ==================== 加载配置 ====================

def _load_config() -> Dict[str, Any]:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "api_auto_test_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning("加载API自动化测试配置失败: %s", str(e))
    return {}


CONFIG = _load_config()
STORAGE_CONFIG = CONFIG.get("storage", {})
UPLOAD_DIR = STORAGE_CONFIG.get("upload_dir", "uploads/api_auto_test")
REPORT_DIR = STORAGE_CONFIG.get("report_dir", "outputs/reports")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = CONFIG.get("upload", {}).get("allowed_extensions", {
    "openapi": [".json", ".yaml", ".yml"],
    "api_doc": [".docx", ".pdf"],
    "flowchart": [".png", ".jpg", ".jpeg"],
})


def _json_response(body: Dict[str, Any], status: int = 200):
    resp = make_response(jsonify(body), status)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp


def _allowed_file(filename: str, doc_type: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS.get(doc_type, [])


def _extract_file_ext(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


# ==================== API: 上传文档 ====================

@api_auto_test_bp.route("/upload", methods=["POST"])
def upload_api_docs():
    """
    上传API文档。
    支持：OpenAPI(.json/.yaml)、接口说明(.docx)、流程图(.png/.jpg)
    """
    logger.info("【API】收到上传文档请求")

    if "file" not in request.files:
        return _json_response({"code": 400, "message": "未找到上传文件", "data": None}, 400)

    file = request.files["file"]
    if file.filename == "":
        return _json_response({"code": 400, "message": "文件名为空", "data": None}, 400)

    doc_type = request.form.get("doc_type", "openapi")
    system_name = request.form.get("system_name", "")
    flowchart_description = request.form.get("flowchart_description", "")

    if not _allowed_file(file.filename, doc_type):
        allowed = ALLOWED_EXTENSIONS.get(doc_type, [])
        return _json_response({
            "code": 400,
            "message": f"不支持的文件类型，当前支持：{', '.join(allowed)}",
            "data": None
        }, 400)

    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    file.save(file_path)

    logger.info("【API】文件已保存: %s", file_path)

    processor = APITestDocProcessor(upload_dir=UPLOAD_DIR)
    result = processor.process_upload(
        file_path=file_path,
        doc_type=doc_type,
        system_name=system_name,
        flowchart_description=flowchart_description,
    )

    processor.save_parsed_result(result)

    response_data = {
        "doc_id": result["doc_id"],
        "doc_type": result["doc_type"],
        "system_name": result["system_name"],
        "parsed_interfaces": result["parsed_interfaces"],
        "flowchart_nodes": result.get("flowchart_nodes", []),
        "file_path": file_path,
        "error": result.get("error"),
    }

    return _json_response({
        "code": 200 if not result.get("error") else 500,
        "message": "success" if not result.get("error") else result.get("error"),
        "data": response_data
    })


# ==================== API: 生成测试用例 ====================

@api_auto_test_bp.route("/generate", methods=["POST"])
def generate_test_cases():
    """
    根据上传的文档生成测试用例。
    """
    logger.info("【API】收到生成测试用例请求")

    payload = request.get_json(silent=True) or {}
    doc_id = payload.get("doc_id")
    if not doc_id:
        return _json_response({"code": 400, "message": "缺少 doc_id", "data": None}, 400)

    processor = APITestDocProcessor(upload_dir=UPLOAD_DIR)
    parsed = processor.load_parsed_result(doc_id)
    if not parsed:
        return _json_response({"code": 404, "message": "文档不存在或已过期", "data": None}, 404)

    options = payload.get("options", {})
    generate_mode = options.get("generate_mode", "comprehensive")
    include_boundary = options.get("include_boundary", True)
    include_error = options.get("include_error", True)
    priority_filter = options.get("priority_filter", ["P0", "P1", "P2"])
    system_name = payload.get("system_name") or parsed.get("system_name", "")

    interface_list = parsed.get("parsed_interfaces", [])
    flowchart_data = parsed.get("flow_data", {})
    flow_nodes = parsed.get("flowchart_nodes", [])

    all_cases = []

    # 从接口列表生成用例
    if interface_list:
        for interface in interface_list:
            cases = _generate_cases_for_interface(interface, options)
            all_cases.extend(cases)

    # 从流程图生成用例
    if flow_nodes:
        cases = _generate_cases_from_flowchart(flowchart_data, options)
        all_cases.extend(cases)

    # 按优先级过滤
    filtered_cases = [c for c in all_cases if c.get("priority") in priority_filter]

    # 插入数据库
    inserted_cases = _insert_cases_to_database(filtered_cases, system_name, doc_id)
    case_ids = [c["id"] for c in inserted_cases]

    # 统计
    by_priority = {}
    by_tag = {}
    for c in inserted_cases:
        p = c.get("priority", "P2")
        by_priority[p] = by_priority.get(p, 0) + 1
        for tag in (c.get("tags") or []):
            by_tag[tag] = by_tag.get(tag, 0) + 1

    return _json_response({
        "code": 200,
        "message": "success",
        "data": {
            "doc_id": doc_id,
            "case_ids": case_ids,
            "case_count": len(inserted_cases),
            "cases": [
                {"id": c["id"], "name": c["name"], "priority": c.get("priority", "P2"), "tags": c.get("tags", [])}
                for c in inserted_cases[:10]
            ],
            "report": {
                "total": len(inserted_cases),
                "by_priority": by_priority,
                "by_tag": by_tag,
            }
        }
    })


def _generate_cases_for_interface(interface: Dict[str, Any], options: Dict[str, Any]) -> List[Dict[str, Any]]:
    """为单个接口生成测试用例"""
    logger.info("【API】为接口生成用例: %s %s", interface.get("method"), interface.get("path"))

    llm_config = CONFIG.get("llm", {})
    client = LLMClient(model=llm_config.get("model", "qwen-plus"), temperature=llm_config.get("temperature", 0.7))

    api_info = json.dumps({
        "interface_name": interface.get("interface_name", ""),
        "description": interface.get("description", ""),
        "method": interface.get("method", "GET"),
        "path": interface.get("path", ""),
        "request_params": interface.get("request_params", []),
        "response_params": interface.get("response_params", []),
    }, ensure_ascii=False)

    constraints = "\n".join([
        f"{p['name']}: {p.get('description', '')} {p.get('constraints', '')}"
        for p in interface.get("request_params", []) if p.get("required")
    ])

    prompt = TEST_CASE_GENERATION_PROMPT.format(api_info=api_info, param_constraints=constraints)

    try:
        response, _ = client.chat_with_prompt(prompt, max_tokens=llm_config.get("max_tokens", 8192))
        import re
        json_match = re.search(r'\[[\s\S]*\]', response)
        if json_match:
            cases = json.loads(json_match.group())
            for case in cases:
                case["request"] = case.get("request") or {}
                case["request"]["method"] = interface.get("method", "GET")
                case["request"]["path"] = interface.get("path", "")
            return cases
    except Exception as e:
        logger.error("【API】生成用例失败: %s", str(e))

    return []


def _generate_cases_from_flowchart(flow_data: Dict[str, Any], options: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从流程图生成测试用例"""
    logger.info("【API】从流程图生成用例")

    nodes = flow_data.get("nodes", [])
    cases = []

    for i, node in enumerate(nodes):
        if node.get("type") == "api":
            case = {
                "id": f"FLOW_{i+1}",
                "title": f"{node.get('name', '流程节点')}测试",
                "priority": "P1",
                "tags": ["流程测试", "依赖链"],
                "request": {
                    "method": node.get("method", "POST"),
                    "path": node.get("api_path", ""),
                    "headers": {},
                    "body": node.get("params", {}),
                },
                "expect": "接口调用成功",
                "status_code": 200,
                "assertions": ["status_code == 200"],
            }
            cases.append(case)

    return cases


def _insert_cases_to_database(cases: List[Dict[str, Any]], system_name: str, doc_id: str) -> List[Dict[str, Any]]:
    """将测试用例插入数据库"""
    logger.info("【API】插入 %d 个用例到数据库", len(cases))

    inserted = []
    try:
        from common.db_mapper.test_case_mapper import TestCaseMapper
        mapper = TestCaseMapper()

        for case in cases:
            try:
                case_entity = {
                    "name": case.get("title") or case.get("name", "未命名用例"),
                    "description": case.get("description", ""),
                    "module": system_name,
                    "system": system_name,
                    "priority": case.get("priority", "P2"),
                    "tags": json.dumps(case.get("tags", []), ensure_ascii=False),
                    "api_config_id": None,
                    "test_steps": json.dumps(case.get("test_steps", []), ensure_ascii=False),
                    "test_data": json.dumps({"request": case.get("request", {})}, ensure_ascii=False),
                    "expected_results": json.dumps(case.get("expected_results", case.get("assertions", [])), ensure_ascii=False),
                    "status": "active",
                    "case_status": "enabled",
                    "case_type": "auto_generated",
                    "source_doc_id": doc_id,
                }
                case_id = mapper.insert(case_entity)
                case["id"] = case_id
                inserted.append(case)
                logger.debug("【API】用例已插入: id=%d, name=%s", case_id, case.get("title"))
            except Exception as e:
                logger.warning("【API】插入用例失败: %s - %s", case.get("title"), str(e))

    except Exception as e:
        logger.error("【API】数据库操作失败: %s", str(e))

    return inserted


# ==================== API: 执行测试 ====================

@api_auto_test_bp.route("/execute", methods=["POST"])
def execute_tests():
    """
    执行测试用例。
    """
    logger.info("【API】收到执行测试请求")

    payload = request.get_json(silent=True) or {}
    case_ids = payload.get("case_ids", [])
    env_id = payload.get("env_id")
    concurrency = payload.get("concurrency", 5)
    mode = payload.get("mode", "parallel")

    if not case_ids:
        return _json_response({"code": 400, "message": "缺少 case_ids", "data": None}, 400)

    test_cases = _load_test_cases_from_db(case_ids)
    if not test_cases:
        return _json_response({"code": 404, "message": "未找到测试用例", "data": None}, 404)

    env_config = _load_env_config(env_id)
    exec_config = CONFIG.get("test_execution", {})

    runner = APITestRunner(
        env_config=env_config,
        concurrency=min(concurrency, exec_config.get("max_concurrency", 20)),
        default_timeout=exec_config.get("default_timeout", 30),
        max_retry=exec_config.get("retry_times", 2),
    )

    execution_id = f"exec-{uuid.uuid4().hex[:12]}"
    results = runner.execute_batch(test_cases, mode=mode)
    summary = runner.get_summary()

    report_gen = ReportGenerator(output_dir=REPORT_DIR)
    report_path = report_gen.generate_html_report(results, summary, execution_id)
    json_report_path = report_gen.generate_json_report(results, summary, execution_id)

    _save_execution_record(execution_id, case_ids, summary, report_path, json_report_path)

    return _json_response({
        "code": 200,
        "message": "success",
        "data": {
            "execution_id": execution_id,
            "status": "completed",
            "summary": summary,
            "report_url": f"/api/auto_test/report/{execution_id}",
            "results_preview": [_result_preview(r) for r in results[:5]],
        }
    })


def _load_test_cases_from_db(case_ids: List[int]) -> List[Dict[str, Any]]:
    """从数据库加载测试用例"""
    try:
        from common.db_mapper.test_case_mapper import TestCaseMapper
        mapper = TestCaseMapper()
        cases = []
        for cid in case_ids:
            entity = mapper.get_by_id(cid)
            if entity:
                case = {
                    "id": entity.id,
                    "name": entity.name,
                    "description": getattr(entity, "description", ""),
                    "priority": getattr(entity, "priority", "P2"),
                    "tags": json.loads(getattr(entity, "tags", "[]") or "[]"),
                    "test_data": json.loads(getattr(entity, "test_data", "{}") or "{}"),
                    "expected_results": json.loads(getattr(entity, "expected_results", "[]") or "[]"),
                }
                cases.append(case)
        return cases
    except Exception as e:
        logger.error("【API】加载测试用例失败: %s", str(e))
        return []


def _load_env_config(env_id: Optional[int]) -> Dict[str, Any]:
    """加载环境配置"""
    if not env_id:
        return {}
    try:
        from common.db_mapper.environment_config_mapper import EnvironmentConfigMapper
        mapper = EnvironmentConfigMapper()
        env = mapper.get_by_id(env_id)
        if env:
            return env.to_json() if hasattr(env, "to_json") else {}
    except Exception as e:
        logger.error("【API】加载环境配置失败: %s", str(e))
    return {}


def _result_preview(r) -> Dict[str, Any]:
    """生成结果预览"""
    return {
        "case_id": r.case_id,
        "case_name": r.case_name,
        "status": r.status,
        "duration_ms": round(r.duration_ms, 1),
    }


def _save_execution_record(
    execution_id: str,
    case_ids: List[int],
    summary: Dict[str, Any],
    html_report: str,
    json_report: str
) -> None:
    """保存执行记录到数据库"""
    try:
        from common.db_mapper.test_execution_mapper import TestExecutionMapper
        mapper = TestExecutionMapper()
        record = {
            "execution_id": execution_id,
            "case_ids": json.dumps(case_ids, ensure_ascii=False),
            "total": summary.get("total", 0),
            "passed": summary.get("passed", 0),
            "failed": summary.get("failed", 0),
            "error_count": summary.get("error", 0),
            "duration_ms": summary.get("total_duration_ms", 0),
            "html_report_path": html_report,
            "json_report_path": json_report,
            "status": "completed",
        }
        mapper.insert(record)
        logger.info("【API】执行记录已保存: %s", execution_id)
    except Exception as e:
        logger.warning("【API】保存执行记录失败: %s", str(e))


# ==================== API: 查询执行结果 ====================

@api_auto_test_bp.route("/results/<execution_id>", methods=["GET"])
def get_execution_results(execution_id: str):
    """
    获取执行结果详情。
    """
    logger.info("【API】查询执行结果: %s", execution_id)

    try:
        from common.db_mapper.test_execution_mapper import TestExecutionMapper
        mapper = TestExecutionMapper()
        record = mapper.get_by_execution_id(execution_id)

        if not record:
            return _json_response({"code": 404, "message": "执行记录不存在", "data": None}, 404)

        # 加载详细结果
        json_report_path = getattr(record, "json_report_path", "")
        results_data = []
        if json_report_path and os.path.exists(json_report_path):
            with open(json_report_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                results_data = data.get("results", [])

        summary = {
            "total": getattr(record, "total", 0),
            "passed": getattr(record, "passed", 0),
            "failed": getattr(record, "failed", 0),
            "error": getattr(record, "error_count", 0),
            "total_duration_ms": getattr(record, "duration_ms", 0),
            "success_rate": round(getattr(record, "passed", 0) / max(getattr(record, "total", 1), 1) * 100, 2),
        }

        return _json_response({
            "code": 200,
            "message": "success",
            "data": {
                "execution_id": execution_id,
                "status": getattr(record, "status", "completed"),
                "start_time": str(getattr(record, "create_time", "")),
                "summary": summary,
                "results": results_data,
                "report_url": f"/api/auto_test/report/{execution_id}",
            }
        })

    except Exception as e:
        logger.error("【API】查询执行结果失败: %s", str(e))
        return _json_response({"code": 500, "message": str(e), "data": None}, 500)


# ==================== API: 下载测试报告 ====================

@api_auto_test_bp.route("/report/<execution_id>", methods=["GET"])
def download_report(execution_id: str):
    """
    下载测试报告（HTML格式）。
    """
    logger.info("【API】下载报告: %s", execution_id)

    report_path = os.path.join(REPORT_DIR, f"{execution_id}.html")
    if not os.path.exists(report_path):
        json_path = os.path.join(REPORT_DIR, f"{execution_id}.json")
        if os.path.exists(json_path):
            return _json_response({"code": 404, "message": "HTML报告不存在，请使用 /results 查看", "data": None}, 404)
        return _json_response({"code": 404, "message": "报告不存在", "data": None}, 404)

    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()

    resp = make_response(content)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers["Content-Disposition"] = f"attachment; filename={execution_id}.html"
    return resp


# ==================== API: 健康检查 ====================

@api_auto_test_bp.route("/health", methods=["GET"])
def health_check():
    """健康检查接口"""
    return _json_response({
        "code": 200,
        "message": "API自动化测试服务正常",
        "data": {
            "status": "ok",
            "upload_dir": UPLOAD_DIR,
            "report_dir": REPORT_DIR,
            "config": {
                "llm_model": CONFIG.get("llm", {}).get("model", ""),
                "default_concurrency": CONFIG.get("test_execution", {}).get("default_concurrency", 5),
            }
        }
    })
