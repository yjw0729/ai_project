"""
Workers 目录

包含各类型 Worker 进程和启动脚本：
- test_worker: 测试执行 Worker
- run_worker: Worker 进程池启动脚本
- start_workers: Worker 统一启动脚本
"""

from workers.run_worker import main as run_worker_main

__all__ = ["run_worker_main"]
