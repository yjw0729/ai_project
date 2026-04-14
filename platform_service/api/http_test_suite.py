# platform_service/api/http_test_suite.py
"""测试套件 API 接口"""

import logging
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from flask import Blueprint, request, jsonify, make_response

logger = logging.getLogger(__name__)

# 创建 Blueprint
test_suite_bp = Blueprint("test_suite", __name__, url_prefix="/api/test-suite")


def _json_response(body: Dict[str, Any], status: int = 200):
    """构建 JSON 响应"""
    resp = make_response(jsonify(body), status)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


def _get_user_id(req) -> str:
    """获取当前用户ID"""
    return req.headers.get("X-User-ID", "anonymous")


# ==================== TestSuite CRUD 接口 ====================

@test_suite_bp.route("", methods=["POST"])
def create_test_suite():
    """
    创建测试套件

    请求体:
    {
        "name": "支付流程测试",
        "description": "支付模块完整流程测试",
        "suite_type": "smoke|regression|function|performance|custom",
        "module": "支付中心",
        "tags": ["支付", "核心"],
        "case_default_config": {
            "default_headers": {"X-Env": "test"},
            "default_timeout": 60
        }
    }

    响应:
    {
        "code": 200,
        "message": "success",
        "data": { ... }
    }
    """
    try:
        payload = request.get_json(silent=True) or {}

        # 验证必填字段
        if not payload.get("name"):
            return _json_response({"code": 400, "message": "套件名称不能为空", "data": None}, 400)

        from common.db_enitiy.test_suite import TestSuite
        from common.db_mapper.test_suite_mapper import TestSuiteMapper

        mapper = TestSuiteMapper()

        # 检查名称唯一性
        existing = mapper.get_by_name(payload["name"])
        if existing:
            return _json_response({"code": 400, "message": f"套件名称已存在: {payload['name']}", "data": None}, 400)

        # 创建实体
        suite = TestSuite(
            name=payload["name"],
            description=payload.get("description"),
            suite_type=payload.get("suite_type", "custom"),
            module=payload.get("module"),
            tags=payload.get("tags"),
            config=payload.get("config"),
            case_default_config=payload.get("case_default_config"),
            creator=_get_user_id(request),
            status="active",
            last_execution_status="not_run",
            total_executions=0,
            success_rate=0.00
        )

        # 应用默认配置
        suite.apply_default_config()

        # 保存
        created = mapper.create(suite)

        logger.info(f"[TestSuite] 创建测试套件: id={created.id}, name={created.name}")

        return _json_response({
            "code": 200,
            "message": "创建成功",
            "data": {
                "id": created.id,
                "name": created.name,
                "suite_type": created.suite_type,
                "module": created.module,
                "status": created.status,
                "creator": created.creator,
                "created_time": created.created_time.isoformat() if created.created_time else None
            }
        })

    except ValueError as e:
        return _json_response({"code": 400, "message": str(e), "data": None}, 400)
    except Exception as e:
        logger.exception("[TestSuite] 创建测试套件失败")
        return _json_response({"code": 500, "message": f"创建失败: {str(e)}", "data": None}, 500)


