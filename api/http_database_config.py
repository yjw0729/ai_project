import logging
import json
from flask import Blueprint, request, jsonify, make_response, current_app
from common.datacase_function.contect_db import test_connection, get_connection_status
from werkzeug.exceptions import BadRequest, HTTPException

from common.db_mapper.database_config_mapper import DatabaseConfigMapper
from common.db_enitiy.database_config import DatabaseConfig

db_config_opt = Blueprint("db_config_opt", __name__)


def json_response(body, status=200):
    resp = make_response(jsonify(body), status)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp


def _parse_database_address(address: str):
    """解析形如 host:port 或 host 的地址"""
    if not address:
        return None, None
    parts = address.split(":")
    host = parts[0].strip()
    port = None
    if len(parts) > 1:
        try:
            port = int(parts[1])
        except ValueError:
            port = None
    return host, port


def _get_default_port(db_type: str) -> int:
    defaults = {
        "mysql": 3306,
        "postgresql": 5432,
        "oracle": 1521,
        "sqlserver": 1433,
        "mongodb": 27017,
    }
    return defaults.get((db_type or "").lower())


def _generate_config_name(env_type: str, db_type: str, database_name: str) -> str:
    parts = [env_type or "default", db_type or "db", database_name or ""]
    return "_".join(filter(None, parts))


@db_config_opt.route("/database/config", methods=["POST"])
def create_database_config():
    """
    新增数据库配置
    必填：env_type, db_type, database_address, database_name, username, password
    """
    try:
        logger = current_app.logger or logging.getLogger(__name__)
        payload = request.get_json(force=True, silent=False) or {}
        logger.info("【新增数据库配置】入参=%s", payload)

        required = ["env_type", "db_type", "database_address", "database_name", "username", "password"]
        missing = [f for f in required if not payload.get(f)]
        if missing:
            return json_response({"code": 400, "msg": f"缺少必填字段: {','.join(missing)}", "data": None}, status=400)

        env_type = (payload.get("env_type") or "").strip().lower()
        db_type = (payload.get("db_type") or "").strip().lower()
        database_address = payload.get("database_address").strip()
        database_name = payload.get("database_name").strip()
        username = payload.get("username").strip()
        password = payload.get("password").strip()
        description = (payload.get("description") or "").strip()
        active = str(payload.get("is_active", "true")).lower() not in ("0", "false", "no")
        pool_size = payload.get("pool_size")
        timeout = payload.get("timeout")

        # 处理池大小/超时默认值
        try:
            pool_size = int(pool_size) if pool_size is not None else 5
        except Exception:
            return json_response({"code": 400, "msg": "pool_size 必须为整数", "data": None}, status=400)

        try:
            timeout = int(timeout) if timeout is not None else 30
        except Exception:
            return json_response({"code": 400, "msg": "timeout 必须为整数", "data": None}, status=400)

        # 校验 env_type/db_type 枚举
        valid_env_types = {"dev", "test", "staging", "prod"}
        if env_type not in valid_env_types:
            return json_response({"code": 400, "msg": f"环境类型不合法，应为 {','.join(valid_env_types)}", "data": None}, status=400)

        valid_db_types = {"mysql", "postgresql", "oracle", "sqlserver", "mongodb"}
        if db_type not in valid_db_types:
            return json_response({"code": 400, "msg": f"数据库类型不合法，应为 {','.join(valid_db_types)}", "data": None}, status=400)

        host, port = _parse_database_address(database_address)
        if not host:
            return json_response({"code": 400, "msg": "数据库地址格式错误，应为 host 或 host:port"}, status=400)
        if port is None:
            port = _get_default_port(db_type)

        name = payload.get("name") or _generate_config_name(env_type, db_type, database_name)

        entity = DatabaseConfig(
            name=name,
            env_type=env_type,
            db_type=db_type,
            host=host,
            port=port,
            database_name=database_name,
            username=username,
            password=password,
            description=description,
            is_active=active,
            pool_size=pool_size,
            timeout=timeout,
        )

        mapper = DatabaseConfigMapper()
        existing = mapper.get_by_name_and_env(name, env_type)
        if existing:
            return json_response({"code": 400, "msg": f"配置已存在: {name}", "data": None}, status=400)

        try:
            saved = mapper.create(entity)
        except Exception as e:
            # 处理唯一约束等数据库错误
            err_msg = str(e)
            if "1062" in err_msg or "Duplicate entry" in err_msg or "unique" in err_msg.lower():
                return json_response({"code": 400, "msg": f"配置重复: {name}", "data": None}, status=400)
            raise

        logger.info("【新增数据库配置】成功 id=%s name=%s", saved.id, saved.name)
        return json_response({"code": 200, "msg": "创建成功", "data": saved.to_dict()}, status=200)

    except BadRequest as bad_req:
        return json_response({"code": 400, "msg": f"请求体不是合法JSON: {bad_req.description}", "data": None}, status=400)
    except ValueError as ve:
        return json_response({"code": 400, "msg": str(ve), "data": None}, status=400)
    except Exception as e:
        logger = current_app.logger or logging.getLogger(__name__)
        logger.exception("【新增数据库配置】服务器内部错误")
        return json_response({"code": 500, "msg": f"server error: {e}", "data": None}, status=500)


