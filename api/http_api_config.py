import logging
import json
from flask import Blueprint, request, jsonify, make_response, current_app
from werkzeug.exceptions import BadRequest

from common.db_enitiy.api_config import ApiConfig
from common.db_mapper.api_config_mapper import ApiConfigMapper

api_config_opt = Blueprint("api_config_opt", __name__)


def json_response(body, status=200):
    resp = make_response(jsonify(body), status)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp


def _parse_payload(strict_json_error: bool = False):
    """
    解析请求体，兼容 JSON / form。
    当 strict_json_error=True 且存在 body 但 JSON 解析失败时，抛出 BadRequest，
    以避免将非法 JSON 误当作空对象导致查询条件失效。
    """
    payload = request.get_json(silent=True)
    if payload is None:
        try:
            if request.data:
                payload = json.loads(request.data.decode("utf-8"))
        except Exception:
            if strict_json_error and request.data:
                raise BadRequest("请求体不是合法JSON")
            payload = None
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    try:
        form_data = request.form.to_dict(flat=True)
        for k, v in form_data.items():
            payload.setdefault(k, v)
    except Exception:
        pass
    return payload


def _parse_bool(val):
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes", "on")
    return bool(val)


def _parse_headers(headers):
    if headers is None:
        return {}
    if isinstance(headers, dict):
        return headers
    if isinstance(headers, str):
        hdr_text = headers.strip().lstrip("{").rstrip("}")
        if ":" in hdr_text and '"' not in hdr_text:
            try:
                pairs = [p for p in hdr_text.split(",") if p.strip()]
                headers_dict = {}
                for p in pairs:
                    if ":" not in p:
                        continue
                    k, v = p.split(":", 1)
                    headers_dict[k.strip()] = v.strip()
                return headers_dict
            except Exception:
                pass
        try:
            return json.loads(headers)
        except json.JSONDecodeError:
            raise ValueError('headers 必须是 JSON 对象，例如 {"Content-Type":"application/json"}')
    raise ValueError("headers 必须是 JSON 对象")


def _parse_body_template(body_tpl):
    if body_tpl is None or body_tpl == "":
        return None
    if isinstance(body_tpl, (dict, list)):
        return body_tpl
    if isinstance(body_tpl, str):
        try:
            return json.loads(body_tpl)
        except json.JSONDecodeError:
            raise ValueError("请求体模板必须是 JSON 对象或数组")
    raise ValueError("请求体模板必须是 JSON 对象或数组")


def _serialize(entity: ApiConfig):
    return {
        "id": entity.id,
        "name": entity.name,
        "description": entity.description,
        "module": entity.module,
        "api_path": entity.api_path,
        "method": entity.method.value if hasattr(entity.method, "value") else entity.method,
        "request_type": entity.request_type.value if hasattr(entity.request_type, "value") else entity.request_type,
        "headers": entity.headers,
        "default_params": entity.default_params,
        "request_body_template": entity.request_body_template,
        "is_encryption": bool(entity.is_encryption),
        "encryption_config": entity.encryption_config,
        "expected_response": entity.expected_response,
        "timeout": entity.timeout,
        "retry_times": entity.retry_times,
        "is_deprecated": bool(entity.is_deprecated),
    }


