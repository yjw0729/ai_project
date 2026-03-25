"""API自动化测试 - Flask API接口层"""

import json
import logging
import os
import traceback
import uuid as uuid_module
from datetime import datetime
from typing import Any, Dict, List, Optional
from flask import Blueprint, request, jsonify, make_response
from werkzeug.utils import secure_filename

from common.rag.processors.api_auto_test_processor import APITestDocProcessor
from common.test_executor import APITestRunner, ReportGenerator
from common.llm.api_test_prompts import TEST_CASE_GENERATION_PROMPT
from common.llm.llm_client import LLMClient
from common.config_loader import get_config
from platform_service.service import rate_limit

# ========== 健壮性基础设施导入（懒加载，优雅降级）==========
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("[WARN] redis 未安装，异步任务追踪功能不可用")

try:
    import pika
    PIKA_AVAILABLE = True
except ImportError:
    PIKA_AVAILABLE = False
    print("[WARN] pika 未安装，消息队列功能不可用")

# MQ客户端和TaskService全局单例（延迟初始化）
_mq_client = None
_task_service = None

logger = logging.getLogger(__name__)


api_auto_test_bp = Blueprint("api_auto_test", __name__, url_prefix="/api/auto_test")


# ==================== 加载配置 ====================

def _load_config() -> Dict[str, Any]:
    """从 ConfigLoader 加载配置"""
    return get_config()._config.get("api_auto_test", {})


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


def _load_retry_times() -> int:
    """从配置文件读取失败重试次数"""
    from common.config_loader import get_config
    return get_config().retry_times


# ==================== 健壮性基础设施：懒加载初始化 ====================

def _get_task_service():
    """
    获取 TaskService 单例（延迟初始化）。
    连接 Redis + MySQL，提供任务追踪能力。
    初始化失败时返回 None（调用方应降级为同步模式）。
    """
    global _task_service
    if _task_service is None and REDIS_AVAILABLE:
        try:
            redis_client = redis.Redis(
                host="localhost",
                port=6379,
                password="pytest_sxp_2026",
                decode_responses=True,
                socket_connect_timeout=3,
            )
            redis_client.ping()

            from common.db_mapper.task_execution_mapper import TaskExecutionMapper
            from platform_service.service.task_service import TaskService

            _task_service = TaskService(redis_client, TaskExecutionMapper())
            logger.info("[OK] TaskService 初始化成功")
        except Exception as e:
            logger.warning("[WARN] TaskService 初始化失败: %s", str(e))
            _task_service = None
    return _task_service


def _get_mq_client():
    """
    获取 MQ 客户端单例（延迟初始化）。
    连接 RabbitMQ，提供消息发布能力。
    初始化失败时返回 None（调用方应降级为同步模式）。
    """
    global _mq_client
    if _mq_client is None and PIKA_AVAILABLE:
        try:
            from platform_service.service.mq_client import get_mq_client as _get
            _mq_client = _get()
            _mq_client.connect()
        except Exception as e:
            logger.warning("[WARN] MQ客户端初始化失败: %s", str(e))
            _mq_client = None
    return _mq_client


# ==================== 辅助函数（异步支持） ====================

def _get_user_id_from_request(req) -> str:
    """
    从请求中提取用户ID。
    TODO: 接入真实会话管理后从此获取 user_id。
    当前从请求头 X-User-ID 获取，默认为 'anonymous'。
    """
    return req.headers.get("X-User-ID", "anonymous")


def _execute_tests_sync(
    payload: dict,
    test_cases: list,
    execution_id: str,
):
    """
    同步执行测试（降级模式）。
    当 RabbitMQ 或 Redis 不可用时，回退到此方法。

    注意：此降级方法仍复用原有 ThreadPoolExecutor 方式，
    因为 TestCaseExecutor 需要数据库完整连接。
    完整 pytest 迁移由 /execute 端点提供。
    """
    logger.info("【API-Sync】同步执行测试用例（降级模式）", case_count=len(test_cases))

    env_config = _load_env_config(payload.get("env_id"))
    exec_config = CONFIG.get("test_execution", {})

    runner = APITestRunner(
        env_config=env_config,
        concurrency=min(payload.get("concurrency", 5), exec_config.get("max_concurrency", 20)),
        default_timeout=exec_config.get("default_timeout", 30),
        max_retry=exec_config.get("retry_times", 2),
    )

    results = runner.execute_batch(test_cases, mode=payload.get("mode", "parallel"))
    summary = runner.get_summary()

    report_gen = ReportGenerator(output_dir=REPORT_DIR)
    report_path = report_gen.generate_html_report(results, summary, execution_id)
    json_report_path = report_gen.generate_json_report(results, summary, execution_id)

    _save_execution_record(execution_id, [tc["id"] for tc in test_cases], summary, report_path, json_report_path)

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


