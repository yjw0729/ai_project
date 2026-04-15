# platform_service/api/http_test_suite_case.py
"""测试套件-用例关联 API 接口"""

import logging
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from flask import Blueprint, request, jsonify, make_response

logger = logging.getLogger(__name__)

# 创建 Blueprint
test_suite_case_bp = Blueprint("test_suite_case", __name__, url_prefix="/api/test-suite")


def _json_response(body: Dict[str, Any], status: int = 200):
    """构建 JSON 响应，确保中文不被转义"""
    resp = make_response(json.dumps(body, ensure_ascii=False, default=_json_default), status)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


def _json_default(obj):
    """处理 datetime 等对象为 ISO 格式字符串"""
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


# ==================== TestSuiteCase 用例管理接口 ====================

@test_suite_case_bp.route("/<int:suite_id>/cases", methods=["POST"])
def add_cases_to_suite(suite_id: int):
    """
    向测试套件添加用例

    请求体:
    {
        "case_ids": [1, 2, 3],           // 必填：要添加的用例ID列表
        "inherit_from_case": true,         // 是否继承用例配置（true=无需自定义，false=自定义）
        "custom_configs": [                // 可选：如果 inherit_from_case=false，在此提供自定义配置
            {
                "case_id": 1,
                "url": "https://custom-url.com/api",
                "request_headers": {"Authorization": "Bearer xxx"},
                "request_params": {"env": "test"},
                "request_body": {"user": "test"},
                "timeout": 60,
                "assertions": [{"check": "status_code", "expected": 200}],
                "preconditions": "自定义前置条件",    // 可选：用例内容（优先于 test_case 表）
                "test_steps": [...],                  // 可选：测试步骤（优先于 test_case 表）
                "test_data": {...}                    // 可选：测试数据（优先于 test_case 表）
            },
            ...
        ]
    }

    响应:
    {
        "code": 200,
        "message": "添加成功",
        "data": {
            "added_count": 3,
            "failed_cases": []
        }
    }
    """
    try:
        payload = request.get_json(silent=True) or {}
        case_ids = payload.get("case_ids", [])
        inherit_from_case = payload.get("inherit_from_case", True)  # 默认继承用例配置
        custom_configs = payload.get("custom_configs", [])

        if not case_ids:
            return _json_response({"code": 400, "message": "用例ID列表不能为空", "data": None}, 400)

        from common.db_mapper.test_suite_mapper import TestSuiteMapper
        from common.db_mapper.test_suite_case_mapper import TestSuiteCaseMapper
        from common.db_mapper.test_case_mapper import TestCaseMapper
        from common.db_enitiy.test_suite_case import TestSuiteCase

        suite_mapper = TestSuiteMapper()
        suite_case_mapper = TestSuiteCaseMapper()
        case_mapper = TestCaseMapper()

        # 验证套件是否存在
        suite = suite_mapper.get_by_id(suite_id)
        if not suite:
            return _json_response({"code": 404, "message": "测试套件不存在", "data": None}, 404)

        # 获取下一个执行顺序
        next_order = suite_case_mapper.get_next_execution_order(suite_id)

        # 构建自定义配置映射
        custom_config_map = {c.get("case_id"): c for c in custom_configs}

        # 添加用例
        added_count = 0
        failed_cases = []

        for i, case_id in enumerate(case_ids):
            try:
                # 验证用例是否存在
                case = case_mapper.get_by_id(case_id)
                if not case:
                    failed_cases.append({"case_id": case_id, "reason": "用例不存在"})
                    continue

                # 检查是否已存在关联（已存在则报错，不静默跳过）
                existing = suite_case_mapper.get_by_suite_and_case(suite_id, case_id)
                if existing:
                    return _json_response({
                        "code": 409,
                        "message": f"用例 {case_id} 已存在于该套件，无法重复添加",
                        "data": {"case_id": case_id, "existing_suite_case_id": existing["id"]}
                    }, 409)

                # 确定执行顺序（追加到末尾）
                execution_order = next_order + i

                # 创建关联记录
                if inherit_from_case:
                    # 继承模式：从 test_case 复制所有信息
                    suite_case = TestSuiteCase.create_association(
                        suite_id=suite_id,
                        case_id=case_id,
                        execution_order=execution_order,
                        config={},
                        enabled=True,
                        name=case.get("name"),
                        case_id_str=case.get("case_id")
                    )
                    # 从 test_case 复制用例内容
                    suite_case.copy_from_case(case)
                else:
                    # 独立配置模式
                    custom = custom_config_map.get(case_id, {})
                    suite_case = TestSuiteCase.create_with_request_config(
                        suite_id=suite_id,
                        case_id=case_id,
                        execution_order=execution_order,
                        name=case.get("name"),
                        case_id_str=case.get("case_id"),
                        url=custom.get("url"),
                        request_headers=custom.get("request_headers"),
                        request_params=custom.get("request_params"),
                        request_body=custom.get("request_body"),
                        timeout=custom.get("timeout", 30),
                        assertions=custom.get("assertions"),
                        preconditions=custom.get("preconditions"),
                        test_steps=custom.get("test_steps"),
                        test_data=custom.get("test_data")
                    )

                suite_case_mapper.create(suite_case)
                added_count += 1

            except Exception as e:
                logger.warning(f"[TestSuiteCase] 添加用例失败: case_id={case_id}, error={str(e)}")
                failed_cases.append({"case_id": case_id, "reason": str(e)})

        logger.info(f"[TestSuiteCase] 向套件 {suite_id} 添加用例: 成功 {added_count}, 失败 {len(failed_cases)}")

        return _json_response({
            "code": 200,
            "message": f"添加成功 {added_count} 个用例",
            "data": {
                "added_count": added_count,
                "failed_cases": failed_cases
            }
        })

    except Exception as e:
        logger.exception("[TestSuiteCase] 添加用例失败")
        return _json_response({"code": 500, "message": f"添加失败: {str(e)}", "data": None}, 500)


