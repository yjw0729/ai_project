#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Worker启动脚本

Usage:
    python run_worker.py                    # 默认启动（cpu_count * 2 + 1 个进程）
    python run_worker.py --workers 3       # 指定3个Worker进程
    python run_worker.py --help             # 查看帮助
"""

import argparse
import sys
import os
import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.worker.worker_pool import WorkerPool, get_optimal_worker_count


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='接口自动化测试 Worker 进程池',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=None,
        help=f'Worker进程数（默认: CPU核心数 * 2 + 1 = {get_optimal_worker_count()}）'
    )

    parser.add_argument(
        '--threads',
        type=int,
        default=3,
        help='每个Worker的线程数（默认: 3）'
    )

    parser.add_argument(
        '--poll-interval',
        type=float,
        default=1.0,
        help='轮询间隔秒数（默认: 1.0）'
    )

    parser.add_argument(
        '--db-path',
        type=str,
        default=None,
        help='数据库路径（默认: ./db/task.db）'
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if args.db_path is None:
        db_path = os.path.join(os.path.dirname(__file__), 'db', 'task.db')
    else:
        db_path = args.db_path

    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        from db import init_db
        init_db(db_path)

    worker_count = args.workers or get_optimal_worker_count()

    print("=" * 50)
    print("接口自动化测试 Worker 启动")
    print("=" * 50)
    print(f"Worker进程数: {worker_count}")
    print(f"每Worker线程数: {args.threads}")
    print(f"轮询间隔: {args.poll_interval}秒")
    print(f"数据库路径: {db_path}")
    print("=" * 50)

    pool = WorkerPool(
        db_path=db_path,
        worker_count=worker_count,
        threads_per_worker=args.threads,
        poll_interval=args.poll_interval
    )

    def signal_handler(signum, frame):
        print("\n收到停止信号，正在关闭...")
        pool.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    pool.start()

    try:
        while True:
            import time
            time.sleep(1)

            if not pool.is_alive():
                print("Worker池异常退出，正在重启...")
                pool = WorkerPool(
                    db_path=db_path,
                    worker_count=worker_count,
                    threads_per_worker=args.threads,
                    poll_interval=args.poll_interval
                )
                pool.start()

    except KeyboardInterrupt:
        print("\n收到停止信号")
    finally:
        pool.stop()


if __name__ == '__main__':
    main()
