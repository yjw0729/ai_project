#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG服务启动脚本
一键启动完整的RAG文档处理服务
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def check_dependencies():
    """检查依赖"""
    print("🔍 检查依赖...")

    required_packages = [
        'flask',
        'chromadb',
        'python-docx',
        'scikit-learn',
        'sentence-transformers',  # 可选，用于本地embedding
        'torch',  # 可选，用于本地模型
    ]

    missing_packages = []

    for package in required_packages:
        try:
            if package == 'sentence-transformers':
                import sentence_transformers
            elif package == 'python-docx':
                import docx
            elif package == 'scikit-learn':
                import sklearn
            elif package == 'chromadb':
                import chromadb
            elif package == 'torch':
                import torch
            else:
                __import__(package)
            print(f"✅ {package}")
        except ImportError:
            if package in ['sentence-transformers', 'torch']:
                print(f"⚠️  {package} (可选，用于本地embedding)")
            else:
                print(f"❌ {package} (必需)")
                missing_packages.append(package)

    if missing_packages:
        print(f"pip install {' '.join(missing_packages)}")
        return False

    return True

def check_config():
    """检查配置"""
    print("\n🔧 检查配置...")

    config_files = [
        'app/config/vector_db/vector_db.json',
        'app/config/rag/rag.json'
    ]

    for config_file in config_files:
        if os.path.exists(config_file):
            print(f"✅ {config_file}")
        else:
            print(f"❌ 缺少配置文件: {config_file}")
            return False

    return True

def start_service():
    """启动服务"""
    print("\n🚀 启动RAG服务...")

    try:
        # 设置环境变量
        os.environ['FLASK_APP'] = 'app/application.py'
        os.environ['FLASK_DEBUG'] = '1'

        # 启动Flask应用
        print("启动Flask应用 (http://localhost:8080)...")
        print("按 Ctrl+C 停止服务")
        print("-" * 50)

        # 使用subprocess启动服务
        cmd = [sys.executable, 'app/application.py']
        process = subprocess.run(cmd)

        return process.returncode == 0

    except KeyboardInterrupt:
        print("\n🛑 服务已停止")
        return True
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return False

def show_usage_guide():
    """显示使用指南"""
    print("\n" + "="*60)
    print("🎉 RAG服务启动成功!")
    print("="*60)
    print("📖 快速使用指南:")
    print()
    print("1. 📤 上传Word文档:")
    print("   curl -X POST http://localhost:8080/rag_service/upload \\")
    print("     -F \"file=@your_document.docx\" \\")
    print("     -F \"document_title=产品设计文档\"")
    print()
    print("2. 🔍 查询文档:")
    print("   curl -X POST http://localhost:8080/rag_service/query \\")
    print("     -H \"Content-Type: application/json\" \\")
    print("     -d '{\"query\": \"产品主要功能是什么？\"}'")
    print()
    print("3. 📋 查看集合:")
    print("   curl http://localhost:8080/rag_service/collections")
    print()
    print("4. 🏥 健康检查:")
    print("   curl http://localhost:8080/rag_service/health")
    print()
    print("📚 详细文档: RAG_API_GUIDE.md")
    print("🧪 测试脚本: python test_rag_api.py")
    print("="*60)

def main():
    """主函数"""
    print("🤖 RAG文档处理服务启动器")
    print("=" * 40)

    # 1. 检查依赖
    if not check_dependencies():
        print("❌ 依赖检查失败，请安装所需的包")
        return

    # 2. 检查配置
    if not check_config():
        print("❌ 配置检查失败，请检查配置文件")
        return

    # 3. 显示配置信息
    print("\n📋 当前配置:")
    try:
        with open('app/config/vector_db/vector_db.json', 'r', encoding='utf-8') as f:
            vector_config = f.read()
        print(f"向量数据库: {vector_config}")

        with open('app/config/rag/rag.json', 'r', encoding='utf-8') as f:
            rag_config = f.read()
        print(f"RAG配置: {rag_config}")
    except Exception as e:
        print(f"读取配置失败: {e}")

    # 4. 启动服务
    if start_service():
        show_usage_guide()
    else:
        print("❌ 服务启动失败")

if __name__ == "__main__":
    main()