@test_suite_case_bp.route("/<int:suite_id>/cases/<int:suite_case_id>", methods=["PUT"])
def update_suite_case(suite_id: int, suite_case_id: int):
    """
    更新套件中的用例配置

    请求体:
    {
        "execution_order": 3,                    // 可选：执行顺序
        "enabled": true,                         // 可选：是否启用
        "url": "https://new-url.com/api",        // 可选：独立配置-URL
        "request_headers": {"X-Custom": "xxx"}, // 可选：独立配置-请求头
        "request_params": {"env": "prod"},       // 可选：独立配置-请求参数
        "request_body": {"user": "admin"},       // 可选：独立配置-请求体
        "timeout": 60,                            // 可选：超时时间
        "assertions": [{"check": "code", "expected": 0}],  // 可选：断言配置
        "preconditions": "...",                  // 可选：用例内容-前置条件
        "test_steps": [...],                     // 可选：用例内容-测试步骤
        "test_data": {...},                      // 可选：用例内容-测试数据
        "reset_to_inherit": false                 // 可选：true=重置为继承用例配置
    }
    """
    try:
        payload = request.get_json(silent=True) or {}

        from common.db_mapper.test_suite_case_mapper import TestSuiteCaseMapper

        mapper = TestSuiteCaseMapper()

        # 获取关联记录
        suite_case = mapper.get_by_id(suite_case_id)
        if not suite_case or suite_case["suite_id"] != suite_id:
            return _json_response({"code": 404, "message": "套件用例关联不存在", "data": None}, 404)

        # 处理重置为继承配置
        if payload.get("reset_to_inherit"):
            logger.info(f"[TestSuiteCase] 重置用例配置: suite_case_id={suite_case_id}")
            mapper.update(suite_case_id, {})  # 触发更新
            return _json_response({
                "code": 200,
                "message": "已重置为继承用例配置",
                "data": {"id": suite_case_id, "reset": True}
            })

        # 构建更新数据
        update_data = {}

        if "execution_order" in payload:
            update_data["execution_order"] = payload["execution_order"]

        if "enabled" in payload:
            update_data["enabled"] = payload["enabled"]

        if "url" in payload:
            update_data["url"] = payload["url"]

        if "request_headers" in payload:
            update_data["request_headers"] = payload["request_headers"]

        if "request_params" in payload:
            update_data["request_params"] = payload["request_params"]

        if "request_body" in payload:
            update_data["request_body"] = payload["request_body"]

        if "timeout" in payload:
            update_data["timeout"] = payload["timeout"]

        if "assertions" in payload:
            update_data["assertions"] = payload["assertions"]

        if "preconditions" in payload:
            update_data["preconditions"] = payload["preconditions"]

        if "test_steps" in payload:
            update_data["test_steps"] = payload["test_steps"]

        if "test_data" in payload:
            update_data["test_data"] = payload["test_data"]

        if not update_data:
            return _json_response({"code": 400, "message": "没有需要更新的字段", "data": None}, 400)

        # 执行更新
        updated = mapper.update(suite_case_id, update_data)

        logger.info(f"[TestSuiteCase] 更新套件用例配置: suite_case_id={suite_case_id}")

        return _json_response({
            "code": 200,
            "message": "更新成功",
            "data": {
                "id": suite_case_id,
                "execution_order": update_data.get("execution_order", suite_case["execution_order"]),
                "enabled": update_data.get("enabled", suite_case["enabled"]),
                "has_custom_config": any([
                    update_data.get("url") is not None or suite_case["url"] is not None,
                    update_data.get("request_headers") is not None or suite_case["request_headers"] is not None,
                    update_data.get("request_params") is not None or suite_case["request_params"] is not None,
                    update_data.get("request_body") is not None or suite_case["request_body"] is not None,
                    update_data.get("assertions") is not None or suite_case["assertions"] is not None,
                    update_data.get("preconditions") is not None or suite_case["preconditions"] is not None,
                    update_data.get("test_steps") is not None or suite_case["test_steps"] is not None,
                    update_data.get("test_data") is not None or suite_case["test_data"] is not None,
                ])
            }
        })

    except Exception as e:
        logger.exception("[TestSuiteCase] 更新套件用例失败")
        return _json_response({"code": 500, "message": f"更新失败: {str(e)}", "data": None}, 500)


