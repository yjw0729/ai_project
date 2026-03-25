#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Flask API 启动脚本

Usage:
    python run_api.py                    # 默认启动，监听 0.0.0.0:5000
    python run_api.py --host 127.0.0.1  # 指定主机
    python run_api.py --port 8080        # 指定端口
    python run_api.py --debug            # 开启调试模式
"""

import argparse
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='Flask API 启动脚本')

    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='监听主机地址（默认: 0.0.0.0）'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='监听端口（默认: 5000）'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='开启调试模式'
    )

    parser.add_argument(
        '--db-path',
        type=str,
        default=None,
        help='数据库路径（可选）'
    )

    return parser.parse_args()


def list_endpoints(app):
    """列出所有注册的API端点"""
    print("\n" + "=" * 60)
    print("已注册的 API 端点")
    print("=" * 60)

    endpoints = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint != 'static':
            methods = ','.join(sorted(rule.methods - {'OPTIONS', 'HEAD'}))
            endpoints.append({
                'methods': methods,
                'endpoint': rule.endpoint,
                'path': rule.rule
            })

    # 按路径排序
    endpoints.sort(key=lambda x: x['path'])

    for ep in endpoints:
        print(f"  {ep['methods']:10s} {ep['path']}")

    print("=" * 60)
    print(f"共 {len(endpoints)} 个端点\n")


def main():
    args = parse_args()

    # 配置
    config = {}
    if args.db_path:
        config['DATABASE'] = args.db_path

    # 创建Flask应用
    app = create_app(config)

    # 列出所有端点
    list_endpoints(app)

    # 启动服务器
    print(f"\n启动 Flask API 服务...")
    print(f"  - 主机: {args.host}")
    print(f"  - 端口: {args.port}")
    print(f"  - 调试: {args.debug}")
    print(f"\n访问 http://127.0.0.1:{args.port} 查看 API\n")

    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug
    )


if __name__ == '__main__':
    main()
