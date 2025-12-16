import logging
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any

import requests
from flask import Blueprint, request, jsonify, make_response, current_app

from common.db_mapper.test_case_mapper import TestCaseMapper
from common.db_mapper.api_config_mapper import ApiConfigMapper
from common.db_mapper.environment_config_mapper import EnvironmentConfigMapper
from common.datacase_function.contect_db import db_session

test_exec_opt = Blueprint("test_exec_opt", __name__)


def json_response(body, status=200):
    resp = make_response(jsonify(body), status)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp


def _join_url(base_url: str, api_path: str) -> str:
    if base_url.endswith("/") and api_path.startswith("/"):
        return base_url[:-1] + api_path
    if (not base_url.endswith("/")) and (not api_path.startswith("/")):
        return base_url + "/" + api_path
    return base_url + api_path


def _merge_headers(env_headers: Dict[str, Any], api_headers: Dict[str, Any], case_headers: Dict[str, Any]):
    merged = {}
    if env_headers:
        merged.update(env_headers)
    if api_headers:
        merged.update(api_headers)
    if case_headers:
        merged.update(case_headers)
    return merged


def _execute_one(case: Dict[str, Any], api_conf: Dict[str, Any], env_conf: Dict[str, Any], timeout: int):
    req = (case.get("test_data") or {}).get("request") or {}
    method = (api_conf.get("method") or req.get("method") or "GET").upper()
    api_path = api_conf.get("api_path") or req.get("path") or ""
    query = req.get("query") or {}
    body = req.get("body") or {}
    case_headers = req.get("headers") or {}
    env_headers = env_conf.get("headers") or {}
    api_headers = api_conf.get("headers") or {}
    request_type = (api_conf.get("request_type") or "json").lower()

    url = _join_url(env_conf.get("base_url") or "", api_path)
    headers = _merge_headers(env_headers, api_headers, case_headers)

    req_kwargs = {"headers": headers, "params": query, "timeout": timeout}
    if request_type == "form":
        req_kwargs["data"] = body
    elif request_type == "file":
        # 简单处理：如果 body 是 {"file": "path"}，尝试上传文件；否则按 data 发送
        files = None
        data = None
        if isinstance(body, dict) and "file" in body and isinstance(body["file"], str):
            try:
                files = {"file": open(body["file"], "rb")}
            except Exception:
                data = body
        else:
            data = body
        if files:
            req_kwargs["files"] = files
        if data:
            req_kwargs["data"] = data
    else:
        req_kwargs["json"] = body

    try:
        resp = requests.request(method, url, **req_kwargs)
        return {
            "case_id": case.get("id"),
            "success": resp.ok,
            "status_code": resp.status_code,
            "elapsed_ms": int(resp.elapsed.total_seconds() * 1000),
            "response_text": resp.text[:1000],
            "url": url,
            "method": method,
        }
    except Exception as e:
        return {
            "case_id": case.get("id"),
            "success": False,
            "error": str(e),
            "url": url,
            "method": method,
        }


