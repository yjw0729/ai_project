"""
断言验证器模块

提供多种断言验证器:
- StatusCodeValidator: HTTP状态码验证
- JsonPathValidator: JSON路径验证
- ContainsValidator: 包含验证
- SchemaValidator: JSON Schema验证
- ResponseTimeValidator: 响应时间验证
- HeaderValidator: 响应头验证
"""

import json
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False

try:
    from jsonpath_ng import parse as jsonpath_parse
    JSONPATH_AVAILABLE = True
except ImportError:
    JSONPATH_AVAILABLE = False


class AssertionResult:
    """断言结果类"""

    def __init__(
        self,
        passed: bool,
        assertion_type: str,
        message: str,
        expected: Any = None,
        actual: Any = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.passed = passed
        self.assertion_type = assertion_type
        self.message = message
        self.expected = expected
        self.actual = actual
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "type": self.assertion_type,
            "message": self.message,
            "expected": self.expected,
            "actual": self.actual,
            "details": self.details,
        }

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"<AssertionResult {status}: {self.assertion_type} - {self.message}>"


class BaseValidator(ABC):
    """断言验证器基类"""

    def __init__(self, assertion_config: Dict[str, Any]):
        self.config = assertion_config
        self.assertion_type = assertion_config.get("type", "")

    @abstractmethod
    def validate(self, response: Any) -> AssertionResult:
        pass

    def _get_status_code(self, response: Any) -> int:
        if hasattr(response, "status_code"):
            return response.status_code
        if isinstance(response, dict):
            return response.get("status_code", 0)
        return 0

    def _get_body(self, response: Any) -> Any:
        if hasattr(response, "json"):
            try:
                return response.json()
            except Exception:
                pass
        if hasattr(response, "text"):
            text = response.text
            try:
                return json.loads(text)
            except Exception:
                return text
        if isinstance(response, dict):
            return response.get("body", response)
        return response

    def _get_headers(self, response: Any) -> Dict[str, str]:
        if hasattr(response, "headers"):
            return dict(response.headers)
        if isinstance(response, dict):
            return response.get("headers", {})
        return {}


class StatusCodeValidator(BaseValidator):
    """HTTP状态码验证器"""

    def validate(self, response: Any) -> AssertionResult:
        expected = self.config.get("expected")
        actual = self._get_status_code(response)
        if isinstance(expected, list):
            passed = actual in expected
            message = f"状态码 {actual} 是否在期望列表 {expected} 中"
        else:
            passed = actual == expected
            message = f"状态码 {actual} 是否等于期望值 {expected}"
        return AssertionResult(
            passed=passed,
            assertion_type=self.assertion_type,
            message=message,
            expected=expected,
            actual=actual,
        )


class JsonPathValidator(BaseValidator):
    """JSON路径验证器"""

    def validate(self, response: Any) -> AssertionResult:
        path = self.config.get("path", "")
        expected = self.config.get("expected")
        body = self._get_body(response)

        if not JSONPATH_AVAILABLE:
            return AssertionResult(
                passed=False,
                assertion_type=self.assertion_type,
                message="jsonpath 库未安装，请运行: pip install jsonpath-ng",
                expected=expected,
                actual=None,
            )

        try:
            expr = jsonpath_parse(path)
            matches = expr.find(body)
            if not matches:
                return AssertionResult(
                    passed=False,
                    assertion_type=self.assertion_type,
                    message=f"JSONPath {path} 未匹配到任何内容",
                    expected=expected,
                    actual=None,
                )

            actual = matches[0].value if len(matches) == 1 else [m.value for m in matches]

            if isinstance(expected, dict) and isinstance(actual, dict):
                passed = actual == expected
            elif isinstance(expected, (list, tuple)) and isinstance(actual, (list, tuple)):
                passed = set(actual) == set(expected)
            else:
                passed = actual == expected

            message = f"JSONPath {path} 的值 {actual} 是否等于期望值 {expected}"

            return AssertionResult(
                passed=passed,
                assertion_type=self.assertion_type,
                message=message,
                expected=expected,
                actual=actual,
            )
        except Exception as e:
            return AssertionResult(
                passed=False,
                assertion_type=self.assertion_type,
                message=f"JSONPath {path} 验证失败: {str(e)}",
                expected=expected,
                actual=None,
                details={"error": str(e)},
            )


