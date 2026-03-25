"""
Core 模块 - pytest 测试执行引擎

提供统一的测试执行调度器，支持：
- 顺序/重复/分布式执行模式
- 标签/优先级过滤
- Allure 报告集成
- 同步和异步执行
"""

from core.runner import (
    TestRunner,
    RunConfig,
    TestResult,
    run_suite,
    run_cases,
    run_with_config,
    run_async,
    ExecutionMode,
    TestStatus,
)

__all__ = [
    "TestRunner",
    "RunConfig",
    "TestResult",
    "ExecutionMode",
    "TestStatus",
    "run_suite",
    "run_cases",
    "run_with_config",
    "run_async",
]
