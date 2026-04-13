"""
测试执行 HTTP 接口

提供测试用例的查询和执行接口。
执行流程：DB读取用例 → PytestGenerator生成.py → TestRunner执行pytest → 回写DB
"""
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Blueprint, request, make_response, current_app, jsonify
from sqlalchemy import func, String

from common.db_mapper.test_case_mapper import TestCaseMapper
from common.db_mapper.api_config_mapper import ApiConfigMapper
from common.db_mapper.environment_config_mapper import EnvironmentConfigMapper
from common.db_mapper.global_variable_mapper import GlobalVariableMapper
from common.datacase_function.contect_db import db_session
from common.db_enitiy.api_config import ApiConfig
from common.test_executor.test_case_executor import TestCaseExecutor
from common.test_executor.pytest_generator import PytestGenerator
from core.runner import TestRunner, RunConfig, ExecutionMode

test_exec_opt = Blueprint("test_exec_opt", __name__)

# 项目根目录，用于生成输出路径
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "outputs", "generated_tests")
ALLURE_RESULTS_DIR = os.path.join(_PROJECT_ROOT, "outputs", "allure-results")
ALLURE_REPORT_DIR = os.path.join(_PROJECT_ROOT, "outputs", "allure-report")


def json_response(body, status=200):
    resp = make_response(_json_dumps(body), status)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


def _json_dumps(data):
    import datetime as dt
    return json.dumps(data, ensure_ascii=False, default=_json_default)


def _json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "to_json"):
        return obj.to_json()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    try:
        return str(obj)
    except Exception:
        return repr(obj)


def _parse_payload() -> Dict[str, Any]:
    """
    兼容从 query / JSON body / form 获取参数
    """
    payload: Any = {}
    try:
        payload = request.args.to_dict(flat=True) or {}
    except Exception:
        payload = {}

    body = request.get_json(silent=True)
    if body is None:
        body = request.get_json(force=True, silent=True)

    if isinstance(body, dict):
        payload.update(body)
    elif body is None:
        try:
            form_data = request.form.to_dict(flat=True)
            if isinstance(form_data, dict):
                payload.update(form_data)
        except Exception:
            pass
        if request.data:
            raw = request.data.decode("utf-8", errors="ignore")
            try:
                raw_obj = json.loads(raw)
                if isinstance(raw_obj, dict):
                    payload.update(raw_obj)
            except Exception:
                if raw.endswith("'") or raw.endswith('"'):
                    try:
                        raw_obj = json.loads(raw[:-1])
                        if isinstance(raw_obj, dict):
                            payload.update(raw_obj)
                    except Exception:
                        pass

    if not isinstance(payload, dict):
        payload = {}
    return payload


@test_exec_opt.route("/testcase/list", methods=["GET", "POST"])
def list_testcases():
    """
    查询测试案例列表（默认全量）

    可选入参（query 或 JSON body 均可）：
    - module: str 功能模块（test_case.module 精确）
    - system: str 系统（按 test_case.system 精确筛选）
    - request_id: str 请求ID（按 api_config.id 转字符串后做模糊匹配）
    - case_status: str 案例状态（enabled/disabled）
    - execution_status: str 最近一次执行结果（not_run/success/failed）

    返回：test_case 表记录数组（to_json）
    """
    logger = current_app.logger or logging.getLogger(__name__)
    payload = _parse_payload()
    logger.info("【查询测试案例】入参=%s", payload)

    module = payload.get("module") or None
    system = payload.get("system") or None
    request_id = payload.get("request_id") or None
    case_status = payload.get("case_status") or None
    execution_status = payload.get("execution_status") or None

    mapper = TestCaseMapper()
    rows = []
    with db_session() as session:
        q = session.query(mapper.entity_class)
        if system or request_id:
            q = q.outerjoin(ApiConfig, ApiConfig.id == mapper.entity_class.api_config_id)

        if module:
            q = q.filter(mapper.entity_class.module == module)
        if case_status:
            q = q.filter(mapper.entity_class.case_status == case_status)
        if execution_status:
            q = q.filter(mapper.entity_class.last_execution_status == execution_status)
        if system:
            q = q.filter(mapper.entity_class.system == system)
        if request_id:
            like_req = f"%{request_id}%"
            q = q.filter(func.cast(ApiConfig.id, String).ilike(like_req))

        rows = q.order_by(
            mapper.entity_class.created_time.desc()
        ).all()
        for r in rows:
            session.expunge(r)

        # 构造返回数据，附加 last_execution_result 和 extract_fields 字段
        data = []
        for r in rows:
            item = r.to_json()
            # 如果有详细执行结果，添加到返回字段
            if hasattr(r, 'last_execution_result') and r.last_execution_result:
                item['last_execution_result'] = r.last_execution_result
            else:
                item['last_execution_result'] = None

            # 直接从 extract_fields 字段获取（如果存在）
            extract_fields = []
            if hasattr(r, 'extract_fields') and r.extract_fields:
                extract_fields = r.extract_fields if isinstance(r.extract_fields, list) else []
            item['extract_fields'] = extract_fields
            data.append(item)

    logger.info("【查询测试案例】返回数量=%s", len(data))
    return json_response({"code": 200, "msg": "查询成功", "data": data}, status=200)


