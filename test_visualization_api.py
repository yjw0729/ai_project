#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试可视化API功能
"""

import requests
import json
import time

def test_visualization_api():
    """测试可视化API"""

    base_url = "http://localhost:8015"

    print("=" * 80)
    print("🎨 测试RAG系统可视化API")
    print("=" * 80)

    try:
        # 1. 获取系统统计，找到可用的集合
        print("\n1️⃣ 获取系统统计信息...")
        response = requests.get(f"{base_url}/rag_service/stats")

        collections = []
        if response.status_code == 200:
            data = response.json()
            if data['code'] == 200:
                collections = data['data'].get('collections', [])
                print(f"✅ 找到 {len(collections)} 个集合")
                for col in collections[:3]:  # 只显示前3个
                    print(f"   📚 {col.get('name', 'unknown')}: {col.get('total_chunks', 0)} 个块")
            else:
                print(f"❌ 获取统计失败: {data.get('message', '未知错误')}")
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")

        if not collections:
            print("⚠️  系统中没有集合，跳过可视化测试")
            return

        # 使用第一个集合进行测试
        test_collection = collections[0].get('name', 'documents')

        # 2. 测试2D UMAP可视化
        print("
2️⃣ 测试2D UMAP可视化..."        params = {
            'algo': 'umap',
            'n': 100,
            'dim': 2,
            'sample_strategy': 'random'
        }

        response = requests.get(f"{base_url}/rag_service/collections/{test_collection}/visualize", params=params)

        if response.status_code == 200:
            data = response.json()
            if data['code'] == 200:
                vis_data = data['data']
                coords = vis_data.get('coords', [])
                print("✅ 2D UMAP可视化成功!"                print(f"   📊 算法: {vis_data.get('algo', 'unknown')}")
                print(f"   📏 维度: {vis_data.get('dim', 0)}D")
                print(f"   🔢 样本数: {len(coords)}")
                print(f"   📈 总样本: {vis_data.get('summary', {}).get('total', 0)}")

                if coords:
                    # 显示前3个坐标点
                    for i, coord in enumerate(coords[:3]):
                        print(".3f"            else:
                print("   ⚠️  未返回坐标数据")
            else:
                print(f"❌ 可视化失败: {data.get('message', '未知错误')}")
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")

        # 3. 测试3D T-SNE可视化
        print("
3️⃣ 测试3D T-SNE可视化..."        params = {
            'algo': 'tsne',
            'n': 50,
            'dim': 3,
            'sample_strategy': 'random',
            'seed': 42
        }

        response = requests.get(f"{base_url}/rag_service/collections/{test_collection}/visualize", params=params)

        if response.status_code == 200:
            data = response.json()
            if data['code'] == 200:
                vis_data = data['data']
                coords = vis_data.get('coords', [])
                print("✅ 3D T-SNE可视化成功!"                print(f"   📊 算法: {vis_data.get('algo', 'unknown')}")
                print(f"   📏 维度: {vis_data.get('dim', 0)}D")
                print(f"   🔢 样本数: {len(coords)}")

                if coords and len(coords) > 0:
                    coord = coords[0]
                    has_z = 'z' in coord
                    print(".3f"                    if has_z:
                        print(".3f"                    print(f"   🏷️  标签: {coord.get('label', 'unknown')}")
                    print(f"   📋 元数据: doc_id={coord.get('meta', {}).get('doc_id', 'unknown')}")
            else:
                print(f"❌ 可视化失败: {data.get('message', '未知错误')}")
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")

        # 4. 测试业务模块过滤可视化
        print("
4️⃣ 测试业务模块过滤可视化..."        # 获取可用的业务模块
        response = requests.get(f"{base_url}/rag_service/business_modules")
        business_modules = []
        if response.status_code == 200:
            data = response.json()
            if data['code'] == 200:
                modules_data = data['data']
                business_modules = [module['key'] for module in modules_data.get('modules', [])]

        if business_modules:
            test_module = business_modules[0]
            print(f"   🎯 使用业务模块过滤: {test_module}")

            params = {
                'algo': 'umap',
                'n': 100,
                'dim': 2,
                'module': test_module
            }

            response = requests.get(f"{base_url}/rag_service/collections/{test_collection}/visualize", params=params)

            if response.status_code == 200:
                data = response.json()
                if data['code'] == 200:
                    vis_data = data['data']
                    coords = vis_data.get('coords', [])
                    print("✅ 业务模块过滤可视化成功!"                    print(f"   🎯 业务模块: {vis_data.get('summary', {}).get('business_module', 'unknown')}")
                    print(f"   🔢 样本数: {len(coords)}")
                else:
                    print(f"❌ 可视化失败: {data.get('message', '未知错误')}")
            else:
                print(f"❌ HTTP请求失败: {response.status_code}")
        else:
            print("   ⚠️  未找到业务模块，跳过过滤测试")

        # 5. 测试原始向量数据接口
        print("
5️⃣ 测试原始向量数据接口..."        params = {
            'limit': 10
        }

        response = requests.get(f"{base_url}/rag_service/collections/{test_collection}/vectors", params=params)

        if response.status_code == 200:
            data = response.json()
            if data['code'] == 200:
                raw_data = data['data']
                print("✅ 原始向量数据获取成功!"                print(f"   🔢 向量数量: {len(raw_data)}")

                if raw_data:
                    vector = raw_data[0]
                    print(f"   📏 向量维度: {len(vector.get('vector', []))}")
                    print(f"   🏷️  标签: {vector.get('label', 'unknown')}")
                    print(f"   📋 案例ID: {vector.get('case_id', 'unknown')}")
            else:
                print(f"❌ 获取失败: {data.get('message', '未知错误')}")
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")

        # 6. 测试参数验证
        print("
6️⃣ 测试参数验证..."        # 测试无效算法
        params = {'algo': 'invalid', 'n': 10, 'dim': 2}
        response = requests.get(f"{base_url}/rag_service/collections/{test_collection}/visualize", params=params)

        if response.status_code == 400:
            data = response.json()
            if 'algo参数必须是' in data.get('message', ''):
                print("✅ 参数验证正常：算法参数验证通过")
            else:
                print(f"❌ 参数验证异常: {data.get('message', '')}")
        else:
            print("❌ 期望400错误码，但收到其他状态码")

        print("\n" + "=" * 80)
        print("🎉 可视化API测试完成！")
        print("这些接口可以为前端提供3D向量可视化能力！")
        print("=" * 80)

        # 提供前端使用的示例数据
        print("
📋 前端集成示例:"        print("""
前端调用示例：

// 2D UMAP可视化
const response = await fetch('/rag_service/collections/documents/visualize?algo=umap&n=1000&dim=2');
const data = await response.json();

// 3D T-SNE可视化（指定业务模块）
const response3D = await fetch('/rag_service/collections/documents/visualize?algo=tsne&n=500&dim=3&module=cross_border_opening');

// 使用ECharts-GL渲染3D散点图
option = {
  xAxis3D: {}, yAxis3D: {}, zAxis3D: {},
  grid3D: {},
  series: [{
    type: 'scatter3D',
    data: data.data.coords.map(item => [item.x, item.y, item.z]),
    symbolSize: 8,
    itemStyle: { opacity: 0.8 }
  }]
};
""")

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
    test_visualization_api()