class ContainsValidator(BaseValidator):
    """包含验证器"""

    def validate(self, response: Any) -> AssertionResult:
        expected = self.config.get("expected")
        body = self._get_body(response)
        if isinstance(body, (dict, list)):
            body_str = json.dumps(body, ensure_ascii=False)
        else:
            body_str = str(body)
        case_sensitive = self.config.get("case_sensitive", True)
        if case_sensitive:
            passed = expected in body_str
        else:
            passed = expected.lower() in body_str.lower()
        message = f"响应内容{'不' if not passed else ''}包含 '{expected}'"
        return AssertionResult(
            passed=passed,
            assertion_type=self.assertion_type,
            message=message,
            expected=expected,
            actual=body_str[:200] if len(body_str) > 200 else body_str,
        )


class SchemaValidator(BaseValidator):
    """JSON Schema验证器"""

    def validate(self, response: Any) -> AssertionResult:
        expected_schema = self.config.get("schema")
        body = self._get_body(response)
        if not JSONSCHEMA_AVAILABLE:
            return AssertionResult(
                passed=False,
                assertion_type=self.assertion_type,
                message="jsonschema 库未安装，请运行: pip install jsonschema",
                expected=expected_schema,
                actual=body,
            )
        if expected_schema is None:
            return AssertionResult(
                passed=False,
                assertion_type=self.assertion_type,
                message="Schema验证缺少 schema 配置",
                expected=expected_schema,
                actual=body,
            )
        try:
            jsonschema.validate(instance=body, schema=expected_schema)
            return AssertionResult(
                passed=True,
                assertion_type=self.assertion_type,
                message="响应符合JSON Schema",
                expected=expected_schema,
                actual=body,
            )
        except jsonschema.ValidationError as e:
            return AssertionResult(
                passed=False,
                assertion_type=self.assertion_type,
                message=f"Schema验证失败: {e.message}",
                expected=expected_schema,
                actual=body,
                details={"validation_error": str(e)},
            )
        except Exception as e:
            return AssertionResult(
                passed=False,
                assertion_type=self.assertion_type,
                message=f"Schema验证异常: {str(e)}",
                expected=expected_schema,
                actual=body,
                details={"error": str(e)},
            )


class ResponseTimeValidator(BaseValidator):
    """响应时间验证器"""

    def validate(self, response: Any) -> AssertionResult:
        max_ms = self.config.get("max_ms")
        actual_ms = self.config.get("response_time_ms")
        if actual_ms is None:
            return AssertionResult(
                passed=False,
                assertion_type=self.assertion_type,
                message="响应时间未记录",
                expected=max_ms,
                actual=None,
            )
        passed = actual_ms <= max_ms
        message = f"响应时间 {actual_ms}ms {'小于等于' if passed else '大于'} 阈值 {max_ms}ms"
        return AssertionResult(
            passed=passed,
            assertion_type=self.assertion_type,
            message=message,
            expected=max_ms,
            actual=actual_ms,
        )


class HeaderValidator(BaseValidator):
    """响应头验证器"""

    def validate(self, response: Any) -> AssertionResult:
        header_name = self.config.get("header")
        expected = self.config.get("expected")
        headers = self._get_headers(response)
        actual = headers.get(header_name)
        if actual is None:
            return AssertionResult(
                passed=False,
                assertion_type=self.assertion_type,
                message=f"响应头 {header_name} 不存在",
                expected=expected,
                actual=None,
            )
        if isinstance(expected, list):
            passed = actual in expected
            message = f"响应头 {header_name}={actual} 是否在期望列表 {expected} 中"
        else:
            if self.config.get("case_sensitive", True):
                passed = actual == expected
            else:
                passed = actual.lower() == expected.lower()
            message = f"响应头 {header_name}={actual} {'等于' if passed else '不等于'} {expected}"
        return AssertionResult(
            passed=passed,
            assertion_type=self.assertion_type,
            message=message,
            expected=expected,
            actual=actual,
        )


