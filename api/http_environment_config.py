import logging
import json
from flask import Blueprint, request, jsonify, make_response, current_app
from werkzeug.exceptions import BadRequest, HTTPException

from common.db_mapper.environment_config_mapper import EnvironmentConfigMapper
from common.db_enitiy.environment_config import EnvironmentConfig

env_config_opt = Blueprint("env_config_opt", __name__)


def json_response(body, status=200):
    resp = make_response(jsonify(body), status)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    # 禁用缓存，确保前端总能获取最新数据
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@env_config_opt.route("/environment/config", methods=["POST"])
def create_environment_config():
    """
    新增环境配置
    必填：name, base_url
    可选：description, headers, timeout, is_encryption, env_type
    """
    try:
        logger = current_app.logger or logging.getLogger(__name__)
        # 支持 JSON、表单、x-www-form-urlencoded，多数情况下不校验 token
        payload = request.get_json(silent=True)
        if payload is None:
            payload = request.get_json(force=True, silent=True)
        if payload is None:
            try:
                # 尝试解析原始 body 为 JSON
                if request.data:
                    payload = json.loads(request.data.decode("utf-8"))
                else:
                    payload = {}
            except Exception:
                payload = {}
        if not isinstance(payload, dict):
            payload = {}

        # 兼容表单
        try:
            form_data = request.form.to_dict(flat=True)
            # 仅在未提供同名字段时填充
            for k, v in form_data.items():
                payload.setdefault(k, v)
        except Exception:
            pass
        logger.info("【新增环境配置】入参=%s", payload)

        required = ["name", "base_url"]
        missing = [f for f in required if not payload.get(f)]
        if missing:
            return json_response({"code": 400, "msg": f"缺少必填字段: {','.join(missing)}", "data": None}, status=400)

        name = payload.get("name").strip()
        base_url = payload.get("base_url").strip()
        if not (base_url.startswith("http://") or base_url.startswith("https://")):
            return json_response({"code": 400, "msg": "环境地址必须以http://或https://开头", "data": None}, status=400)
        base_url = base_url.rstrip("/")

        description = (payload.get("description") or "").strip()
        headers = payload.get("headers") or {}
        if isinstance(headers, str):
            # 容错：支持 "k:v,k2:v2" 或 "{Content-type:application/json}" 这类未加引号形式
            hdr_text = headers.strip().lstrip("{").rstrip("}")
            if ":" in hdr_text and '"' not in hdr_text:
                try:
                    pairs = [p for p in hdr_text.split(",") if p.strip()]
                    headers = {}
                    for p in pairs:
                        if ":" not in p:
                            continue
                        k, v = p.split(":", 1)
                        headers[k.strip()] = v.strip()
                except Exception:
                    headers = headers  # fallback to original string, will fail below
            if isinstance(headers, str):
                try:
                    headers = json.loads(headers)
                except json.JSONDecodeError:
                    return json_response({"code": 400, "msg": "headers 必须是 JSON 对象，示例: {\"Content-Type\":\"application/json\"}", "data": None}, status=400)
        elif headers is None:
            headers = {}

        timeout = payload.get("timeout", 30)
        try:
            timeout = int(timeout)
            if timeout <= 0:
                raise ValueError
        except Exception:
            return json_response({"code": 400, "msg": "timeout 必须为正整数", "data": None}, status=400)

        is_encryption = payload.get("is_encryption", False)
        if isinstance(is_encryption, str):
            is_encryption = is_encryption.lower() in ("true", "1", "yes", "on")
        else:
            is_encryption = bool(is_encryption)

        env_type = (payload.get("env_type") or "").strip().lower() or "dev"

        mapper = EnvironmentConfigMapper()

        # 允许环境名称重复，不再做唯一性校验

        entity = EnvironmentConfig(
            name=name,
            base_url=base_url,
            description=description,
            headers=headers,
            timeout=timeout,
            is_encryption=is_encryption,
            env_type=env_type,
            is_active=True,
        )
        try:
            saved = mapper.create(entity)
        except Exception as e:
            # 处理唯一约束等数据库错误（如 uk_env_name）
            err_msg = str(e)
            if "1062" in err_msg or "Duplicate entry" in err_msg or "uk_env_name" in err_msg:
                return json_response({"code": 400, "msg": f"环境名称已存在: {name}", "data": None}, status=400)
            raise

        logger.info("【新增环境配置】成功 id=%s name=%s", getattr(saved, "id", None), getattr(saved, "name", None))
        return json_response({"code": 200, "msg": "创建成功", "data": saved.to_json()}, status=200)

    except BadRequest as bad_req:
        return json_response({"code": 400, "msg": f"请求体不是合法JSON: {bad_req.description}", "data": None}, status=400)
    except ValueError as ve:
        return json_response({"code": 400, "msg": str(ve), "data": None}, status=400)
    except Exception as e:
        logger = current_app.logger or logging.getLogger(__name__)
        logger.exception("【新增环境配置】服务器内部错误")
        return json_response({"code": 500, "msg": f"server error: {e}", "data": None}, status=500)


