#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
冒烟测试执行脚本

该脚本用于执行冒烟测试，验证核心功能是否正常工作。
通常在代码提交后或上线前快速验证关键功能路径。

用法:
    python run_smoke_tests.py
    python run_smoke_tests.py --verbose
    python run_smoke_tests.py --parallel --workers 4

作者: Test Automation Team
版本: 1.0.0
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from typing import List, Optional


class SmokeTestRunner:
    """冒烟测试执行器

    用于快速验证核心功能的冒烟测试执行器。
    支持快速执行和详细报告输出。
    """

    # 冒烟测试标记配置
    SMOKE_MARKERS = ["smoke"]

    # P0 优先级也作为冒烟测试的一部分
    SMOKE_MARKERS_WITH_P0 = ["smoke", "P0"]

    def __init__(
        self,
        include_p0: bool = True,
        test_path: str = "tests/",
        parallel: bool = True,
        workers: Optional[int] = None,
        allure_dir: str = "allure-results",
        verbose: bool = True,
        capture_output: bool = False,
        fail_fast: bool = False,
    ) -> None:
        """初始化冒烟测试执行器

        Args:
            include_p0: 是否包含 P0 优先级测试
            test_path: 测试路径
            parallel: 是否并行执行
            workers: 并行工作进程数
            allure_dir: Allure 结果输出目录
            verbose: 是否详细输出
            capture_output: 是否捕获输出
            fail_fast: 是否快速失败
        """
        self.include_p0 = include_p0
        self.test_path = test_path
        self.parallel = parallel
        self.workers = workers or -1
        self.allure_dir = allure_dir
        self.verbose = verbose
        self.capture_output = capture_output
        self.fail_fast = fail_fast
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

    @property
    def markers(self) -> str:
        """获取测试标记表达式

        Returns:
            pytest 标记表达式
        """
        if self.include_p0:
            return " or ".join(self.SMOKE_MARKERS_WITH_P0)
        return " or ".join(self.SMOKE_MARKERS)

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

        if self.fail_fast:
            options.append("-x")

        return " ".join(options)

    def _build_command(self) -> str:
        """构建 pytest 命令

        Returns:
            完整的 pytest 命令
        """
        options = self._build_options()
        return (
            f"pytest {self.test_path} -m '{self.markers}' "
            f"{options} --alluredir={self.allure_dir}"
        )

    def validate_environment(self) -> bool:
        """验证测试环境

        Returns:
            环境是否就绪
        """
        checks = []

        # 检查测试目录是否存在
        if os.path.exists(self.test_path):
            checks.append(True)
        else:
            print(f"警告: 测试目录 {self.test_path} 不存在")
            checks.append(False)

        # 检查 pytest 是否可用
        try:
            result = subprocess.run(
                ["pytest", "--version"],
                capture_output=True,
                text=True,
            )
            checks.append(result.returncode == 0)
        except FileNotFoundError:
            print("错误: pytest 未安装")
            checks.append(False)

        return all(checks)

    def run(self) -> int:
        """执行冒烟测试

        Returns:
            测试结果退出码
        """
        if not self.validate_environment():
            print("环境验证失败，请检查配置")
            return 1

        # 确保 allure 目录存在
        os.makedirs(self.allure_dir, exist_ok=True)

        self.start_time = datetime.now()
        command = self._build_command()

        print("=" * 60)
        print("Smoke Test Execution Started")
        print("=" * 60)
        print(f"Markers: {self.markers}")
        print(f"Include P0: {self.include_p0}")
        print(f"Test Path: {self.test_path}")
        print(f"Parallel: {self.parallel}")
        print(f"Workers: {'auto' if self.workers == -1 else self.workers}")
        print(f"Fail Fast: {self.fail_fast}")
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
            print("Smoke Test Execution Summary")
            print("=" * 60)
            print(f"Status: {'PASSED' if result.returncode == 0 else 'FAILED'}")
            print(f"Exit Code: {result.returncode}")
            print(f"Duration: {duration:.2f} seconds")
            print(f"Markers: {self.markers}")
            print("=" * 60)

            if result.stdout and self.verbose:
                print("\n--- STDOUT ---")
                print(result.stdout)

            if result.stderr and self.verbose:
                print("\n--- STDERR ---")
                print(result.stderr)

            # 输出简要结果
            if result.returncode == 0:
                print("\n✓ 冒烟测试通过 - 核心功能正常")
            else:
                print("\n✗ 冒烟测试失败 - 请检查失败的测试用例")

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
        description="执行冒烟测试 - 快速验证核心功能",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                     # 执行冒烟测试 (smoke + P0)
  %(prog)s --no-p0             # 仅执行 smoke 标记的测试
  %(prog)s --parallel          # 并行执行
  %(prog)s --parallel --workers 4  # 使用 4 个工作进程
  %(prog)s --fail-fast         # 快速失败模式

说明:
  默认情况下，冒烟测试会执行带有 'smoke' 和 'P0' 标记的测试用例。
  这些用例代表核心功能和关键业务路径。
        """,
    )

    parser.add_argument(
        "--include-p0",
        action="store_true",
        default=True,
        help="包含 P0 优先级测试 (默认: True)",
    )

    parser.add_argument(
        "--no-p0",
        action="store_true",
        help="不包含 P0 优先级测试",
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

    parser.add_argument(
        "--fail-fast",
        "-x",
        action="store_true",
        help="遇到第一个失败就停止",
    )

    return parser.parse_args()


def main() -> int:
    """主函数

    Returns:
        退出码
    """
    args = parse_arguments()

    # 处理参数
    parallel = args.parallel and not args.no_parallel
    include_p0 = args.include_p0 and not args.no_p0
    verbose = args.verbose and not args.quiet

    runner = SmokeTestRunner(
        include_p0=include_p0,
        test_path=args.test_path,
        parallel=parallel,
        workers=args.workers,
        allure_dir=args.allure_dir,
        verbose=verbose,
        fail_fast=args.fail_fast,
    )

    return runner.run()


if __name__ == "__main__":
    sys.exit(main())