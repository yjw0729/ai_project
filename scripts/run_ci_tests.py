#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CI 测试执行入口脚本

该脚本用于在 CI/CD 环境中执行 API 测试，支持多种测试标记和执行模式。
可以直接通过命令行或 CI/CD 流水线调用。

用法:
    python run_ci_tests.py --marker ci_cd
    python run_ci_tests.py --marker smoke --parallel
    python run_ci_tests.py --marker regression --workers 4

注意:
    pytest.ini 中已配置默认的重试机制 (--reruns=2 --reruns-delay=1)。
    在 CI 流水线中，如果需要禁用重试以加快反馈速度，可以使用：
    pytest ... -p no:rerunfailures ...

作者: Test Automation Team
版本: 1.0.0
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from typing import List, Optional


class CITestRunner:
    """CI 测试执行器

    用于在 CI/CD 环境中执行 API 测试，支持配置化执行不同的测试标记。
    """

    # 测试标记与描述的映射
    MARKER_DESCRIPTIONS = {
        "smoke": "冒烟测试 - 核心功能验证",
        "regression": "回归测试 - 完整功能验证",
        "ci_cd": "CI/CD 集成 - 流水线集成测试",
        "P0": "P0 优先级 - 关键业务路径",
        "P1": "P1 优先级 - 重要功能",
        "P2": "P2 优先级 - 次要功能",
        "P3": "P3 优先级 - 边缘功能",
    }

    # pytest 命令模板
    PYTEST_TEMPLATE = "pytest {test_path} -m {marker} {options} --alluredir={allure_dir}"

    def __init__(
        self,
        marker: str = "ci_cd",
        test_path: str = "tests/",
        parallel: bool = True,
        workers: Optional[int] = None,
        allure_dir: str = "allure-results",
        verbose: bool = True,
        capture_output: bool = False,
    ) -> None:
        """初始化 CI 测试执行器

        Args:
            marker: 测试标记 (smoke, regression, ci_cd, P0, P1, P2, P3)
            test_path: 测试路径
            parallel: 是否并行执行
            workers: 并行工作进程数，None 表示自动
            allure_dir: Allure 结果输出目录
            verbose: 是否详细输出
            capture_output: 是否捕获输出
        """
        self.marker = marker
        self.test_path = test_path
        self.parallel = parallel
        self.workers = workers or -1  # -1 表示 auto
        self.allure_dir = allure_dir
        self.verbose = verbose
        self.capture_output = capture_output
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

    def _build_options(self) -> str:
        """构建 pytest 选项

        Returns:
            pytest 选项字符串
        """
        options = []

        if self.verbose:
            options.append("-v")

        options.append("--tb=short")

        if self.parallel:
            options.append(f"-n {self.workers}")

        return " ".join(options)

    def _build_command(self) -> str:
        """构建完整的 pytest 命令

        Returns:
            完整的 pytest 命令字符串
        """
        options = self._build_options()
        return self.PYTEST_TEMPLATE.format(
            test_path=self.test_path,
            marker=self.marker,
            options=options,
            allure_dir=self.allure_dir,
        )

    def validate_marker(self) -> bool:
        """验证测试标记是否有效

        Returns:
            标记是否有效
        """
        return self.marker in self.MARKER_DESCRIPTIONS

    def run(self) -> int:
        """执行测试

        Returns:
            测试结果退出码 (0 表示成功)
        """
        if not self.validate_marker():
            print(f"错误: 无效的测试标记 '{self.marker}'")
            print(f"有效的标记: {', '.join(self.MARKER_DESCRIPTIONS.keys())}")
            return 1

        # 确保 allure 目录存在
        os.makedirs(self.allure_dir, exist_ok=True)

        self.start_time = datetime.now()
        command = self._build_command()

        print("=" * 60)
        print("CI Test Execution Started")
        print("=" * 60)
        print(f"Marker: {self.marker} - {self.MARKER_DESCRIPTIONS.get(self.marker, '')}")
        print(f"Test Path: {self.test_path}")
        print(f"Parallel: {self.parallel}")
        print(f"Workers: {'auto' if self.workers == -1 else self.workers}")
        print(f"Allure Dir: {self.allure_dir}")
        print(f"Command: {command}")
        print("=" * 60)

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=self.capture_output,
                text=True,
            )

            self.end_time = datetime.now()
            duration = (self.end_time - self.start_time).total_seconds()

            print("\n" + "=" * 60)
            print("Test Execution Summary")
            print("=" * 60)
            print(f"Exit Code: {result.returncode}")
            print(f"Duration: {duration:.2f} seconds")
            print(f"Marker: {self.marker}")
            print("=" * 60)

            if result.stdout and self.verbose:
                print("\n--- STDOUT ---")
                print(result.stdout)

            if result.stderr and self.verbose:
                print("\n--- STDERR ---")
                print(result.stderr)

            return result.returncode

        except KeyboardInterrupt:
            print("\n测试执行被用户中断")
            return 130
        except Exception as e:
            print(f"执行测试时出错: {e}")
            return 1


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数

    Returns:
        解析后的参数对象
    """
    parser = argparse.ArgumentParser(
        description="CI 测试执行入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --marker ci_cd              # 执行 CI/CD 集成测试
  %(prog)s --marker smoke --parallel   # 执行冒烟测试(并行)
  %(prog)s --marker regression --workers 4  # 执行回归测试(4个进程)
  %(prog)s --marker P0 --no-parallel  # 执行 P0 优先级测试(串行)

支持的标记:
  smoke       - 冒烟测试
  regression  - 回归测试
  ci_cd       - CI/CD 集成测试
  P0, P1, P2, P3 - 优先级测试
        """,
    )

    parser.add_argument(
        "--marker",
        "-m",
        type=str,
        default="ci_cd",
        choices=["smoke", "regression", "ci_cd", "P0", "P1", "P2", "P3"],
        help="测试标记 (默认: ci_cd)",
    )

    parser.add_argument(
        "--test-path",
        "-t",
        type=str,
        default="tests/",
        help="测试路径 (默认: tests/)",
    )

    parser.add_argument(
        "--parallel",
        "-p",
        action="store_true",
        default=True,
        help="是否并行执行 (默认: True)",
    )

    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="禁用并行执行",
    )

    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=None,
        help="并行工作进程数 (默认: auto)",
    )

    parser.add_argument(
        "--allure-dir",
        "-a",
        type=str,
        default="allure-results",
        help="Allure 结果目录 (默认: allure-results)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=True,
        help="详细输出 (默认: True)",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="安静模式 - 最小化输出",
    )

    return parser.parse_args()


def main() -> int:
    """主函数

    Returns:
        退出码
    """
    args = parse_arguments()

    # 处理 no-parallel 参数
    parallel = args.parallel and not args.no_parallel

    # 处理 quiet 参数
    verbose = args.verbose and not args.quiet

    runner = CITestRunner(
        marker=args.marker,
        test_path=args.test_path,
        parallel=parallel,
        workers=args.workers,
        allure_dir=args.allure_dir,
        verbose=verbose,
    )

    return runner.run()


if __name__ == "__main__":
    sys.exit(main())