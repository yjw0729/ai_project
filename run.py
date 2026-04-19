#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
服务器部署启动脚本

Usage:
    python run.py                          # 默认监听 0.0.0.0:8080（服务器部署推荐）
    python run.py --host 0.0.0.0 --port 8080   # 明确指定地址和端口
    python run.py --port 9000             # 仅改端口
    python run.py --debug                 # 开启调试模式
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app


def parse_args():
    parser = argparse.ArgumentParser(description='Flask API 服务器部署启动脚本')
    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='监听地址（默认: 0.0.0.0，支持外网访问）'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8080,
        help='监听端口（默认: 8080）'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='开启调试模式'
    )
    return parser.parse_args()


def list_endpoints(app):
    print("\n" + "=" * 60)
    print("已注册的 API 端点")
    print("=" * 60)
    endpoints = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint != 'static':
            methods = ','.join(sorted(rule.methods - {'OPTIONS', 'HEAD'}))
            endpoints.append({'methods': methods, 'endpoint': rule.endpoint, 'path': rule.rule})
    endpoints.sort(key=lambda x: x['path'])
    for ep in endpoints:
        print(f"  {ep['methods']:10s} {ep['path']}")
    print("=" * 60)
    print(f"共 {len(endpoints)} 个端点\n")


def main():
    args = parse_args()
    app = create_app()
    list_endpoints(app)

    print(f"\n启动 Flask API 服务 [服务器模式]")
    print(f"  - 监听地址: {args.host}")
    print(f"  - 监听端口: {args.port}")
    print(f"  - 调试模式: {args.debug}")
    print(f"\n访问地址: http://{args.host}:{args.port}\n")

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
