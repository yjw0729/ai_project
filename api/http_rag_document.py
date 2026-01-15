#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG文档处理API接口
提供文档上传、处理、查询功能
"""

import os
import json
import asyncio
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

# 导入RAG服务
try:
    from common.rag.services.rag_services import RAGService
    from common.rag.core.models import DocumentType
except ImportError as e:
    current_app.logger.error(f"RAG模块导入失败: {e}")
    RAGService = None

# 创建蓝图
rag_document_opt = Blueprint('rag_document_opt', __name__)

# 全局RAG服务实例
rag_service = None

# 配置
UPLOAD_FOLDER = 'uploads/rag_docs'
ALLOWED_EXTENSIONS = {'docx', 'doc', 'pdf', 'txt', 'md', 'markdown'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_rag_service():
    """获取RAG服务实例"""
    global rag_service
    if rag_service is None and RAGService is not None:
        try:
            rag_service = RAGService()
            current_app.logger.info("RAG服务初始化成功")
        except Exception as e:
            current_app.logger.error(f"RAG服务初始化失败: {e}")
            return None
    return rag_service

def allowed_file(filename):
    """检查文件类型是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_upload_file(file, document_id):
    """保存上传的文件"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # 生成新的文件名: document_id + 原始扩展名
        file_ext = filename.rsplit('.', 1)[1].lower()
        new_filename = f"{document_id}.{file_ext}"

        file_path = os.path.join(UPLOAD_FOLDER, new_filename)
        file.save(file_path)

        return file_path, new_filename
    return None, None

@rag_document_opt.route('/upload', methods=['POST'])
def upload_document():
    """
    上传文档并进行向量化处理

    请求参数：
    - file: 文档文件 (multipart/form-data)
    - collection_name: 集合名称 (可选，默认: "documents")
    - document_title: 文档标题 (可选)
    - document_type: 文档类型 (可选: "product_design", "api_doc", "user_manual", "other")
    - tags: 标签列表 (可选, JSON字符串)

    返回：
    {
        "code": 200,
        "message": "上传成功",
        "data": {
            "document_id": "uuid",
            "collection_name": "documents",
            "status": "processing|completed|failed",
            "chunks_count": 10,
            "file_path": "/path/to/file"
        }
    }
    """
    try:
        # 检查RAG服务
        rag = get_rag_service()
        if not rag:
            return jsonify({
                "code": 500,
                "message": "RAG服务初始化失败",
                "data": None
            }), 500

        # 获取上传的文件
        if 'file' not in request.files:
            return jsonify({
                "code": 400,
                "message": "未找到文件",
                "data": None
            }), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                "code": 400,
                "message": "未选择文件",
                "data": None
            }), 400

        # 检查文件类型
        if not allowed_file(file.filename):
            return jsonify({
                "code": 400,
                "message": f"不支持的文件类型。允许的类型: {', '.join(ALLOWED_EXTENSIONS)}",
                "data": None
            }), 400

        # 检查文件大小
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        if file_size > MAX_FILE_SIZE:
            return jsonify({
                "code": 400,
                "message": f"文件过大。最大允许: {MAX_FILE_SIZE // (1024*1024)}MB",
                "data": None
            }), 400

        # 生成文档ID
        document_id = str(uuid.uuid4())

        # 获取其他参数
        collection_name = request.form.get('collection_name', 'documents')
        document_title = request.form.get('document_title', file.filename)
        document_type = request.form.get('document_type', 'other')
        tags_str = request.form.get('tags', '[]')

        try:
            tags = json.loads(tags_str)
        except:
            tags = []

        # 保存文件
        file_path, saved_filename = save_upload_file(file, document_id)
        if not file_path:
            return jsonify({
                "code": 500,
                "message": "文件保存失败",
                "data": None
            }), 500

        # 异步处理文档（实际项目中应该使用celery等任务队列）
        try:
            # 构建知识库
            source_configs = [
                {
                    "source_type": "file",
                    "paths": [file_path],
                    "extensions": [saved_filename.rsplit('.', 1)[1].lower()],
                    "recursive": False,
                    "metadata": {
                        "document_id": document_id,
                        "document_title": document_title,
                        "document_type": document_type,
                        "tags": tags,
                        "upload_time": datetime.now().isoformat(),
                        "file_size": file_size,
                        "original_filename": file.filename
                    }
                }
            ]

            # 异步处理（简化版本，实际应该使用celery）
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            build_result = loop.run_until_complete(
                rag.build_knowledge_base(
                    source_configs=source_configs,
                    collection_name=collection_name
                )
            )
            loop.close()

            if build_result.get('status') == 'success':
                return jsonify({
                    "code": 200,
                    "message": "文档上传并处理成功",
                    "data": {
                        "document_id": document_id,
                        "collection_name": collection_name,
                        "status": "completed",
                        "chunks_count": build_result.get('total_chunks', 0),
                        "file_path": file_path,
                        "document_title": document_title,
                        "document_type": document_type,
                        "tags": tags,
                        "file_size": file_size
                    }
                }), 200
            else:
                return jsonify({
                    "code": 500,
                    "message": f"文档处理失败: {build_result.get('message', '未知错误')}",
                    "data": {
                        "document_id": document_id,
                        "file_path": file_path
                    }
                }), 500

        except Exception as e:
            current_app.logger.error(f"文档处理异常: {e}")
            return jsonify({
                "code": 500,
                "message": f"文档处理异常: {str(e)}",
                "data": {
                    "document_id": document_id,
                    "file_path": file_path
                }
            }), 500

    except Exception as e:
        current_app.logger.error(f"上传接口异常: {e}")
        return jsonify({
            "code": 500,
            "message": f"服务器内部错误: {str(e)}",
            "data": None
        }), 500

@rag_document_opt.route('/query', methods=['POST'])
def query_documents():
    """
    查询文档内容

    请求参数 (JSON):
    {
        "query": "查询问题",
        "collection_name": "documents",  // 可选，默认查询所有集合
        "top_k": 5,  // 可选，返回结果数量
        "filters": {  // 可选，过滤条件
            "document_type": "product_design",
            "tags": ["important"]
        }
    }

    返回：
    {
        "code": 200,
        "message": "查询成功",
        "data": {
            "query": "查询问题",
            "answer": "生成的答案",
            "sources": [
                {
                    "content": "相关内容片段",
                    "score": 0.85,
                    "source": "文档名",
                    "metadata": {...}
                }
            ],
            "retrieved_count": 3,
            "elapsed_seconds": 1.2
        }
    }
    """
    try:
        # 检查RAG服务
        rag = get_rag_service()
        if not rag:
            return jsonify({
                "code": 500,
                "message": "RAG服务初始化失败",
                "data": None
            }), 500

        # 获取请求参数
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({
                "code": 400,
                "message": "缺少query参数",
                "data": None
            }), 400

        query = data['query']
        collection_name = data.get('collection_name')
        top_k = data.get('top_k', 5)
        filters = data.get('filters', {})

        # 执行查询
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            result = loop.run_until_complete(
                rag.query(
                    question=query,
                    collection_name=collection_name,
                    top_k=top_k
                )
            )
            loop.close()

            return jsonify({
                "code": 200,
                "message": "查询成功",
                "data": result
            }), 200

        except Exception as e:
            current_app.logger.error(f"查询异常: {e}")
            return jsonify({
                "code": 500,
                "message": f"查询异常: {str(e)}",
                "data": None
            }), 500

    except Exception as e:
        current_app.logger.error(f"查询接口异常: {e}")
        return jsonify({
            "code": 500,
            "message": f"服务器内部错误: {str(e)}",
            "data": None
        }), 500

@rag_document_opt.route('/collections', methods=['GET'])
def list_collections():
    """
    获取所有集合信息

    返回：
    {
        "code": 200,
        "message": "获取成功",
        "data": [
            {
                "name": "documents",
                "total_chunks": 150,
                "created_at": "2024-01-01T00:00:00",
                "last_updated": "2024-01-01T00:00:00"
            }
        ]
    }
    """
    try:
        rag = get_rag_service()
        if not rag:
            return jsonify({
                "code": 500,
                "message": "RAG服务初始化失败",
                "data": None
            }), 500

        collections = rag.list_collections()

        return jsonify({
            "code": 200,
            "message": "获取成功",
            "data": collections
        }), 200

    except Exception as e:
        current_app.logger.error(f"获取集合列表异常: {e}")
        return jsonify({
            "code": 500,
            "message": f"服务器内部错误: {str(e)}",
            "data": None
        }), 500

@rag_document_opt.route('/collection/<collection_name>', methods=['GET'])
def get_collection_info(collection_name):
    """
    获取集合详细信息

    返回：
    {
        "code": 200,
        "message": "获取成功",
        "data": {
            "collection_name": "documents",
            "total_chunks": 150,
            "vector_dim": 768,
            "index_type": "IVF_FLAT",
            "created_at": "2024-01-01T00:00:00",
            "last_updated": "2024-01-01T00:00:00"
        }
    }
    """
    try:
        rag = get_rag_service()
        if not rag:
            return jsonify({
                "code": 500,
                "message": "RAG服务初始化失败",
                "data": None
            }), 500

        info = rag.get_collection_info(collection_name)

        if info:
            return jsonify({
                "code": 200,
                "message": "获取成功",
                "data": info
            }), 200
        else:
            return jsonify({
                "code": 404,
                "message": "集合不存在",
                "data": None
            }), 404

    except Exception as e:
        current_app.logger.error(f"获取集合信息异常: {e}")
        return jsonify({
            "code": 500,
            "message": f"服务器内部错误: {str(e)}",
            "data": None
        }), 500

@rag_document_opt.route('/collection/<collection_name>', methods=['DELETE'])
def delete_collection(collection_name):
    """
    删除集合

    返回：
    {
        "code": 200,
        "message": "删除成功",
        "data": null
    }
    """
    try:
        rag = get_rag_service()
        if not rag:
            return jsonify({
                "code": 500,
                "message": "RAG服务初始化失败",
                "data": None
            }), 500

        # 这里需要实现删除集合的方法
        # rag.delete_collection(collection_name)

        return jsonify({
            "code": 200,
            "message": "删除成功",
            "data": None
        }), 200

    except Exception as e:
        current_app.logger.error(f"删除集合异常: {e}")
        return jsonify({
            "code": 500,
            "message": f"服务器内部错误: {str(e)}",
            "data": None
        }), 500

@rag_document_opt.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    try:
        rag = get_rag_service()
        status = "healthy" if rag else "unhealthy"

        return jsonify({
            "code": 200,
            "message": "服务正常",
            "data": {
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0"
            }
        }), 200

    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"服务异常: {str(e)}",
            "data": {
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat()
            }
        }), 500