@test_suite_bp.route("/<int:suite_id>", methods=["GET"])
def get_test_suite(suite_id: int):
    """
    获取测试套件详情

    响应:
    {
        "code": 200,
        "data": {
            "id": 1,
            "name": "支付流程测试",
            "description": "...",
            "suite_type": "smoke",
            "module": "支付中心",
            "tags": [...],
            "case_default_config": {...},
            "last_execution_status": "passed",
            "last_execution_time": "2026-04-13T10:00:00",
            "total_executions": 10,
            "success_rate": 85.5,
            "cases": [
                {
                    "id": 1,
                    "case_id": "TEST_CASE_000001",
                    "case_name": "用户登录",
                    "execution_order": 1,
                    "enabled": true,
                    "has_custom_config": false,
                    "custom_config_summary": [],
                    "url": null,
                    "request_headers": null,
                    ...
                }
            ]
        }
    }
    """
    try:
        from common.db_mapper.test_suite_mapper import TestSuiteMapper
        from common.db_mapper.test_suite_case_mapper import TestSuiteCaseMapper
        from common.db_mapper.test_case_mapper import TestCaseMapper

        suite_mapper = TestSuiteMapper()
        suite_case_mapper = TestSuiteCaseMapper()
        case_mapper = TestCaseMapper()

        # 获取套件
        suite = suite_mapper.get_by_id(suite_id)
        if not suite:
            return _json_response({"code": 404, "message": "测试套件不存在", "data": None}, 404)

        # 获取套件下的用例
        suite_cases = suite_case_mapper.get_cases_by_suite(suite_id, enabled_only=False, order_by_execution=True)

        # 构作用例列表
        cases_data = []
        for sc in suite_cases:
            case = case_mapper.get_by_id(sc.case_id)
            if case:
                cases_data.append({
                    "id": sc.id,
                    "case_id": case.id,
                    "case_id_str": getattr(case, "case_id", None),
                    "case_name": case.name,
                    "module": case.module,
                    "priority": getattr(case, "priority", "P2"),
                    "execution_order": sc.execution_order,
                    "enabled": sc.enabled,
                    "has_custom_config": sc.has_custom_config(),
                    "custom_config_summary": sc.get_custom_config_summary(),
                    "url": sc.url,
                    "request_headers": sc.request_headers,
                    "request_params": sc.request_params,
                    "request_body": sc.request_body,
                    "timeout": sc.timeout,
                    "assertions": sc.assertions,
                    "preconditions": sc.preconditions,
                    "test_steps": sc.test_steps,
                    "test_data": sc.test_data
                })

        return _json_response({
            "code": 200,
            "message": "success",
            "data": {
                "id": suite.id,
                "name": suite.name,
                "description": suite.description,
                "suite_type": suite.suite_type,
                "module": suite.module,
                "tags": suite.get_tags() if callable(suite.get_tags) else suite.tags,
                "config": suite.config,
                "case_default_config": suite.case_default_config,
                "last_execution_status": suite.last_execution_status,
                "last_execution_time": suite.last_execution_time.isoformat() if suite.last_execution_time else None,
                "last_execution_id": suite.last_execution_id,
                "total_executions": suite.total_executions or 0,
                "success_rate": float(suite.success_rate or 0),
                "status": suite.status,
                "creator": suite.creator,
                "created_time": suite.created_time.isoformat() if suite.created_time else None,
                "updated_time": suite.updated_time.isoformat() if suite.updated_time else None,
                "case_count": len(cases_data),
                "enabled_case_count": len([c for c in cases_data if c["enabled"]]),
                "cases": cases_data
            }
        })

    except Exception as e:
        logger.exception("[TestSuite] 获取测试套件详情失败")
        return _json_response({"code": 500, "message": f"获取失败: {str(e)}", "data": None}, 500)


@test_suite_bp.route("/<int:suite_id>", methods=["PUT"])
def update_test_suite(suite_id: int):
    """
    更新测试套件

    请求体:
    {
        "name": "新的套件名称",
        "description": "新的描述",
        "suite_type": "regression",
        "module": "新的模块",
        "tags": ["新标签"],
        "case_default_config": {...},
        "status": "active|inactive"
    }
    """
    try:
        payload = request.get_json(silent=True) or {}

        from common.db_mapper.test_suite_mapper import TestSuiteMapper

        mapper = TestSuiteMapper()

        # 检查套件是否存在
        existing = mapper.get_by_id(suite_id)
        if not existing:
            return _json_response({"code": 404, "message": "测试套件不存在", "data": None}, 404)

        # 检查名称唯一性（如果修改了名称）
        if "name" in payload and payload["name"] != existing.name:
            name_conflict = mapper.get_by_name(payload["name"])
            if name_conflict and name_conflict.id != suite_id:
                return _json_response({"code": 400, "message": f"套件名称已存在: {payload['name']}", "data": None}, 400)

        # 构建更新数据
        update_data = {}
        for key in ["name", "description", "suite_type", "module", "tags", "config",
                    "case_default_config", "status"]:
            if key in payload:
                update_data[key] = payload[key]

        if not update_data:
            return _json_response({"code": 400, "message": "没有需要更新的字段", "data": None}, 400)

        # 执行更新
        updated = mapper.update(suite_id, update_data)

        logger.info(f"[TestSuite] 更新测试套件: id={suite_id}")

        return _json_response({
            "code": 200,
            "message": "更新成功",
            "data": {
                "id": updated.id,
                "name": updated.name,
                "suite_type": updated.suite_type,
                "module": updated.module,
                "status": updated.status,
                "updated_time": updated.updated_time.isoformat() if updated.updated_time else None
            }
        })

    except ValueError as e:
        return _json_response({"code": 400, "message": str(e), "data": None}, 400)
    except Exception as e:
        logger.exception("[TestSuite] 更新测试套件失败")
        return _json_response({"code": 500, "message": f"更新失败: {str(e)}", "data": None}, 500)


