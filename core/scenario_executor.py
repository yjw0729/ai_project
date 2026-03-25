"""
场景测试执行器

用于执行多步骤的业务场景测试用例
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from jsonpath_ng import parse as jsonpath_parse
    JSONPATH_AVAILABLE = True
except ImportError:
    JSONPATH_AVAILABLE = False


from mock_service.server import MockServer, MockRule
from assertion.validators import AssertionExecutor
from parametrize.driver import VariableReplacer


class ScenarioStepResult:
    """场景步骤执行结果"""
    def __init__(
        self,
        step_number: int,
        description: str,
        success: bool,
        request: Dict[str, Any] = None,
        response: Any = None,
        response_body: Any = None,
        status_code: int = 0,
        elapsed_ms: float = 0,
        extracted_data: Dict[str, Any] = None,
        errors: List[str] = None
    ):
        self.step_number = step_number
        self.description = description
        self.success = success
        self.request = request or {}
        self.response = response
        self.response_body = response_body
        self.status_code = status_code
        self.elapsed_ms = elapsed_ms
        self.extracted_data = extracted_data or {}
        self.errors = errors or []

    @property
    def passed(self) -> bool:
        return self.success


class ScenarioExecutionResult:
    """场景执行结果"""
    def __init__(
        self,
        scenario_name: str,
        case_title: str,
        success: bool,
        total_steps: int,
        passed_steps: int = 0,
        failed_steps: int = 0,
        step_results: List[ScenarioStepResult] = None,
        elapsed_ms: float = 0,
        errors: List[str] = None
    ):
        self.scenario_name = scenario_name
        self.case_title = case_title
        self.success = success
        self.total_steps = total_steps
        self.passed_steps = passed_steps
        self.failed_steps = failed_steps
        self.step_results = step_results or []
        self.elapsed_ms = elapsed_ms
        self.errors = errors or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "case_title": self.case_title,
            "success": self.success,
            "total_steps": self.total_steps,
            "passed_steps": self.passed_steps,
            "failed_steps": self.failed_steps,
            "step_results": [
                {
                    "step_number": r.step_number,
                    "description": r.description,
                    "success": r.success,
                    "status_code": r.status_code,
                    "elapsed_ms": r.elapsed_ms,
                    "extracted_data": r.extracted_data,
                    "errors": r.errors
                }
                for r in self.step_results
            ],
            "elapsed_ms": self.elapsed_ms,
            "errors": self.errors
        }


class ScenarioTestExecutor:
    """
    场景测试执行器

    用于执行包含多个步骤的业务场景测试用例

    使用示例:
        executor = ScenarioTestExecutor(base_url="http://api.example.com")

        # 方式1: 从场景用例执行
        result = executor.execute_scenario({
            "scenario_name": "用户下单流程",
            "test_steps": [
                {
                    "step_number": 1,
                    "description": "用户登录",
                    "api": "POST /api/v1/login",
                    "body": {"username": "test", "password": "123"},
                    "extract": {"token": "$.data.token"}
                },
                {
                    "step_number": 2,
                    "description": "查询商品",
                    "api": "GET /api/v1/products",
                    "headers": {"Authorization": "{{token}}"}
                }
            ]
        })

        # 方式2: 执行步骤列表
        steps = [...]
        result = executor.execute_steps(steps)

        # 方式3: 使用上下文数据
        executor.set_context_data({"user_id": 123})
        result = executor.execute_scenario(scenario)
    """

    def __init__(
        self,
        base_url: str = "",
        default_headers: Dict[str, str] = None,
        timeout: int = 30,
        mock_server: MockServer = None
    ):
        self.base_url = base_url.rstrip("/")
        self.default_headers = default_headers or {}
        self.timeout = timeout
        self.mock_server = mock_server

        # 上下文数据（用于步骤间数据传递）
        self.context_data: Dict[str, Any] = {}

        # 变量替换器
        self.variable_replacer = VariableReplacer()

        # HTTP 客户端
        self.session = requests.Session() if REQUESTS_AVAILABLE else None

    def set_context_data(self, data: Dict[str, Any]) -> None:
        """设置上下文数据"""
        self.context_data.update(data)

    def get_context_data(self, key: str, default: Any = None) -> Any:
        """获取上下文数据"""
        return self.context_data.get(key, default)

    def clear_context_data(self) -> None:
        """清空上下文数据"""
        self.context_data.clear()

    def _replace_variables(self, text: Any) -> Any:
        """替换变量"""
        if isinstance(text, str):
            return self.variable_replacer.replace(text, self.context_data)
        elif isinstance(text, dict):
            return {k: self._replace_variables(v) for k, v in text.items()}
        elif isinstance(text, list):
            return [self._replace_variables(item) for item in text]
        return text

    def _extract_data(self, response_body: Any, extract_rules: Dict[str, str]) -> Dict[str, Any]:
        """从响应中提取数据"""
        extracted = {}
        if not extract_rules or not JSONPATH_AVAILABLE:
            return extracted

        for key, jsonpath_expr in extract_rules.items():
            try:
                # 支持 jsonpath 格式
                if jsonpath_expr.startswith("$"):
                    matcher = jsonpath_parse(jsonpath_expr)
                    matches = matcher.find(response_body)
                    if matches:
                        extracted[key] = matches[0].value
                else:
                    # 简单 key 提取
                    if isinstance(response_body, dict):
                        extracted[key] = response_body.get(jsonpath_expr)
            except Exception as e:
                logger.warning(f"提取数据失败: {key} = {jsonpath_expr}, error: {e}")

        return extracted

    def _execute_step(self, step: Dict[str, Any]) -> ScenarioStepResult:
        """执行单个步骤"""
        step_number = step.get("step_number", 1)
        description = step.get("description", "")
        api = step.get("api", "")

        # 解析 API 信息
        parts = api.split()
        if len(parts) >= 2:
            method = parts[0].upper()
            path = parts[1]
        elif len(parts) == 1:
            method = "GET"
            path = parts[0]
        else:
            return ScenarioStepResult(
                step_number=step_number,
                description=description,
                success=False,
                errors=["无效的 API 格式"]
            )

        # 替换变量
        path = self._replace_variables(path)
        headers = self._replace_variables(step.get("headers", {}))
        query = self._replace_variables(step.get("query", {}))
        body = self._replace_variables(step.get("body", {}))

        # 合并请求头
        request_headers = {**self.default_headers, **headers}

        # 构建请求
        url = urljoin(self.base_url + "/", path.lstrip("/"))

        request_info = {
            "method": method,
            "url": url,
            "headers": request_headers,
            "params": query,
            "json": body if method in ["POST", "PUT", "PATCH"] else None
        }

        result = ScenarioStepResult(
            step_number=step_number,
            description=description,
            success=False,
            request=request_info
        )

        # 检查 Mock Server
        if self.mock_server:
            mock_result = self.mock_server.match_request(method, path)
            if mock_result:
                response = self.mock_server.get_response(mock_result)
                result.status_code = response.get("status", 200)
                result.response_body = response.get("body")
                result.success = result.status_code < 400
                if result.success:
                    extracted = self._extract_data(result.response_body, step.get("extract", {}))
                    result.extracted_data = extracted
                    self.context_data.update(extracted)
                return result

        # 发送 HTTP 请求
        if not REQUESTS_AVAILABLE or not self.session:
            result.errors.append("requests 库不可用")
            return result

        try:
            start_time = time.time()

            if method == "GET":
                response = self.session.get(url, headers=request_headers, params=query, timeout=self.timeout)
            elif method == "POST":
                response = self.session.post(url, headers=request_headers, json=body, timeout=self.timeout)
            elif method == "PUT":
                response = self.session.put(url, headers=request_headers, json=body, timeout=self.timeout)
            elif method == "PATCH":
                response = self.session.patch(url, headers=request_headers, json=body, timeout=self.timeout)
            elif method == "DELETE":
                response = self.session.delete(url, headers=request_headers, timeout=self.timeout)
            else:
                result.errors.append(f"不支持的 HTTP 方法: {method}")
                return result

            result.elapsed_ms = (time.time() - start_time) * 1000
            result.status_code = response.status_code
            result.response = response

            try:
                result.response_body = response.json()
            except:
                result.response_body = response.text

            result.success = response.status_code < 400

            # 提取数据
            if result.success:
                extracted = self._extract_data(result.response_body, step.get("extract", {}))
                result.extracted_data = extracted
                self.context_data.update(extracted)

        except Exception as e:
            result.errors.append(f"请求异常: {str(e)}")
            logger.error(f"步骤 {step_number} 执行失败: {e}")

        return result

    def execute_step(self, step: Dict[str, Any]) -> ScenarioStepResult:
        """执行单个步骤（公开方法）"""
        return self._execute_step(step)

    def execute_steps(self, steps: List[Dict[str, Any]]) -> ScenarioExecutionResult:
        """执行步骤列表"""
        if not steps:
            return ScenarioExecutionResult(
                scenario_name="",
                case_title="",
                success=False,
                total_steps=0,
                errors=["步骤列表为空"]
            )

        # 按步骤号排序
        sorted_steps = sorted(steps, key=lambda x: x.get("step_number", 0))

        # 设置初始上下文
        self.clear_context_data()

        scenario_name = ""
        case_title = ""

        start_time = time.time()
        step_results = []
        passed_count = 0
        failed_count = 0
        errors = []

        for step in sorted_steps:
            scenario_name = step.get("scenario_name", scenario_name)
            case_title = step.get("title", case_title)

            result = self._execute_step(step)
            step_results.append(result)

            if result.success:
                passed_count += 1
            else:
                failed_count += 1
                errors.append(f"步骤 {result.step_number} 失败: {', '.join(result.errors)}")

        elapsed_ms = (time.time() - start_time) * 1000

        return ScenarioExecutionResult(
            scenario_name=scenario_name,
            case_title=case_title,
            success=failed_count == 0,
            total_steps=len(sorted_steps),
            passed_steps=passed_count,
            failed_steps=failed_count,
            step_results=step_results,
            elapsed_ms=elapsed_ms,
            errors=errors
        )

    def execute_scenario(self, scenario: Dict[str, Any]) -> ScenarioExecutionResult:
        """执行场景测试用例"""
        steps = scenario.get("test_steps", [])
        return self.execute_steps(steps)

    def execute_with_api_case(
        self,
        case: Dict[str, Any],
        base_url: str = None
    ) -> ScenarioExecutionResult:
        """执行标准接口测试用例（转换为场景执行）"""
        if base_url:
            self.base_url = base_url.rstrip("/")

        # 构建步骤
        request = case.get("request", {})
        if isinstance(request, str):
            # 简单格式: "POST /api/v1/login"
            api = request
            body = {}
            headers = {}
        else:
            api = f"{request.get('method', 'GET')} {request.get('path', '/')}"
            body = request.get("body", {})
            headers = request.get("headers", {})

        steps = [{
            "step_number": 1,
            "description": case.get("description", case.get("title", "执行接口")),
            "api": api,
            "headers": headers,
            "body": body,
            "extract": {},
            "expected_results": case.get("expected_results", [])
        }]

        return self.execute_steps(steps)


# pytest 集成
def pytest_execute_scenario(scenario: Dict[str, Any], base_url: str = None, fail_fast: bool = False):
    """
    pytest 场景执行函数

    使用示例:
        def test_order_flow():
            scenario = {
                "scenario_name": "下单流程",
                "title": "正常下单",
                "test_steps": [...]
            }
            result = pytest_execute_scenario(scenario, base_url="http://localhost:5000")
            assert result.success, f"场景执行失败: {result.errors}"
    """
    executor = ScenarioTestExecutor(base_url=base_url or "")

    if fail_fast:
        # 失败快速停止模式
        steps = scenario.get("test_steps", [])
        for step in steps:
            result = executor.execute_step(step)
            if not result.success:
                raise AssertionError(f"步骤 {result.step_number} 失败: {', '.join(result.errors)}")
        return True

    result = executor.execute_scenario(scenario)
    return result
