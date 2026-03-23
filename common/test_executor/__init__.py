"""
测试执行层模块索引。

提供功能：
- api_test_runner: API 测试执行器（支持串行/并发）
- parameter_resolver: 参数变量替换（全局变量、前置接口变量、特殊变量）
- assertion_engine: 断言引擎（多种断言类型）
- fixture_manager: Fixture 管理器
- report_generator: 测试报告生成器
"""

from common.test_executor.api_test_runner import APITestRunner, TestResult
from common.test_executor.parameter_resolver import ParameterResolver
from common.test_executor.assertion_engine import AssertionEngine, AssertionResult
from common.test_executor.fixture_manager import FixtureManager
from common.test_executor.report_generator import ReportGenerator

__all__ = [
    "APITestRunner",
    "TestResult",
    "ParameterResolver",
    "AssertionEngine",
    "AssertionResult",
    "FixtureManager",
    "ReportGenerator",
]
