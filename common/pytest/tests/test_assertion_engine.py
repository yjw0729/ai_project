"""
断言引擎测试
测试 common/services/assertion/validators.py 中的所有验证器
以及 common/services/assertion_engine.py 的服务封装
"""
import pytest
import json
from unittest.mock import MagicMock
from common.assertion import (
    AssertionExecutor, AssertionResult,
    StatusCodeValidator, JsonPathValidator, ContainsValidator,
    SchemaValidator, ResponseTimeValidator, HeaderValidator,
    RegexValidator, LengthValidator, TypeValidator, NotEmptyValidator
)
from common.services.assertion_engine import AssertionService


# ==================== Mock Response Helper ====================

def make_mock_response(status_code=200, body=None, headers=None, elapsed_ms=100):
    """创建模拟的 requests.Response 对象"""
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {"Content-Type": "application/json"}
    response.elapsed = MagicMock()
    response.elapsed.total_seconds = lambda: elapsed_ms / 1000

    if body is None:
        body = {"code": 0, "message": "success", "data": []}

    if isinstance(body, dict):
        response.json = lambda: body
        response.text = json.dumps(body)
    else:
        response.text = str(body)
        response.json = lambda: {}

    return response


# ==================== StatusCodeValidator Tests ====================

class TestStatusCodeValidator:

    def test_single_status_code_match(self):
        validator = StatusCodeValidator({"type": "status_code", "expected": 200})
        response = make_mock_response(status_code=200)
        result = validator.validate(response)
        assert result.passed is True

    def test_single_status_code_mismatch(self):
        validator = StatusCodeValidator({"type": "status_code", "expected": 200})
        response = make_mock_response(status_code=404)
        result = validator.validate(response)
        assert result.passed is False
        assert result.actual == 404

    def test_multiple_allowed_codes(self):
        validator = StatusCodeValidator({"type": "status_code", "expected": [200, 201, 204]})
        response = make_mock_response(status_code=201)
        result = validator.validate(response)
        assert result.passed is True


# ==================== JsonPathValidator Tests ====================

class TestJsonPathValidator:

    def test_nested_json_path_match(self):
        validator = JsonPathValidator({
            "type": "json_path",
            "path": "$.data.user.name",
            "expected": "张三"
        })
        response = make_mock_response(body={
            "code": 0,
            "data": {
                "user": {
                    "name": "张三",
                    "age": 30
                }
            }
        })
        result = validator.validate(response)
        assert result.passed is True

    def test_json_path_not_found(self):
        validator = JsonPathValidator({
            "type": "json_path",
            "path": "$.data.nonexistent",
            "expected": "value"
        })
        response = make_mock_response(body={"code": 0, "data": {}})
        result = validator.validate(response)
        assert result.passed is False

    def test_json_path_array_index(self):
        validator = JsonPathValidator({
            "type": "json_path",
            "path": "$.data.items[0]",
            "expected": "a"
        })
        response = make_mock_response(body={
            "code": 0,
            "data": {"items": ["a", "b", "c"]}
        })
        result = validator.validate(response)
        assert result.passed is True


# ==================== ContainsValidator Tests ====================

class TestContainsValidator:

    def test_contains_match(self):
        validator = ContainsValidator({
            "type": "contains",
            "expected": "成功"
        })
        response = make_mock_response(body={"message": "操作成功"})
        result = validator.validate(response)
        assert result.passed is True

    def test_contains_case_insensitive(self):
        validator = ContainsValidator({
            "type": "contains",
            "expected": "success",
            "case_sensitive": False
        })
        response = make_mock_response(body={"message": "SUCCESS"})
        result = validator.validate(response)
        assert result.passed is True


# ==================== SchemaValidator Tests ====================