@test_exec_opt.route("/testcase/execute", methods=["POST"])
def execute_testcases():
    """
    通过 pytest 框架执行测试案例。

    入参（query 或 JSON body 均可）：
    - case_ids: list[int] 必填，1 个或多个，需要在 test_case 表中存在
    - env_id: int 必填，指定 environment_config.id，用于获取 base_url / headers / timeout

    执行流程：
        1. 从 DB 读取用例数据
        2. 动态生成 pytest .py 文件（放在 outputs/generated_tests/）
        3. TestRunner 调用 pytest.main() 执行
        4. 解析 Allure JSON 结果获取每个用例的通过/失败状态
        5. 回写 last_execution_status / last_execution_time 到 test_case 表

    返回：
        - 执行汇总（总数/通过/失败/跳过/耗时）
        - 每个用例的执行结果列表
        - Allure 报告路径
    """
    logger = current_app.logger or logging.getLogger(__name__)
    payload = _parse_payload()

    logger.info("【执行测试案例】原始入参=%s", payload)

    # ---- 参数解析 ----
    case_ids = payload.get("case_ids") or []
    if isinstance(case_ids, str):
        try:
            case_ids = json.loads(case_ids)
        except Exception:
            case_ids = [case_ids]
    env_id = payload.get("env_id")

    if not case_ids or not isinstance(case_ids, list):
        logger.warning("【执行测试案例】case_ids 非法，解析结果=%s", case_ids)
        return json_response({"code": 400, "msg": "case_ids 必须是非空数组", "data": None}, status=400)
    if env_id is None:
        logger.warning("【执行测试案例】env_id 缺失")
        return json_response({"code": 400, "msg": "env_id 必填", "data": None}, status=400)

    # ---- 查询环境配置 ----
    env_mapper = EnvironmentConfigMapper()
    env = env_mapper.get_by_id(env_id)
    if not env:
        logger.warning("【执行测试案例】环境不存在 env_id=%s", env_id)
        return json_response({"code": 404, "msg": f"环境不存在: {env_id}", "data": None}, status=404)
    env_dict = env.to_json()
    base_url = env_dict.get("base_url") or "http://localhost"
    timeout_default = env_dict.get("timeout") or 30
    logger.info("【执行测试案例】使用环境 env_id=%s, base_url=%s", env_id, base_url)

    # ---- 获取全局变量 ----
    var_mapper = GlobalVariableMapper()
    global_variables = var_mapper.get_all_variables_dict(environment_id=env_id)
    logger.info("【执行测试案例】加载全局变量数量: %d", len(global_variables))

    # ---- 加载用例数据 ----
    try:
        executor = TestCaseExecutor()
        execution_cases = executor.load_cases(case_ids, env_id)
    except Exception as e:
        logger.error("【执行测试案例】加载用例失败: %s", e)
        return json_response({"code": 500, "msg": f"加载用例失败: {e}", "data": None}, status=500)

    if not execution_cases:
        logger.warning("【执行测试案例】未找到有效用例 case_ids=%s", case_ids)
        return json_response({"code": 404, "msg": "未找到任何有效测试案例", "data": None}, status=404)

    logger.info("【执行测试案例】成功加载 %d 个用例", len(execution_cases))

    # ---- 收集所有用例的变量配置 ----
    all_variables = dict(global_variables)  # 先复制全局变量
    for exec_case in execution_cases:
        case_vars = getattr(exec_case, 'case_variables', {}) or {}
        if case_vars:
            logger.info("【执行测试案例】用例 %s 的 preconditions 变量: %s",
                       exec_case.case_id, case_vars)
            all_variables.update(case_vars)

    logger.info("【执行测试案例】合并后总变量数: %d, 变量列表: %s",
                len(all_variables), list(all_variables.keys()))

    # ---- 生成唯一执行ID ----
    execution_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(ALLURE_RESULTS_DIR, exist_ok=True)

    # ---- 生成 pytest 测试文件 ----
    try:
        generator = PytestGenerator(output_dir=OUTPUT_DIR)
        test_file = generator.generate(
            cases=execution_cases,
            execution_id=execution_id,
            base_url=base_url,
            retry_times=0,
            timeout=timeout_default,
            global_variables=all_variables,
        )
        logger.info("【执行测试案例】生成测试文件: %s", test_file)
    except Exception as e:
        logger.error("【执行测试案例】生成测试文件失败: %s", e)
        return json_response({"code": 500, "msg": f"生成测试文件失败: {e}", "data": None}, status=500)

    # ---- 执行 pytest ----
    config = RunConfig(
        test_paths=[test_file],
        mode=ExecutionMode.SEQUENTIAL,
        allure_results_dir=ALLURE_RESULTS_DIR,
        allure_report_dir=ALLURE_REPORT_DIR,
        enable_allure=False,
        enable_json_report=False,
        verbose=True,
        fail_fast=False,
        no_conftest=False,  # 允许 conftest.py 加载，以便 session hooks 写入结果文件
    )

    try:
        runner = TestRunner(config)
        test_result = runner.run()
        logger.info("【执行测试案例】pytest 执行完成: %s", test_result)
    except Exception as e:
        logger.error("【执行测试案例】pytest 执行异常: %s", e)
        return json_response({
            "code": 500,
            "msg": f"pytest 执行异常: {e}",
            "data": {"test_file": test_file, "errors": [str(e)]}
        }, status=500)

    # ---- 解析测试结果 ----
    # 当 Allure 未启用时，根据 pytest 退出码判断每个用例的结果
    logger.info("【执行测试案例】test_result.test_file=%s", test_result.test_file)
    case_results = _parse_allure_results(execution_cases, test_result, logger)

    # ---- 生成 Allure HTML 报告（仅在启用时）----
    allure_report_path = None
    if test_result.allure_results_dir:
        try:
            report_dir = runner.generate_allure_report(
                results_dir=ALLURE_RESULTS_DIR,
                report_dir=ALLURE_REPORT_DIR,
            )
            if report_dir:
                allure_report_path = os.path.join(report_dir, "index.html")
                logger.info("【执行测试案例】Allure HTML 报告已生成: %s", allure_report_path)
            else:
                logger.info("【执行测试案例】Allure HTML 报告未生成（可能未安装 allure 命令）")
        except Exception as e:
            logger.info("【执行测试案例】生成 Allure 报告时异常: %s", e)
    else:
        logger.info("【执行测试案例】Allure 报告已跳过（enable_allure=False）")

    # ---- 回写 DB ----
    _write_back_results(execution_cases, case_results, logger)

    # ---- 构造返回数据 ----
    success_count = sum(1 for r in case_results if r.get("status") == "passed")
    failed_count = sum(1 for r in case_results if r.get("status") == "failed")

    logger.info("【执行测试案例】完成，总数=%s, 成功=%s, 失败=%s", len(case_results), success_count, failed_count)

    return json_response({
        "code": 200,
        "msg": "执行完成",
        "data": {
            "execution_id": execution_id,
            "test_file": test_file,
            "summary": {
                "total": len(case_results),
                "passed": success_count,
                "failed": failed_count,
                "skipped": test_result.skipped,
                "duration_seconds": round(test_result.duration_seconds, 2),
                "exit_code": test_result.exit_code,
                "success_rate": test_result.success_rate,
            },
            "case_results": case_results,
            "allure_report": allure_report_path,
        }
    }, status=200)


