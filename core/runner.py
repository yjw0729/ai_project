"""
测试执行调度器 - 核心模块

提供统一的 pytest 执行封装，支持：
- 测试路径指定
- 执行模式选择（顺序/重复/分布式）
- 标签/优先级过滤
- Allure 报告配置
- 结构化测试结果返回
- 同步和异步执行
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pytest

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """测试执行模式枚举"""
    SEQUENTIAL = "sequential"  # 顺序执行
    REPEAT = "repeat"         # 重复执行
    DISTRIBUTED = "distributed"  # 分布式执行


class TestStatus(Enum):
    """测试状态枚举"""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    NO_TESTS = "no_tests"


@dataclass
class RunConfig:
    """
    测试执行配置类。

    用于管理测试执行的各种参数，包括测试路径、执行模式、
    标签过滤、报告配置等。

    Attributes:
        test_paths: 测试路径列表，可以是文件、目录或模块
        mode: 执行模式（顺序/重复/分布式）
        repeat_count: 重复执行次数（仅在 REPEAT 模式下有效）
        workers: 分布式执行的 worker 数量（"auto" 表示自动检测）
        markers: pytest 标记过滤列表（如 ["smoke", "regression"]）
        priority: 优先级过滤（"P0", "P1", "P2", "P3"）
        allure_results_dir: Allure 结果目录路径
        allure_report_dir: Allure 报告目录路径
        verbose: 是否显示详细输出
        capture: 日志捕获模式（"sys", "no", "fd", "tee-sys"）
        timeout: 单个测试超时时间（秒）
        fail_fast: 遇到失败是否快速停止
        continue_on_collection_errors: 收集失败是否继续
        extra_args: 额外的 pytest 参数列表
    """
    test_paths: List[str] = field(default_factory=list)
    mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    repeat_count: int = 1
    workers: Union[str, int] = "auto"
    markers: List[str] = field(default_factory=list)
    priority: Optional[str] = None
    allure_results_dir: str = "./allure-results"
    allure_report_dir: str = "./allure-report"
    verbose: bool = True
    capture: str = "sys"
    timeout: Optional[int] = None
    fail_fast: bool = False
    continue_on_collection_errors: bool = False
    extra_args: List[str] = field(default_factory=list)

    def __post_init__(self):
        """验证配置参数"""
        if self.repeat_count < 1:
            raise ValueError("repeat_count must be >= 1")
        if self.workers != "auto" and isinstance(self.workers, int) and self.workers < 1:
            raise ValueError("workers must be >= 1 or 'auto'")
        if self.priority and self.priority not in ["P0", "P1", "P2", "P3"]:
            raise ValueError("priority must be one of: P0, P1, P2, P3")


@dataclass
class TestResult:
    """
    结构化测试结果类。

    封装 pytest 执行后的结果数据，提供统一的接口访问测试执行信息。

    Attributes:
        exit_code: pytest 退出码（0 表示成功）
        status: 总体测试状态
        total: 总测试数
        passed: 通过数
        failed: 失败数
        skipped: 跳过数
        error: 错误数
        duration_seconds: 总执行时间（秒）
        collected_items: 收集的测试项数量
        allure_results_dir: Allure 结果目录
        allure_report_dir: Allure 报告目录
        raw_output: pytest 原始输出
        errors: 执行过程中的错误列表
    """
    exit_code: int
    status: TestStatus
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    error: int = 0
    duration_seconds: float = 0.0
    collected_items: int = 0
    allure_results_dir: Optional[str] = None
    allure_report_dir: Optional[str] = None
    raw_output: str = ""
    errors: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """判断是否全部通过"""
        return self.status == TestStatus.PASSED

    @property
    def success_rate(self) -> float:
        """计算成功率百分比"""
        if self.total == 0:
            return 0.0
        return round(self.passed / self.total * 100, 2)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "exit_code": self.exit_code,
            "status": self.status.value,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "error": self.error,
            "success": self.success,
            "success_rate": self.success_rate,
            "duration_seconds": self.duration_seconds,
            "collected_items": self.collected_items,
            "allure_results_dir": self.allure_results_dir,
            "allure_report_dir": self.allure_report_dir,
            "errors": self.errors,
        }

    def __str__(self) -> str:
        return (
            f"TestResult(status={self.status.value}, "
            f"passed={self.passed}/{self.total}, "
            f"failed={self.failed}, "
            f"skipped={self.skipped}, "
            f"error={self.error}, "
            f"duration={self.duration_seconds:.2f}s, "
            f"success_rate={self.success_rate}%)"
        )


class TestRunner:
    """
    测试执行调度器。

    封装 pytest.main() 调用，提供统一的测试执行接口。
    支持多种执行模式、标签过滤、Allure 报告等功能。

    Example:
        # 基础用法
        runner = TestRunner()
        result = runner.run(test_paths=["tests/"])

        # 指定执行模式
        config = RunConfig(
            test_paths=["tests/api/"],
            mode=ExecutionMode.DISTRIBUTED,
            workers="auto",
            markers=["smoke", "regression"]
        )
        result = runner.run(config=config)

        # 使用便捷方法
        result = run_suite("tests/smoke/")
        result = run_cases(["tests/test_login.py::test_login_success"])
    """

    def __init__(self, config: Optional[RunConfig] = None):
        """
        初始化 TestRunner。

        Args:
            config: 执行配置，如果为 None 则使用默认配置
        """
        self.config = config or RunConfig()
        self._collected_output: str = ""

    def run(
        self,
        test_paths: Optional[List[str]] = None,
        config: Optional[RunConfig] = None,
    ) -> TestResult:
        """
        执行测试。

        Args:
            test_paths: 测试路径列表，覆盖 config 中的 test_paths
            config: 执行配置，覆盖实例配置

        Returns:
            TestResult: 结构化的测试结果
        """
        # 合并配置
        run_config = self._merge_config(test_paths, config)

        # 构建 pytest 参数
        pytest_args = self._build_pytest_args(run_config)

        logger.info("【TestRunner】开始执行测试，参数: %s", pytest_args)

        # 记录执行开始时间
        start_time = datetime.now()

        try:
            # 执行 pytest
            exit_code = pytest.main(pytest_args)
        except SystemExit as e:
            exit_code = e.code
        except Exception as e:
            logger.error("【TestRunner】执行异常: %s", str(e))
            return self._build_result(
                exit_code=1,
                status=TestStatus.ERROR,
                errors=[str(e)],
                config=run_config,
                start_time=start_time,
            )

        # 解析执行结果
        result = self._parse_result(exit_code, run_config, start_time)

        logger.info("【TestRunner】执行完成: %s", result)
        return result

    def run_async(
        self,
        test_paths: Optional[List[str]] = None,
        config: Optional[RunConfig] = None,
    ) -> asyncio.Task:
        """
        异步执行测试。

        Args:
            test_paths: 测试路径列表
            config: 执行配置

        Returns:
            asyncio.Task: 异步任务对象
        """
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(
            None,
            self.run,
            test_paths,
            config,
        )

    def _merge_config(
        self,
        test_paths: Optional[List[str]] = None,
        config: Optional[RunConfig] = None,
    ) -> RunConfig:
        """合并配置参数"""
        if config:
            run_config = config
        else:
            run_config = self.config

        if test_paths:
            run_config.test_paths = test_paths

        return run_config

    def _build_pytest_args(self, config: RunConfig) -> List[str]:
        """
        构建 pytest 命令行参数。

        Args:
            config: 执行配置

        Returns:
            List[str]: pytest 参数列表
        """
        args: List[str] = []

        # 测试路径
        if config.test_paths:
            args.extend(config.test_paths)
        else:
            args.append("tests/")

        # 执行模式
        if config.mode == ExecutionMode.REPEAT:
            args.extend(["--count", str(config.repeat_count)])
        elif config.mode == ExecutionMode.DISTRIBUTED:
            args.extend(["-n", str(config.workers)])

        # 标记过滤
        if config.markers:
            marker_expr = " and ".join(config.markers)
            args.extend(["-m", marker_expr])

        # 优先级过滤
        if config.priority:
            args.extend(["-m", config.priority])

        # Allure 配置
        args.extend(["--alluredir", config.allure_results_dir])

        # 清理之前的结果
        args.append("--clean-alluredir")

        # JSON 报告配置（用于提取真实统计信息）
        json_report_path = self._get_json_report_path(config)
        args.extend(["--json-report", "--json-report-file", json_report_path])

        # 详细输出
        if config.verbose:
            args.append("-v")

        # 日志捕获
        args.extend(["-s", "--capture", config.capture])

        # 失败快速停止
        if config.fail_fast:
            args.append("-x")

        # 超时设置
        if config.timeout:
            args.extend(["--timeout", str(config.timeout)])

        # 收集错误继续
        if config.continue_on_collection_errors:
            args.append("--continue-on-collection-errors")

        # 额外的参数
        if config.extra_args:
            args.extend(config.extra_args)

        return args

    def _parse_result(
        self,
        exit_code: int,
        config: RunConfig,
        start_time: datetime,
    ) -> TestResult:
        """解析测试执行结果"""
        # 计算执行时间
        duration = (datetime.now() - start_time).total_seconds()

        # 从退出码判断状态
        if exit_code == 0:
            status = TestStatus.PASSED
        elif exit_code == 5:
            status = TestStatus.NO_TESTS
        else:
            status = TestStatus.FAILED

        # 从 JSON 报告中提取真实统计信息
        json_report_path = self._get_json_report_path(config)
        passed, failed, skipped, error, json_duration = self._parse_json_report(json_report_path)
        total = passed + failed + skipped + error
        if total == 0:
            total = passed  # 如果都是 0，可能全部通过

        # 如果 JSON 报告中没有 duration，使用 Python 计时
        if json_duration > 0:
            duration = json_duration

        return TestResult(
            exit_code=exit_code,
            status=status,
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            error=error,
            duration_seconds=duration,
            collected_items=total,
            allure_results_dir=config.allure_results_dir,
            allure_report_dir=config.allure_report_dir,
            raw_output=self._collected_output,
        )

    def _get_json_report_path(self, config: RunConfig) -> str:
        """获取 JSON 报告文件路径"""
        # 使用与 allure_results_dir 同级的 temp_results.json
        allure_dir = Path(config.allure_results_dir).resolve()
        json_report_path = allure_dir.parent / "temp_results.json"
        return str(json_report_path)

    def _parse_json_report(self, json_path: str) -> Tuple[int, int, int, int, float]:
        """
        解析 JSON 测试报告文件，提取统计信息。

        Returns:
            Tuple of (passed, failed, skipped, error, duration_seconds)
        """
        if not os.path.exists(json_path):
            logger.warning("【TestRunner】JSON 报告文件不存在: %s", json_path)
            return (0, 0, 0, 0, 0.0)

        try:
            with open(json_path, encoding="utf-8") as f:
                report = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("【TestRunner】解析 JSON 报告失败: %s", e)
            return (0, 0, 0, 0, 0.0)

        summary = report.get("summary", {})
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        skipped = summary.get("skipped", 0)
        error = summary.get("error", 0)
        duration = report.get("duration", 0.0)

        # 清理临时 JSON 文件
        try:
            os.remove(json_path)
            logger.debug("【TestRunner】已清理 JSON 报告文件: %s", json_path)
        except OSError:
            pass

        return (passed, failed, skipped, error, duration)

    def _build_result(
        self,
        exit_code: int,
        status: TestStatus,
        errors: List[str],
        config: RunConfig,
        start_time: datetime,
    ) -> TestResult:
        """构建测试结果对象"""
        duration = (datetime.now() - start_time).total_seconds()

        return TestResult(
            exit_code=exit_code,
            status=status,
            duration_seconds=duration,
            allure_results_dir=config.allure_results_dir,
            allure_report_dir=config.allure_report_dir,
            errors=errors,
        )

    def generate_allure_report(
        self,
        results_dir: Optional[str] = None,
        report_dir: Optional[str] = None,
    ) -> str:
        """
        生成 Allure 报告。

        Args:
            results_dir: Allure 结果目录
            report_dir: Allure 报告输出目录

        Returns:
            str: 报告目录路径
        """
        import subprocess

        results_dir = results_dir or self.config.allure_results_dir
        report_dir = report_dir or self.config.allure_report_dir

        cmd = [
            "allure",
            "generate",
            results_dir,
            "-o",
            report_dir,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info("【TestRunner】Allure 报告生成成功: %s", report_dir)
            return report_dir
        except FileNotFoundError:
            logger.warning("【TestRunner】allure 命令未找到，请确保已安装 Allure")
            return ""
        except subprocess.CalledProcessError as e:
            logger.error("【TestRunner】Allure 报告生成失败: %s", e.stderr)
            return ""


def run_suite(
    test_path: str,
    mode: ExecutionMode = ExecutionMode.SEQUENTIAL,
    markers: Optional[List[str]] = None,
    priority: Optional[str] = None,
    repeat_count: int = 1,
    workers: Union[str, int] = "auto",
    allure_results_dir: str = "./allure-results",
) -> TestResult:
    """
    运行测试套件的便捷方法。

    Args:
        test_path: 测试路径（目录或文件）
        mode: 执行模式
        markers: pytest 标记列表
        priority: 优先级过滤
        repeat_count: 重复次数
        workers: 分布式 worker 数量
        allure_results_dir: Allure 结果目录

    Returns:
        TestResult: 测试结果
    """
    config = RunConfig(
        test_paths=[test_path],
        mode=mode,
        markers=markers or [],
        priority=priority,
        repeat_count=repeat_count,
        workers=workers,
        allure_results_dir=allure_results_dir,
    )

    runner = TestRunner(config)
    return runner.run()


def run_cases(
    test_paths: List[str],
    mode: ExecutionMode = ExecutionMode.SEQUENTIAL,
    fail_fast: bool = False,
    allure_results_dir: str = "./allure-results",
) -> TestResult:
    """
    运行指定测试用例的便捷方法。

    Args:
        test_paths: 测试用例路径列表
        mode: 执行模式
        fail_fast: 遇到失败是否快速停止
        allure_results_dir: Allure 结果目录

    Returns:
        TestResult: 测试结果
    """
    config = RunConfig(
        test_paths=test_paths,
        mode=mode,
        fail_fast=fail_fast,
        allure_results_dir=allure_results_dir,
    )

    runner = TestRunner(config)
    return runner.run()


def run_with_config(config: RunConfig) -> TestResult:
    """
    使用配置对象运行测试的便捷方法。

    Args:
        config: 执行配置

    Returns:
        TestResult: 测试结果
    """
    runner = TestRunner(config)
    return runner.run()


async def run_async(config: RunConfig) -> TestResult:
    """
    异步运行测试的便捷方法。

    Args:
        config: 执行配置

    Returns:
        TestResult: 测试结果
    """
    runner = TestRunner(config)
    task = runner.run_async(config=config)
    return await task
