#!/usr/bin/env python3
"""
各服务独立启动脚本。

当前项目为单体架构，此脚本为未来服务拆分做准备。
拆分后，每个服务将拥有独立的 requirements.txt 和启动命令。
"""

import subprocess
import os
import sys
import signal
import time

SERVICES = {
    "platform": {
        "description": "主测试平台（API + Web）",
        "command": [sys.executable, "app/application.py"],
        "port": 5000,
        "deps": ["redis", "mysql", "rabbitmq"],
    },
    "workers": {
        "description": "Worker 进程（LLM + Test + RAG）",
        "command": [sys.executable, "workers/start_workers.py"],
        "port": None,
        "deps": ["redis", "rabbitmq"],
    },
}


def start_service(name: str):
    info = SERVICES.get(name)
    if not info:
        print(f"未知服务: {name}")
        return None

    print(f"启动 {name} ({info['description']})...")
    proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.Popen(
        info["command"],
        cwd=proj_root,
    )
    return proc


def stop_service(proc):
    if proc:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def check_dependencies(deps: list):
    import socket

    checks = {
        "redis": ("localhost", 6379),
        "mysql": ("localhost", 3306),
        "rabbitmq": ("localhost", 5672),
    }

    for dep in deps:
        if dep not in checks:
            continue
        host, port = checks[dep]
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        try:
            result = sock.connect_ex((host, port))
            if result == 0:
                print(f"  OK - {dep} is ready ({host}:{port})")
            else:
                print(f"  MISSING - {dep} not ready ({host}:{port}), please start first")
        except Exception as e:
            print(f"  ERROR - {dep} check failed: {e}")
        finally:
            sock.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Service startup script")
    parser.add_argument("service", nargs="?", choices=list(SERVICES.keys()) + ["all", "check"],
                        help="Start specific service, 'all', or 'check' for dependency check")
    args = parser.parse_args()

    if args.service == "check":
        all_deps = set()
        for info in SERVICES.values():
            all_deps.update(info.get("deps", []))
        print("Checking dependency services...")
        check_dependencies(list(all_deps))
        return

    target = args.service or "all"

    if target == "all":
        all_deps = set()
        for info in SERVICES.values():
            all_deps.update(info.get("deps", []))
        print("Checking dependencies first...")
        check_dependencies(list(all_deps))

        procs = {}
        for name in SERVICES:
            procs[name] = start_service(name)

        print("\nAll services started. Press Ctrl+C to stop...\n")

        try:
            signal.signal(signal.SIGINT, lambda s, f: None)
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping all services...")
            for name, proc in procs.items():
                print(f"Stopping {name}...")
                stop_service(proc)
    else:
        proc = start_service(target)
        if proc:
            print(f"\n{target} started (PID: {proc.pid}). Press Ctrl+C to stop...\n")
            try:
                proc.wait()
            except KeyboardInterrupt:
                stop_service(proc)


if __name__ == "__main__":
    main()
