"""
[DEPRECATED] 请使用 assertion/validators.py 的 AssertionExecutor
此模块将在未来版本中移除
"""

"""
API自动化测试 - 断言引擎
支持多种断言类型：状态码、响应字段、正则、时间等
"""

import re
import json
import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AssertionResult:
    """断言结果"""
    name: str
    passed: bool
    expected: Any
    actual: Any
    message: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "expected": self.expected,
            "actual": self.actual,
            "message": self.message,
            "error": self.error,
        }


class AssertionEngine:
    """断言引擎"""

    # 内置断言类型
    SUPPORTED_ASSERTIONS = [
        "status_code",      # HTTP状态码
        "equals",           # 精确相等
        "not_equals",       # 不相等
        "contains",         # 包含
        "not_contains",     # 不包含
        "regex",            # 正则匹配
        "json_path",        # JSON路径断言
        "response_time",    # 响应时间
        "schema",           # JSON Schema验证
        "header",           # 响应头断言
        "type_check",       # 类型检查
        "length",           # 长度检查
        "greater_than",     # 大于
        "less_than",        # 小于
        "in_list",          # 在列表中
        "not_in_list",      # 不在列表中
    ]

    def __init__(self):
        self.results: List[AssertionResult] = []

    def reset(self) -> None:
        """重置断言结果"""
        self.results = []

    def assert_all(self, response: Any, assertions: List[Union[str, Dict]]) -> List[AssertionResult]:
        """
        执行所有断言。
        response: 响应对象（requests.Response或dict）
        assertions: 断言列表，支持字符串和字典格式
        """
        self.reset()

        # 将响应对象转换为可访问的字典
        resp_dict = self._normalize_response(response)
        response_time = getattr(response, "elapsed", None)
        status_code = getattr(response, "status_code", None)
        headers = getattr(response, "headers", {})

        for assertion in assertions:
            try:
                result = self._execute_assertion(
                    assertion, resp_dict, status_code, response_time, headers
                )
                self.results.append(result)
            except Exception as e:
                logger.error("【断言执行】断言 %s 执行异常: %s", assertion, str(e))
                self.results.append(AssertionResult(
                    name=str(assertion),
                    passed=False,
                    expected=None,
                    actual=None,
                    error=str(e)
                ))

        passed_count = sum(1 for r in self.results if r.passed)
        logger.info("【断言执行】完成，总数=%d, 通过=%d, 失败=%d",
                    len(self.results), passed_count, len(self.results) - passed_count)

        return self.results

    def _normalize_response(self, response: Any) -> Dict[str, Any]:
        """将响应标准化为字典"""
        if isinstance(response, dict):
            return response
        if hasattr(response, "json"):
            try:
                return response.json()
            except Exception:
                pass
        if hasattr(response, "text"):
            try:
                return {"_raw_text": response.text}
            except Exception:
                pass
        return {"_raw": str(response)}

    def _execute_assertion(
        self,
        assertion: Union[str, Dict],
        resp_dict: Dict[str, Any],
        status_code: Optional[int],
        response_time: Optional[float],
        headers: Dict[str, str]
    ) -> AssertionResult:
        """执行单个断言"""
        # 字符串格式: "status_code == 200" 或 "response.code == 0"
        if isinstance(assertion, str):
            return self._parse_string_assertion(assertion, resp_dict, status_code, response_time)

        # 字典格式: {"type": "equals", "path": "code", "expected": 0}
        if isinstance(assertion, dict):
            assert_type = assertion.get("type", "equals")
            return self._execute_typed_assertion(assertion, resp_dict, status_code, response_time, headers)

        return AssertionResult(
            name=str(assertion),
            passed=False,
            expected=None,
            actual=None,
            error="Unsupported assertion format"
        )

    def _parse_string_assertion(
        self,
        assertion_str: str,
        resp_dict: Dict[str, Any],
        status_code: Optional[int],
        response_time: Optional[float]
    ) -> AssertionResult:
        """解析字符串格式的断言"""
        assertion_str = assertion_str.strip()

        # status_code == 200
        if re.match(r'^status_code\s*(==|!=|>|<|>=|<=)\s*\d+$', assertion_str):
            return self._parse_status_code_assertion(assertion_str, status_code)

        # response_time < 1000
        if re.match(r'^response_time\s*(==|!=|>|<|>=|<=)\s*\d+$', assertion_str):
            return self._parse_response_time_assertion(assertion_str, response_time)

        # response.xxx == value
        if '==' in assertion_str:
            parts = assertion_str.split('==')
            path = parts[0].strip()
            expected_str = ''.join(parts[1:]).strip()
            return self._assert_json_path(path, expected_str, resp_dict, operator='==')

        # response.xxx != value
        if '!=' in assertion_str:
            parts = assertion_str.split('!=')
            path = parts[0].strip()
            expected_str = ''.join(parts[1:]).strip()
            return self._assert_json_path(path, expected_str, resp_dict, operator='!=')

        return AssertionResult(
            name=assertion_str,
            passed=False,
            expected=None,
            actual=None,
            error="无法解析断言字符串"
        )

    def _parse_status_code_assertion(self, assertion_str: str, status_code: Optional[int]) -> AssertionResult:
        """解析状态码断言"""
        match = re.match(r'^status_code\s*(==|!=|>|<|>=|<=)\s*(\d+)$', assertion_str)
        if not match:
            return AssertionResult(name=assertion_str, passed=False, expected=None, actual=None)

        operator = match.group(1)
        expected = int(match.group(2))

        if status_code is None:
            return AssertionResult(
                name=assertion_str, passed=False, expected=expected, actual=None,
                error="响应对象无status_code"
            )

        passed = self._compare_values(status_code, expected, operator)
        return AssertionResult(
            name=assertion_str,
            passed=passed,
            expected=f"status_code{operator}{expected}",
            actual=status_code,
            message="通过" if passed else f"预期状态码{expected}，实际{status_code}"
        )

    def _parse_response_time_assertion(self, assertion_str: str, response_time: Optional[float]) -> AssertionResult:
        """解析响应时间断言"""
        match = re.match(r'^response_time\s*(==|!=|>|<|>=|<=)\s*(\d+)$', assertion_str)
        if not match:
            return AssertionResult(name=assertion_str, passed=False, expected=None, actual=None)

        operator = match.group(1)
        expected = int(match.group(2))

        if response_time is None:
            return AssertionResult(
                name=assertion_str, passed=False, expected=f"{expected}ms", actual=None,
                error="响应对象无elapsed时间"
            )

        actual_ms = int(response_time * 1000)
        passed = self._compare_values(actual_ms, expected, operator)
        return AssertionResult(
            name=assertion_str,
            passed=passed,
            expected=f"{expected}ms",
            actual=f"{actual_ms}ms",
            message="通过" if passed else f"预期响应时间{expected}ms，实际{actual_ms}ms"
        )

    def _execute_typed_assertion(
        self,
        assertion: Dict[str, Any],
        resp_dict: Dict[str, Any],
        status_code: Optional[int],
        response_time: Optional[float],
        headers: Dict[str, str]
    ) -> AssertionResult:
        """执行字典格式的断言"""
        assert_type = assertion.get("type", "equals")

        if assert_type == "status_code":
            expected = assertion.get("expected", 200)
            return self._assert_equals(status_code, expected, f"status_code")

        elif assert_type == "equals":
            path = assertion.get("path", "")
            expected = assertion.get("expected")
            name = assertion.get("name", path)
            return self._assert_json_path(path, expected, resp_dict, operator='==')

        elif assert_type == "not_equals":
            path = assertion.get("path", "")
            expected = assertion.get("expected")
            name = assertion.get("name", f"not_equals:{path}")
            return self._assert_json_path(path, expected, resp_dict, operator='!=')

        elif assert_type == "contains":
            path = assertion.get("path", "")
            expected = assertion.get("expected", "")
            name = assertion.get("name", f"contains:{path}")
            return self._assert_contains(resp_dict, path, expected, name)

        elif assert_type == "regex":
            path = assertion.get("path", "")
            pattern = assertion.get("pattern", "")
            name = assertion.get("name", f"regex:{path}")
            return self._assert_regex(resp_dict, path, pattern, name)

        elif assert_type == "response_time":
            expected = assertion.get("expected", 1000)
            operator = assertion.get("operator", "<")
            name = assertion.get("name", "response_time")
            actual_ms = int(response_time * 1000) if response_time else None
            passed = self._compare_values(actual_ms, expected, operator) if actual_ms is not None else False
            return AssertionResult(
                name=name, passed=passed,
                expected=f"{expected}ms", actual=f"{actual_ms}ms" if actual_ms else None
            )

        elif assert_type == "header":
            header_name = assertion.get("header", "")
            expected = assertion.get("expected")
            name = assertion.get("name", f"header:{header_name}")
            actual = headers.get(header_name, headers.get(header_name.lower(), headers.get(header_name.upper())))
            passed = actual == expected
            return AssertionResult(
                name=name, passed=passed, expected=expected, actual=actual
            )

        elif assert_type == "json_path":
            path = assertion.get("path", "")
            expected = assertion.get("expected")
            operator = assertion.get("operator", "==")
            name = assertion.get("name", path)
            return self._assert_json_path(path, expected, resp_dict, operator)

        elif assert_type == "in_list":
            path = assertion.get("path", "")
            values = assertion.get("values", [])
            name = assertion.get("name", f"in_list:{path}")
            actual = self._get_json_path_value(resp_dict, path)
            passed = actual in values
            return AssertionResult(
                name=name, passed=passed, expected=values, actual=actual
            )

        elif assert_type == "not_in_list":
            path = assertion.get("path", "")
            values = assertion.get("values", [])
            name = assertion.get("name", f"not_in_list:{path}")
            actual = self._get_json_path_value(resp_dict, path)
            passed = actual not in values
            return AssertionResult(
                name=name, passed=passed, expected=f"not in {values}", actual=actual
            )

        elif assert_type == "length":
            path = assertion.get("path", "")
            expected = assertion.get("expected")
            operator = assertion.get("operator", "==")
            name = assertion.get("name", f"length:{path}")
            actual_list = self._get_json_path_value(resp_dict, path)
            actual_len = len(actual_list) if actual_list is not None else None
            passed = self._compare_values(actual_len, expected, operator) if actual_len is not None else False
            return AssertionResult(
                name=name, passed=passed, expected=f"length{operator}{expected}", actual=actual_len
            )

        elif assert_type == "type_check":
            path = assertion.get("path", "")
            expected_type = assertion.get("expected_type", "")
            name = assertion.get("name", f"type:{path}")
            actual_value = self._get_json_path_value(resp_dict, path)
            actual_type = type(actual_value).__name__ if actual_value is not None else "None"
            passed = actual_type.lower() == expected_type.lower()
            return AssertionResult(
                name=name, passed=passed, expected=expected_type, actual=actual_type
            )

        else:
            return AssertionResult(
                name=f"unknown:{assert_type}",
                passed=False, expected=None, actual=None,
                error=f"不支持的断言类型: {assert_type}"
            )

    def _get_json_path_value(self, data: Any, path: str) -> Any:
        """获取JSON路径对应的值"""
        if not path:
            return data

        keys = path.split('.')
        current = data

        for key in keys:
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list):
                try:
                    idx = int(key)
                    current = current[idx]
                except (ValueError, IndexError):
                    return None
            else:
                return None

        return current

    def _assert_json_path(
        self,
        path: str,
        expected: Any,
        resp_dict: Dict[str, Any],
        operator: str = "=="
    ) -> AssertionResult:
        """JSON路径断言"""
        actual = self._get_json_path_value(resp_dict, path)

        # 类型转换
        if actual is not None and expected is not None:
            if isinstance(actual, int) and isinstance(expected, str) and expected.isdigit():
                expected = int(expected)
            elif isinstance(actual, float) and isinstance(expected, str):
                try:
                    expected = float(expected)
                except ValueError:
                    pass

        passed = self._compare_values(actual, expected, operator)

        return AssertionResult(
            name=f"{path} {operator} {expected}",
            passed=passed,
            expected=expected,
            actual=actual,
            message="通过" if passed else f"预期[{expected}]，实际[{actual}]"
        )

    def _assert_equals(self, actual: Any, expected: Any, name: str) -> AssertionResult:
        """相等断言"""
        passed = actual == expected
        return AssertionResult(
            name=name,
            passed=passed,
            expected=expected,
            actual=actual,
            message="通过" if passed else f"预期{expected}，实际{actual}"
        )

    def _assert_contains(self, resp_dict: Dict[str, Any], path: str, expected: Any, name: str) -> AssertionResult:
        """包含断言"""
        actual = self._get_json_path_value(resp_dict, path)
        if actual is None:
            actual_str = ""
        elif isinstance(actual, (dict, list)):
            actual_str = json.dumps(actual, ensure_ascii=False)
        else:
            actual_str = str(actual)

        passed = str(expected) in actual_str
        return AssertionResult(
            name=name,
            passed=passed,
            expected=f"包含 {expected}",
            actual=actual_str[:200],
            message="通过" if passed else f"预期包含'{expected}'，实际'{actual_str[:100]}'"
        )

    def _assert_regex(self, resp_dict: Dict[str, Any], path: str, pattern: str, name: str) -> AssertionResult:
        """正则断言"""
        actual = self._get_json_path_value(resp_dict, path)
        if actual is None:
            actual_str = ""
        else:
            actual_str = str(actual)

        try:
            match = re.search(pattern, actual_str)
            passed = match is not None
            return AssertionResult(
                name=name,
                passed=passed,
                expected=f"匹配 {pattern}",
                actual=actual_str[:200],
                message="通过" if passed else f"正则{pattern}未匹配到{actual_str[:100]}"
            )
        except re.error as e:
            return AssertionResult(
                name=name, passed=False,
                expected=f"匹配 {pattern}", actual=actual_str[:200],
                error=f"正则表达式错误: {e}"
            )

    @staticmethod
    def _compare_values(actual: Any, expected: Any, operator: str) -> bool:
        """比较值"""
        try:
            if operator == "==":
                return actual == expected
            elif operator == "!=":
                return actual != expected
            elif operator == ">":
                return actual > expected
            elif operator == ">=":
                return actual >= expected
            elif operator == "<":
                return actual < expected
            elif operator == "<=":
                return actual <= expected
            else:
                return actual == expected
        except TypeError:
            return False
