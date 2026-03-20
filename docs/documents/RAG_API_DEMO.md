#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG模块完整API接口文档和测试Demo
服务地址: http://172.20.10.4:8015
"""

BASE_URL = "http://172.20.10.4:8015"

API_DOCS = f"""
================================================================================
RAG模块API接口完整文档
================================================================================
服务地址: {BASE_URL}
服务端口: 8015
================================================================================

一、基础接口
================================================================================

1. 健康检查
--------------------------------------------------------------------------------
请求地址: GET {BASE_URL}/rag_service/health
返回示例:
{{
    "code": 200,
    "message": "服务正常",
    "data": {{
        "status": "healthy",
        "timestamp": "2026-03-04T13:30:03.718321",
        "version": "1.0.0"
    }}
}}

2. 获取业务模块列表
--------------------------------------------------------------------------------
请求地址: GET {BASE_URL}/rag_service/business_modules
返回示例:
{{
    "code": 200,
    "data": {{
        "modules": [
            {{
                "category": "cross_border",
                "description": "跨境业务开户申请文档",
                "enabled": true,
                "key": "cross_border_opening",
                "name": "跨境开户"
            }},
            ...
        ],
        "total_count": 4
    }},
    "message": "获取成功"
}}

3. 获取集合列表
--------------------------------------------------------------------------------
请求地址: GET {BASE_URL}/rag_service/collections
返回示例:
{{
    "code": 200,
    "data": [
        {{
            "name": "documents",
            "total_chunks": 10,
            "created_at": "2024-01-01T00:00:00",
            "last_updated": "2024-01-01T00:00:00"
        }}
    ],
    "message": "获取成功"
}}

================================================================================
二、文档上传和问答接口
================================================================================

1. 单文档上传（普通文档）
--------------------------------------------------------------------------------
请求地址: POST {BASE_URL}/rag_service/upload
Content-Type: multipart/form-data
参数说明:
- file: 文件 (必填)
- business_module: 业务模块 (必填，如: cross_border_opening)
- document_title: 文档标题 (可选)
- collection_name: 集合名称 (可选，默认: documents)
- document_type: 文档类型 (可选)
- tags: 标签JSON数组 (可选)

返回示例:
{{
    "code": 200,
    "data": {{
        "document_id": "uuid",
        "collection_name": "documents",
        "business_module": "cross_border_opening",
        "status": "completed",
        "chunks_count": 10,
        "file_path": "uploads/rag_docs/xxx.docx"
    }},
    "message": "文档上传并处理成功"
}}

调用示例(cURL):
curl -X POST "{BASE_URL}/rag_service/upload" \\
  -F "file=@your_document.docx" \\
  -F "business_module=cross_border_opening" \\
  -F "document_title=产品设计文档"

2. 查询文档内容（RAG问答）
--------------------------------------------------------------------------------
请求地址: POST {BASE_URL}/rag_service/query
Content-Type: application/json
参数说明:
- query: 查询问题 (必填)
- collection_name: 集合名称 (可选，默认查询所有)
- business_module: 业务模块 (可选)
- top_k: 返回结果数量 (可选，默认: 5)

返回示例:
{{
    "code": 200,
    "data": {{
        "query": "这个文档的主要内容是什么？",
        "answer": "根据文档内容，这是一个关于...",
        "sources": [
            {{
                "content": "文档内容片段...",
                "score": 0.85,
                "source": "文档名"
            }}
        ],
        "retrieved_count": 3,
        "elapsed_seconds": 1.2
    }},
    "message": "查询成功"
}}

调用示例:
curl -X POST "{BASE_URL}/rag_service/query" \\
  -H "Content-Type: application/json" \\
  -d '{{"query": "这个文档写了什么内容？", "top_k": 5}}'

================================================================================
三、PRD和技术文档双上传接口
================================================================================

1. 同时上传PRD和技术文档
--------------------------------------------------------------------------------
请求地址: POST {BASE_URL}/rag_service/upload_dual
Content-Type: multipart/form-data
参数说明:
- prd_file: PRD文档文件 (可选，至少上传一个)
- tech_spec_file: 技术规格文档文件 (可选，至少上传一个)
- business_module: 业务模块 (必填)
- collection_name: 集合名称 (可选)
- document_title: 文档标题 (可选)

返回示例:
{{
    "code": 200,
    "data": {{
        "prd_document_id": "uuid",
        "tech_spec_document_id": "uuid",
        "collection_name": "documents",
        "business_module": "cross_border_opening",
        "status": "completed",
        "prd_chunks_count": 5,
        "tech_spec_chunks_count": 10,
        "total_chunks_count": 15,
        "prompt_type": "both",
        "content_file": "xxx_content.json"
    }},
    "message": "文档上传并处理成功"
}}

2. 生成测试案例
--------------------------------------------------------------------------------
请求地址: POST {BASE_URL}/rag_service/generate_test_cases_v2
Content-Type: application/json
参数说明:
- content_file: 文档内容文件名 (必填，上传接口返回的content_file)
- prompt_type: 提示词类型 (可选: auto/prd/tech_spec/both，默认: auto)
- output_format: 输出格式 (可选: json，默认: json)

返回示例:
{{
    "code": 200,
    "message": "生成成功",
    "data": {{
        "test_cases": [
            {{
                "title": "验证功能正常",
                "module": "功能模块",
                "priority": "P0",
                "test_type": "功能测试",
                "precondition": "系统正常",
                "steps": ["步骤1", "步骤2"],
                "expected_result": "结果正确"
            }}
        ],
        "prompt_type": "both"
    }}
}}

================================================================================
四、版本迭代场景接口
================================================================================

1. 检索相关上下文
--------------------------------------------------------------------------------
请求地址: POST {BASE_URL}/rag_service/search_context
Content-Type: application/json
参数说明:
- query: 查询内容 (必填)
- collection_name: 集合名称 (可选)
- top_k: 返回结果数量 (可选，默认: 10)

返回示例:
{{
    "code": 200,
    "message": "查询成功",
    "data": {{
        "results": [
            {{
                "content": "相关内容片段",
                "score": 0.85,
                "metadata": {{}}
            }}
        ],
        "total": 10
    }}
}}

2. 生成迭代测试案例
--------------------------------------------------------------------------------
请求地址: POST {BASE_URL}/rag_service/generate_iteration_test_cases
Content-Type: application/json
参数说明:
- increment_content: 增量需求描述 (必填)
- iteration_type: 迭代类型 (可选: new_feature/bug_fix/optimization，默认: new_feature)
- collection_name: 集合名称 (可选)
- business_module: 业务模块 (可选)
- context_top_k: 检索相关上下文数量 (可选，默认: 10)
- output_format: 输出格式 (可选: json，默认: json)

返回示例:
{{
    "code": 200,
    "message": "生成成功",
    "data": {{
        "test_cases": [...],
        "iteration_type": "new_feature",
        "context_count": 5,
        "context_summary": [...]
    }}
}}

3. 更新向量数据库
--------------------------------------------------------------------------------
请求地址: POST {BASE_URL}/rag_service/update_vector_store
Content-Type: application/json
参数说明:
- file: 文档文件路径 (必填，需要先上传到uploads/rag_docs目录)
- business_module: 业务模块 (必填)
- collection_name: 集合名称 (可选)
- document_type: 文档类型 (可选)

返回示例:
{{
    "code": 200,
    "message": "更新成功",
    "data": {{
        "chunks_count": 10,
        "document_id": "uuid"
    }}
}}

================================================================================
"""

if __name__ == "__main__":
    print(API_DOCS)
