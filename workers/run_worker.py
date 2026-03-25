#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Worker启动脚本

基于进程池的Worker启动脚本，使用SQLite本地数据库。

Usage:
    python workers/run_worker.py                          # 默认启动（cpu_count * 2 + 1 个进程）
    python workers/run_worker.py --workers 3               # 指定3个Worker进程
    python workers/run_worker.py --threads 8                # 每个Worker 8个线程
    python workers/run_worker.py --poll-interval 2          # 轮询间隔2秒
    python workers/run_worker.py --db-path ./db/task.db     # 指定数据库路径
    python workers/run_worker.py --help                     # 查看帮助
"""

import argparse
import sys
import os
import signal
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.worker.worker_pool import WorkerPool, get_optimal_worker_count

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
        default=4,
        help='每个Worker的线程数（默认: 4）'
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

    # 确定数据库路径
    if args.db_path is None:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(project_root, 'db', 'task.db')
    else:
        db_path = args.db_path

    # 确保数据库目录存在
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        logger.info(f"创建数据库目录: {db_dir}")

    # 初始化数据库（如果不存在）
    if not os.path.exists(db_path):
        try:
            from db import init_db
            init_db(db_path)
        except Exception as e:
            logger.warning(f"初始化数据库失败: {e}，将使用懒加载方式")

    # 计算Worker数量
    worker_count = args.workers or get_optimal_worker_count()

    print("=" * 50)
    print("接口自动化测试 Worker 启动")
    print("=" * 50)
    print(f"Worker进程数: {worker_count}")
    print(f"每Worker线程数: {args.threads}")
    print(f"轮询间隔: {args.poll_interval}秒")
    print(f"数据库路径: {db_path}")
    print("=" * 50)

    # 创建并启动Worker池
    pool = WorkerPool(
        worker_count=worker_count,
        threads_per_worker=args.threads,
        poll_interval=args.poll_interval,
        db_path=db_path
    )

    # 信号处理
    def signal_handler(signum, frame):
        print("\n收到停止信号，正在关闭...")
        pool.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    pool.start()

    print(f"\nWorker进程池已启动!")
    print(f"  - 进程数: {worker_count}")
    print(f"  - 每进程线程数: {args.threads}")
    print(f"  - 轮询间隔: {args.poll_interval}秒")
    print(f"\n按 Ctrl+C 停止\n")

    try:
        import time
        while True:
            time.sleep(1)

            # 检查进程池状态
            if not pool.is_alive():
                logger.warning("Worker池异常退出，正在重启...")
                pool = WorkerPool(
                    worker_count=worker_count,
                    threads_per_worker=args.threads,
                    poll_interval=args.poll_interval,
                    db_path=db_path
                )
                pool.start()

    except KeyboardInterrupt:
        print("\n收到停止信号")
    finally:
        pool.stop()
        print("Worker进程池已停止")


if __name__ == '__main__':
    main()