@test_suite_case_bp.route("/<int:suite_id>/cases/<int:suite_case_id>", methods=["DELETE"])
def remove_case_from_suite(suite_id: int, suite_case_id: int):
    """
    从测试套件移除用例
    """
    try:
        from common.db_mapper.test_suite_case_mapper import TestSuiteCaseMapper

        mapper = TestSuiteCaseMapper()

        # 获取关联记录
        suite_case = mapper.get_by_id(suite_case_id)
        if not suite_case or suite_case["suite_id"] != suite_id:
            return _json_response({"code": 404, "message": "套件用例关联不存在", "data": None}, 404)

        # 删除关联
        mapper.delete(suite_case_id)

        logger.info(f"[TestSuiteCase] 从套件移除用例: suite_case_id={suite_case_id}")

        return _json_response({
            "code": 200,
            "message": "移除成功",
            "data": {"id": suite_case_id}
        })

    except Exception as e:
        logger.exception("[TestSuiteCase] 移除用例失败")
        return _json_response({"code": 500, "message": f"移除失败: {str(e)}", "data": None}, 500)


@test_suite_case_bp.route("/<int:suite_id>/cases/reorder", methods=["PUT"])
def reorder_suite_cases(suite_id: int):
    """
    重新排序套件中的用例

    请求体:
    {
        "case_orders": [
            {"suite_case_id": 1, "execution_order": 1},
            {"suite_case_id": 2, "execution_order": 2},
            {"suite_case_id": 3, "execution_order": 3}
        ]
    }

    响应:
    {
        "code": 200,
        "message": "排序更新成功",
        "data": {"updated_count": 3}
    }
    """
    try:
        payload = request.get_json(silent=True) or {}
        case_orders = payload.get("case_orders", [])

        if not case_orders:
            return _json_response({"code": 400, "message": "排序数据不能为空", "data": None}, 400)

        from common.db_mapper.test_suite_case_mapper import TestSuiteCaseMapper

        mapper = TestSuiteCaseMapper()

        updated_count = 0
        for item in case_orders:
            suite_case_id = item.get("suite_case_id")
            execution_order = item.get("execution_order")

            if suite_case_id and execution_order is not None:
                try:
                    mapper.update(suite_case_id, {"execution_order": execution_order})
                    updated_count += 1
                except Exception as e:
                    logger.warning(f"[TestSuiteCase] 更新排序失败: suite_case_id={suite_case_id}, error={str(e)}")

        logger.info(f"[TestSuiteCase] 更新套件用例排序: suite_id={suite_id}, 更新 {updated_count} 条")

        return _json_response({
            "code": 200,
            "message": f"排序更新成功",
            "data": {"updated_count": updated_count}
        })

    except Exception as e:
        logger.exception("[TestSuiteCase] 更新排序失败")
        return _json_response({"code": 500, "message": f"更新失败: {str(e)}", "data": None}, 500)