class RegexValidator(BaseValidator):
    """正则表达式验证器"""

    def validate(self, response: Any) -> AssertionResult:
        pattern = self.config.get("pattern")
        body = self._get_body(response)
        if isinstance(body, (dict, list)):
            body_str = json.dumps(body, ensure_ascii=False)
        else:
            body_str = str(body)
        try:
            regex = re.compile(pattern)
            match = regex.search(body_str)
            passed = match is not None
            message = f"响应{'匹配' if passed else '不匹配'}正则表达式 {pattern}"
            actual = match.group(0) if match else None
        except re.error as e:
            passed = False
            message = f"正则表达式错误: {str(e)}"
            actual = None
        return AssertionResult(
            passed=passed,
            assertion_type=self.assertion_type,
            message=message,
            expected=pattern,
            actual=actual,
        )


class LengthValidator(BaseValidator):
    """长度验证器"""

    def validate(self, response: Any) -> AssertionResult:
        min_length = self.config.get("min")
        max_length = self.config.get("max")
        path = self.config.get("path")
        body = self._get_body(response)

        if path:
            if JSONPATH_AVAILABLE:
                expr = jsonpath_parse(path)
                matches = expr.find(body)
                if matches:
                    actual = matches[0].value if len(matches) == 1 else [m.value for m in matches]
                else:
                    actual = None
            else:
                return AssertionResult(
                    passed=False,
                    assertion_type=self.assertion_type,
                    message="jsonpath 库未安装",
                    expected={"min": min_length, "max": max_length},
                    actual=None,
                )
        else:
            if isinstance(body, (dict, list)):
                actual = len(body)
            else:
                actual = len(str(body))

        if actual is None:
            return AssertionResult(
                passed=False,
                assertion_type=self.assertion_type,
                message=f"JSONPath {path} 未匹配到内容",
                expected={"min": min_length, "max": max_length},
                actual=None,
            )

        if min_length is not None and max_length is not None:
            passed = min_length <= actual <= max_length
            message = f"长度 {actual} 是否在范围 [{min_length}, {max_length}] 内"
        elif min_length is not None:
            passed = actual >= min_length
            message = f"长度 {actual} 是否大于等于 {min_length}"
        elif max_length is not None:
            passed = actual <= max_length
            message = f"长度 {actual} 是否小于等于 {max_length}"
        else:
            passed = False
            message = "长度验证缺少 min 或 max 配置"

        return AssertionResult(
            passed=passed,
            assertion_type=self.assertion_type,
            message=message,
            expected={"min": min_length, "max": max_length},
            actual=actual,
        )


class TypeValidator(BaseValidator):
    """类型验证器"""

    TYPE_MAPPING = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
    }

    def validate(self, response: Any) -> AssertionResult:
        expected_type = self.config.get("expected")
        path = self.config.get("path")
        body = self._get_body(response)

        if path:
            if JSONPATH_AVAILABLE:
                expr = jsonpath_parse(path)
                matches = expr.find(body)
                if matches:
                    actual_value = matches[0].value if len(matches) == 1 else [m.value for m in matches]
                else:
                    actual_value = None
            else:
                return AssertionResult(
                    passed=False,
                    assertion_type=self.assertion_type,
                    message="jsonpath 库未安装",
                    expected=expected_type,
                    actual=None,
                )
        else:
            actual_value = body

        if actual_value is None:
            return AssertionResult(
                passed=False,
                assertion_type=self.assertion_type,
                message=f"JSONPath {path} 未匹配到内容",
                expected=expected_type,
                actual=None,
            )

        expected_python_type = self.TYPE_MAPPING.get(expected_type)
        if expected_python_type is None:
            return AssertionResult(
                passed=False,
                assertion_type=self.assertion_type,
                message=f"未知的类型: {expected_type}",
                expected=expected_type,
                actual=type(actual_value).__name__,
            )

        passed = isinstance(actual_value, expected_python_type)
        message = f"类型 {type(actual_value).__name__} {'等于' if passed else '不等于'} 期望类型 {expected_type}"
        return AssertionResult(
            passed=passed,
            assertion_type=self.assertion_type,
            message=message,
            expected=expected_type,
            actual=type(actual_value).__name__,
        )


