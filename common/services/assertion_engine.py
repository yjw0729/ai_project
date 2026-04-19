"""
Assertion service layer and engine for evaluating response assertions.

Exports:
    AssertionService  - existing service wrapper (from existing code)
    AssertionEngine   - assertion execution engine
    AssertionResult  - result of a single assertion
    VariableContext  - variable interpolation context
    AssertionEvaluator - per-field assertion evaluator
"""

import json
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional, Set

from common.models.assertion import (
    AssertionField,
    AssertionResult as _ModelResult,
    AssertionTemplate,
)


# ---------------------------------------------------------------------------
# Re-export the existing AssertionService (unchanged)
# ---------------------------------------------------------------------------
from typing import List as _List, Dict as _Dict, Any as _Any
from common.assertion import AssertionExecutor, AssertionResult

# Re-export AssertionResult so __init__.py can import it from this module
AssertionResult = AssertionResult


class AssertionService:
    """Assertion service - unified assertion execution interface."""

    def __init__(self):
        self.executor = AssertionExecutor()

    def validate(
        self,
        response,
        response_time_ms: float,
        assertions: _List[_Dict[_Any, _Any]]
    ) -> _Dict[_Any, _Any]:
        results = self.executor.execute(response, response_time_ms)
        passed_count = sum(1 for r in results if r.passed)
        failed_count = len(results) - passed_count
        return {
            "passed": self.executor.all_passed(results),
            "total": len(results),
            "passed_count": passed_count,
            "failed_count": failed_count,
            "results": results
        }

    def get_summary(self, results: _List[AssertionResult]) -> _Dict[_Any, _Any]:
        executor = AssertionExecutor()
        return executor.get_summary(results)


# ---------------------------------------------------------------------------
# New assertion engine classes (used by tests/test_assertion_engine.py)
# ---------------------------------------------------------------------------


class _AssertionResultLocal:
    """Result of a single assertion evaluation (matches app.models.assertion.AssertionResult interface)."""

    def __init__(
        self,
        field: str = "",
        passed: bool = False,
        expected: Any = None,
        actual: Any = None,
        message: str = "",
        assertion_type: str = "",
        details: Optional[Dict[str, Any]] = None,
        execution_time_ms: float = 0.0,
    ):
        self.field = field
        self.passed = passed
        self.expected = expected
        self.actual = actual
        self.message = message
        self.assertion_type = assertion_type
        self.details = details or {}
        self.execution_time_ms = execution_time_ms

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'field': self.field,
            'passed': self.passed,
            'expected': self.expected,
            'actual': self.actual,
            'message': self.message,
        }
        if self.assertion_type:
            result['assertion_type'] = self.assertion_type
        if self.details:
            result['details'] = self.details
        if self.execution_time_ms:
            result['execution_time_ms'] = self.execution_time_ms
        return result