@env_config_opt.route("/environment/config", methods=["GET"])
def query_environment_config():
    """
    查询环境配置
    支持参数：
    - name: 环境名称（精确）
    - base_url: 环境地址（模糊）
    - env_type: 环境类型
    - active_only: 是否仅查询启用的
    """
    try:
        logger = current_app.logger or logging.getLogger(__name__)

        # 同时支持 query 参数、form、JSON body；优先非空值
        payload = request.get_json(silent=True) or {}

        def pick(key: str):
            val_arg = request.args.get(key, None)
            val_form = request.form.get(key, None)
            val_body = payload.get(key, None)
            for v in (val_arg, val_form, val_body):
                if v is not None and str(v).strip() != "":
                    return v
            return None

        name = pick("name")
        base_url = pick("base_url")
        env_type_raw = pick("env_type")
        active_only_raw = request.args.get("active_only", None)
        if active_only_raw is None:
            active_only_raw = payload.get("active_only", None)

        # active_only 解析：默认 true；空串表示不限制；false/0/no 为 False
        if active_only_raw is None:
            active_only = True
        elif str(active_only_raw).strip() == "":
            active_only = None
        else:
            active_only = str(active_only_raw).lower() not in ("false", "0", "no")

        env_type = (env_type_raw or "").strip().lower() if env_type_raw else None

        mapper = EnvironmentConfigMapper()
        results = []
        if name:
            env = mapper.get_by_name(name)
            if env and (not env_type or str(env.env_type) == env_type):
                results = [env]
        elif base_url:
            results = mapper.get_by_base_url_pattern(base_url, active_only=(active_only is not False))
        else:
            results = mapper.get_all(active_only=(active_only is not False))

        if env_type:
            results = [r for r in results if str(r.env_type) == env_type]

        data = [r.to_json() for r in results]
        logger.info("【查询环境配置】返回 %d 条记录", len(data))
        return json_response({"code": 200, "msg": "查询成功", "data": data}, status=200)

    except Exception as e:
        logger = current_app.logger or logging.getLogger(__name__)
        logger.exception("【查询环境配置】服务器内部错误")
        return json_response({"code": 500, "msg": f"查询失败: {e}", "data": None}, status=500)