class NotEmptyValidator(BaseValidator):
    """非空验证器"""

    def validate(self, response: Any) -> AssertionResult:
        path = self.config.get("path")
        body = self._get_body(response)

        if path:
            if JSONPATH_AVAILABLE:
                expr = jsonpath_parse(path)
                matches = expr.find(body)
                if matches:
                    actual_value = matches[0].value if len(matches) == 1 else [m.value for m in matches]
                else:
                    actual_value = None
            else:
                return AssertionResult(
                    passed=False,
                    assertion_type=self.assertion_type,
                    message="jsonpath 库未安装",
                    expected="not empty",
                    actual=None,
                )
        else:
            actual_value = body

        if actual_value is None:
            passed = False
        elif isinstance(actual_value, (str, list, dict)):
            passed = len(actual_value) > 0
        else:
            passed = actual_value is not None

        message = f"值 {'非空' if passed else '为空'}"
        return AssertionResult(
            passed=passed,
            assertion_type=self.assertion_type,
            message=message,
            expected="not empty",
            actual=actual_value,
        )


class AssertionExecutor:
    """断言执行器"""

    VALIDATORS = {
        "status_code": StatusCodeValidator,
        "json_path": JsonPathValidator,
        "contains": ContainsValidator,
        "schema": SchemaValidator,
        "response_time": ResponseTimeValidator,
        "header": HeaderValidator,
        "regex": RegexValidator,
        "length": LengthValidator,
        "type": TypeValidator,
        "not_empty": NotEmptyValidator,
    }

    def __init__(self, assertions: Optional[List[Dict[str, Any]]] = None):
        self.assertions = assertions or []

    def add_assertion(self, assertion: Dict[str, Any]) -> None:
        self.assertions.append(assertion)

    def execute(
        self,
        response: Any,
        response_time_ms: Optional[float] = None,
    ) -> List[AssertionResult]:
        results = []
        for assertion in self.assertions:
            assertion_type = assertion.get("type")
            if assertion_type == "response_time" and response_time_ms is not None:
                assertion = assertion.copy()
                assertion["response_time_ms"] = response_time_ms
            validator_class = self.VALIDATORS.get(assertion_type)
            if validator_class is None:
                results.append(
                    AssertionResult(
                        passed=False,
                        assertion_type=assertion_type,
                        message=f"未知的断言类型: {assertion_type}",
                        expected=assertion.get("expected"),
                        actual=None,
                    )
                )
                continue
            try:
                validator = validator_class(assertion)
                result = validator.validate(response)
                results.append(result)
            except Exception as e:
                results.append(
                    AssertionResult(
                        passed=False,
                        assertion_type=assertion_type,
                        message=f"断言执行异常: {str(e)}",
                        expected=assertion.get("expected"),
                        actual=None,
                        details={"error": str(e)},
                    )
                )
        return results

    def execute_single(
        self,
        response: Any,
        assertion: Dict[str, Any],
        response_time_ms: Optional[float] = None,
    ) -> AssertionResult:
        assertion_copy = assertion.copy()
        if assertion_copy.get("type") == "response_time" and response_time_ms is not None:
            assertion_copy["response_time_ms"] = response_time_ms
        assertion_type = assertion_copy.get("type")
        validator_class = self.VALIDATORS.get(assertion_type)
        if validator_class is None:
            return AssertionResult(
                passed=False,
                assertion_type=assertion_type,
                message=f"未知的断言类型: {assertion_type}",
                expected=assertion_copy.get("expected"),
                actual=None,
            )
        try:
            validator = validator_class(assertion_copy)
            return validator.validate(response)
        except Exception as e:
            return AssertionResult(
                passed=False,
                assertion_type=assertion_type,
                message=f"断言执行异常: {str(e)}",
                expected=assertion_copy.get("expected"),
                actual=None,
                details={"error": str(e)},
            )

    def all_passed(self, results: List[AssertionResult]) -> bool:
        return all(result.passed for result in results)

    def get_failed_results(self, results: List[AssertionResult]) -> List[AssertionResult]:
        return [result for result in results if not result.passed]

    def get_summary(self, results: List[AssertionResult]) -> Dict[str, Any]:
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "all_passed": failed == 0,
            "results": [r.to_dict() for r in results],
        }