def _parse_allure_results(
    execution_cases: List[Any],
    test_result,
    logger,
) -> List[Dict[str, Any]]:
    """
    解析测试用例执行结果。

    优先级：
    1. pytest hook 生成的 .test_results.json → 最准确，包含每个用例的失败原因
    2. 如果 Allure 结果目录存在且有 JSON 文件 → 正常解析
    3. 否则 → 根据 pytest 退出码判断（exit_code=0=passed, 其他=failed）
    """
    results = []

    # 优先读取 pytest hook 生成的结果文件
    # 注意：pytest hook 在测试文件同目录下生成 .test_results.json
    result_file = None
    if test_result.test_file:
        result_file = os.path.join(os.path.dirname(test_result.test_file), ".test_results.json")
        logger.info("【结果解析】pytest 结果文件路径: %s", result_file)

    if result_file and os.path.exists(result_file):
        logger.info("【结果解析】pytest 结果文件存在，开始解析...")
        try:
            results = _parse_pytest_results(execution_cases, result_file, logger)
            if results:
                logger.info("【结果解析】从 pytest 结果文件成功解析 %d 个用例结果", len(results))
                # 解析完成后删除结果文件
                try:
                    if result_file and os.path.exists(result_file):
                        os.remove(result_file)
                        logger.info("【结果解析】已删除结果文件: %s", result_file)
                except Exception as e:
                    logger.warning("【结果解析】删除结果文件失败: %s", e)
                return results
        except Exception as e:
            logger.warning("【结果解析】pytest 结果文件解析失败: %s", e)
    else:
        logger.warning("【结果解析】pytest 结果文件不存在: %s", result_file)

    # 其次检查 Allure 结果文件
    results_dir = test_result.allure_results_dir or ALLURE_RESULTS_DIR
    has_results = os.path.exists(results_dir) and any(
        f.endswith(".json") for f in os.listdir(results_dir)
    )

    if has_results:
        results = _parse_allure_from_files(execution_cases, results_dir, test_result, logger)
        if results:
            logger.info("【结果解析】从 Allure 文件成功解析 %d 个用例结果", len(results))
            return results

    # 最后兜底：根据 pytest 退出码判断
    logger.warning("【结果解析】未找到详细结果文件，根据 pytest 退出码判断")
    exit_code = test_result.exit_code
    for case in execution_cases:
        status = "passed" if exit_code == 0 else "failed"
        results.append({
            "case_id": case.db_id,
            "case_name": case.name,
            "status": status,
            "message": f"根据 pytest 退出码判断（exit_code={exit_code}）",
        })

    return results


