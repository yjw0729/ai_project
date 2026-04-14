# platform_service/api/http_test_suite_execute.py
"""测试套件执行 API 接口"""

import logging
import json
import uuid as uuid_module
from datetime import datetime
from typing import Any, Dict, List, Optional
from flask import Blueprint, request, jsonify, make_response

logger = logging.getLogger(__name__)

# 创建 Blueprint
test_suite_execute_bp = Blueprint("test_suite_execute", __name__, url_prefix="/api/test-suite")


def _json_response(body: Dict[str, Any], status: int = 200):
    """构建 JSON 响应"""
    resp = make_response(jsonify(body), status)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


def _get_user_id(req) -> str:
    """获取当前用户ID"""
    return req.headers.get("X-User-ID", "anonymous")


# ==================== 请求配置合并工具 ====================

def get_suite_case_request_config(suite_case, test_case, suite):
    """
    获取套件用例的最终请求配置

    规则：
    1. 优先使用 suite_case 的独立配置
    2. 如果 suite_case 的字段为空，使用 test_case 的配置
    3. 如果 test_case 的字段也为空，使用 suite 的 case_default_config
    """
    result = {}

    # URL
    result["url"] = suite_case.url or (test_case.url if hasattr(test_case, "url") else None)

    # 请求头
    result["request_headers"] = suite_case.request_headers
    if result["request_headers"] is None and hasattr(test_case, "request_headers"):
        result["request_headers"] = test_case.request_headers
    # 合并套件级默认请求头
    if suite and suite.case_default_config and "default_headers" in suite.case_default_config:
        default_headers = suite.case_default_config.get("default_headers", {})
        if result["request_headers"]:
            result["request_headers"] = {**result["request_headers"], **default_headers}
        else:
            result["request_headers"] = default_headers

    # 请求参数
    result["request_params"] = suite_case.request_params
    if result["request_params"] is None and hasattr(test_case, "request_params"):
        result["request_params"] = test_case.request_params
    # 合并套件级默认请求参数
    if suite and suite.case_default_config and "default_params" in suite.case_default_config:
        default_params = suite.case_default_config.get("default_params", {})
        if result["request_params"]:
            result["request_params"] = {**result["request_params"], **default_params}
        else:
            result["request_params"] = default_params

    # 请求体
    result["request_body"] = suite_case.request_body
    if result["request_body"] is None and hasattr(test_case, "request_body"):
        result["request_body"] = test_case.request_body

    # 超时时间
    result["timeout"] = suite_case.timeout
    if result["timeout"] is None and hasattr(test_case, "timeout"):
        result["timeout"] = test_case.timeout
    if result["timeout"] is None and suite and suite.case_default_config and "default_timeout" in suite.case_default_config:
        result["timeout"] = suite.case_default_config.get("default_timeout")

    # 断言配置
    result["assertions"] = suite_case.assertions
    if result["assertions"] is None and hasattr(test_case, "assertions"):
        result["assertions"] = test_case.assertions

    # 用例内容（核心逻辑）
    result["preconditions"] = suite_case.preconditions
    if result["preconditions"] is None:
        result["preconditions"] = getattr(test_case, "preconditions", None)

    result["test_steps"] = suite_case.test_steps
    if result["test_steps"] is None:
        result["test_steps"] = getattr(test_case, "test_steps", None)

    result["test_data"] = suite_case.test_data
    if result["test_data"] is None:
        result["test_data"] = getattr(test_case, "test_data", None)

    return result


# ==================== TestSuite 执行接口 ====================