@test_suite_case_bp.route("/<int:suite_id>/cases/batch-update", methods=["PUT"])
def batch_update_suite_cases(suite_id: int):
    """
    批量更新套件中的用例配置

    请求体:
    {
        "updates": [
            {
                "suite_case_id": 1,
                "url": "https://new-url.com/api",
                "request_headers": {"Authorization": "Bearer xxx"},
                "enabled": true
            },
            {
                "suite_case_id": 2,
                "enabled": false
            }
        ]
    }
    """
    try:
        payload = request.get_json(silent=True) or {}
        updates = payload.get("updates", [])

        if not updates:
            return _json_response({"code": 400, "message": "更新数据不能为空", "data": None}, 400)

        from common.db_mapper.test_suite_case_mapper import TestSuiteCaseMapper

        mapper = TestSuiteCaseMapper()

        updated_count = 0
        failed = []

        for item in updates:
            suite_case_id = item.get("suite_case_id")
            if not suite_case_id:
                continue

            # 过滤掉 suite_case_id
            update_data = {k: v for k, v in item.items() if k != "suite_case_id"}

            if not update_data:
                continue

            try:
                # 验证关联是否存在
                suite_case = mapper.get_by_id(suite_case_id)
                if not suite_case or suite_case["suite_id"] != suite_id:
                    failed.append({"suite_case_id": suite_case_id, "reason": "关联不存在"})
                    continue

                mapper.update(suite_case_id, update_data)
                updated_count += 1

            except Exception as e:
                failed.append({"suite_case_id": suite_case_id, "reason": str(e)})

        logger.info(f"[TestSuiteCase] 批量更新套件用例: 更新 {updated_count} 条, 失败 {len(failed)} 条")

        return _json_response({
            "code": 200,
            "message": f"批量更新完成: 成功 {updated_count}, 失败 {len(failed)}",
            "data": {
                "updated_count": updated_count,
                "failed": failed
            }
        })

    except Exception as e:
        logger.exception("[TestSuiteCase] 批量更新失败")
        return _json_response({"code": 500, "message": f"批量更新失败: {str(e)}", "data": None}, 500)