def _parse_pytest_results(
    execution_cases: List[Any],
    result_file: str,
    logger,
) -> List[Dict[str, Any]]:
    """
    从 pytest hook 生成的 .test_results.json 文件中解析每个用例的结果。
    """
    results = []

    if not os.path.exists(result_file):
        logger.warning("【pytest结果】结果文件不存在: %s", result_file)
        return results

    try:
        with open(result_file, encoding="utf-8") as f:
            test_results = json.load(f)
    except Exception as e:
        logger.warning("【pytest结果】读取失败 %s: %s", result_file, e)
        return results

    if not test_results:
        logger.warning("【pytest结果】结果文件为空: %s", result_file)
        return results

    logger.info("【pytest结果】文件=%s, 找到 %d 个用例结果: %s", result_file, len(test_results), list(test_results.keys()))

    def _safe_name(case_id: str) -> str:
        """将 case_id 转换为合法的 Python 函数名（与 pytest_generator 保持一致）"""
        import re
        return re.sub(r"[^a-zA-Z0-9_]", "_", str(case_id))[:50]

    matched_count = 0
    for idx, case in enumerate(execution_cases):
        # 函数名格式: test_{idx+1}_{_safe_name(case_id)}（与生成代码一致）
        func_name = f"test_{idx + 1}_{_safe_name(case.case_id)}"
        logger.info("【pytest结果】尝试匹配用例 %s (函数名: %s)", case.case_id, func_name)

        matched = False
        for key, value in test_results.items():
            # 标准化 key：去掉 .py 前缀、::分隔符后的部分
            pure_name = key.split("::")[-1] if "::" in key else key
            # 去掉 .py 后缀（可能有多层后缀）
            pure_name = pure_name.replace(".py", "")

            # 精确匹配或包含匹配
            if func_name == pure_name or func_name == key:
                logger.info("【pytest结果】匹配成功: %s -> %s", func_name, key)
                results.append({
                    "case_id": case.db_id,
                    "case_name": case.name,
                    "status": value.get("status", "failed"),
                    "message": value.get("message", ""),
                    "fail_response": value.get("fail_response", ""),
                    "success_response": value.get("success_response", ""),
                    "extract_fields": value.get("extract_fields", {}),
                })
                matched = True
                matched_count += 1
                break
            # 部分匹配（key 中包含 func_name 或 func_name 包含 key 的核心部分）
            elif pure_name in func_name or func_name in pure_name:
                logger.info("【pytest结果】模糊匹配: %s -> %s", func_name, key)
                results.append({
                    "case_id": case.db_id,
                    "case_name": case.name,
                    "status": value.get("status", "failed"),
                    "message": value.get("message", ""),
                    "fail_response": value.get("fail_response", ""),
                    "success_response": value.get("success_response", ""),
                    "extract_fields": value.get("extract_fields", {}),
                })
                matched = True
                matched_count += 1
                break

        if not matched:
            logger.warning("【pytest结果】未找到用例 %s (尝试匹配: %s)，所有key: %s", case.case_id, func_name, list(test_results.keys()))
            results.append({
                "case_id": case.db_id,
                "case_name": case.name,
                "status": "skipped",
                "message": "未在结果文件中找到对应用例",
            })

    logger.info("【pytest结果】匹配完成: 成功 %d/%d 个", matched_count, len(execution_cases))
    return results


