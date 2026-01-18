#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试不同文档类型的向量化功能
"""

import asyncio
import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.rag.core.vector_indexer import VectorIndexer
from common.rag.core.config_manager import ConfigManager
from common.rag.core.models import DocumentChunk, DocumentType

async def test_different_embedding_models():
    """测试不同文档类型的向量化"""

    print("=" * 60)
    print("🧪 测试不同文档类型的向量化功能")
    print("=" * 60)

    try:
        # 初始化配置管理器
        config_manager = ConfigManager("app/config")

        # 初始化向量索引器
        indexer = VectorIndexer(config_manager)

        # 测试文本
        test_texts = [
            "用户需要能够通过手机号和密码登录系统",
            "API接口需要返回JSON格式的数据",
            "def login_user(username, password): return authenticate(username, password)",
            "数据库表结构设计：user(id, username, email, created_at)"
        ]

        # 测试不同文档类型
        doc_types = [
            DocumentType.PRODUCT_REQ,
            DocumentType.API_DOC,
            DocumentType.TECH_SPEC,
            DocumentType.TEST_CASE
        ]

        for i, doc_type in enumerate(doc_types):
            print(f"\n📄 测试文档类型: {doc_type.value}")

            # 创建文档块
            chunk = DocumentChunk(
                content=test_texts[i],
                doc_type=doc_type,
                chunk_index=0,
                start_pos=0,
                end_pos=len(test_texts[i])
            )

            # 获取embedding配置
            embedding_config = indexer._get_embedding_config_for_document(doc_type.value)
            print(f"   使用模型: {embedding_config['provider']}/{embedding_config['model']}")
            print(f"   向量维度: {embedding_config.get('dimension', '未知')}")

            # 生成向量
            vectors = await indexer.generate_embeddings([test_texts[i]], embedding_config)
            print(f"   生成向量: {len(vectors)}个, 维度: {len(vectors[0]) if vectors else 0}")

        print("\n✅ 所有文档类型测试完成！")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_different_embedding_models())


