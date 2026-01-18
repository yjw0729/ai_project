#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG系统完整流程测试脚本
测试从文档采集到检索查询的完整流程
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
from common.rag.core.models import DocumentType

async def test_document_processing_pipeline():
    """测试文档处理完整流程"""

    print("=" * 80)
    print("🧪 RAG系统文档处理流水线测试")
    print("=" * 80)

    try:
        # 1. 初始化RAG服务
        print("\n1️⃣ 初始化RAG服务...")
        rag = RAGService()
        print("✅ RAG服务初始化成功")

        # 2. 准备测试文档
        print("\n2️⃣ 准备测试文档...")

        # 创建测试目录
        test_docs_dir = Path("test_documents")
        test_docs_dir.mkdir(exist_ok=True)

        # 创建不同类型的测试文档
        test_documents = {
            "api_doc.md": {
                "content": """# 用户登录API文档

## 接口描述
用户登录接口，用于验证用户身份并返回访问令牌。

## 请求参数
- `username`: 用户名，字符串类型，必填
- `password`: 密码，字符串类型，必填
- `remember_me`: 记住登录状态，布尔类型，可选

## 响应格式
```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "token": "jwt_token_string",
    "user_info": {
      "user_id": 123,
      "username": "testuser"
    }
  }
}
```

## 错误码说明
- 400: 参数错误
- 401: 用户名或密码错误
- 429: 请求过于频繁
""",
                "doc_type": DocumentType.API_DOC
            },

            "requirements.txt": {
                "content": """产品需求文档 - 用户管理系统

1. 用户注册功能
   - 支持手机号注册
   - 支持邮箱注册
   - 密码强度验证
   - 验证码机制

2. 用户登录功能
   - 支持账号密码登录
   - 支持手机号验证码登录
   - 支持第三方登录（微信、支付宝）
   - 记住登录状态功能

3. 用户信息管理
   - 个人资料修改
   - 头像上传功能
   - 密码修改
   - 账号绑定/解绑

4. 安全要求
   - 密码加密存储
   - JWT token认证
   - 请求频率限制
   - 登录失败锁定机制
""",
                "doc_type": DocumentType.PRODUCT_REQ
            },

            "code_example.py": {
                "content": """# 用户认证服务代码示例

from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime

auth_bp = Blueprint('auth', __name__)

class UserAuthService:
    \"\"\"用户认证服务\"\"\"

    def __init__(self, db_connection):
        self.db = db_connection

    def register_user(self, username, password, email):
        \"\"\"用户注册\"\"\"
        # 密码加密
        hashed_password = generate_password_hash(password)

        # 存储到数据库
        user_id = self.db.insert_user({
            'username': username,
            'password': hashed_password,
            'email': email,
            'created_at': datetime.datetime.now()
        })

        return {'user_id': user_id, 'message': '注册成功'}

    def authenticate_user(self, username, password):
        \"\"\"用户认证\"\"\"
        # 从数据库获取用户信息
        user = self.db.get_user_by_username(username)

        if not user:
            return {'error': '用户不存在'}

        # 验证密码
        if not check_password_hash(user['password'], password):
            return {'error': '密码错误'}

        # 生成JWT token
        token = jwt.encode({
            'user_id': user['id'],
            'username': user['username'],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, 'secret_key', algorithm='HS256')

        return {
            'token': token,
            'user_info': {
                'user_id': user['id'],
                'username': user['username']
            }
        }

# 使用示例
auth_service = UserAuthService(db_connection)
result = auth_service.register_user('testuser', 'password123', 'test@example.com')
""",
                "doc_type": DocumentType.TECH_SPEC
            }
        }

        # 写入测试文件
        for filename, doc_info in test_documents.items():
            file_path = test_docs_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(doc_info["content"])
            print(f"   📄 创建测试文档: {filename} ({doc_info['doc_type'].value})")

        # 3. 测试文档采集
        print("\n3️⃣ 测试文档采集...")

        source_configs = [{
            "source_type": "file",
            "paths": [str(test_docs_dir)],
            "extensions": [".md", ".txt", ".py"],
            "recursive": True,
            "metadata": {
                "test_batch": "pipeline_test",
                "created_at": datetime.now().isoformat()
            }
        }]

        documents = await rag.data_collector.collect_from_multiple_sources(source_configs)

        print(f"✅ 文档采集完成: 发现 {len(documents)} 个文档")
        for doc in documents:
            print(f"   📋 {doc.id}: {Path(doc.source_uri).name} ({len(doc.content)} 字符)")

        if not documents:
            print("❌ 文档采集失败，未找到任何文档")
            return

        # 4. 测试文档处理
        print("\n4️⃣ 测试文档处理和分块...")

        chunks = rag.document_processor.process_documents(documents)

        print(f"✅ 文档处理完成: {len(documents)} 文档 → {len(chunks)} 块")

        # 统计分块信息
        chunk_stats = {}
        for chunk in chunks:
            doc_type = chunk.doc_type.value if chunk.doc_type else "unknown"
            if doc_type not in chunk_stats:
                chunk_stats[doc_type] = []
            chunk_stats[doc_type].append(len(chunk.content))

        for doc_type, lengths in chunk_stats.items():
            print(f"   📊 {doc_type}: {len(lengths)} 块, 平均长度: {sum(lengths)/len(lengths):.0f} 字符")

        if not chunks:
            print("❌ 文档分块失败，未生成任何块")
            return

        # 5. 测试向量化
        print("\n5️⃣ 测试向量化处理...")

        # 构建知识库（会自动进行向量化）
        collection_name = f"test_collection_{int(datetime.now().timestamp())}"

        build_result = await rag.build_knowledge_base(
            source_configs=source_configs,
            collection_name=collection_name
        )

        if build_result.get('status') == 'success':
            print("✅ 知识库构建成功!")
            print(f"   📚 集合名称: {build_result['collection_name']}")
            print(f"   📄 文档数量: {build_result['total_documents']}")
            print(f"   🧩 块数量: {build_result['total_chunks']}")
            print(f"   ⏱️  处理时间: {build_result['elapsed_seconds']:.2f}秒")
        else:
            print(f"❌ 知识库构建失败: {build_result.get('message', '未知错误')}")
            return

        # 6. 测试检索功能
        print("\n6️⃣ 测试检索功能...")

        test_queries = [
            "如何实现用户登录功能？",
            "用户注册需要哪些参数？",
            "JWT token是什么？",
            "密码应该如何加密存储？"
        ]

        for query in test_queries:
            print(f"\n🔍 查询: '{query}'")

            results = await rag.search(query, collection_name=collection_name, top_k=3)

            if results:
                print(f"   ✅ 找到 {len(results)} 个相关结果:")
                for i, (chunk, score) in enumerate(results[:3]):
                    content_preview = chunk.content[:100].replace('\n', ' ')
                    print(f"      {i+1}. 相关度: {score:.3f} - {content_preview}...")
            else:
                print("   ❌ 未找到相关结果")

        # 7. 测试集合管理
        print("\n7️⃣ 测试集合管理功能...")

        # 获取集合信息
        collections = rag.list_collections()
        print(f"✅ 当前集合数量: {len(collections)}")

        for collection in collections:
            if collection['name'] == collection_name:
                print(f"   📊 测试集合信息:")
                print(f"      名称: {collection['name']}")
                print(f"      块数量: {collection['total_chunks']}")
                print(f"      创建时间: {collection['created_at']}")
                break

        # 8. 清理测试数据
        print("\n8️⃣ 清理测试数据...")

        # 删除测试集合
        rag.vector_indexer.delete_collection(collection_name)
        print(f"✅ 已删除测试集合: {collection_name}")

        # 删除测试文件
        for file_path in test_docs_dir.glob("*"):
            file_path.unlink()
        test_docs_dir.rmdir()
        print("✅ 已清理测试文件")

        print("\n" + "=" * 80)
        print("🎉 RAG系统流水线测试完成！")
        print("   ✅ 文档采集: 通过")
        print("   ✅ 文档分块: 通过")
        print("   ✅ 向量化: 通过")
        print("   ✅ 向量存储: 通过")
        print("   ✅ 检索查询: 通过")
        print("   ✅ 集合管理: 通过")
        print("=" * 80)

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

async def test_custom_document():
    """测试用户提供的自定义文档"""

    print("\n" + "=" * 80)
    print("📄 测试自定义文档")
    print("=" * 80)

    print("\n请将你的文档文件放到项目根目录，然后告诉我文件名和文档类型。")
    print("支持的文档类型:")
    print("  - api_documentation: API文档")
    print("  - product_requirement: 产品需求文档")
    print("  - design_document: 设计文档")
    print("  - technical_specification: 技术规范")
    print("  - test_case: 测试用例")

    print("\n例如:")
    print("  文档名: my_api.pdf")
    print("  类型: api_documentation")

if __name__ == "__main__":
    print("选择测试类型:")
    print("1. 运行完整流水线测试（使用内置测试文档）")
    print("2. 测试自定义文档")

    choice = input("\n请选择 (1 或 2): ").strip()

    if choice == "1":
        asyncio.run(test_document_processing_pipeline())
    elif choice == "2":
        asyncio.run(test_custom_document())
    else:
        print("无效选择")