@test_suite_case_bp.route("/<int:suite_id>/cases", methods=["PUT"])
def replace_suite_cases(suite_id: int):
    """
    更新套件中的用例列表（增量更新，支持新增/修改/删除）

    逻辑说明：
    1. 传入的用例列表会与套件中现有用例进行对比
    2. 新增：列表中有但套件中没有的用例 → 新增到套件
    3. 更新：列表中和套件中都有的用例 → 更新执行顺序
    4. 删除：套件中有但列表中没有的用例 → 从套件移除
    5. 保留：现有用例的自定义配置不会被覆盖

    请求体:
    {
        "case_ids": [1, 2, 3],           // 必填：要写入套件的用例ID列表（顺序即执行顺序）
        "inherit_from_case": true,       // 可选：新增用例时是否从 test_case 继承配置（默认 true）
        "custom_configs": [              // 可选：新增用例的独立配置（已存在的用例配置不会被覆盖）
            {
                "case_id": 1,
                "enabled": true,
                "url": "https://custom-url.com/api",
                "request_headers": {"Authorization": "Bearer xxx"},
                "request_params": {"env": "test"},
                "request_body": {"user": "test"},
                "timeout": 60,
                "assertions": [{"check": "status_code", "expected": 200}],
                "preconditions": "自定义前置条件",
                "test_steps": [...],
                "test_data": {...}
            },
            ...
        ]
    }

    响应:
    {
        "code": 200,
        "message": "更新成功",
        "data": {
            "added_count": 1,              // 新增数量
            "updated_count": 2,           // 更新数量（执行顺序变化）
            "deleted_count": 0,           // 删除数量
            "unchanged_count": 0,          // 未变化数量
            "total_cases": 3,              // 最终总数
            "case_ids": [1, 2, 3],         // 最终用例ID列表
            "execution_orders": {"1": 1, "2": 2, "3": 3}
        }
    }
    """
    try:
        payload = request.get_json(silent=True) or {}
        case_ids = payload.get("case_ids", [])
        inherit_from_case = payload.get("inherit_from_case", True)
        custom_configs = payload.get("custom_configs", [])

        if not case_ids:
            return _json_response({"code": 400, "message": "用例ID列表不能为空", "data": None}, 400)

        # 去重并保持顺序
        seen = set()
        unique_case_ids = []
        for cid in case_ids:
            if cid not in seen:
                seen.add(cid)
                unique_case_ids.append(cid)
        case_ids = unique_case_ids

        from common.db_mapper.test_suite_mapper import TestSuiteMapper
        from common.db_mapper.test_suite_case_mapper import TestSuiteCaseMapper
        from common.db_mapper.test_case_mapper import TestCaseMapper
        from common.db_enitiy.test_suite_case import TestSuiteCase

        suite_mapper = TestSuiteMapper()
        suite_case_mapper = TestSuiteCaseMapper()
        case_mapper = TestCaseMapper()

        # 验证套件是否存在
        suite = suite_mapper.get_by_id(suite_id)
        if not suite:
            return _json_response({"code": 404, "message": "测试套件不存在", "data": None}, 404)

        # 验证所有用例都存在
        invalid_cases = []
        case_map = {}
        for case_id in case_ids:
            case = case_mapper.get_by_id(case_id)
            if not case:
                invalid_cases.append(case_id)
            else:
                case_map[case_id] = case

        if invalid_cases:
            return _json_response({
                "code": 400,
                "message": f"以下用例不存在: {invalid_cases}",
                "data": {"invalid_cases": invalid_cases}
            }, 400)

        # 获取套件中现有的用例关联
        existing_associations = suite_case_mapper.get_cases_by_suite(
            suite_id, enabled_only=False, order_by_execution=True
        )
        # 构建现有关联的映射: case_id -> association
        existing_map = {}
        for assoc in existing_associations:
            case_id = assoc.get("case_id") if isinstance(assoc, dict) else assoc.case_id
            existing_map[case_id] = assoc

        # 获取现有用例ID集合
        existing_case_ids = set(existing_map.keys())
        # 获取目标用例ID集合
        target_case_ids = set(case_ids)

        # 计算差异
        to_add = target_case_ids - existing_case_ids  # 新增
        to_update = target_case_ids & existing_case_ids  # 更新
        to_delete = existing_case_ids - target_case_ids  # 删除

        logger.info(f"[TestSuiteCase] 增量更新套件用例: suite_id={suite_id}, "
                    f"新增={len(to_add)}, 更新={len(to_update)}, 删除={len(to_delete)}")

        # 构建自定义配置映射
        custom_config_map = {c.get("case_id"): c for c in custom_configs}

        added_count = 0
        updated_count = 0
        deleted_count = 0
        unchanged_count = 0
        execution_orders = {}

        # 1. 处理更新：更新现有用例的执行顺序（保留自定义配置）
        for case_id in case_ids:
            execution_orders[str(case_id)] = case_ids.index(case_id) + 1

            if case_id in to_update:
                # 查找现有的关联记录
                assoc = existing_map[case_id]
                old_order = assoc.get("execution_order") if isinstance(assoc, dict) else assoc.execution_order
                new_order = case_ids.index(case_id) + 1

                if old_order != new_order:
                    # 执行顺序变化，需要更新
                    assoc_id = assoc.get("id") if isinstance(assoc, dict) else assoc.id
                    suite_case_mapper.update(assoc_id, {"execution_order": new_order})
                    updated_count += 1
                    logger.info(f"[TestSuiteCase] 更新执行顺序: case_id={case_id}, {old_order} -> {new_order}")
                else:
                    unchanged_count += 1

        # 2. 处理新增：添加新用例到套件
        for case_id in to_add:
            order = case_ids.index(case_id) + 1
            case = case_map[case_id]
            custom = custom_config_map.get(case_id, {})

            if inherit_from_case:
                # 继承模式：从 test_case 复制所有信息
                suite_case = TestSuiteCase.create_association(
                    suite_id=suite_id,
                    case_id=case_id,
                    execution_order=order,
                    config={},
                    enabled=custom.get("enabled", True),
                    name=case.get("name") if isinstance(case, dict) else case.name,
                    case_id_str=case.get("case_id") if isinstance(case, dict) else getattr(case, "case_id", str(case_id))
                )
                # 从 test_case 复制用例内容
                suite_case.copy_from_case(case)
            else:
                # 独立配置模式
                suite_case = TestSuiteCase.create_with_request_config(
                    suite_id=suite_id,
                    case_id=case_id,
                    execution_order=order,
                    name=case.get("name") if isinstance(case, dict) else case.name,
                    case_id_str=case.get("case_id") if isinstance(case, dict) else getattr(case, "case_id", str(case_id)),
                    url=custom.get("url"),
                    request_headers=custom.get("request_headers"),
                    request_params=custom.get("request_params"),
                    request_body=custom.get("request_body"),
                    timeout=custom.get("timeout", 30),
                    assertions=custom.get("assertions"),
                    preconditions=custom.get("preconditions"),
                    test_steps=custom.get("test_steps"),
                    test_data=custom.get("test_data")
                )
                suite_case.enabled = custom.get("enabled", True)

            suite_case_mapper.create(suite_case)
            added_count += 1
            logger.info(f"[TestSuiteCase] 新增用例: case_id={case_id}, order={order}")

        # 3. 处理删除：移除不再需要的用例
        for case_id in to_delete:
            assoc = existing_map[case_id]
            assoc_id = assoc.get("id") if isinstance(assoc, dict) else assoc.id
            suite_case_mapper.delete(assoc_id)
            deleted_count += 1
            logger.info(f"[TestSuiteCase] 删除用例: case_id={case_id}")

        logger.info(f"[TestSuiteCase] 增量更新完成: suite_id={suite_id}, "
                    f"新增={added_count}, 更新={updated_count}, 删除={deleted_count}, "
                    f"未变化={unchanged_count}")

        return _json_response({
            "code": 200,
            "message": f"更新成功（新增 {added_count}, 更新 {updated_count}, 删除 {deleted_count}）",
            "data": {
                "added_count": added_count,
                "updated_count": updated_count,
                "deleted_count": deleted_count,
                "unchanged_count": unchanged_count,
                "total_cases": len(case_ids),
                "case_ids": case_ids,
                "execution_orders": execution_orders
            }
        })

    except Exception as e:
        logger.exception("[TestSuiteCase] 更新套件用例失败")
        return _json_response({"code": 500, "message": f"更新失败: {str(e)}", "data": None}, 500)


