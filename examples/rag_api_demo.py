#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Python请求示例 - RAG模块API
"""

import requests
import json

BASE_URL = "http://172.20.10.4:8015"


# ==================== 1. 基础接口 ====================

def health_check():
    """健康检查"""
    response = requests.get(f"{BASE_URL}/rag_service/health")
    return response.json()


def get_business_modules():
    """获取业务模块"""
    response = requests.get(f"{BASE_URL}/rag_service/business_modules")
    return response.json()


def get_collections():
    """获取集合列表"""
    response = requests.get(f"{BASE_URL}/rag_service/collections")
    return response.json()


# ==================== 2. 文档上传和问答 ====================

def upload_document(file_path, business_module, document_title=None):
    """
    上传文档
    file_path: 文件路径
    business_module: 业务模块 (如: cross_border_opening)
    document_title: 文档标题 (可选)
    """
    with open(file_path, 'rb') as f:
        files = {'file': (file_path, f)}
        data = {
            'business_module': business_module,
            'document_title': document_title or file_path,
            'collection_name': 'documents'
        }
        response = requests.post(
            f"{BASE_URL}/rag_service/upload",
            files=files,
            data=data
        )
    return response.json()


def query_document(query, top_k=5):
    """
    查询文档
    query: 查询问题
    top_k: 返回结果数量
    """
    data = {
        "query": query,
        "top_k": top_k
    }
    response = requests.post(
        f"{BASE_URL}/rag_service/query",
        json=data
    )
    return response.json()


# ==================== 3. PRD和技术文档双上传 ====================

def upload_dual_documents(prd_file, tech_spec_file, business_module, document_title=None):
    """
    同时上传PRD和技术文档
    prd_file: PRD文档路径
    tech_spec_file: 技术文档路径
    business_module: 业务模块
    document_title: 文档标题 (可选)
    """
    with open(prd_file, 'rb') as f1, open(tech_spec_file, 'rb') as f2:
        files = {
            'prd_file': (prd_file, f1),
            'tech_spec_file': (tech_spec_file, f2)
        }
        data = {
            'business_module': business_module,
            'document_title': document_title or 'Dual Document',
            'collection_name': 'documents'
        }
        response = requests.post(
            f"{BASE_URL}/rag_service/upload_dual",
            files=files,
            data=data
        )
    return response.json()


def generate_test_cases(content_file, prompt_type='auto', output_format='json'):
    """
    生成测试案例
    content_file: 上传双文档后返回的content_file
    prompt_type: 提示词类型 (auto/prd/tech_spec/both)
    output_format: 输出格式 (json)
    """
    data = {
        'content_file': content_file,
        'prompt_type': prompt_type,
        'output_format': output_format
    }
    response = requests.post(
        f"{BASE_URL}/rag_service/generate_test_cases_v2",
        json=data
    )
    return response.json()


# ==================== 4. 版本迭代场景 ====================

def search_context(query, collection_name='documents', top_k=10):
    """
    检索相关上下文
    query: 查询内容
    collection_name: 集合名称
    top_k: 返回结果数量
    """
    data = {
        'query': query,
        'collection_name': collection_name,
        'top_k': top_k
    }
    response = requests.post(
        f"{BASE_URL}/rag_service/search_context",
        json=data
    )
    return response.json()


def generate_iteration_test_cases(increment_content, iteration_type='new_feature',
                                  collection_name='documents', business_module=None,
                                  context_top_k=10, output_format='json'):
    """
    生成迭代测试案例
    increment_content: 增量需求内容
    iteration_type: 迭代类型 (new_feature/bug_fix/optimization)
    collection_name: 集合名称
    business_module: 业务模块
    context_top_k: 检索上下文数量
    output_format: 输出格式
    """
    data = {
        'increment_content': increment_content,
        'iteration_type': iteration_type,
        'collection_name': collection_name,
        'business_module': business_module,
        'context_top_k': context_top_k,
        'output_format': output_format
    }
    response = requests.post(
        f"{BASE_URL}/rag_service/generate_iteration_test_cases",
        json=data
    )
    return response.json()


# ==================== 测试示例 ====================

if __name__ == "__main__":
    # 1. 健康检查
    print("="*60)
    print("1. 健康检查")
    print("="*60)
    result = health_check()
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 2. 获取业务模块
    print("\n" + "="*60)
    print("2. 获取业务模块")
    print("="*60)
    result = get_business_modules()
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 3. 查询文档
    print("\n" + "="*60)
    print("3. 查询文档")
    print("="*60)
    result = query_document("这个文档有哪些接口？")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 4. 检索上下文
    print("\n" + "="*60)
    print("4. 检索上下文")
    print("="*60)
    result = search_context("Challenge接口")
    print(json.dumps(result, ensure_ascii=False, indent=2))