@test_suite_execute_bp.route("/<int:suite_id>/execute", methods=["POST"])
def execute_test_suite(suite_id: int):
    """
    执行测试套件

    请求体（可选）:
    {
        "env_id": 1,                          // 环境ID
        "concurrency": 1,                      // 并发数（默认1）
        "fail_fast": false,                    // 失败快速停止（默认false）
        "retry_times": 0,                      // 重试次数（默认0）
        "case_ids": [1, 2, 3]                 // 可选：只执行指定的用例（不传则执行全部）
    }

    响应:
    {
        "code": 200,
        "message": "执行成功",
        "data": {
            "execution_id": "exec-xxx",
            "status": "completed",
            "suite_id": 1,
            "suite_name": "支付流程测试",
            "summary": {
                "total": 10,
                "passed": 8,
                "failed": 2,
                "skipped": 0,
                "success_rate": 80.0
            },
            "duration_seconds": 12.5,
            "started_at": "2026-04-13T10:00:00",
            "finished_at": "2026-04-13T10:00:12",
            "report_url": "/api/auto_test/report/exec-xxx"
        }
    }
    """
    try:
        payload = request.get_json(silent=True) or {}
        env_id = payload.get("env_id")
        concurrency = payload.get("concurrency", 1)
        fail_fast = payload.get("fail_fast", False)
        retry_times = payload.get("retry_times", 0)
        case_ids_filter = payload.get("case_ids")  # 可选：只执行指定用例

        from common.db_mapper.test_suite_mapper import TestSuiteMapper
        from common.db_mapper.test_suite_case_mapper import TestSuiteCaseMapper
        from common.db_mapper.test_case_mapper import TestCaseMapper
        from common.config_loader import get_config
        from common.test_executor.pytest_generator import PytestGenerator
        from core.runner import TestRunner, RunConfig, ExecutionMode

        suite_mapper = TestSuiteMapper()
        suite_case_mapper = TestSuiteCaseMapper()
        case_mapper = TestCaseMapper()

        # 1. 获取套件
        suite = suite_mapper.get_by_id(suite_id)
        if not suite:
            return _json_response({"code": 404, "message": "测试套件不存在", "data": None}, 404)

        # 2. 获取套件下的用例
        suite_cases = suite_case_mapper.get_cases_by_suite(suite_id, enabled_only=True, order_by_execution=True)

        if not suite_cases:
            return _json_response({"code": 400, "message": "测试套件中没有启用的用例", "data": None}, 400)

        # 如果指定了 case_ids，则过滤
        if case_ids_filter:
            suite_cases = [sc for sc in suite_cases if sc.case_id in case_ids_filter]
            if not suite_cases:
                return _json_response({"code": 400, "message": "指定的用例不在套件中或未启用", "data": None}, 400)

        # 3. 加载用例详情
        cases_to_execute = []
        for sc in suite_cases:
            case = case_mapper.get_by_id(sc.case_id)
            if not case:
                logger.warning(f"[TestSuite-Execute] 用例不存在: case_id={sc.case_id}")
                continue

            # 获取最终请求配置（合并套件和用例的配置）
            request_config = get_suite_case_request_config(sc, case, suite)

            # 构建用例执行数据
            case_data = {
                "id": case.id,
                "case_id": getattr(case, "case_id", None),
                "name": case.name,
                "module": case.module,
                "priority": getattr(case, "priority", "P2"),
                "timeout": request_config["timeout"] or 30,
                "max_retry_times": retry_times,
                # 请求配置
                "url": request_config["url"],
                "request_headers": request_config["request_headers"],
                "request_params": request_config["request_params"],
                "request_body": request_config["request_body"],
                "assertions": request_config["assertions"],
                # 用例内容（优先用 suite_case 的，没有则 fallback 到 test_case）
                "preconditions": request_config["preconditions"],
                "test_steps": request_config["test_steps"],
                "test_data": request_config["test_data"],
                # 套件用例信息
                "suite_case_id": sc.id,
                "execution_order": sc.execution_order,
                "has_custom_config": sc.has_custom_config()
            }

            cases_to_execute.append(case_data)

        if not cases_to_execute:
            return _json_response({"code": 400, "message": "没有可执行的用例", "data": None}, 400)

        # 4. 生成执行ID
        execution_id = f"exec-{uuid_module.uuid4().hex[:12]}"

        # 5. 获取环境 base_url
        config_loader = get_config()
        base_url = "http://localhost:5000"
        if env_id:
            try:
                from common.db_mapper.environment_config_mapper import EnvironmentConfigMapper
                env_mapper = EnvironmentConfigMapper()
                env_cfg = env_mapper.get_by_id(env_id)
                if env_cfg and hasattr(env_cfg, "base_url") and env_cfg.base_url:
                    base_url = env_cfg.base_url
            except Exception as e:
                logger.warning(f"[TestSuite-Execute] 获取环境配置失败: {str(e)}")

        # 6. 生成 pytest 测试文件
        try:
            generator = PytestGenerator(output_dir=config_loader.generated_tests_dir)
            test_file_path = generator.generate(
                cases=cases_to_execute,
                execution_id=execution_id,
                base_url=base_url,
                retry_times=retry_times,
                timeout=config_loader.default_timeout
            )
            logger.info(f"[TestSuite-Execute] 生成测试文件: {test_file_path}")
        except Exception as e:
            logger.exception("[TestSuite-Execute] 生成测试文件失败")
            return _json_response({"code": 500, "message": f"生成测试文件失败: {str(e)}", "data": None}, 500)

        # 7. 构建 pytest 执行配置
        allure_results_dir = config_loader.allure_results_dir
        os.makedirs(allure_results_dir, exist_ok=True)
        full_allure_results_dir = f"{allure_results_dir}/{execution_id}"
        os.makedirs(full_allure_results_dir, exist_ok=True)

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
            allure_results_dir=full_allure_results_dir,
            allure_report_dir=f"{config_loader.report_dir}/{execution_id}",
            fail_fast=fail_fast,
            verbose=True,
            capture="sys",
            timeout=config_loader.default_timeout,
        )

        # 8. 更新套件执行状态为 running
        suite.last_execution_status = "running"
        suite.last_execution_id = execution_id
        suite_mapper.update(suite_id, {
            "last_execution_status": "running",
            "last_execution_id": execution_id
        })

        # 9. 执行 pytest
        started_at = datetime.now()
        try:
            runner = TestRunner(run_config)
            result = runner.run()
            logger.info(f"[TestSuite-Execute] pytest 执行完成: {result}")
        except Exception as e:
            logger.exception("[TestSuite-Execute] pytest 执行失败")
            # 更新套件执行状态为失败
            suite_mapper.update(suite_id, {
                "last_execution_status": "failed"
            })
            return _json_response({"code": 500, "message": f"执行失败: {str(e)}", "data": None}, 500)

        finished_at = datetime.now()
        duration_seconds = (finished_at - started_at).total_seconds()

        # 10. 更新套件执行统计
        suite_mapper.update(suite_id, {
            "last_execution_status": "passed" if result.failed == 0 else "failed",
            "last_execution_time": finished_at,
            "total_executions": (suite.total_executions or 0) + 1,
        })

        # 更新成功率
        if suite.total_executions and suite.total_executions > 0:
            new_rate = (result.passed / result.total * 100) if result.total > 0 else 0
            # 简单移动平均
            avg_rate = (float(suite.success_rate or 0) + new_rate) / 2
            suite_mapper.update(suite_id, {"success_rate": avg_rate})

        # 11. 生成 Allure 报告
        allure_report_dir = ""
        try:
            allure_report_dir = runner.generate_allure_report(
                results_dir=full_allure_results_dir,
                report_dir=run_config.allure_report_dir
            )
        except Exception as e:
            logger.warning(f"[TestSuite-Execute] 生成 Allure 报告失败: {str(e)}")

        # 12. 构应响应
        return _json_response({
            "code": 200,
            "message": "执行成功",
            "data": {
                "execution_id": execution_id,
                "status": "completed",
                "suite_id": suite_id,
                "suite_name": suite.name,
                "summary": {
                    "total": result.total,
                    "passed": result.passed,
                    "failed": result.failed,
                    "skipped": result.skipped,
                    "success_rate": result.success_rate,
                },
                "duration_seconds": duration_seconds,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "exit_code": result.exit_code,
                "report_url": f"/api/auto_test/report/{execution_id}" if allure_report_dir else None
            }
        })

    except Exception as e:
        logger.exception("[TestSuite-Execute] 执行测试套件失败")
        return _json_response({"code": 500, "message": f"执行失败: {str(e)}", "data": None}, 500)


