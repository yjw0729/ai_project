#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试统计API功能
"""

import requests
import json
import time

def test_stats_api():
    """测试统计API"""

    base_url = "http://localhost:8015"

    print("=" * 80)
    print("🧪 测试RAG系统统计API")
    print("=" * 80)

    try:
        # 1. 测试获取系统统计
        print("\n1️⃣ 测试获取系统统计信息...")
        response = requests.get(f"{base_url}/rag_service/stats")

        if response.status_code == 200:
            data = response.json()
            if data['code'] == 200:
                stats = data['data']
                print("✅ 系统统计获取成功!")

                # 显示概览信息
                overview = stats.get('overview', {})
                print("
📊 系统概览:"                print(f"   集合数量: {overview.get('total_collections', 0)}")
                print(f"   总文本块: {overview.get('total_chunks', 0)}")
                print(f"   向量维度: {overview.get('vector_dimensions', 768)}")

                # 显示存储信息
                storage = stats.get('storage', {})
                print("
💾 存储信息:"                print(f"   ChromaDB数据: {storage.get('chroma_data_size', 0)} MB")
                print(f"   上传文件: {storage.get('uploads_size', 0)} MB")
                print(f"   缓存文件: {storage.get('cache_size', 0)} MB")
                print(f"   日志文件: {storage.get('logs_size', 0)} MB")
                print(f"   RAG总大小: {storage.get('total_rag_size', 0)} MB")

                # 显示系统磁盘信息
                system_disk = storage.get('system_disk', {})
                if 'total' in system_disk:
                    print("
🖥️  系统磁盘:"                    print(f"   总容量: {system_disk['total']} GB")
                    print(f"   已使用: {system_disk['used']} GB")
                    print(f"   可用: {system_disk['free']} GB")
                    print(f"   使用率: {system_disk['percent']}%")

                # 显示业务模块统计
                business_modules = stats.get('business_modules', [])
                print("
🏢 业务模块统计:"                for module in business_modules:
                    print(f"   {module['name']} ({module['module_key']}):")
                    print(f"      文档数: {module['document_count']}")
                    print(f"      块数: {module['chunk_count']}")
                    print(f"      状态: {'启用' if module['enabled'] else '禁用'}")

            else:
                print(f"❌ API返回错误: {data.get('message', '未知错误')}")
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")

        # 2. 测试获取业务模块列表
        print("\n2️⃣ 测试获取业务模块列表...")
        response = requests.get(f"{base_url}/rag_service/business_modules")

        if response.status_code == 200:
            data = response.json()
            if data['code'] == 200:
                modules_data = data['data']
                modules = modules_data.get('modules', [])
                print(f"✅ 业务模块列表获取成功! 共 {len(modules)} 个模块")

                for module in modules[:3]:  # 只显示前3个
                    print(f"   🏷️  {module['name']} ({module['key']}) - {module['description']}")
            else:
                print(f"❌ API返回错误: {data.get('message', '未知错误')}")
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")

        # 3. 测试集合详细信息（如果有集合的话）
        print("\n3️⃣ 测试集合详细信息...")

        # 首先获取系统统计，看有哪些集合
        response = requests.get(f"{base_url}/rag_service/stats")
        if response.status_code == 200:
            data = response.json()
            if data['code'] == 200:
                collections = data['data'].get('collections', [])
                if collections:
                    # 测试第一个集合的详细信息
                    collection_name = collections[0].get('name', '')
                    if collection_name:
                        print(f"   查询集合: {collection_name}")
                        response = requests.get(f"{base_url}/rag_service/collections/{collection_name}/stats")

                        if response.status_code == 200:
                            data = response.json()
                            if data['code'] == 200:
                                col_data = data['data']
                                print("✅ 集合详细信息获取成功!"                                print(f"      集合名称: {col_data.get('collection_name', 'unknown')}")
                                basic_info = col_data.get('basic_info', {})
                                print(f"      块数量: {basic_info.get('total_chunks', 0)}")
                                vector_stats = col_data.get('vector_stats', {})
                                print(f"      向量维度: {vector_stats.get('vector_dimensions', 768)}")
                            else:
                                print(f"❌ API返回错误: {data.get('message', '未知错误')}")
                        else:
                            print(f"❌ HTTP请求失败: {response.status_code}")
                else:
                    print("   ℹ️  系统中暂无集合")
            else:
                print("   ⚠️  无法获取集合列表")

        print("\n" + "=" * 80)
        print("🎉 统计API测试完成！")
        print("这些API可以让您清楚地了解系统中的数据存储情况！")
        print("=" * 80)

    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器，请确保应用正在运行在 http://localhost:8015")
        print("\n启动命令:")
        print("cd deploy && ./deploy_docker.sh")
        print("或者: python -m pytest_sxp.app.run")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_stats_api()