class VariableContext:
    """Maintains request, response, and variable contexts for interpolation."""

    def __init__(self):
        self._vars: Dict[str, Any] = {}
        self._request: Dict[str, Any] = {}
        self._response: Dict[str, Any] = {}

    def set_variable(self, name: str, value: Any):
        self._vars[name] = value

    def get_variable(self, name: str) -> Optional[Any]:
        return self._vars.get(name)

    def set_request(self, request: Dict[str, Any]):
        self._request = request

    def set_response(self, response: Dict[str, Any]):
        self._response = response

    def resolve_value(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        pattern = re.compile(r'\{\{(request|response|var)\.(\w+(?:\.\w+)*)\}\}')
        resolved = value
        for match in pattern.finditer(value):
            prefix = match.group(1)
            path = match.group(2)
            if prefix == 'request':
                src = self._request
            elif prefix == 'response':
                src = self._response
            else:
                src = self._vars
            parts = path.split('.')
            val = src
            for part in parts:
                if isinstance(val, dict):
                    val = val.get(part)
                else:
                    val = None
                    break
            resolved = resolved.replace(match.group(0), str(val) if val is not None else '')
        return resolved

    def get_nested(self, data: Dict[str, Any], path: str) -> Any:
        parts = path.split('.')
        val = data
        for part in parts:
            if isinstance(val, dict):
                val = val.get(part)
            else:
                return None
        return val


class AssertionEvaluator:
    """Evaluates individual assertions against response data."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _get_exception_code_value(self, field: AssertionField) -> Dict[str, Any]:
        if not self.db_path or not field.exception_code:
            return {}
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.execute(
                "SELECT code, description, http_status, response_code, suggestion, module "
                "FROM exception_codes WHERE code = ?",
                (field.exception_code,),
            )
            row = cur.fetchone()
            conn.close()
            if not row:
                return {}
            return {
                'code': row[0],
                'description': row[1],
                'http_status': row[2],
                'response_code': row[3],
                'suggestion': row[4],
                'module': row[5],
            }
        except Exception:
            return {}

    def evaluate(self, field: AssertionField, response: Dict[str, Any], ctx: VariableContext) -> _AssertionResultLocal:
        start = time.time()
        actual = None
        passed = False
        message = ''
        expected = field.expected

        expected = ctx.resolve_value(expected)
        actual = ctx.get_nested(response, field.field) if field.field else response

        type_lower = field.type.lower()
        try:
            if type_lower == 'equals':
                passed = str(actual) == str(expected)
                message = f"字段 '{field.field}' 值 '{actual}' {'匹配' if passed else '不匹配'} 预期 '{expected}'"
            elif type_lower == 'not_equals':
                passed = str(actual) != str(expected)
                message = f"字段 '{field.field}' 值 '{actual}' {'不等于' if passed else '等于'} '{expected}'"
            elif type_lower == 'not_null':
                passed = actual is not None
                message = f"字段 '{field.field}' {'不为空' if passed else '为空'}"
            elif type_lower == 'is_null':
                passed = actual is None
                message = f"字段 '{field.field}' {'为空' if passed else '不为空'}"
            elif type_lower == 'exists':
                passed = actual is not None
                message = f"字段 '{field.field}' {'存在' if passed else '不存在'}"
            elif type_lower == 'contains':
                needle = str(expected)
                haystack = str(actual) if actual is not None else ''
                passed = needle in haystack
                message = f"'{needle}' {'在' if passed else '不在'} '{haystack}' 中"
            elif type_lower == 'not_contains':
                needle = str(expected)
                haystack = str(actual) if actual is not None else ''
                passed = needle not in haystack
                message = f"'{needle}' {'不在' if passed else '在'} '{haystack}' 中"
            elif type_lower == 'matches':
                passed = bool(re.match(field.pattern or '', str(actual) if actual else ''))
                message = f"字段 '{field.field}' 值 '{actual}' {'匹配' if passed else '不匹配'} 正则 '{field.pattern}'"
            elif type_lower == 'greater_than':
                passed = float(actual) > float(expected) if actual is not None else False
                message = f"字段 '{field.field}' 值 {actual} {'大于' if passed else '不大于'} {expected}"
            elif type_lower == 'less_than':
                passed = float(actual) < float(expected) if actual is not None else False
                message = f"字段 '{field.field}' 值 {actual} {'小于' if passed else '不小于'} {expected}"
            elif type_lower == 'greater_equals':
                passed = float(actual) >= float(expected) if actual is not None else False
                message = f"字段 '{field.field}' 值 {actual} {'大于等于' if passed else '小于'} {expected}"
            elif type_lower == 'less_equals':
                passed = float(actual) <= float(expected) if actual is not None else False
                message = f"字段 '{field.field}' 值 {actual} {'小于等于' if passed else '大于'} {expected}"
            elif type_lower == 'between':
                val = float(actual) if actual is not None else None
                mn = float(field.min_value) if field.min_value is not None else None
                mx = float(field.max_value) if field.max_value is not None else None
                passed = mn is not None and mx is not None and mn <= val <= mx
                message = f"字段 '{field.field}' 值 {actual} {'在' if passed else '不在'} 范围 [{mn}, {mx}]"
            elif type_lower == 'in':
                passed = str(actual) in [str(e) for e in (expected if isinstance(expected, list) else [expected])]
                message = f"字段 '{field.field}' 值 '{actual}' {'在' if passed else '不在'} 列表中"
            elif type_lower == 'not_in':
                passed = str(actual) not in [str(e) for e in (expected if isinstance(expected, list) else [expected])]
                message = f"字段 '{field.field}' 值 '{actual}' {'不在' if passed else '在'} 排除列表中"
            elif type_lower == 'length':
                actual_len = len(actual) if actual is not None else 0
                passed = actual_len == int(expected) if expected is not None else False
                message = f"字段 '{field.field}' 长度 {actual_len} {'等于' if passed else '不等于'} {expected}"
            else:
                message = f"未知的断言类型: {field.type}"
        except Exception as e:
            passed = False
            message = f"断言执行错误: {e}"

        return _AssertionResultLocal(
            field=field.field,
            passed=passed,
            expected=expected,
            actual=actual,
            message=message or field.message,
            assertion_type=field.type,
            execution_time_ms=(time.time() - start) * 1000,
        )


class AssertionEngine:
    """Main engine for executing assertion suites."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self._evaluator = AssertionEvaluator(db_path)

    def generate_assertions_from_exception_code(self, code: str) -> List[AssertionField]:
        result = self._evaluator._get_exception_code_value(
            AssertionField(field='code', exception_code=code)
        )
        if not result:
            return []
        return [AssertionField(
            field='code',
            source='fixed',
            type='equals',
            expected=result.get('response_code'),
            exception_code=code,
        )]

    def execute(
        self,
        assertions: List[Dict[str, Any]],
        response: Dict[str, Any],
        request: Optional[Dict[str, Any]] = None,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ctx = VariableContext()
        if request:
            ctx.set_request(request)
        ctx.set_response(response)
        if variables:
            for k, v in variables.items():
                ctx.set_variable(k, v)

        results: List[Dict[str, Any]] = []
        passed = 0
        failed = 0

        for assertion_dict in assertions:
            af = AssertionField.from_dict(assertion_dict)
            if af.source == 'exception_code' and af.exception_code:
                exc_result = self._evaluator._get_exception_code_value(af)
                if exc_result and af.expected is None:
                    af.expected = exc_result.get('response_code')
            result = self._evaluator.evaluate(af, response, ctx)
            results.append(result.to_dict())
            if result.passed:
                passed += 1
            else:
                failed += 1

        return {
            'success': failed == 0,
            'total': len(assertions),
            'passed': passed,
            'failed': failed,
            'results': results,
        }