@test_suite_execute_bp.route("/<int:suite_id>/execution-history", methods=["GET"])
def get_suite_execution_history(suite_id: int):
    """
    获取测试套件执行历史

    查询参数:
    - page: 页码（默认1）
    - page_size: 每页数量（默认20）

    响应:
    {
        "code": 200,
        "data": {
            "suite_id": 1,
            "suite_name": "支付流程测试",
            "current_status": {
                "last_execution_status": "passed",
                "last_execution_time": "2026-04-13T10:00:00",
                "total_executions": 10,
                "success_rate": 85.5
            },
            "executions": [
                {
                    "execution_id": "exec-xxx",
                    "started_at": "2026-04-13T10:00:00",
                    "finished_at": "2026-04-13T10:00:12",
                    "duration_seconds": 12.5,
                    "status": "passed",
                    "summary": {
                        "total": 10,
                        "passed": 9,
                        "failed": 1,
                        "success_rate": 90.0
                    }
                }
            ]
        }
    }
    """
    try:
        from common.db_mapper.test_suite_mapper import TestSuiteMapper

        suite_mapper = TestSuiteMapper()

        # 获取套件
        suite = suite_mapper.get_by_id(suite_id)
        if not suite:
            return _json_response({"code": 404, "message": "测试套件不存在", "data": None}, 404)

        # TODO: 后续扩展：从 test_suite_execution 表获取历史记录
        # 当前暂时返回当前执行状态
        current_status = {
            "last_execution_status": suite.last_execution_status,
            "last_execution_time": suite.last_execution_time.isoformat() if suite.last_execution_time else None,
            "last_execution_id": suite.last_execution_id,
            "total_executions": suite.total_executions or 0,
            "success_rate": float(suite.success_rate or 0)
        }

        return _json_response({
            "code": 200,
            "message": "success",
            "data": {
                "suite_id": suite_id,
                "suite_name": suite.name,
                "current_status": current_status,
                "executions": []  # TODO: 后续从 test_suite_execution 表获取
            }
        })

    except Exception as e:
        logger.exception("[TestSuite-Execute] 获取执行历史失败")
        return _json_response({"code": 500, "message": f"获取失败: {str(e)}", "data": None}, 500)


# 导入 os（用于创建目录）
import os