@test_suite_case_bp.route("/<int:suite_id>/cases/clear", methods=["DELETE"])
def clear_suite_cases(suite_id: int):
    """
    清空套件中的所有用例（保留套件本身）
    """
    try:
        from common.db_mapper.test_suite_mapper import TestSuiteMapper
        from common.db_mapper.test_suite_case_mapper import TestSuiteCaseMapper

        suite_mapper = TestSuiteMapper()
        suite_case_mapper = TestSuiteCaseMapper()

        # 验证套件是否存在
        suite = suite_mapper.get_by_id(suite_id)
        if not suite:
            return _json_response({"code": 404, "message": "测试套件不存在", "data": None}, 404)

        # 清空用例
        deleted_count = suite_case_mapper.clear_suite_cases(suite_id)

        logger.info(f"[TestSuiteCase] 清空套件用例: suite_id={suite_id}, 删除 {deleted_count} 条")

        return _json_response({
            "code": 200,
            "message": f"已清空 {deleted_count} 个用例",
            "data": {"deleted_count": deleted_count}
        })

    except Exception as e:
        logger.exception("[TestSuiteCase] 清空用例失败")
        return _json_response({"code": 500, "message": f"清空失败: {str(e)}", "data": None}, 500)


@test_suite_case_bp.route("/<int:suite_id>/cases/statistics", methods=["GET"])
def get_suite_case_statistics(suite_id: int):
    """
    获取套件用例统计信息
    """
    try:
        from common.db_mapper.test_suite_mapper import TestSuiteMapper
        from common.db_mapper.test_suite_case_mapper import TestSuiteCaseMapper

        suite_mapper = TestSuiteMapper()
        suite_case_mapper = TestSuiteCaseMapper()

        # 验证套件是否存在
        suite = suite_mapper.get_by_id(suite_id)
        if not suite:
            return _json_response({"code": 404, "message": "测试套件不存在", "data": None}, 404)

        # 获取统计
        stats = suite_case_mapper.get_suite_statistics(suite_id)

        return _json_response({
            "code": 200,
            "message": "success",
            "data": {
                "suite_id": suite_id,
                "suite_name": suite["name"],
                **stats
            }
        })

    except Exception as e:
        logger.exception("[TestSuiteCase] 获取统计失败")
        return _json_response({"code": 500, "message": f"获取失败: {str(e)}", "data": None}, 500)
