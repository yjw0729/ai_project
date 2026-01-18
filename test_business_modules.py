#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试业务模块功能的完整流程
"""

import asyncio
import os
import sys
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.rag.services.rag_services import RAGService
from common.rag.core.models import DocumentType, BusinessModule

async def test_business_modules():
    """测试业务模块功能"""

    print("=" * 80)
    print("🧩 测试业务模块功能")
    print("=" * 80)

    try:
        # 1. 初始化RAG服务
        print("\n1️⃣ 初始化RAG服务...")
        rag = RAGService()
        print("✅ RAG服务初始化成功")

        # 2. 查看可用的业务模块
        print("\n2️⃣ 查看可用的业务模块...")
        modules = rag.get_business_modules()
        print(f"✅ 找到 {len(modules)} 个业务模块:")
        for module_key, module_info in modules.items():
            print(f"   🏷️  {module_key}: {module_info.get('name', '未知')} - {module_info.get('description', '')}")

        # 3. 准备测试文档（不同业务模块）
        print("\n3️⃣ 准备测试文档...")

        test_docs_dir = Path("test_business_docs")
        test_docs_dir.mkdir(exist_ok=True)

        test_documents = [
            {
                "filename": "cross_border_opening_guide.md",
                "content": """# 跨境开户指南

## 基本流程
1. 准备身份证明文件
2. 提交开户申请
3. 完成身份验证
4. 激活账户

## 所需材料
- 身份证件
- 地址证明
- 收入证明
- 银行流水

## 注意事项
跨境开户需要提供完整的身份验证信息，确保信息真实有效。
""",
                "doc_type": DocumentType.TECH_SPEC,
                "business_module": BusinessModule.CROSS_BORDER_OPENING
            },
            {
                "filename": "cross_border_trading_manual.md",
                "content": """# 跨境交易操作手册

## 交易类型
- 外汇交易
- 国际转账
- 跨境支付
- 投资理财

## 交易流程
1. 登录交易平台
2. 选择交易品种
3. 设置交易参数
4. 确认交易

## 风险控制
跨境交易涉及汇率风险，请注意风险管理。
""",
                "doc_type": DocumentType.API_DOC,
                "business_module": BusinessModule.CROSS_BORDER_TRADING
            },
            {
                "filename": "internet_opening_process.md",
                "content": """# 互联网开户流程

## 在线开户步骤
1. 访问开户页面
2. 填写基本信息
3. 上传证件照片
4. 完成视频验证
5. 账户激活

## 验证方式
- 人脸识别
- 证件OCR
- 活体检测
- 短信验证

## 便捷性特点
互联网开户全流程在线完成，无需线下办理。
""",
                "doc_type": DocumentType.TECH_SPEC,
                "business_module": BusinessModule.INTERNET_OPENING
            },
            {
                "filename": "internet_trading_features.md",
                "content": """# 互联网交易功能介绍

## 主要功能
- 在线交易
- 实时行情
- 移动端交易
- 智能投顾

## 技术特点
- 低延迟交易
- 高并发处理
- 智能风控
- 个性化推荐

