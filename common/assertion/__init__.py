# assertion - 断言核心模块
#
# 提供断言验证和自动生成功能，独立于业务服务层。
# 位于 common/assertion/，被 common/test_executor/ 和 common/services/ 共同引用。
#
# 断言格式示例:
#   expected_results = [
#       {"type": "status_code", "expected": 200},
#       {"type": "json_path", "path": "$.code", "expected": 0},
#       {"type": "contains", "expected": "success"},
#       {"type": "schema", "schema": {...}},
#       {"type": "response_time", "max_ms": 5000},
#       {"type": "header", "header": "Content-Type", "expected": "application/json"}
#   ]

from common.assertion.validators import (
    AssertionResult,
    AssertionExecutor,
    StatusCodeValidator,
    JsonPathValidator,
    ContainsValidator,
    SchemaValidator,
    ResponseTimeValidator,
    HeaderValidator,
    RegexValidator,
    LengthValidator,
    TypeValidator,
    NotEmptyValidator,
)

from common.assertion.auto_generator import (
    AssertionGenerator,
    SmartAssertionGenerator,
    create_assertion_executor,
    generate_assertions,
)

__all__ = [
    # 验证器
    "AssertionResult",
    "AssertionExecutor",
    "StatusCodeValidator",
    "JsonPathValidator",
    "ContainsValidator",
    "SchemaValidator",
    "ResponseTimeValidator",
    "HeaderValidator",
    "RegexValidator",
    "LengthValidator",
    "TypeValidator",
    "NotEmptyValidator",
    # 生成器
    "AssertionGenerator",
    "SmartAssertionGenerator",
    "create_assertion_executor",
    "generate_assertions",
]