def _parse_allure_from_files(
    execution_cases: List[Any],
    results_dir: str,
    test_result,
    logger,
) -> List[Dict[str, Any]]:
    """从 Allure 结果文件中解析用例执行状态"""
    results = []
    case_map = {str(case.db_id): case for case in execution_cases}

    def _safe_name(case_id: str) -> str:
        """将 case_id 转换为合法的 Python 函数名（与 pytest_generator 保持一致）"""
        import re
        return re.sub(r"[^a-zA-Z0-9_]", "_", str(case_id))[:50]

    json_files = [f for f in os.listdir(results_dir) if f.endswith(".json")]
    logger.info("【Allure结果】找到 %d 个结果文件", len(json_files))

    parsed_uuids = set()

    for json_file in json_files:
        file_path = os.path.join(results_dir, json_file)
        try:
            with open(file_path, encoding="utf-8") as f:
                allure_case = json.load(f)

            # 从 allure报告中获取测试名称或UUID
            name = allure_case.get("name", "")
            full_name = allure_case.get("fullName", "")
            uuid_str = allure_case.get("uuid", "")

            # 匹配用例：优先按 db_id 匹配（通过 test_函数名中嵌入的索引）
            matched_case = None
            matched_db_id = None

            # 方式1：从 fullName 中提取函数索引来匹配
            # 函数名格式: test_{idx+1}_{_safe_name(case_id)}
            for idx, case in enumerate(execution_cases):
                func_pattern = f"test_{idx + 1}_{_safe_name(case.case_id)}"
                if func_pattern in (full_name or name):
                    matched_case = case
                    matched_db_id = case.db_id
                    break

            # 方式2：按顺序映射（如果所有结果文件数量与用例数一致）
            if matched_case is None and len(json_files) == len(execution_cases):
                # 尝试按文件修改时间排序后按顺序匹配
                pass

            # 方式3：从 allure 附加信息中查找 db_id
            if matched_case is None:
                extra = allure_case.get("extra", {}) or {}
                parameters = extra.get("custom", {}) or {}
                if "db_id" in parameters:
                    db_id = int(parameters["db_id"])
                    matched_case = case_map.get(str(db_id))
                    if matched_case:
                        matched_db_id = db_id

            if matched_case and matched_db_id:
                status = allure_case.get("status", "failed")
                message = ""
                if status == "failed":
                    message = _extract_failure_message(allure_case)

                results.append({
                    "case_id": matched_db_id,
                    "case_name": matched_case.name,
                    "status": status,
                    "message": message,
                    "duration_ms": allure_case.get("time", {}).get("duration", 0),
                })
                parsed_uuids.add(json_file)
            else:
                logger.warning("【Allure结果】无法匹配用例: %s (%s)", name, json_file)

        except Exception as e:
            logger.warning("【Allure结果】解析文件失败 %s: %s", json_file, e)

    # 未解析到的用例标记为 skipped
    matched_db_ids = {r["case_id"] for r in results}
    for case in execution_cases:
        if case.db_id not in matched_db_ids:
            results.append({
                "case_id": case.db_id,
                "case_name": case.name,
                "status": "skipped",
                "message": "未能解析执行结果",
            })

    return results