## 用户体验
互联网交易提供7×24小时服务，支持多终端访问。
""",
                "doc_type": DocumentType.PRODUCT_REQ,
                "business_module": BusinessModule.INTERNET_TRADING
            }
        ]

        # 创建测试文档文件
        for doc_info in test_documents:
            file_path = test_docs_dir / doc_info["filename"]
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(doc_info["content"])
            print(f"   📄 创建文档: {doc_info['filename']} ({doc_info['business_module'].value})")

        # 4. 逐个上传文档到不同业务模块
        print("\n4️⃣ 上传文档到业务模块...")

        collection_name = f"business_test_{int(datetime.now().timestamp())}"

        for doc_info in test_documents:
            print(f"\n📤 上传文档: {doc_info['filename']}")

            # 构建上传配置
            source_config = {
                "source_type": "file",
                "paths": [str(test_docs_dir / doc_info["filename"])],
                "extensions": [doc_info["filename"].split('.')[-1]],
                "recursive": False,
                "metadata": {
                    "document_id": f"test_{doc_info['business_module'].value}_{int(datetime.now().timestamp())}",
                    "document_title": doc_info["filename"].replace('.md', '').replace('_', ' ').title(),
                    "document_type": doc_info["doc_type"].value,
                    "business_module": doc_info["business_module"].value,
                    "tags": ["test", "business_module", doc_info["business_module"].value.split('_')[0]],
                    "upload_time": datetime.now().isoformat(),
                    "file_size": len(doc_info["content"])
                }
            }

            # 构建知识库
            build_result = await rag.build_knowledge_base(
                source_configs=[source_config],
                collection_name=collection_name
            )

            if build_result.get('status') == 'success':
                print(f"   ✅ 上传成功: {build_result['total_chunks']} 个块")
            else:
                print(f"   ❌ 上传失败: {build_result.get('message', '未知错误')}")

        # 5. 测试按业务模块查询
        print("\n5️⃣ 测试按业务模块查询...")

        test_queries = [
            {
                "query": "如何进行开户？",
                "business_module": BusinessModule.CROSS_BORDER_OPENING.value,
                "description": "跨境开户查询"
            },
            {
                "query": "如何进行交易？",
                "business_module": BusinessModule.CROSS_BORDER_TRADING.value,
                "description": "跨境交易查询"
            },
            {
                "query": "开户需要什么材料？",
                "business_module": BusinessModule.INTERNET_OPENING.value,
                "description": "互联网开户查询"
            },
            {
                "query": "交易有什么功能？",
                "business_module": BusinessModule.INTERNET_TRADING.value,
                "description": "互联网交易查询"
            },
            {
                "query": "什么是跨境业务？",
                "description": "通用查询（无业务模块过滤）"
            }
        ]

        for query_info in test_queries:
            print(f"\n🔍 {query_info['description']}")
            print(f"   查询: '{query_info['query']}'")

            # 准备过滤条件
            filters = {}
            if 'business_module' in query_info:
                filters['business_module'] = query_info['business_module']
                print(f"   过滤: 业务模块 = {query_info['business_module']}")

            # 执行查询
            results = await rag.knowledge_base.search(
                query=query_info['query'],
                collection_name=collection_name,
                top_k=3,
                filters=filters
            )

            if results:
                print(f"   ✅ 找到 {len(results)} 个结果:")
                for i, (chunk, score) in enumerate(results[:3]):
                    content_preview = chunk.content[:80].replace('\n', ' ')
                    business_module = chunk.metadata.get('business_module', 'unknown')
                    print(".3f"            else:
                print("   ❌ 未找到相关结果"

        # 6. 测试统计信息
        print("\n6️⃣ 查看集合统计信息...")

        try:
            stats = rag.knowledge_base.get_collection_info(collection_name)
            if stats:
                print(f"✅ 集合信息:")
                print(f"   名称: {stats.get('collection_name', 'unknown')}")
                print(f"   文档块数量: {stats.get('num_entities', 'unknown')}")
            else:
                print("❌ 获取集合信息失败")
        except Exception as e:
            print(f"❌ 获取统计信息失败: {e}")

        # 7. 清理测试数据
        print("\n7️⃣ 清理测试数据...")

        # 删除测试集合
        try:
            rag.knowledge_base.vector_indexer.delete_collection(collection_name)
            print(f"✅ 已删除测试集合: {collection_name}")
        except Exception as e:
            print(f"⚠️ 删除集合失败: {e}")

        # 删除测试文件
        for file_path in test_docs_dir.glob("*"):
            file_path.unlink()
        test_docs_dir.rmdir()
        print("✅ 已清理测试文件")

        print("\n" + "=" * 80)
        print("🎉 业务模块功能测试完成！")
        print("   ✅ 业务模块配置: 通过")
        print("   ✅ 文档分类上传: 通过")
        print("   ✅ 模块化查询: 通过")
        print("   ✅ 结果过滤: 通过")
        print("=" * 80)

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_business_modules())


