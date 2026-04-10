"""
数据库字段断言验证器

支持多种断言操作符：
- equals / not_equals - 等于 / 不等于
- contains / starts_with / ends_with - 字符串包含 / 开头 / 结尾
- regex - 正则匹配
- greater_than / less_than / greater_or_equal / less_or_equal - 数值比较
- between - 范围断言
- in_list / not_in_list - 在列表中 / 不在列表中
- is_null / is_not_null - 空值 / 非空断言
- length_equals / length_greater_than / length_less_than - 长度断言
- type_equals - 类型断言
"""
import logging
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FieldValidationResult:
    """字段验证结果"""
    field: str                        # 字段名
    operator: str                    # 操作符
    passed: bool                     # 是否通过
    expected: Any                    # 期望值
    actual: Any                      # 实际值
    message: str = ""                 # 验证消息
    error: Optional[str] = None       # 错误信息

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "operator": self.operator,
            "passed": self.passed,
            "expected": self.expected,
            "actual": self.actual,
            "message": self.message,
            "error": self.error,
        }


class DbFieldValidator:
    """
    数据库字段断言验证器

    对单条查询结果的指定字段进行断言验证。
    """

    # 支持的操作符
    OPERATORS = [
        # 相等
        "equals",
        "not_equals",
        # 字符串操作
        "contains",
        "not_contains",
        "starts_with",
        "ends_with",
        "regex",
        # 数值比较
        "greater_than",
        "less_than",
        "greater_or_equal",
        "less_or_equal",
        "between",
        # 列表操作
        "in_list",
        "not_in_list",
        # 空值
        "is_null",
        "is_not_null",
        # 长度
        "length_equals",
        "length_greater_than",
        "length_less_than",
        "length_between",
        # 类型
        "type_equals",
        # 通用
        "not_empty",
    ]

    def __init__(self):
        pass

    def validate(
        self,
        row: Dict[str, Any],
        field: str,
        operator: str,
        expected: Any = None,
        message: Optional[str] = None,
    ) -> FieldValidationResult:
        """
        验证字段值

        Args:
            row: 查询结果行（字典）
            field: 字段名（支持点号分隔的嵌套字段）
            operator: 操作符
            expected: 期望值
            message: 自定义消息

        Returns:
            FieldValidationResult: 验证结果
        """
        # 获取字段值
        actual = self._get_field_value(row, field)

        # 获取验证方法
        validator_method = self._get_validator_method(operator)
        if validator_method is None:
            return FieldValidationResult(
                field=field,
                operator=operator,
                passed=False,
                expected=expected,
                actual=actual,
                error=f"不支持的操作符: {operator}",
            )

        # 执行验证
        try:
            passed, msg = validator_method(actual, expected)
            result_message = message or msg
            return FieldValidationResult(
                field=field,
                operator=operator,
                passed=passed,
                expected=expected,
                actual=actual,
                message=result_message,
            )
        except Exception as e:
            logger.error("【DbFieldValidator】验证异常: field=%s, operator=%s, error=%s",
                        field, operator, str(e))
            return FieldValidationResult(
                field=field,
                operator=operator,
                passed=False,
                expected=expected,
                actual=actual,
                error=str(e),
            )

    def validate_all(
        self,
        row: Dict[str, Any],
        assertions: List[Dict[str, Any]],
    ) -> List[FieldValidationResult]:
        """
        执行多个字段验证

        Args:
            row: 查询结果行
            assertions: 断言配置列表
                [
                    {"field": "status", "operator": "equals", "expected": "PAID"},
                    {"field": "amount", "operator": "greater_than", "expected": 0},
                ]

        Returns:
            List[FieldValidationResult]: 验证结果列表
        """
        results = []
        for assertion in assertions:
            field = assertion.get("field", "")
            operator = assertion.get("operator", "equals")
            expected = assertion.get("expected")
            message = assertion.get("message")

            result = self.validate(
                row=row,
                field=field,
                operator=operator,
                expected=expected,
                message=message,
            )
            results.append(result)

        return results

    def _get_field_value(self, row: Dict[str, Any], field: str) -> Any:
        """
        获取字段值

        Args:
            row: 数据行
            field: 字段名（支持点号分隔，如 "user.profile.name"）

        Returns:
            字段值，如果不存在返回 None
        """
        if not field:
            return row

        parts = field.split('.')
        current = row

        for part in parts:
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    index = int(part)
                    current = current[index]
                except (ValueError, IndexError):
                    return None
            else:
                return None

        return current

    def _get_validator_method(self, operator: str):
        """获取操作符对应的验证方法"""
        method_map = {
            "equals": self._validate_equals,
            "not_equals": self._validate_not_equals,
            "contains": self._validate_contains,
            "not_contains": self._validate_not_contains,
            "starts_with": self._validate_starts_with,
            "ends_with": self._validate_ends_with,
            "regex": self._validate_regex,
            "greater_than": self._validate_greater_than,
            "less_than": self._validate_less_than,
            "greater_or_equal": self._validate_greater_or_equal,
            "less_or_equal": self._validate_less_or_equal,
            "between": self._validate_between,
            "in_list": self._validate_in_list,
            "not_in_list": self._validate_not_in_list,
            "is_null": self._validate_is_null,
            "is_not_null": self._validate_is_not_null,
            "length_equals": self._validate_length_equals,
            "length_greater_than": self._validate_length_greater_than,
            "length_less_than": self._validate_length_less_than,
            "length_between": self._validate_length_between,
            "type_equals": self._validate_type_equals,
            "not_empty": self._validate_not_empty,
        }
        return method_map.get(operator)

    # ---- 验证方法 ----

    def _validate_equals(self, actual: Any, expected: Any) -> tuple:
        """等于"""
        passed = actual == expected
        return passed, f"预期等于 [{expected}]，实际 [{actual}]"

    def _validate_not_equals(self, actual: Any, expected: Any) -> tuple:
        """不等于"""
        passed = actual != expected
        return passed, f"预期不等于 [{expected}]，实际 [{actual}]"

    def _validate_contains(self, actual: Any, expected: Any) -> tuple:
        """包含"""
        if actual is None:
            return False, f"预期包含 [{expected}]，实际为 None"
        actual_str = str(actual)
        passed = str(expected) in actual_str
        return passed, f"预期包含 [{expected}]，实际 [{actual_str}]"

    def _validate_not_contains(self, actual: Any, expected: Any) -> tuple:
        """不包含"""
        if actual is None:
            return True, f"预期不包含 [{expected}]，实际为 None"
        actual_str = str(actual)
        passed = str(expected) not in actual_str
        return passed, f"预期不包含 [{expected}]，实际 [{actual_str}]"

    def _validate_starts_with(self, actual: Any, expected: Any) -> tuple:
        """字符串开头"""
        if actual is None:
            return False, f"预期以 [{expected}] 开头，实际为 None"
        actual_str = str(actual)
        passed = actual_str.startswith(str(expected))
        return passed, f"预期以 [{expected}] 开头，实际 [{actual_str}]"

    def _validate_ends_with(self, actual: Any, expected: Any) -> tuple:
        """字符串结尾"""
        if actual is None:
            return False, f"预期以 [{expected}] 结尾，实际为 None"
        actual_str = str(actual)
        passed = actual_str.endswith(str(expected))
        return passed, f"预期以 [{expected}] 结尾，实际 [{actual_str}]"

    def _validate_regex(self, actual: Any, expected: Any) -> tuple:
        """正则匹配"""
        if actual is None:
            return False, f"正则 [{expected}] 匹配失败，实际为 None"
        try:
            pattern = re.compile(str(expected))
            match = pattern.search(str(actual))
            passed = match is not None
            return passed, f"正则 [{expected}] {'匹配' if passed else '不匹配'} [{actual}]"
        except re.error as e:
            return False, f"正则表达式错误: {e}"

    def _validate_greater_than(self, actual: Any, expected: Any) -> tuple:
        """大于"""
        try:
            passed = float(actual) > float(expected)
            return passed, f"预期大于 [{expected}]，实际 [{actual}]"
        except (ValueError, TypeError) as e:
            return False, f"无法比较 [{actual}] 和 [{expected}]: {e}"

    def _validate_less_than(self, actual: Any, expected: Any) -> tuple:
        """小于"""
        try:
            passed = float(actual) < float(expected)
            return passed, f"预期小于 [{expected}]，实际 [{actual}]"
        except (ValueError, TypeError) as e:
            return False, f"无法比较 [{actual}] 和 [{expected}]: {e}"

    def _validate_greater_or_equal(self, actual: Any, expected: Any) -> tuple:
        """大于等于"""
        try:
            passed = float(actual) >= float(expected)
            return passed, f"预期大于等于 [{expected}]，实际 [{actual}]"
        except (ValueError, TypeError) as e:
            return False, f"无法比较 [{actual}] 和 [{expected}]: {e}"

    def _validate_less_or_equal(self, actual: Any, expected: Any) -> tuple:
        """小于等于"""
        try:
            passed = float(actual) <= float(expected)
            return passed, f"预期小于等于 [{expected}]，实际 [{actual}]"
        except (ValueError, TypeError) as e:
            return False, f"无法比较 [{actual}] 和 [{expected}]: {e}"

    def _validate_between(self, actual: Any, expected: Any) -> tuple:
        """在范围内"""
        if not isinstance(expected, dict):
            return False, f"between 操作符需要 expected 为字典 {{min, max}}"
        min_val = expected.get("min")
        max_val = expected.get("max")
        try:
            actual_num = float(actual)
            passed = (min_val is None or actual_num >= min_val) and \
                     (max_val is None or actual_num <= max_val)
            return passed, f"预期在 [{min_val}, {max_val}] 范围内，实际 [{actual}]"
        except (ValueError, TypeError) as e:
            return False, f"无法比较 [{actual}] 和范围 [{min_val}, {max_val}]: {e}"

    def _validate_in_list(self, actual: Any, expected: Any) -> tuple:
        """在列表中"""
        if not isinstance(expected, list):
            return False, f"in_list 操作符需要 expected 为列表"
        passed = actual in expected
        return passed, f"预期在 {expected} 中，实际 [{actual}]"

    def _validate_not_in_list(self, actual: Any, expected: Any) -> tuple:
        """不在列表中"""
        if not isinstance(expected, list):
            return False, f"not_in_list 操作符需要 expected 为列表"
        passed = actual not in expected
        return passed, f"预期不在 {expected} 中，实际 [{actual}]"

    def _validate_is_null(self, actual: Any, expected: Any) -> tuple:
        """为空"""
        passed = actual is None
        return passed, f"预期为空，实际 [{actual}]"

    def _validate_is_not_null(self, actual: Any, expected: Any) -> tuple:
        """不为空"""
        passed = actual is not None
        return passed, f"预期不为空，实际为 None" if not passed else "通过"

    def _validate_length_equals(self, actual: Any, expected: Any) -> tuple:
        """长度等于"""
        if actual is None:
            return False, f"无法获取长度，实际为 None"
        try:
            actual_len = len(actual)
            passed = actual_len == int(expected)
            return passed, f"预期长度等于 [{expected}]，实际长度 [{actual_len}]"
        except (ValueError, TypeError) as e:
            return False, f"无法获取长度: {e}"

    def _validate_length_greater_than(self, actual: Any, expected: Any) -> tuple:
        """长度大于"""
        if actual is None:
            return False, f"无法获取长度，实际为 None"
        try:
            actual_len = len(actual)
            passed = actual_len > int(expected)
            return passed, f"预期长度大于 [{expected}]，实际长度 [{actual_len}]"
        except (ValueError, TypeError) as e:
            return False, f"无法获取长度: {e}"

    def _validate_length_less_than(self, actual: Any, expected: Any) -> tuple:
        """长度小于"""
        if actual is None:
            return False, f"无法获取长度，实际为 None"
        try:
            actual_len = len(actual)
            passed = actual_len < int(expected)
            return passed, f"预期长度小于 [{expected}]，实际长度 [{actual_len}]"
        except (ValueError, TypeError) as e:
            return False, f"无法获取长度: {e}"

    def _validate_length_between(self, actual: Any, expected: Any) -> tuple:
        """长度在范围内"""
        if not isinstance(expected, dict):
            return False, f"length_between 操作符需要 expected 为字典 {{min, max}}"
        if actual is None:
            return False, f"无法获取长度，实际为 None"
        try:
            actual_len = len(actual)
            min_val = expected.get("min")
            max_val = expected.get("max")
            passed = (min_val is None or actual_len >= min_val) and \
                     (max_val is None or actual_len <= max_val)
            return passed, f"预期长度在 [{min_val}, {max_val}] 范围内，实际长度 [{actual_len}]"
        except (ValueError, TypeError) as e:
            return False, f"无法获取长度: {e}"

    def _validate_type_equals(self, actual: Any, expected: Any) -> tuple:
        """类型等于"""
        if actual is None:
            type_name = "None"
        else:
            type_name = type(actual).__name__

        expected_lower = str(expected).lower()
        type_map = {
            "string": ["str", "string"],
            "int": ["int", "integer"],
            "float": ["float", "double"],
            "bool": ["bool", "boolean"],
            "list": ["list", "array"],
            "dict": ["dict", "object"],
            "datetime": ["datetime", "date", "time"],
            "none": ["None", "null"],
        }

        valid_types = type_map.get(expected_lower, [expected_lower])
        passed = type_name.lower() in valid_types
        return passed, f"预期类型为 [{expected}]，实际类型 [{type_name}]"

    def _validate_not_empty(self, actual: Any, expected: Any) -> tuple:
        """非空"""
        if actual is None:
            return False, "预期非空，实际为 None"
        if isinstance(actual, (str, list, dict, tuple)):
            passed = len(actual) > 0
            return passed, f"预期非空，实际为空" if not passed else "通过"
        passed = actual != "" and actual != 0
        return passed, f"预期非空，实际 [{actual}]"


# 全局单例
_global_validator: Optional[DbFieldValidator] = None


def get_db_field_validator() -> DbFieldValidator:
    """获取全局字段验证器实例"""
    global _global_validator
    if _global_validator is None:
        _global_validator = DbFieldValidator()
    return _global_validator