@api_config_opt.route("/api/config", methods=["POST"])
def create_api_config():
    """
    新增接口地址
    入参：名称(name)、描述(description)、归属模块(module)、请求地址(api_path)、请求方式(method)、
    默认请求头(headers)、是否加密(is_encryption)、超时时间(timeout)、重试次数(retry_times)、
    请求体模板(request_body_template)、请求类型(request_type: file/json/form)
    """
    logger = current_app.logger or logging.getLogger(__name__)
    try:
        payload = _parse_payload()
        logger.info("【新增接口配置】入参=%s", payload)

        required = ["name", "module", "api_path", "method"]
        missing = [f for f in required if not payload.get(f)]
        if missing:
            return json_response({"code": 400, "msg": f"缺少必填字段: {','.join(missing)}", "data": None}, status=400)

        name = payload.get("name").strip()
        description = (payload.get("description") or "").strip()
        module = payload.get("module").strip()
        api_path = payload.get("api_path").strip()

        method = (payload.get("method") or "GET").strip().upper()
        allowed_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
        if method not in allowed_methods:
            return json_response({"code": 400, "msg": f"请求方式不支持: {method}", "data": None}, status=400)

        request_type = (payload.get("request_type") or "json").strip().lower()
        allowed_types = {"json", "form", "file"}
        if request_type not in allowed_types:
            return json_response({"code": 400, "msg": f"请求类型必须是 json/form/file，当前: {request_type}", "data": None}, status=400)

        headers = payload.get("headers")
        try:
            headers = _parse_headers(headers)
        except ValueError as ve:
            return json_response({"code": 400, "msg": str(ve), "data": None}, status=400)

        is_encryption = _parse_bool(payload.get("is_encryption", False))

        timeout = payload.get("timeout", 30)
        retry_times = payload.get("retry_times", 0)
        try:
            timeout = int(timeout)
            if timeout <= 0:
                raise ValueError
        except Exception:
            return json_response({"code": 400, "msg": "timeout 必须为正整数", "data": None}, status=400)
        try:
            retry_times = int(retry_times)
            if retry_times < 0:
                raise ValueError
        except Exception:
            return json_response({"code": 400, "msg": "retry_times 必须为非负整数", "data": None}, status=400)

        try:
            request_body_template = _parse_body_template(payload.get("request_body_template"))
        except ValueError as ve:
            return json_response({"code": 400, "msg": str(ve), "data": None}, status=400)

        # 支持可选 db_key，默认还是使用 default
        db_key = (payload.get("db_key") or request.args.get("db_key") or "default").strip()
        mapper = ApiConfigMapper(db_key=db_key)
        duplicate = mapper.get_by_unique(module, api_path, method)
        if duplicate:
            return json_response({"code": 400, "msg": "同模块+路径+方法的接口已存在", "data": _serialize(duplicate)}, status=400)

        entity = ApiConfig(
            name=name,
            description=description,
            module=module,
            api_path=api_path,
            method=method,
            request_type=request_type,
            headers=headers,
            default_params=payload.get("default_params"),
            request_body_template=request_body_template,
            is_encryption=is_encryption,
            timeout=timeout,
            retry_times=retry_times,
            is_deprecated=False,
        )

        saved = mapper.create(entity)
        logger.info("【新增接口配置】成功 id=%s", saved.id)
        return json_response({"code": 200, "msg": "新增成功", "data": _serialize(saved)}, status=200)

    except BadRequest as bad:
        return json_response({"code": 400, "msg": f"请求体不是合法JSON: {bad.description}", "data": None}, status=400)
    except Exception as e:
        logger.exception("【新增接口配置】服务器内部错误")
        return json_response({"code": 500, "msg": f"新增失败: {e}", "data": None}, status=500)


@api_config_opt.route("/api/config", methods=["GET"])
def list_api_configs():
    """
    查询接口配置
    支持查询参数或JSON：keyword(模糊name/描述/path)，module，method，request_type，include_deprecated
    """
    logger = current_app.logger or logging.getLogger(__name__)
    try:
        # 查询默认宽松解析；若 body 是非法 JSON，则按空对象处理，避免 400
        payload = _parse_payload(strict_json_error=False)
        # query string 优先
        keyword = request.args.get("keyword")
        module = request.args.get("module")
        method = request.args.get("method")
        request_type = request.args.get("request_type")
        include_deprecated = request.args.get("include_deprecated")

        # 如果 query 未提供，再从 body 取；确保字符串化再 strip
        if keyword is None:
            keyword = payload.get("keyword")
        if module is None:
            module = payload.get("module")
        if method is None and "method" in payload:
            mval = payload.get("method")
            method = str(mval) if mval is not None else None
        if request_type is None and "request_type" in payload:
            rtval = payload.get("request_type")
            request_type = str(rtval) if rtval is not None else None
        if include_deprecated is None:
            include_deprecated = payload.get("include_deprecated", "false")
        include_deprecated = _parse_bool(include_deprecated)

        if method:
            method = method.strip().upper()
        if request_type:
            request_type = request_type.strip().lower()

        # 支持通过 query/body 传入 db_key，默认 default
        db_key = (payload.get("db_key") or request.args.get("db_key") or "default").strip()
        mapper = ApiConfigMapper(db_key=db_key)
        rows = mapper.search_configs(
            keyword=keyword.strip() if keyword else None,
            module=module.strip() if module else None,
            method=method,
            request_type=request_type,
            include_deprecated=include_deprecated,
        )
        data = [_serialize(r) for r in rows]
        logger.info("【查询接口配置】返回 %s 条", len(data))
        return json_response({"code": 200, "msg": "查询成功", "data": data}, status=200)
    except Exception as e:
        logger.exception("【查询接口配置】服务器内部错误")
        return json_response({"code": 500, "msg": f"查询失败: {e}", "data": None}, status=500)