class TestSchemaValidator:

    def test_valid_schema(self):
        validator = SchemaValidator({
            "type": "schema",
            "schema": {
                "type": "object",
                "required": ["code", "data"],
                "properties": {
                    "code": {"type": "integer"},
                    "data": {"type": "array"}
                }
            }
        })
        response = make_mock_response(body={"code": 0, "data": []})
        result = validator.validate(response)
        assert result.passed is True

    def test_invalid_schema(self):
        validator = SchemaValidator({
            "type": "schema",
            "schema": {
                "type": "object",
                "required": ["code"],
                "properties": {"code": {"type": "integer"}}
            }
        })
        response = make_mock_response(body={"code": "not_int", "data": []})
        result = validator.validate(response)
        assert result.passed is False


# ==================== ResponseTimeValidator Tests ====================

class TestResponseTimeValidator:

    def test_within_limit(self):
        validator = ResponseTimeValidator({
            "type": "response_time",
            "max_ms": 500,
            "response_time_ms": 200
        })
        result = validator.validate(None)
        assert result.passed is True

    def test_exceeds_limit(self):
        validator = ResponseTimeValidator({
            "type": "response_time",
            "max_ms": 100,
            "response_time_ms": 500
        })
        result = validator.validate(None)
        assert result.passed is False


# ==================== AssertionExecutor Integration Tests ====================

class TestAssertionExecutor:

    def test_execute_multiple_assertions(self):
        executor = AssertionExecutor([
            {"type": "status_code", "expected": 200},
            {"type": "json_path", "path": "$.code", "expected": 0},
            {"type": "json_path", "path": "$.message", "expected": "success"},
            {"type": "contains", "expected": "success"}
        ])
        response = make_mock_response(status_code=200, body={
            "code": 0,
            "message": "success",
            "data": [{"id": 1, "name": "item1"}]
        })

        results = executor.execute(response, 150)
        assert len(results) == 4
        assert executor.all_passed(results) is True

    def test_partial_failure(self):
        executor = AssertionExecutor([
            {"type": "status_code", "expected": 200},
            {"type": "json_path", "path": "$.code", "expected": 0}
        ])
        response = make_mock_response(status_code=404, body={"code": 404})

        results = executor.execute(response, 100)
        assert len(results) == 2
        assert executor.all_passed(results) is False
        failed = executor.get_failed_results(results)
        assert len(failed) == 2

    def test_unknown_assertion_type(self):
        executor = AssertionExecutor([
            {"type": "unknown_type", "expected": "value"}
        ])
        response = make_mock_response()
        results = executor.execute(response, 100)
        assert len(results) == 1
        assert results[0].passed is False
        assert "未知的断言类型" in results[0].message


# ==================== AssertionService Tests ====================

class TestAssertionService:

    def test_validate_success(self):
        service = AssertionService()
        response = make_mock_response(status_code=200, body={
            "code": 0, "message": "success"
        })

        assertions = [
            {"type": "status_code", "expected": 200},
            {"type": "json_path", "path": "$.code", "expected": 0}
        ]

        result = service.validate(response, 100, assertions)
        assert result["passed"] is True
        assert result["total"] == 2
        assert result["passed_count"] == 2
        assert result["failed_count"] == 0

    def test_validate_failure(self):
        service = AssertionService()
        response = make_mock_response(status_code=500, body={"code": 500})

        assertions = [
            {"type": "status_code", "expected": 200},
            {"type": "response_time", "max_ms": 50}
        ]

        result = service.validate(response, 200, assertions)
        assert result["passed"] is False
        assert result["failed_count"] == 2

    def test_get_summary(self):
        service = AssertionService()
        executor = AssertionExecutor([
            {"type": "status_code", "expected": 200},
            {"type": "contains", "expected": "success"}
        ])
        response = make_mock_response(body={"code": 0, "message": "success"})
        results = executor.execute(response, 100)

        summary = service.get_summary(results)
        assert summary["total"] == 2
        assert summary["passed"] == 2
        assert summary["failed"] == 0
        assert summary["all_passed"] is True