@test_suite_bp.route("/<int:suite_id>", methods=["DELETE"])
def delete_test_suite(suite_id: int):
    """
    删除测试套件（硬删除，级联删除关联的 test_suite_case）
    """
    try:
        from common.db_mapper.test_suite_mapper import TestSuiteMapper

        mapper = TestSuiteMapper()

        # 检查套件是否存在
        existing = mapper.get_by_id(suite_id)
        if not existing:
            return _json_response({"code": 404, "message": "测试套件不存在", "data": None}, 404)

        # 执行硬删除（外键设置了 CASCADE，会自动删除关联记录）
        mapper.delete(suite_id, soft_delete=False)

        logger.info(f"[TestSuite] 删除测试套件: id={suite_id}, name={existing.name}")

        return _json_response({
            "code": 200,
            "message": "删除成功",
            "data": {"id": suite_id}
        })

    except Exception as e:
        logger.exception("[TestSuite] 删除测试套件失败")
        return _json_response({"code": 500, "message": f"删除失败: {str(e)}", "data": None}, 500)


@test_suite_bp.route("/list", methods=["GET"])
def list_test_suites():
    """
    获取测试套件列表

    查询参数:
    - suite_type: 按类型过滤
    - module: 按模块过滤
    - status: 按状态过滤 (active/inactive)
    - keyword: 关键词搜索
    - page: 页码（默认1）
    - page_size: 每页数量（默认20）

    响应:
    {
        "code": 200,
        "data": {
            "items": [...],
            "total": 100,
            "page": 1,
            "page_size": 20
        }
    }
    """
    try:
        from common.db_mapper.test_suite_mapper import TestSuiteMapper

        # 解析参数
        suite_type = request.args.get("suite_type")
        module = request.args.get("module")
        status = request.args.get("status", "active")
        keyword = request.args.get("keyword")
        try:
            page = int(request.args.get("page", 1))
            page_size = int(request.args.get("page_size", 20))
        except ValueError:
            page, page_size = 1, 20

        mapper = TestSuiteMapper()

        # 获取列表
        if keyword or suite_type or module:
            suites = mapper.search_suites(
                keyword=keyword,
                suite_type=suite_type,
                module=module,
                active_only=(status == "active")
            )
        else:
            suites = mapper.get_all(active_only=(status == "active"))

        # 分页
        total = len(suites)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = suites[start:end]

        # 构作用户数据
        items = []
        for s in paginated:
            items.append({
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "suite_type": s.suite_type,
                "module": s.module,
                "tags": s.get_tags() if callable(s.get_tags) else s.tags,
                "last_execution_status": s.last_execution_status,
                "last_execution_time": s.last_execution_time.isoformat() if s.last_execution_time else None,
                "total_executions": s.total_executions or 0,
                "success_rate": float(s.success_rate or 0),
                "status": s.status,
                "creator": s.creator,
                "created_time": s.created_time.isoformat() if s.created_time else None
            })

        return _json_response({
            "code": 200,
            "message": "success",
            "data": {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size
            }
        })

    except Exception as e:
        logger.exception("[TestSuite] 获取测试套件列表失败")
        return _json_response({"code": 500, "message": f"获取失败: {str(e)}", "data": None}, 500)