@db_config_opt.route("/database/config", methods=["GET"])
def query_database_config():
    """
    查询数据库配置
    支持参数：
    - env_type: 环境类型（精确，可选）
    - db_type: 数据库类型（精确，可选）
    - name: 配置名称（精确，可选）
    - keyword: 模糊查询（名称、描述、host、库名、用户名、密码，可选）
    - active_only: 是否仅查询启用的，默认true；传false查询全部
    """
    try:
        logger = current_app.logger or logging.getLogger(__name__)
        # 同时支持 query 参数、form、JSON body；优先非空值（去空格后）
        payload = request.get_json(silent=True) or request.get_json(force=True, silent=True) or {}

        def pick(key: str):
            val_arg = request.args.get(key, None)
            val_form = request.form.get(key, None)
            val_body = payload.get(key, None)
            for v in (val_arg, val_form, val_body):
                if v is not None and str(v).strip() != "":
                    return v
            return None

        env_type_raw = pick("env_type")
        db_type_raw = pick("db_type")
        name_raw = pick("name")
        keyword = pick("keyword")
        active_only_raw = request.args.get("active_only", None)
        if active_only_raw is None:
            active_only_raw = payload.get("active_only", None)

        # active_only 规则：
        # - None: 默认 True（仅激活）
        # - 空串: 不筛选激活状态
        # - 其他: "false"/"0"/"no" 视为 False，否则 True
        if active_only_raw is None:
            active_only = True
        elif str(active_only_raw).strip() == "":
            active_only = None  # 不过滤
        else:
            active_only = str(active_only_raw).lower() not in ("false", "0", "no")

        # 规范化并校验枚举；传入非法值则直接返回空结果
        env_type = (env_type_raw or "").strip().lower()
        db_type = (db_type_raw or "").strip().lower()
        name = (name_raw or "").strip()
        valid_env_types = {"dev", "test", "staging", "prod"}
        valid_db_types = {"mysql", "postgresql", "oracle", "sqlserver", "mongodb"}

        logger.info("【查询数据库配置】env_type=%s, db_type=%s, name=%s, keyword=%s, active_only=%s",
                    env_type_raw, db_type_raw, name_raw, keyword, active_only)

        if env_type and env_type not in valid_env_types:
            logger.info("【查询数据库配置】env_type 非法(%s)，返回空结果", env_type_raw)
            return json_response({"code": 200, "msg": "查询成功", "data": []}, status=200)

        if db_type and db_type not in valid_db_types:
            logger.info("【查询数据库配置】db_type 非法(%s)，返回空结果", db_type_raw)
            return json_response({"code": 200, "msg": "查询成功", "data": []}, status=200)

        mapper = DatabaseConfigMapper()
        # 直接精确过滤 env_type / db_type（若传入），为空则不限制，默认按激活状态过滤
        results = mapper.search_configs(
            keyword=keyword,
            env_type=env_type if env_type else None,
            db_type=db_type if db_type else None,
            name=name if name else None,
            active_only=active_only
        )
        data = [r.to_dict() for r in results]
        logger.info("【查询数据库配置】返回 %d 条记录", len(data))
        return json_response({"code": 200, "msg": "查询成功", "data": data}, status=200)

    except Exception as e:
        logger = current_app.logger or logging.getLogger(__name__)
        logger.exception("【查询数据库配置】服务器内部错误")
        return json_response({"code": 500, "msg": f"查询失败: {e}", "data": None}, status=500)


