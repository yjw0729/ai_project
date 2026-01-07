import os
import json
import logging
from flask import Blueprint, jsonify, request, make_response, current_app
from werkzeug.exceptions import HTTPException, BadRequest

from common.llm.ai_case_generator import generate_api_test_cases
from common.llm.llm_client import OpenAILLMClient
from utils.read_config_path.read_ai_config import load_ai_config
from common.db_mapper.test_case_mapper import TestCaseMapper
from common.db_enitiy.test_case import TestCase
from common.db_enitiy.api_config import ApiConfig
from common.datacase_function.contect_db import db_session

ai_generate_opt = Blueprint("ai_generate_opt", __name__)


def json_response(body, status=200):
    resp = make_response(jsonify(body), status)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp


def _load_stub_cases():
    """挡板：当 use_llm=false 时返回预置用例及原始信息。"""
    logger = current_app.logger or logging.getLogger(__name__)
    try:
        project_root = os.path.dirname(os.path.dirname(__file__))
        # 使用最新指定的挡板文件
        stub_path = os.path.join(project_root, "data", "generated_cases", "创建用户_20251215182031.json")
        if not os.path.exists(stub_path):
            logger.warning("[ai/generate_testcases] stub file not found: %s", stub_path)
            return {"cases": [], "prompt": "", "raw_output": "", "persist_path": None}
        with open(stub_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            cases = data.get("cases") or []
            prompt = data.get("prompt") or ""
            raw_output = data.get("raw_output") or ""
            logger.info("[ai/generate_testcases] stub cases loaded: %s", len(cases))
            return {
                "cases": cases,
                "prompt": prompt,
                "raw_output": raw_output,
                "persist_path": stub_path,
            }
    except Exception as e:
        logger.warning("[ai/generate_testcases] load stub failed: %s", e, exc_info=True)
        return {"cases": [], "prompt": "", "raw_output": "", "persist_path": None}


def _get_or_create_api_config(api_name: str, api_desc: str, path: str, method: str, headers: dict, module: str, logger, db_key: str = "default"):
    """根据模块+路径+方法获取或创建 api_config，返回 id"""
    method_val = (method or "GET").upper()
    module_val = module or api_name or "default"
    with db_session(db_key) as session:
        existing = session.query(ApiConfig).filter(
            ApiConfig.module == module_val,
            ApiConfig.api_path == path,
            ApiConfig.method == method_val,
            ApiConfig.is_deprecated == False,
        ).first()
        if existing:
            logger.info("【api_config】命中已存在 id=%s, module=%s, path=%s, method=%s", existing.id, module_val, path, method_val)
            return existing.id
        api_conf = ApiConfig(
            name=api_name or path,
            description=api_desc or "",
            module=module_val,
            api_path=path,
            method=method_val,
            headers=headers or {},
        )
        session.add(api_conf)
        session.flush()
        session.refresh(api_conf)
        logger.info("【api_config】新建 id=%s, module=%s, path=%s, method=%s", api_conf.id, module_val, path, method_val)
        return api_conf.id


def _case_to_entity(
    api_name: str,
    creator: str,
    case: dict,
    api_config_id: int = None,
    module: str = None,
    system: str = None,
) -> TestCase:
    """将生成的用例字典转换为 TestCase ORM 实体。

    :param api_name: 接口名称（用于默认模块名/用例名）
    :param creator: 创建人
    :param case: 单条用例字典
    :param api_config_id: 关联的 api_config.id
    :param module: 所属模块（前端入参，可选；为空时回退到 api_name）
    :param system: 所属系统（前端入参，可选）
    """
    request_block = case.get("request") or {}
    method = request_block.get("method") or ""
    path = request_block.get("path") or ""
    body = request_block.get("body") or {}
    query = request_block.get("query") or {}
    headers = request_block.get("headers") or {}

    # 组装测试步骤：至少一个步骤，满足验证要求
    step_desc = f"调用接口 {method} {path}".strip()
    step_data = {
        "body": body,
        "query": query,
        "headers": headers,
    }
    test_steps = [
        {
            "step_number": 1,
            "description": step_desc,
            "expected": case.get("expect") or "",
            "data": step_data,
        }
    ]

    expected_results = case.get("assertions") or []
    priority = str(case.get("priority") or "P2").upper()
    if priority not in ["P0", "P1", "P2", "P3"]:
        priority = "P2"

    # 所属模块优先使用外部显式传入的 module，其次使用 api_name，最后 default
    module_val = module or api_name or "default"

    return TestCase(
        name=case.get("title") or (api_name + "_case"),
        description=case.get("expect") or "",
        module=module_val,
        system=system,
        priority=priority,
        tags=case.get("tags") or [],
        preconditions="",
        test_steps=test_steps,
        setup_scripts=None,
        teardown_scripts=None,
        expected_results=expected_results,
        test_data={
            "request": {
                "method": method,
                "path": path,
                "headers": headers,
                "query": query,
                "body": body,
            }
        },
        variables=None,
        max_retry_times=0,
        timeout=None,
        # 兼容旧字段：status 仍保留（草稿/废弃等生命周期）
        status="draft",
        # 新字段：默认“启用 + 未执行”，便于前端直接展示/执行
        case_status="enabled",
        last_execution_status="not_run",
        last_execution_time=None,
        version=1,
        creator=creator or "ai_generator",
        reviewer=None,
        review_status="pending",
        review_comment=None,
        api_config_id=api_config_id,
    )


def _save_cases_to_db(
    api_name: str,
    creator: str,
    cases: list,
    logger,
    db_key: str = "default",
    api_config_id: int = None,
    module: str = None,
    system: str = None,
):
    mapper = TestCaseMapper(db_key=db_key)
    saved_ids = []
    logger.info("【数据库写入】开始写入用例，总数=%d, api_name=%s, creator=%s, db_key=%s",
                len(cases), api_name, creator, db_key)
    for idx, c in enumerate(cases):
        try:
            entity = _case_to_entity(
                api_name,
                creator,
                c,
                api_config_id=api_config_id,
                module=module,
                system=system,
            )
            case_id = mapper.create(entity)
            saved_ids.append(case_id)
            # 不再访问 entity（已脱管），直接使用原始标题避免 DetachedInstanceError
            case_name = c.get("title") or api_name or "unknown"
            logger.info("【数据库写入】用例 %d/%d 写入成功，id=%d, name=%s",
                       idx + 1, len(cases), case_id, case_name)
        except Exception as e:
            logger.error("【数据库写入】用例 %d/%d 写入失败: %s, 用例名称=%s",
                        idx + 1, len(cases), str(e), c.get("title", "未知"), exc_info=True)
    logger.info("【数据库写入】完成，成功=%d, 失败=%d, saved_ids=%s",
                len(saved_ids), len(cases) - len(saved_ids), saved_ids)
    return saved_ids


@ai_generate_opt.route("/ai/generate_testcases", methods=["POST"])
def generate_testcases():
    """
    请求体示例：
    {
        "api_name": "创建用户",
        "api_desc": "用于创建用户的接口",
        "http_method": "POST",
        "path": "/api/user/create",
        "headers": {"Authorization": "Bearer xxx"},
        "params_example": {"name": "张三", "age": 18},
        "constraints": "年龄18-60之间，name必填",
        "max_cases": 10,
        "persist": true
    }
    """
    try:
        logger = current_app.logger or logging.getLogger(__name__)
        # silent=False 以便 JSON 解析失败时抛出 BadRequest，统一转成 JSON 错误响应
        payload = request.get_json(force=True, silent=False) or {}
        persist = payload.get("persist", False)
        ai_conf = load_ai_config()
        # 挡板生效：强制不调用大模型
        use_llm = False
        logger.info("【接口调用开始】/ai/generate_testcases 入参=%s, 是否调用大模型=%s", payload, use_llm)

        required_fields = ["api_name", "http_method", "path", "params_example"]
        missing = [f for f in required_fields if not payload.get(f)]
        if missing:
            return json_response(
                {"code": 400, "msg": f"缺少必填字段: {','.join(missing)}", "data": None},
                status=400,
            )

        llm_client = None
        if use_llm:
            api_key = ai_conf.get("api_key")
            if not api_key:
                return json_response(
                    {"code": 500, "msg": "大模型已开启，但未配置 api_key（可在 app/ai_config.json 或环境变量 QWEN_API_KEY 设置）", "data": None},
                    status=500,
                )
            base_url = (ai_conf.get("base_url") or "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
            model = ai_conf.get("model") or "qwen-turbo"
            temperature = ai_conf.get("temperature", 0.2)
            max_tokens = ai_conf.get("max_tokens", 1024)
            timeout = ai_conf.get("timeout", 600)
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
                base_url,
                model,
                temperature,
                max_tokens,
                timeout,
            )

        # 生成落盘目录：项目根目录/data/generated_cases
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
                api_name=payload.get("api_name"),
                api_desc=payload.get("api_desc") or "",
                http_method=payload.get("http_method"),
                path=payload.get("path"),
                params_example=payload.get("params_example") or {},
                headers=payload.get("headers") or {},
                constraints=payload.get("constraints"),
                # 不再强制数量上限，留空由提示词决定尽量全面覆盖
                max_cases=int(payload.get("max_cases")) if payload.get("max_cases") is not None else None,
                persist_dir=persist_dir,
                llm_client=llm_client,
            )

        # 写入数据库
        creator = payload.get("creator") or "ai_generator"
        db_key = payload.get("db_key") or "default"
        module = payload.get("module")  # 所属模块（可选）
        system = payload.get("system")  # 所属系统（可选）

        # 获取/创建 api_config 以便后续案例关联
        api_config_id = _get_or_create_api_config(
            api_name=payload.get("api_name"),
            api_desc=payload.get("api_desc") or "",
            path=payload.get("path"),
            method=payload.get("http_method"),
            headers=payload.get("headers") or {},
            module=payload.get("api_name") or "default",
            logger=logger,
            db_key=db_key,
        )
        persist_to_db = ai_conf.get("persist_to_db", True)
        if persist_to_db:
            saved_ids = _save_cases_to_db(
                payload.get("api_name"),
                creator,
                result.get("cases") or [],
                logger,
                db_key=db_key,
                api_config_id=api_config_id,
                module=module,
                system=system,
            )
        else:
            saved_ids = []
            logger.info("【配置】persist_to_db=false，本次不写入数据库")
        result["saved_case_ids"] = saved_ids

        logger.info(
            "【接口调用完成】是否调用大模型=%s, 生成用例数=%s, parse_fail=%s, 落盘路径=%s, 写库IDs=%s",
            bool(llm_client),
            len(result.get("cases", [])),
            result.get("parse_fail_count", 0),
            result.get("persist_path"),
            result.get("saved_case_ids"),
        )
        if result.get("raw_output"):
            logger.debug("【大模型原始输出】%s", result["raw_output"])

        return json_response({"code": 200, "msg": "success", "data": result}, status=200)
    except BadRequest as bad_req:
        logger = current_app.logger or logging.getLogger(__name__)
        logger.warning("【接口异常】请求体不是合法JSON: %s", bad_req)
        return json_response(
            {"code": 400, "msg": f"请求体不是合法JSON: {bad_req.description}", "data": None},
            status=400,
        )
    except HTTPException as http_err:
        logger = current_app.logger or logging.getLogger(__name__)
        logger.warning("【接口异常】HTTP错误: %s", http_err, exc_info=True)
        return json_response(
            {"code": http_err.code, "msg": http_err.description, "data": None},
            status=http_err.code,
        )
    except Exception as e:
        logger = current_app.logger or logging.getLogger(__name__)
        logger.exception("【接口异常】服务器内部错误")
        return json_response(
            {"code": 500, "msg": f"server error: {e}", "data": None},
            status=500,
        )