def _generate_cases_sync(
    payload: dict,
    doc_id: str,
    parsed: dict,
    processor: Any,
):
    """
    同步生成测试用例（降级模式）。
    当 RabbitMQ 或 Redis 不可用时，回退到此方法。
    复用原有 generate_test_cases 的核心逻辑。
    """
    logger.info("【API-Generate-Sync】同步生成用例（降级模式）")

    options = payload.get("options", {})
    priority_filter = options.get("priority_filter", ["P0", "P1", "P2"])
    system_name = payload.get("system_name") or parsed.get("system_name", "")

    interface_list = parsed.get("parsed_interfaces", [])
    flow_nodes = parsed.get("flowchart_nodes", [])
    flow_data = parsed.get("flow_data", {})

    all_cases = []

    if interface_list:
        for interface in interface_list:
            cases = _generate_cases_for_interface(interface, options)
            all_cases.extend(cases)

    if flow_nodes:
        cases = _generate_cases_from_flowchart(flow_data, options)
        all_cases.extend(cases)

    filtered_cases = [c for c in all_cases if c.get("priority") in priority_filter]
    inserted_cases = _insert_cases_to_database(filtered_cases, system_name, doc_id)
    case_ids = [c["id"] for c in inserted_cases]

    by_priority = {}
    by_tag = {}
    for c in inserted_cases:
        p = c.get("priority", "P2")
        by_priority[p] = by_priority.get(p, 0) + 1
        for tag in (c.get("tags") or []):
            by_tag[tag] = by_tag.get(tag, 0) + 1

    return _json_response({
        "code": 200,
        "message": "用例生成完成",
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


# ==================== API: 异步任务 - 测试执行 ====================

@api_auto_test_bp.route("/execute-async", methods=["POST"])
@rate_limit("execute_async")
def execute_tests_async():
    """
    【新增】异步执行测试用例。
    提交任务后立即返回 task_id，前端通过 /task/{task_id} 轮询查进度。

    请求体：
    {
        "case_ids": [1, 2, 3],
        "env_id": 1,
        "concurrency": 5,
        "mode": "parallel"
    }

    响应：
    {
        "code": 200,
        "message": "任务已提交",
        "data": {
            "task_id": "xxx-xxx",
            "execution_id": "exec-xxx",
            "status": "queued",
            "message": "任务已加入执行队列"
        }
    }
    """
    logger.info("【API-Async】收到异步执行测试请求")

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

    user_id = _get_user_id_from_request(request)
    execution_id = f"exec-{uuid_module.uuid4().hex[:12]}"
    trace_id = request.headers.get("X-Trace-ID", "")

    task_service = _get_task_service()
    mq_client = _get_mq_client()

    if task_service is None or mq_client is None:
        logger.warning("健壮性基础设施不可用，降级为同步模式")
        return _execute_tests_sync(payload, test_cases, execution_id)

    task_id = task_service.create_task(
        user_id=user_id,
        task_type="test.execute",
        payload={
            "execution_id": execution_id,
            "case_ids": case_ids,
            "env_id": env_id,
            "concurrency": min(concurrency, 20),
            "mode": mode,
        },
        description=f"执行 {len(case_ids)} 个测试用例",
        trace_id=trace_id,
        max_retries=0,
    )

    from shared.common_proto.mq_messages import build_test_execute_message
    message = build_test_execute_message(
        task_id=task_id,
        user_id=user_id,
        payload={
            "execution_id": execution_id,
            "case_ids": case_ids,
            "env_id": env_id,
            "concurrency": min(concurrency, 20),
            "mode": mode,
        },
        trace_id=trace_id,
    )

    publish_ok = mq_client.publish("test.execute", message)

    if not publish_ok:
        logger.warning("消息队列发布失败，降级为同步模式", task_id=task_id)
        return _execute_tests_sync(payload, test_cases, execution_id)

    logger.info("【API-Async】任务已提交",
        task_id=task_id,
        execution_id=execution_id,
        case_count=len(case_ids)
    )

    return _json_response({
        "code": 200,
        "message": "任务已提交",
        "data": {
            "task_id": task_id,
            "execution_id": execution_id,
            "status": "queued",
            "case_count": len(case_ids),
            "message": f"任务已加入执行队列，共 {len(case_ids)} 个用例",
            "query_url": f"/api/auto_test/task/{task_id}",
        }
    })


@api_auto_test_bp.route("/task/<task_id>", methods=["GET"])
def get_task_status(task_id: str):
    """
    【新增】查询任务状态。
    用于前端轮询查询异步任务进度。

    响应：
    {
        "code": 200,
        "data": {
            "task_id": "xxx",
            "status": "running",
            "progress": "45",
            "result_summary": {...},
            "error": null
        }
    }
    """
    user_id = _get_user_id_from_request(request)
    task_service = _get_task_service()

    if task_service is None:
        return _json_response({
            "code": 503,
            "message": "任务追踪服务不可用（Redis未连接）",
            "data": None
        }, 503)

    task = task_service.get_status(task_id, user_id)
    if not task:
        return _json_response({
            "code": 404,
            "message": "任务不存在或无权访问",
            "data": None
        }, 404)

    return _json_response({
        "code": 200,
        "message": "success",
        "data": {
            "task_id": task["task_id"],
            "status": task["status"],
            "task_type": task.get("task_type"),
            "progress": task.get("progress", "0"),
            "result_summary": task.get("result_summary"),
            "error": task.get("error"),
            "created_time": task.get("created_time"),
            "updated_time": task.get("updated_time"),
        }
    })


@api_auto_test_bp.route("/task/<task_id>/cancel", methods=["POST"])
def cancel_task(task_id: str):
    """
    【新增】取消任务。
    只能取消 pending / queued / retrying 状态的任务。
    """
    user_id = _get_user_id_from_request(request)
    task_service = _get_task_service()

    if task_service is None:
        return _json_response({"code": 503, "message": "任务追踪服务不可用（Redis未连接）", "data": None}, 503)

    ok = task_service.cancel_task(task_id, user_id)
    if not ok:
        return _json_response({
            "code": 400,
            "message": "任务无法取消（可能已运行完成、正在运行或不存在）",
            "data": None
        }, 400)

    return _json_response({
        "code": 200,
        "message": "任务已取消",
        "data": {"task_id": task_id}
    })


@api_auto_test_bp.route("/task/list", methods=["GET"])
def list_user_tasks():
    """
    【新增】获取当前用户的所有任务列表。
    支持按状态过滤：?status=pending&status=running&status=completed

    响应：
    {
        "code": 200,
        "data": {
            "tasks": [...],
            "count": 5
        }
    }
    """
    user_id = _get_user_id_from_request(request)
    status_filter = request.args.getlist("status")
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        limit = 50

    task_service = _get_task_service()
    if task_service is None:
        return _json_response({"code": 503, "message": "任务追踪服务不可用（Redis未连接）", "data": None}, 503)

    tasks = task_service.get_user_tasks(user_id, status_filter or None, min(limit, 200))
    return _json_response({
        "code": 200,
        "message": "success",
        "data": {
            "tasks": tasks,
            "count": len(tasks)
        }
    })


# ==================== API: 异步任务 - 用例生成 ====================

@api_auto_test_bp.route("/generate-async", methods=["POST"])
@rate_limit("generate_async")
def generate_cases_async():
    """
    【新增】异步生成测试用例。
    提交任务后立即返回 task_id，前端轮询查进度。

    请求体：
    {
        "doc_id": "xxx",
        "system_name": "用户中心",
        "options": {
            "generate_mode": "comprehensive",
            "priority_filter": ["P0", "P1", "P2"]
        }
    }

    响应：
    {
        "code": 200,
        "message": "任务已提交",
        "data": {
            "task_id": "xxx",
            "status": "queued",
            "query_url": "/api/auto_test/task/xxx"
        }
    }
    """
    logger.info("【API-Generate-Async】收到异步生成用例请求")

    payload = request.get_json(silent=True) or {}
    doc_id = payload.get("doc_id")
    if not doc_id:
        return _json_response({"code": 400, "message": "缺少 doc_id", "data": None}, 400)

    processor = APITestDocProcessor(upload_dir=UPLOAD_DIR)
    parsed = processor.load_parsed_result(doc_id)
    if not parsed:
        return _json_response({"code": 404, "message": "文档不存在或已过期", "data": None}, 404)

    user_id = _get_user_id_from_request(request)
    trace_id = request.headers.get("X-Trace-ID", "")
    task_service = _get_task_service()
    mq_client = _get_mq_client()

    if task_service is None or mq_client is None:
        logger.warning("健壮性基础设施不可用，降级为同步模式")
        return _generate_cases_sync(payload, doc_id, parsed, processor)

    task_id = task_service.create_task(
        user_id=user_id,
        task_type="llm.generate",
        payload={
            "doc_id": doc_id,
            "system_name": payload.get("system_name", ""),
            "options": payload.get("options", {}),
        },
        description=f"为文档 {doc_id} 生成测试用例",
        trace_id=trace_id,
        max_retries=3,
    )

    from shared.common_proto.mq_messages import build_llm_generate_message
    message = build_llm_generate_message(
        task_id=task_id,
        user_id=user_id,
        payload={
            "doc_id": doc_id,
            "system_name": payload.get("system_name", ""),
            "options": payload.get("options", {}),
        },
        trace_id=trace_id,
    )

    publish_ok = mq_client.publish("llm.generate", message)

    if not publish_ok:
        logger.warning("消息队列发布失败，降级为同步模式", task_id=task_id)
        return _generate_cases_sync(payload, doc_id, parsed, processor)

    return _json_response({
        "code": 200,
        "message": "任务已提交",
        "data": {
            "task_id": task_id,
            "doc_id": doc_id,
            "status": "queued",
            "message": "用例生成任务已加入队列",
            "query_url": f"/api/auto_test/task/{task_id}",
        }
    })


# ==================== API: 上传文档 ====================

def _json_response(body: Dict[str, Any], status: int = 200):
    resp = make_response(jsonify(body), status)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    # 禁用缓存，确保前端总能获取最新数据
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
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
    unique_filename = f"{uuid_module.uuid4().hex}_{filename}"
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
@rate_limit("execute")
def execute_tests():
    """
    执行测试用例（pytest + requests 方式）。

    请求体：
    {
        "case_ids": [1, 2, 3],
        "env_id": 1,
        "concurrency": 5,        # pytest-xdist 并发数（可选）
        "retry_times": 2,        # 失败重试次数（从配置文件读取，可选）
        "fail_fast": false       # 失败快速停止（可选）
    }

    响应：
    {
        "code": 200,
        "message": "success",
        "data": {
            "execution_id": "exec-xxx",
            "status": "completed",
            "summary": {
                "total": 10,
                "passed": 8,
                "failed": 2,
                "skipped": 0,
                "success_rate": 80.0
            },
            "duration_seconds": 12.5,
            "report_url": "/api/auto_test/report/exec-xxx",
            "allure_results_dir": "outputs/allure-results/exec-xxx"
        }
    }
    """
    from common.config_loader import get_config
    from common.test_executor.test_case_executor import TestCaseExecutor
    from common.test_executor.pytest_generator import PytestGenerator
    from core.runner import TestRunner, RunConfig, ExecutionMode

    logger.info("【API-Execute】收到测试执行请求")

    # 1. 解析请求参数
    payload = request.get_json(silent=True) or {}
    case_ids = payload.get("case_ids", [])
    env_id = payload.get("env_id")
    concurrency = payload.get("concurrency", 5)

    # 从配置文件读取重试次数（可被请求参数覆盖）
    config_loader = get_config()
    retry_times = payload.get("retry_times", config_loader.retry_times)
    fail_fast = payload.get("fail_fast", config_loader.fail_fast)
    default_timeout = payload.get("timeout", config_loader.default_timeout)

    if not case_ids:
        return _json_response({"code": 400, "message": "缺少 case_ids 参数", "data": None}, 400)

    # 2. 生成执行 ID
    execution_id = f"exec-{uuid_module.uuid4().hex[:12]}"

    # 3. 加载用例（从 DB）
    try:
        executor = TestCaseExecutor()
        cases = executor.load_cases(case_ids, env_id)
        if not cases:
            return _json_response({"code": 404, "message": "未找到测试用例", "data": None}, 404)
    except Exception as e:
        logger.exception("【API-Execute】加载用例失败")
        return _json_response({"code": 500, "message": f"加载用例失败: {e}", "data": None}, 500)

    # 4. 获取环境 base_url
    base_url = "http://localhost:5000"
    if env_id:
        from common.db_mapper.environment_config_mapper import EnvironmentConfigMapper
        env_mapper = EnvironmentConfigMapper()
        env_cfg = env_mapper.get_by_id(env_id)
        if env_cfg and hasattr(env_cfg, "base_url"):
            base_url = env_cfg.base_url or base_url

    # 5. 生成 pytest 测试文件
    try:
        generator = PytestGenerator(output_dir=config_loader.generated_tests_dir)
        test_file_path = generator.generate(
            cases=cases,
            execution_id=execution_id,
            base_url=base_url,
            retry_times=retry_times,
            timeout=default_timeout
        )
        logger.info("【API-Execute】生成测试文件: %s", test_file_path)
    except Exception as e:
        logger.exception("【API-Execute】生成测试文件失败")
        return _json_response({"code": 500, "message": f"生成测试文件失败: {e}", "data": None}, 500)

    # 6. 构建 pytest 执行配置
    allure_results_dir = os.path.join(config_loader.allure_results_dir, execution_id)
    os.makedirs(allure_results_dir, exist_ok=True)

    # 根据 concurrency 决定执行模式
    if concurrency > 1:
        mode = ExecutionMode.DISTRIBUTED
        workers = concurrency
    else:
        mode = ExecutionMode.SEQUENTIAL
        workers = "auto"

    run_config = RunConfig(
        test_paths=[test_file_path],
        mode=mode,
        repeat_count=retry_times,
        workers=workers,
        allure_results_dir=allure_results_dir,
        allure_report_dir=os.path.join(config_loader.report_dir, execution_id),
        fail_fast=fail_fast,
        verbose=True,
        capture="sys",
        timeout=default_timeout,
    )

    # 7. 执行 pytest
    try:
        runner = TestRunner(run_config)
        result = runner.run()
        logger.info("【API-Execute】pytest 执行完成: %s", result)
    except Exception as e:
        logger.exception("【API-Execute】pytest 执行失败")
        return _json_response({"code": 500, "message": f"执行失败: {e}", "data": None}, 500)

    # 8. 生成 Allure 报告
    allure_report_dir = ""
    try:
        allure_report_dir = runner.generate_allure_report(
            results_dir=allure_results_dir,
            report_dir=run_config.allure_report_dir
        )
    except Exception as e:
        logger.warning("【API-Execute】生成 Allure 报告失败: %s", e)

    # 9. 回写执行结果到 DB
    try:
        for case in cases:
            case_status = "success" if result.passed > 0 else "failed"
            executor.save_execution_result(case.db_id, case_status)
    except Exception as e:
        logger.warning("【API-Execute】回写执行结果失败: %s", e)

    # 10. 构建响应
    return _json_response({
        "code": 200,
        "message": "success",
        "data": {
            "execution_id": execution_id,
            "status": "completed",
            "summary": {
                "total": result.total,
                "passed": result.passed,
                "failed": result.failed,
                "skipped": result.skipped,
                "success_rate": result.success_rate,
            },
            "duration_seconds": result.duration_seconds,
            "exit_code": result.exit_code,
            "report_url": f"/api/auto_test/report/{execution_id}" if allure_report_dir else None,
            "allure_results_dir": allure_results_dir,
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