@db_config_opt.route("/database/config/<int:config_id>", methods=["PUT"])
def update_database_config(config_id: int):
    """
    编辑数据库配置，支持部分字段更新：
    - database_address, database_name, username, password, description, is_active
    """
    try:
        logger = current_app.logger or logging.getLogger(__name__)
        payload = request.get_json(force=True, silent=False) or {}
        logger.info("【更新数据库配置】id=%d, 入参=%s", config_id, payload)

        update_data = {}
        if "database_address" in payload:
            host, port = _parse_database_address(payload.get("database_address", ""))
            if not host:
                return json_response({"code": 400, "msg": "数据库地址格式错误，应为 host 或 host:port"}, status=400)
            update_data["host"] = host
            if port is None:
                port = _get_default_port(payload.get("db_type"))
            update_data["port"] = port

        for field in ["database_name", "username", "password", "description"]:
            if field in payload:
                val = payload.get(field)
                update_data[field] = val

        if "is_active" in payload:
            update_data["is_active"] = bool(payload.get("is_active"))

        if "db_type" in payload:
            update_data["db_type"] = payload.get("db_type")

        if "env_type" in payload:
            update_data["env_type"] = payload.get("env_type")

        if not update_data:
            return json_response({"code": 400, "msg": "没有提供要更新的字段", "data": None}, status=400)

        mapper = DatabaseConfigMapper()
        updated = mapper.update(config_id, update_data)
        if not updated:
            return json_response({"code": 404, "msg": "数据库配置不存在", "data": None}, status=404)

        logger.info("【更新数据库配置】成功 id=%d", config_id)
        return json_response({"code": 200, "msg": "更新成功", "data": updated.to_dict()}, status=200)

    except BadRequest as bad_req:
        return json_response({"code": 400, "msg": f"请求体不是合法JSON: {bad_req.description}", "data": None}, status=400)
    except ValueError as ve:
        return json_response({"code": 400, "msg": str(ve), "data": None}, status=400)
    except Exception as e:
        logger = current_app.logger or logging.getLogger(__name__)
        logger.exception("【更新数据库配置】服务器内部错误")
        return json_response({"code": 500, "msg": f"更新失败: {e}", "data": None}, status=500)


@db_config_opt.route("/database/config/<int:config_id>", methods=["DELETE"])
def delete_database_config(config_id: int):
    """
    删除数据库配置（硬删除），只需路径参数 id
    """
    try:
        logger = current_app.logger or logging.getLogger(__name__)
        mapper = DatabaseConfigMapper()

        success = mapper.delete(config_id, soft_delete=False)
        if not success:
            return json_response({"code": 404, "msg": "数据库配置不存在", "data": None}, status=404)

        logger.info("【删除数据库配置】硬删除成功 id=%d", config_id)
        return json_response({"code": 200, "msg": "删除成功（硬删除）", "data": {"id": config_id, "delete_type": "硬删除"}}, status=200)

    except Exception as e:
        logger = current_app.logger or logging.getLogger(__name__)
        logger.exception("【删除数据库配置】服务器内部错误")
        return json_response({"code": 500, "msg": f"删除失败: {e}", "data": None}, status=500)