@test_exec_opt.route("/testcase/execute", methods=["POST"])
def execute_testcases():
    """
    执行测试案例（并发）
    入参：
    - case_ids: list[int] 必填，1 个或多个，需要在 test_case 表中存在
    - env_id: int 必填，指定 environment_config.id，用于获取 base_url / headers / timeout
    - concurrency: int 可选，并发线程数，默认 5
    """
    logger = current_app.logger or logging.getLogger(__name__)
    # 兼容 JSON / form / x-www-form-urlencoded，容错尾部多余引号
    payload = request.get_json(silent=True)
    if payload is None:
        payload = request.get_json(force=True, silent=True)
    if payload is None:
        payload = {}
        try:
            form_data = request.form.to_dict(flat=True)
            payload.update(form_data)
        except Exception:
            pass
        if not payload and request.data:
            raw = request.data.decode("utf-8", errors="ignore")
            try:
                payload = json.loads(raw)
            except Exception:
                # 尝试去掉尾部多余的引号再解析
                if raw.endswith("'") or raw.endswith('"'):
                    try:
                        payload = json.loads(raw[:-1])
                    except Exception:
                        payload = {}
                else:
                    payload = {}
    if not isinstance(payload, dict):
        payload = {}

    logger.info("【执行测试案例】原始入参=%s", payload)

    case_ids = payload.get("case_ids") or []
    # 如果是字符串形式的 list，尝试解析
    if isinstance(case_ids, str):
        try:
            case_ids = json.loads(case_ids)
        except Exception:
            case_ids = [case_ids]
    env_id = payload.get("env_id")
    concurrency = payload.get("concurrency")
    if concurrency is None:
        concurrency = 5
    try:
        concurrency = int(concurrency)
        if concurrency <= 0:
            concurrency = 1
    except Exception:
        concurrency = 5

    if not case_ids or not isinstance(case_ids, list):
        logger.warning("【执行测试案例】case_ids 非法，解析结果=%s", case_ids)
        return json_response({"code": 400, "msg": "case_ids 必须是非空数组", "data": None}, status=400)
    if env_id is None:
        logger.warning("【执行测试案例】env_id 缺失")
        return json_response({"code": 400, "msg": "env_id 必填", "data": None}, status=400)

    # 查环境
    env_mapper = EnvironmentConfigMapper()
    env = env_mapper.get_by_id(env_id)
    if not env:
        logger.warning("【执行测试案例】环境不存在 env_id=%s", env_id)
        return json_response({"code": 404, "msg": f"环境不存在: {env_id}", "data": None}, status=404)
    env_dict = env.to_json()
    logger.info("【执行测试案例】使用环境 env_id=%s, base_url=%s", env_id, env_dict.get("base_url"))

    # 查用例和关联 api_config
    case_mapper = TestCaseMapper()
    api_mapper = ApiConfigMapper()
    cases = []
    api_cache = {}

    # 为了批量查询，直接开一个只读 session
    with db_session() as session:
        rows = session.query(case_mapper.entity_class).filter(case_mapper.entity_class.id.in_(case_ids)).all()
        for r in rows:
            session.expunge(r)
            cases.append(r)

    if not cases:
        logger.warning("【执行测试案例】根据 case_ids 未找到任何案例 case_ids=%s", case_ids)
        return json_response({"code": 404, "msg": "未找到任何测试案例", "data": None}, status=404)

    # 准备 api_config 映射
    for c in cases:
        api_id = getattr(c, "api_config_id", None)
        if api_id and api_id not in api_cache:
            api_obj = api_mapper.get_by_id(api_id)
            if api_obj:
                api_cache[api_id] = api_obj
            else:
                logger.warning("【执行测试案例】用例 id=%s 关联的 api_config 不存在 api_config_id=%s", c.id, api_id)

    # 执行
    futures = []
    results = []
    timeout_default = env_dict.get("timeout") or 30
    max_workers = min(len(cases), concurrency)
    logger.info("【执行测试案例】开始执行，用例数=%s, 并发数=%s, 默认超时=%s", len(cases), max_workers, timeout_default)
    executor = ThreadPoolExecutor(max_workers=max_workers)
    for c in cases:
        api_obj = api_cache.get(getattr(c, "api_config_id", None))
        if not api_obj:
            results.append({
                "case_id": c.id,
                "success": False,
                "error": "关联的 api_config 不存在",
            })
            continue
        api_dict = api_obj.to_dict() if hasattr(api_obj, "to_dict") else api_obj.to_json()
        case_dict = c.to_json()
        case_timeout = case_dict.get("timeout") or api_dict.get("timeout") or timeout_default
        logger.info("【执行测试案例】提交用例执行 case_id=%s, api_config_id=%s, url=%s, timeout=%s",
                    c.id, getattr(c, "api_config_id", None),
                    _join_url(env_dict.get("base_url") or "", api_dict.get("api_path") or ""),
                    case_timeout)
        fut = executor.submit(_execute_one, case_dict, api_dict, env_dict, case_timeout)
        futures.append(fut)

    for fut in as_completed(futures):
        results.append(fut.result())
    executor.shutdown(wait=True)

    success_count = sum(1 for r in results if r.get("success"))
    logger.info("【执行测试案例】完成，总数=%s, 成功=%s", len(results), success_count)
    return json_response({"code": 200, "msg": "执行完成", "data": results}, status=200)