@env_config_opt.route("/environment/config/<int:config_id>", methods=["PUT"])
def update_environment_config(config_id: int):
    """
    编辑环境配置，支持部分字段更新：
    name, base_url, description, headers, timeout, is_encryption, env_type
    """
    try:
        logger = current_app.logger or logging.getLogger(__name__)
        payload = request.get_json(force=True, silent=False) or {}
        logger.info("【更新环境配置】id=%d 入参=%s", config_id, payload)

        mapper = EnvironmentConfigMapper()
        existing = mapper.get_by_id(config_id)
        if not existing:
            return json_response({"code": 404, "msg": "环境配置不存在", "data": None}, status=404)

        update_data = {}

        if "name" in payload:
            name = (payload.get("name") or "").strip()
            if name:
                conflict = mapper.get_by_name(name)
                if conflict and conflict.id != config_id:
                    return json_response({"code": 400, "msg": f"环境名称已存在: {name}", "data": None}, status=400)
                update_data["name"] = name

        if "base_url" in payload:
            base_url = (payload.get("base_url") or "").strip()
            if base_url:
                if not (base_url.startswith("http://") or base_url.startswith("https://")):
                    return json_response({"code": 400, "msg": "环境地址必须以http://或https://开头", "data": None}, status=400)
                update_data["base_url"] = base_url.rstrip("/")

        if "description" in payload:
            update_data["description"] = (payload.get("description") or "").strip()

        if "headers" in payload:
            headers = payload.get("headers")
            if isinstance(headers, str):
                hdr_text = headers.strip().lstrip("{").rstrip("}")
                if ":" in hdr_text and '"' not in hdr_text:
                    try:
                        pairs = [p for p in hdr_text.split(",") if p.strip()]
                        headers = {}
                        for p in pairs:
                            if ":" not in p:
                                continue
                            k, v = p.split(":", 1)
                            headers[k.strip()] = v.strip()
                    except Exception:
                        headers = headers
                if isinstance(headers, str):
                    try:
                        headers = json.loads(headers)
                    except json.JSONDecodeError:
                        return json_response({"code": 400, "msg": "headers 必须是 JSON 对象，示例: {\"Content-Type\":\"application/json\"}", "data": None}, status=400)
            if headers is not None:
                if not isinstance(headers, dict):
                    return json_response({"code": 400, "msg": "headers 必须是 JSON 对象", "data": None}, status=400)
                update_data["headers"] = headers

        if "timeout" in payload:
            timeout = payload.get("timeout")
            try:
                timeout = int(timeout)
                if timeout <= 0:
                    raise ValueError
                update_data["timeout"] = timeout
            except Exception:
                return json_response({"code": 400, "msg": "timeout 必须为正整数", "data": None}, status=400)

        if "is_encryption" in payload:
            is_encryption = payload.get("is_encryption")
            if isinstance(is_encryption, str):
                is_encryption = is_encryption.lower() in ("true", "1", "yes", "on")
            else:
                is_encryption = bool(is_encryption)
            update_data["is_encryption"] = is_encryption

        if "env_type" in payload:
            env_type = (payload.get("env_type") or "").strip().lower()
            if env_type:
                update_data["env_type"] = env_type

        if not update_data:
            return json_response({"code": 400, "msg": "没有提供要更新的字段", "data": None}, status=400)

        updated = mapper.update(config_id, update_data)
        if not updated:
            return json_response({"code": 404, "msg": "环境配置不存在", "data": None}, status=404)

        logger.info("【更新环境配置】成功 id=%d", config_id)
        return json_response({"code": 200, "msg": "更新成功", "data": updated.to_json()}, status=200)

    except BadRequest as bad_req:
        return json_response({"code": 400, "msg": f"请求体不是合法JSON: {bad_req.description}", "data": None}, status=400)
    except ValueError as ve:
        return json_response({"code": 400, "msg": str(ve), "data": None}, status=400)
    except Exception as e:
        logger = current_app.logger or logging.getLogger(__name__)
        logger.exception("【更新环境配置】服务器内部错误")
        return json_response({"code": 500, "msg": f"更新失败: {e}", "data": None}, status=500)


@env_config_opt.route("/environment/config/<int:config_id>", methods=["DELETE"])
def delete_environment_config(config_id: int):
    """
    删除环境配置（硬删除），只需路径参数 id
    """
    try:
        logger = current_app.logger or logging.getLogger(__name__)
        mapper = EnvironmentConfigMapper()

        success = mapper.delete(config_id, soft_delete=False)
        if not success:
            return json_response({"code": 404, "msg": "环境配置不存在", "data": None}, status=404)

        logger.info("【删除环境配置】硬删除成功 id=%d", config_id)
        return json_response({"code": 200, "msg": "删除成功（硬删除）", "data": {"id": config_id, "delete_type": "硬删除"}}, status=200)

    except Exception as e:
        logger = current_app.logger or logging.getLogger(__name__)
        logger.exception("【删除环境配置】服务器内部错误")
        return json_response({"code": 500, "msg": f"删除失败: {e}", "data": None}, status=500)