@db_config_opt.route("/database/connection/status", methods=["GET"])
def get_database_connection_status():
    """
    获取数据库连接状态
    支持参数：
    - db_key: 数据库配置键名，默认 "default"
    """
    try:
        logger = current_app.logger or logging.getLogger(__name__)

        # 获取参数
        db_key = request.args.get("db_key", "default")

        logger.info("【数据库连接状态】检查 db_key=%s", db_key)

        # 获取连接状态
        status = get_connection_status(db_key)

        # 测试连接
        connection_ok = test_connection(db_key)

        result = {
            "db_key": db_key,
            "connection_status": "正常" if connection_ok else "异常",
            "pool_info": {
                "pool_size": status.get("pool_size", 0),
                "checked_out": status.get("checked_out", 0),
                "checked_in": status.get("checked_in", 0),
                "invalid_count": status.get("invalid", 0)
            },
            "last_test_time": status.get("timestamp", None),
            "error_message": None if connection_ok else status.get("error", "未知错误")
        }

        logger.info("【数据库连接状态】db_key=%s, status=%s, pool=%s/%s",
                   db_key, result["connection_status"],
                   result["pool_info"]["checked_out"], result["pool_info"]["pool_size"])

        return json_response({
            "code": 200,
            "msg": "查询成功",
            "data": result
        }, status=200)

    except Exception as e:
        logger = current_app.logger or logging.getLogger(__name__)
        logger.exception("【数据库连接状态】服务器内部错误")
        return json_response({"code": 500, "msg": f"查询失败: {e}", "data": None}, status=500)


@db_config_opt.route("/database/connection/test", methods=["POST"])
def test_database_connection():
    """
    测试数据库连接
    请求体JSON：
    {
        "db_key": "default",  // 可选，默认 "default"
        "host": "localhost",   // 可选，用于临时测试
        "port": 3306,         // 可选
        "database_name": "test", // 可选
        "username": "root",   // 可选
        "password": "password" // 可选
    }
    """
    try:
        logger = current_app.logger or logging.getLogger(__name__)
        payload = request.get_json(force=True, silent=False) or {}

        db_key = payload.get("db_key", "default")

        # 如果提供了连接参数，则进行临时连接测试
        if any(key in payload for key in ["host", "port", "database_name", "username", "password"]):
            # 临时连接测试
            from sqlalchemy import create_engine
            from urllib.parse import quote_plus

            host = payload.get("host", "localhost")
            port = payload.get("port", 3306)
            database_name = payload.get("database_name", "")
            username = payload.get("username", "")
            password = payload.get("password", "")

            connection_string = f"mysql+pymysql://{username}:{quote_plus(password)}@{host}:{port}/{database_name}"

            try:
                engine = create_engine(connection_string, connect_args={'connect_timeout': 5})
                with engine.connect() as conn:
                    result = conn.execute("SELECT 1 as test")
                    row = result.fetchone()
                    success = row is not None and row[0] == 1

                return json_response({
                    "code": 200,
                    "msg": "连接测试成功" if success else "连接测试失败",
                    "data": {
                        "connection_success": success,
                        "host": host,
                        "port": port,
                        "database": database_name
                    }
                }, status=200)

            except Exception as e:
                logger.error("【数据库连接测试】临时连接失败: %s", e)
                return json_response({
                    "code": 200,
                    "msg": "连接测试失败",
                    "data": {
                        "connection_success": False,
                        "error": str(e),
                        "host": host,
                        "port": port,
                        "database": database_name
                    }
                }, status=200)

        else:
            # 测试配置的数据库连接
            connection_ok = test_connection(db_key)

            return json_response({
                "code": 200,
                "msg": "连接测试完成",
                "data": {
                    "db_key": db_key,
                    "connection_success": connection_ok
                }
            }, status=200)

    except BadRequest as bad_req:
        return json_response({"code": 400, "msg": f"请求体不是合法JSON: {bad_req.description}", "data": None}, status=400)
    except Exception as e:
        logger = current_app.logger or logging.getLogger(__name__)
        logger.exception("【数据库连接测试】服务器内部错误")
        return json_response({"code": 500, "msg": f"测试失败: {e}", "data": None}, status=500)

