import os
import logging
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

from common.llm.doc_parser import (
    parse_doc_file,
    constraints_from_fields,
    build_params_example,
)
from common.llm.ai_case_generator import generate_api_test_cases
from utils.read_config_path.read_ai_config import load_ai_config
from common.llm.llm_client import OpenAILLMClient
from api.http_ai_generate_cases import _load_stub_cases, _save_cases_to_db, _get_or_create_api_config

doc_parser_opt = Blueprint("doc_parser_opt", __name__)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _json_error(msg: str, code: int = 400):
    return jsonify({"code": code, "msg": msg, "data": None}), code


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
    组合流程：上传文档并生成测试用例。
    入参（form-data）：
    - file: docx/pdf（必填）
    - api_name, http_method, path（必填）
    - api_desc, max_cases, persist（可选）
    - module: 所属模块（可选）
    - system: 所属系统（可选）
    - request_json: 请求入参JSON字符串（可选，优先使用）
    - response_json: 响应出参JSON字符串（可选）
    """
    import json
    logger = current_app.logger or logging.getLogger(__name__)
    payload = request.form.to_dict()
    logger.info(
        "【generate_from_doc 入参原始】form=%s, files=%s",
        payload,
        list(request.files.keys()),
    )
    persist = payload.get("persist", "false").lower() == "true"

    required = ["api_name", "http_method", "path"]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        return _json_error(f"缺少必填字段: {','.join(missing)}")

    if "file" not in request.files:
        return _json_error("缺少文件字段 file")
    file = request.files["file"]
    if file.filename == "":
        return _json_error("文件名为空")

    if not file.filename or not isinstance(file.filename, str):
        return _json_error("文件名为空或类型错误")
    # filename = secure_filename(file.filename)
    logging.info(f'获取到的filename{file.filename}')
    saved_path = os.path.join(UPLOAD_DIR, file.filename)
    file.save(saved_path)
    logger.info("【generate_from_doc 入参】payload=%s, filename=%s", payload, file.filename)

    # 解析文档获取字段和约束
    fields = []
    constraints = ""
    try:
        parsed = parse_doc_file(saved_path, location_hint="body.data")
        fields = parsed.get("fields") or []
        constraints = constraints_from_fields(fields)
    except Exception as e:
        logger.exception("文档解析失败")
        return _json_error(f"文档解析失败: {e}", code=500)

    # 优先使用传入的request_json，其次使用文档中提取的，最后使用build_params_example
    params_example = None
    if payload.get("request_json"):
        try:
            params_example = json.loads(payload.get("request_json"))
            logger.info("【使用传入的request_json】%s", params_example)
        except json.JSONDecodeError as e:
            logger.warning("【request_json解析失败】%s，将使用文档解析结果", e)

    if not params_example:
        params_example = parsed.get("params_example")
        if params_example:
            logger.info("【使用文档中提取的JSON示例】%s", params_example)

    if not params_example:
        params_example = build_params_example(fields)
        logger.info("【使用build_params_example生成的示例】%s", params_example)

    # 解析响应JSON（如果传入）
    response_example = None
    if payload.get("response_json"):
        try:
            response_example = json.loads(payload.get("response_json"))
            logger.info("【使用传入的response_json】%s", response_example)
        except json.JSONDecodeError as e:
            logger.warning("【response_json解析失败】%s", e)

    # 复用generate_testcases接口的流程
    # 构建与generate_testcases相同的payload结构
    testcase_payload = {
        "api_name": payload.get("api_name"),
        "api_desc": payload.get("api_desc") or "",
        "http_method": payload.get("http_method"),
        "path": payload.get("path"),
        "params_example": params_example,
        "headers": payload.get("headers") or {},
        "constraints": constraints,
        # 不再强制数量上限，留空由提示词决定尽量全面覆盖
        "max_cases": int(payload.get("max_cases")) if payload.get("max_cases") is not None else None,
        "persist": persist,
        "creator": payload.get("creator") or "ai_generator",
        "db_key": payload.get("db_key") or "default",
        # 新增：所属模块 & 所属系统（可选）
        "module": payload.get("module"),
        "system": payload.get("system"),
    }

    # 调用generate_testcases的核心逻辑（但不走HTTP路由）
    from api.http_ai_generate_cases import _load_stub_cases, _save_cases_to_db
    from utils.read_config_path.read_ai_config import load_ai_config
    from common.llm.llm_client import OpenAILLMClient

    ai_conf = load_ai_config()
    use_llm = bool(ai_conf.get("use_llm") or ai_conf.get("user_llm"))
    llm_client = None
    if use_llm:
        api_key = ai_conf.get("api_key")
        if not api_key:
            return _json_error("大模型已开启但未配置 api_key", code=500)
        base_url = (ai_conf.get("base_url") or "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
        model = ai_conf.get("model") or "qwen-turbo"
        temperature = ai_conf.get("temperature", 0.2)
        max_tokens = ai_conf.get("max_tokens", 1024)
        timeout = ai_conf.get("timeout", 1200)
        llm_client = OpenAILLMClient(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        logger.info(
            "【调用大模型】base_url=%s model=%s temperature=%s max_tokens=%s timeout=%s",
            base_url, model, temperature, max_tokens, timeout
        )

    project_root = os.path.dirname(os.path.dirname(__file__))
    persist_dir = os.path.join(project_root, "data", "generated_cases") if persist else None

    if not use_llm:
        stub = _load_stub_cases()
        result = {
            "review_id": "stub",
            "cases": stub.get("cases", []),
            "prompt": stub.get("prompt", ""),
            "raw_output": stub.get("raw_output", ""),
            "persist_path": stub.get("persist_path"),
        }
    else:
        result = generate_api_test_cases(
            api_name=testcase_payload.get("api_name"),
            api_desc=testcase_payload.get("api_desc") or "",
            http_method=testcase_payload.get("http_method"),
            path=testcase_payload.get("path"),
            params_example=testcase_payload.get("params_example") or {},
            headers=testcase_payload.get("headers") or {},
            constraints=testcase_payload.get("constraints"),
            max_cases=testcase_payload.get("max_cases"),
            persist_dir=persist_dir,
            llm_client=llm_client,
        )

    # 获取/创建 api_config
    api_config_id = _get_or_create_api_config(
        api_name=testcase_payload.get("api_name"),
        api_desc=testcase_payload.get("api_desc") or "",
        path=testcase_payload.get("path"),
        method=testcase_payload.get("http_method"),
        headers=testcase_payload.get("headers") or {},
        module=testcase_payload.get("api_name") or "default",
        logger=logger,
        db_key=testcase_payload.get("db_key"),
    )

    # 写入数据库
    saved_ids = []
    persist_to_db = ai_conf.get("persist_to_db", True)
    if persist_to_db:
        saved_ids = _save_cases_to_db(
            testcase_payload.get("api_name"),
            testcase_payload.get("creator"),
            result.get("cases") or [],
            logger,
            db_key=testcase_payload.get("db_key"),
            api_config_id=api_config_id,
            module=testcase_payload.get("module"),
            system=testcase_payload.get("system"),
        )
    else:
        logger.info("【配置】persist_to_db=false，本次不写入数据库")

    logger.info(
        "【文档生成用例完成】用例数=%s, 写入数据库成功数=%s, parse_fail=%s, max_cases=%s, use_llm=%s",
        len(result.get("cases", [])),
        len(saved_ids),
        result.get("parse_fail_count", 0),
        testcase_payload.get("max_cases"),
        bool(llm_client),
    )

    # 优化响应：只返回cases和saved_case_ids
    response_data = {
        "cases": result.get("cases", []),
        "saved_case_ids": saved_ids,
    }
    return jsonify({"code": 200, "msg": "success", "data": response_data})

