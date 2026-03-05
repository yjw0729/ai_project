#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG系统监控和管理工具
提供命令行界面来查看和管理RAG系统状态
"""

import requests
import json
import time
from datetime import datetime
import os
import sys

class RAGMonitor:
    """RAG系统监控器"""

    def __init__(self, base_url="http://localhost:8015"):
        self.base_url = base_url
        self.session = requests.Session()

    def make_request(self, endpoint, method="GET", **kwargs):
        """发送HTTP请求"""
        try:
            url = f"{self.base_url}{endpoint}"
            response = self.session.request(method, url, **kwargs)
            return response.json() if response.status_code == 200 else None
        except:
            return None

    def print_header(self, title):
        """打印标题"""
        print("\n" + "="*60)
        print(f" {title}")
        print("="*60)

    def print_separator(self):
        """打印分隔线"""
        print("-" * 60)

    def format_size(self, size_mb):
        """格式化文件大小"""
        if size_mb < 1024:
            return f"{size_mb:.1f} MB"
        else:
            return f"{size_mb/1024:.1f} GB"

    def show_overview(self):
        """显示系统概览"""
        self.print_header("📊 RAG系统概览")

        data = self.make_request("/rag_service/stats")
        if not data or data.get('code') != 200:
            print("❌ 无法获取系统统计信息")
            return

        stats = data['data']

        # 概览信息
        overview = stats.get('overview', {})
        print(f"   📚 集合数量: {overview.get('total_collections', 0)}")
        print(f"   🧩 总文本块: {overview.get('total_chunks', 0)}")
        print(f"   📏 向量维度: {overview.get('vector_dimensions', 768)}")

        # 向量数据库信息
        vector_db = stats.get('vector_database', {})
        print(f"   类型: {vector_db.get('db_type', 'unknown')}")
        print(f"   集合数: {vector_db.get('collection_count', 0)}")
        print(f"   存储路径: {vector_db.get('storage_path', 'unknown')}")

        # 存储信息
        storage = stats.get('storage', {})
        print(f"   ChromaDB数据: {self.format_size(storage.get('chroma_data_size', 0))}")
        print(f"   上传文件: {self.format_size(storage.get('uploads_size', 0))}")
        print(f"   缓存文件: {self.format_size(storage.get('cache_size', 0))}")
        print(f"   日志文件: {self.format_size(storage.get('logs_size', 0))}")
        print(f"   RAG总大小: {self.format_size(storage.get('total_rag_size', 0))}")

        # 系统磁盘信息
        system_disk = storage.get('system_disk', {})
        if 'total' in system_disk:
            print(f" 总容量: {system_disk['total']:.1f} GB")
            print(f"   已使用: {system_disk['used']:.1f} GB ({system_disk['percent']}%)")
            print(f"   可用: {system_disk['free']:.1f} GB")

        print(f"\n📅 最后更新: {stats.get('last_updated', 'unknown')}")

    def show_collections(self):
        """显示集合列表"""
        self.print_header("📚 集合管理")

        data = self.make_request("/rag_service/stats")
        if not data or data.get('code') != 200:
            print("❌ 无法获取集合信息")
            return

        collections = data['data'].get('collections', [])

        if not collections:
            print("📭 系统中暂无集合")
            return

        print(f"{'名称':<20} {'块数量':<10} {'创建时间':<20}")
        print("-" * 60)

        for collection in collections:
            name = collection.get('name', 'unknown')[:18]
            chunks = str(collection.get('total_chunks', 0))
            created = collection.get('created_at', 'unknown')[:19]  # 只显示日期时间部分
            print(f"{name:<20} {chunks:<10} {created:<20}")

        print(f"\n共 {len(collections)} 个集合")

        # 让用户选择查看详细信息
        if len(collections) > 0:
            print("\n输入集合名称查看详细信息 (按回车跳过):")
            choice = input("集合名称: ").strip()
            if choice:
                self.show_collection_detail(choice)

    def show_collection_detail(self, collection_name):
        """显示集合详细信息"""
        print(f"\n🔍 集合 '{collection_name}' 详细信息:")

        data = self.make_request(f"/rag_service/collections/{collection_name}/stats")
        if not data or data.get('code') != 200:
            print("❌ 无法获取集合详细信息")
            return

        col_data = data['data']

        print(f"   集合名称: {col_data.get('collection_name', 'unknown')}")
        print(f"   最后更新: {col_data.get('last_updated', 'unknown')}")

        basic_info = col_data.get('basic_info', {})
        if basic_info:
            print(f"      总块数: {basic_info.get('total_chunks', 0)}")
            print(f"      向量维度: {basic_info.get('vector_dim', 768)}")
            print(f"      索引类型: {basic_info.get('index_type', 'default')}")
            print(f"      创建时间: {basic_info.get('created_at', 'unknown')}")

        vector_stats = col_data.get('vector_stats', {})
        if vector_stats:
            print(f"      总实体数: {vector_stats.get('total_entities', 0)}")
            print(f"      相似度度量: {vector_stats.get('metric_type', 'cosine')}")

            chroma_info = vector_stats.get('chroma_info', {})
            if chroma_info and 'collection_name' in chroma_info:
                print(f"         集合ID: {chroma_info.get('collection_id', 'unknown')}")

    def show_business_modules(self):
        """显示业务模块统计"""
        self.print_header("🏢 业务模块管理")

        # 获取业务模块列表
        data = self.make_request("/rag_service/business_modules")
        if data and data.get('code') == 200:
            modules_data = data['data']
            modules = modules_data.get('modules', [])
            print("🏷️  配置的业务模块:")
            for module in modules:
                status = "✅" if module.get('enabled', True) else "❌"
                print(f"   {status} {module['name']} ({module['key']})")
                print(f"      分类: {module.get('category', 'unknown')}")
                print(f"      描述: {module.get('description', '无')}")
                print()

        # 获取业务模块统计
        data = self.make_request("/rag_service/stats")
        if data and data.get('code') == 200:
            business_modules = data['data'].get('business_modules', [])
            if business_modules:
                print(f"{'模块名称':<15} {'文档数':<8} {'块数':<8} {'状态':<6}")
                print("-" * 50)

                for module in business_modules:
                    name = module.get('name', 'unknown')[:12]
                    docs = str(module.get('document_count', 0))
                    chunks = str(module.get('chunk_count', 0))
                    status = "启用" if module.get('enabled', True) else "禁用"
                    print(f"{name:<15} {docs:<8} {chunks:<8} {status:<6}")

                print(f"\n共 {len(business_modules)} 个业务模块")

    def show_menu(self):
        """显示主菜单"""
        while True:
            self.print_header("🎯 RAG系统监控面板")
            print("1. 📊 系统概览")
            print("2. 📚 集合管理")
            print("3. 🏢 业务模块管理")
            print("4. 🔄 刷新数据")
            print("5. 🚪 退出")
            print()

            choice = input("请选择操作 (1-5): ").strip()

            if choice == "1":
                self.show_overview()
            elif choice == "2":
                self.show_collections()
            elif choice == "3":
                self.show_business_modules()
            elif choice == "4":
                print("🔄 刷新中...")
                time.sleep(1)
            elif choice == "5":
                print("👋 再见！")
                break
            else:
                print("❌ 无效选择，请重新输入")

            if choice in ["1", "2", "3"]:
                input("\n按回车键继续...")

    def run(self):
        """运行监控器"""
        print("🚀 启动RAG系统监控器...")

        # 检查服务是否运行
        try:
            response = self.session.get(f"{self.base_url}/rag_service/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 200:
                    print("✅ 成功连接到RAG服务")
                    self.show_menu()
                else:
                    print("❌ RAG服务返回错误")
            else:
                print("❌ RAG服务响应异常")
        except requests.exceptions.ConnectionError:
            print("❌ 无法连接到RAG服务")
            print(f"\n请确保服务正在运行在: {self.base_url}")
            print("\n启动命令:")
            print("  Docker部署: cd deploy && ./deploy_docker.sh")
            print("  本地运行: python -m pytest_sxp.app.run")
        except Exception as e:
            print(f"❌ 连接失败: {e}")

if __name__ == "__main__":
    # 支持命令行参数指定URL
    url = "http://localhost:8015"
    if len(sys.argv) > 1:
        url = sys.argv[1]

    monitor = RAGMonitor(url)
    monitor.run()