def _extract_failure_message(allure_case: Dict) -> str:
    """从 Allure 结果中提取失败信息"""
    try:
        # 方式1：从 failures 列表中获取（pytest-allure 格式）
        failures = allure_case.get("failures", []) or []
        if failures:
            msg = failures[0].get("message", "")
            if msg:
                return msg[:2000]

        # 方式2：从 statusMessage 字段获取
        status_message = allure_case.get("statusMessage", "")
        if status_message:
            return status_message[:2000]

        # 方式3：从 statusTrace 中获取
        trace = allure_case.get("statusTrace", "") or ""
        if trace:
            lines = trace.strip().split('\n')
            brief = '\n'.join(lines[:5])
            return brief[:2000]

        # 方式4：从 extra 嵌套中获取（某些 allure 插件格式）
        extra = allure_case.get("extra", {}) or {}
        if extra:
            # 尝试从 nested 字段获取
            nested = extra.get("nested", [])
            if nested and isinstance(nested, list):
                for item in nested:
                    msg = item.get("statusMessage", "") or item.get("message", "")
                    if msg:
                        return msg[:2000]
    except Exception:
        pass
    return "用例执行失败"


def _write_back_results(
    execution_cases: List[Any],
    case_results: List[Dict[str, Any]],
    logger,
) -> None:
    """
    将执行结果回写到 test_case 表。

    存储内容：
    - last_execution_status: 执行状态（success/failed/not_run）
    - last_execution_time: 执行时间
    - last_execution_result: 详细执行结果（JSON）
    """
    if not case_results:
        return

    try:
        result_map = {r["case_id"]: r for r in case_results}
        now = datetime.now()

        with db_session() as session:
            case_mapper = TestCaseMapper()
            entity = case_mapper.entity_class

            success_count = 0
            failed_count = 0

            for case in execution_cases:
                result = result_map.get(case.db_id)
                if result is None:
                    continue

                status = result.get("status", "failed")
                # 将 allure 状态映射为 DB 状态
                db_status = "success" if status == "passed" else "failed"

                if db_status == "success":
                    success_count += 1
                else:
                    failed_count += 1

                # 构造详细执行结果
                execution_detail = {
                    "execution_time": now.isoformat(),
                    "status": db_status,
                    "case_name": result.get("case_name", ""),
                    "message": result.get("message", ""),
                    "duration_ms": result.get("duration_ms", 0),
                    # 响应 body：失败取 fail_response，成功取 success_response（仅当配置了 extract_fields 时有值）
                    "response_body": result.get("fail_response") or result.get("success_response") or "",
                    # 提取字段结果
                    "extract_fields": result.get("extract_fields") or {},
                }

                session.query(entity).filter(
                    entity.id == case.db_id
                ).update(
                    {
                        "last_execution_status": db_status,
                        "last_execution_time": now,
                        "last_execution_result": execution_detail,
                    },
                    synchronize_session=False
                )

        logger.info("【回写DB】成功回写 %d 条执行状态（成功=%d, 失败=%d）",
                    len(execution_cases), success_count, failed_count)
    except Exception as e:
        logger.warning("【回写DB】回写执行状态失败: %s", e)