@api_config_opt.route("/api/config/<int:config_id>", methods=["PUT"])
def update_api_config(config_id: int):
    """
    更新接口配置（部分字段）
    """
    logger = current_app.logger or logging.getLogger(__name__)
    try:
        payload = _parse_payload()
        logger.info("【更新接口配置】id=%s 入参=%s", config_id, payload)

        update_data = {}

        if "name" in payload and payload.get("name"):
            update_data["name"] = payload.get("name").strip()
        if "description" in payload:
            update_data["description"] = (payload.get("description") or "").strip()
        if "module" in payload and payload.get("module"):
            update_data["module"] = payload.get("module").strip()
        if "api_path" in payload and payload.get("api_path"):
            update_data["api_path"] = payload.get("api_path").strip()
        if "method" in payload and payload.get("method"):
            method = payload.get("method").strip().upper()
            allowed_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
            if method not in allowed_methods:
                return json_response({"code": 400, "msg": f"请求方式不支持: {method}", "data": None}, status=400)
            update_data["method"] = method
        if "request_type" in payload:
            rt = (payload.get("request_type") or "").strip().lower()
            if rt:
                if rt not in {"json", "form", "file"}:
                    return json_response({"code": 400, "msg": f"请求类型必须是 json/form/file，当前: {rt}", "data": None}, status=400)
                update_data["request_type"] = rt
        if "headers" in payload:
            try:
                update_data["headers"] = _parse_headers(payload.get("headers"))
            except ValueError as ve:
                return json_response({"code": 400, "msg": str(ve), "data": None}, status=400)
        if "is_encryption" in payload:
            update_data["is_encryption"] = _parse_bool(payload.get("is_encryption"))
        if "timeout" in payload:
            try:
                t = int(payload.get("timeout"))
                if t <= 0:
                    raise ValueError
                update_data["timeout"] = t
            except Exception:
                return json_response({"code": 400, "msg": "timeout 必须为正整数", "data": None}, status=400)
        if "retry_times" in payload:
            try:
                r = int(payload.get("retry_times"))
                if r < 0:
                    raise ValueError
                update_data["retry_times"] = r
            except Exception:
                return json_response({"code": 400, "msg": "retry_times 必须为非负整数", "data": None}, status=400)
        if "request_body_template" in payload:
            try:
                update_data["request_body_template"] = _parse_body_template(payload.get("request_body_template"))
            except ValueError as ve:
                return json_response({"code": 400, "msg": str(ve), "data": None}, status=400)
        if "is_deprecated" in payload:
            update_data["is_deprecated"] = _parse_bool(payload.get("is_deprecated"))

        if not update_data:
            return json_response({"code": 400, "msg": "没有提供要更新的字段", "data": None}, status=400)

        db_key = (payload.get("db_key") or request.args.get("db_key") or "default").strip()
        mapper = ApiConfigMapper(db_key=db_key)
        updated = mapper.update(config_id, update_data)
        if not updated:
            return json_response({"code": 404, "msg": "接口配置不存在", "data": None}, status=404)

        logger.info("【更新接口配置】成功 id=%s", config_id)
        return json_response({"code": 200, "msg": "更新成功", "data": _serialize(updated)}, status=200)
    except Exception as e:
        logger.exception("【更新接口配置】服务器内部错误")
        return json_response({"code": 500, "msg": f"更新失败: {e}", "data": None}, status=500)


@api_config_opt.route("/api/config/<int:config_id>", methods=["DELETE"])
def delete_api_config(config_id: int):
    """硬删除接口配置"""
    logger = current_app.logger or logging.getLogger(__name__)
    try:
        db_key = (request.args.get("db_key") or "default").strip()
        mapper = ApiConfigMapper(db_key=db_key)
        success = mapper.delete(config_id)
        if not success:
            return json_response({"code": 404, "msg": "接口配置不存在", "data": None}, status=404)
        logger.info("【删除接口配置】硬删除成功 id=%s", config_id)
        return json_response({"code": 200, "msg": "删除成功（硬删除）", "data": {"id": config_id}}, status=200)
    except Exception as e:
        logger.exception("【删除接口配置】服务器内部错误")
        return json_response({"code": 500, "msg": f"删除失败: {e}", "data": None}, status=500)

