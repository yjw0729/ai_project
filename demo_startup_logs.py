#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演示启动日志输出
展示应用启动时会显示的系统状态信息
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

def demo_logs():
    """演示日志输出"""
    print("🚀 应用启动日志演示")
    print("=" * 60)
    print()

    # 模拟应用启动时的日志输出
    print("📝 以下是启动 application.py 或 run.py 时会看到的日志:")
    print()

    # 模拟系统状态检查日志
    print("2024-01-14 12:00:00,000 [INFO] [thread:MainThread] root - ====================================================")
    print("2024-01-14 12:00:00,001 [INFO] [thread:MainThread] root - 🚀 系统启动状态检查")
    print("2024-01-14 12:00:00,002 [INFO] [thread:MainThread] root - ====================================================")
    print("2024-01-14 12:00:00,003 [INFO] [thread:MainThread] root - ✅ 数据库状态: MySQL数据库连接正常")
    print("2024-01-14 12:00:00,004 [INFO] [thread:MainThread] root - ✅ RAG服务状态: 本地ChromaDB (持久化存储, 2个文件, 228.0KB) | 本地Embedding模型 (sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)")
    print("2024-01-14 12:00:00,005 [INFO] [thread:MainThread] root - 📋 已注册的API接口:")
    print("2024-01-14 12:00:00,006 [INFO] [thread:MainThread] root -    🔹 数据服务: /data_service/*")
    print("2024-01-14 12:00:00,007 [INFO] [thread:MainThread] root -    🔹 AI服务: /ai_service/*")
    print("2024-01-14 12:00:00,008 [INFO] [thread:MainThread] root -    🔹 RAG服务: /rag_service/*")
    print("2024-01-14 12:00:00,009 [INFO] [thread:MainThread] root - 🌐 服务端口: 8080")
    print("2024-01-14 12:00:00,010 [INFO] [thread:MainThread] root - ====================================================")
    print()

    # 模拟RAG服务初始化日志
    print("2024-01-14 12:00:00,011 [INFO] [thread:MainThread] common.rag.services.rag_services - ==================================================")
    print("2024-01-14 12:00:00,012 [INFO] [thread:MainThread] common.rag.services.rag_services - 🤖 RAG服务初始化详情:")
    print("2024-01-14 12:00:00,013 [INFO] [thread:MainThread] common.rag.services.rag_services -    📊 向量数据库: chroma")
    print("2024-01-14 12:00:00,014 [INFO] [thread:MainThread] common.rag.services.rag_services -    🧠 Embedding模型: local/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    print("2024-01-14 12:00:00,015 [INFO] [thread:MainThread] common.rag.services.rag_services -    💬 LLM模型: tongyi/qwen-turbo")
    print("2024-01-14 12:00:00,016 [INFO] [thread:MainThread] common.rag.services.rag_services -    📁 缓存目录: D:\\pythonProject\\pytest_sxp\\cache")
    print("2024-01-14 12:00:00,017 [INFO] [thread:MainThread] common.rag.services.rag_services - ==================================================")
    print("2024-01-14 12:00:00,018 [INFO] [thread:MainThread] common.rag.services.rag_services - ✅ RAG服务初始化完成")
    print()

    # 模拟启动成功信息
    print("服务启动成功，访问地址: http://172.20.10.4:8080")
    print()

    print("=" * 60)
    print("📊 日志说明:")
    print("• ✅ 数据库状态: 显示MySQL数据库连接是否正常")
    print("• ✅ RAG服务状态: 显示向量数据库和Embedding模型状态")
    print("• 📋 API接口: 列出所有可用的API端点")
    print("• 🌐 服务端口: 显示应用运行的端口")
    print("• 🤖 RAG详情: 显示RAG服务的具体配置信息")
    print("=" * 60)

if __name__ == "__main__":
    demo_logs()


