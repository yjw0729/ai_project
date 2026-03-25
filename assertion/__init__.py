# assertion - 断言模块
#
# 提供断言验证和自动生成功能
#
# 主要组件:
#   - validators: 多种断言验证器
#   - auto_generator: 断言执行器和自动生成器
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

from assertion.validators import (
    StatusCodeValidator,
    JsonPathValidator,
    ContainsValidator,
    SchemaValidator,
    ResponseTimeValidator,
    HeaderValidator,
    AssertionExecutor,
)

from assertion.auto_generator import AssertionGenerator

__all__ = [
    "StatusCodeValidator",
    "JsonPathValidator",
    "ContainsValidator",
    "SchemaValidator",
    "ResponseTimeValidator",
    "HeaderValidator",
    "AssertionExecutor",
    "AssertionGenerator",
]
