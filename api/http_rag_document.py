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
            import os
            # 获取项目根目录
            # 尝试多种可能的配置目录
            base_dirs = [
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # api目录的父目录
                os.getcwd(),  # 当前工作目录
            ]
            
            config_dir = None
            for base_dir in base_dirs:
                test_path = os.path.join(base_dir, "app", "config", "rag", "business_modules.json")
                if os.path.exists(test_path):
                    config_dir = os.path.join(base_dir, "app", "config")
                    print(f"[DEBUG] 找到配置目录: {config_dir}")
                    break
            
            if config_dir is None:
                # 使用绝对路径的兜底方案
                config_dir = os.path.abspath("app/config")
                print(f"[DEBUG] 使用默认配置目录: {config_dir}")
            
            rag_service = RAGService(config_dir=config_dir)
            print(f"[DEBUG] RAG服务初始化成功，业务模块: {list(rag_service.get_business_modules().keys())}")
            current_app.logger.info("RAG服务初始化成功")
        except Exception as e:
            current_app.logger.error(f"RAG服务初始化失败: {e}")
            import traceback
            current_app.logger.error(traceback.format_exc())
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
    - document_type: 文档类型 (可选: "api_documentation", "product_requirement", "design_document", "technical_specification", "test_case", "bug_report")
    - business_module: 业务模块 (必填: "cross_border_opening", "cross_border_trading", "internet_opening", "internet_trading")
    - tags: 标签列表 (可选, JSON字符串)

    返回：
    {
        "code": 200,
        "message": "上传成功",
        "data": {
            "document_id": "uuid",
            "collection_name": "documents",
            "business_module": "cross_border_opening",
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

        # 获取其他参数（默认使用当前RAG配置中的集合名称）
        default_collection = getattr(getattr(rag, "vector_db_config", None), "collection_name", "documents")
        collection_name = request.form.get('collection_name', default_collection)
        document_title = request.form.get('document_title', file.filename)
        document_type = request.form.get('document_type', 'other')
        business_module = request.form.get('business_module', '')
        tags_str = request.form.get('tags', '[]')

        # 验证业务模块
        if not business_module:
            return jsonify({
                "code": 400,
                "message": "必须指定业务模块 (business_module)",
                "data": None
            }), 400

        if not rag.validate_business_module(business_module):
            available_modules = list(rag.get_business_modules().keys())
            return jsonify({
                "code": 400,
                "message": f"无效的业务模块: {business_module}。可用的模块: {', '.join(available_modules)}",
                "data": None
            }), 400

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
                        "business_module": business_module,
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
                        "business_module": business_module,
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
        "business_module": "cross_border_opening",  // 可选，按业务模块过滤
        "top_k": 5,  // 可选，返回结果数量
        "filters": {  // 可选，过滤条件
            "document_type": "api_documentation",
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
        # 简化版查询：只需要query参数，其他使用默认值
        # 默认使用当前RAG配置中的集合名称
        default_collection = getattr(getattr(rag, "vector_db_config", None), "collection_name", None)
        collection_name = data.get('collection_name') or default_collection
        top_k = data.get('top_k', 5)

        # 移除复杂的filters参数，默认不进行过滤，让向量数据库自动匹配
        filters = None

        # 执行查询
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            result = loop.run_until_complete(
                rag.query(
                    question=query,
                    collection_name=collection_name,
                    top_k=top_k,
                    filters=filters if filters else None
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

        # 删除集合（Chroma: 物理删除集合；同时更新 collections.json 中的记录）
        try:
            rag.knowledge_base.delete_collection(collection_name)
        except Exception as e:
            current_app.logger.error(f"删除集合失败: {e}")
            return jsonify({
                "code": 500,
                "message": f"删除集合失败: {str(e)}",
                "data": {
                    "collection_name": collection_name
                }
            }), 500

        return jsonify({
            "code": 200,
            "message": "删除成功",
            "data": {
                "collection_name": collection_name
            }
        }), 200

    except Exception as e:
        current_app.logger.error(f"删除集合异常: {e}")
        return jsonify({
            "code": 500,
            "message": f"服务器内部错误: {str(e)}",
            "data": None
        }), 500


@rag_document_opt.route('/collection/<collection_name>/rebuild', methods=['POST'])
def rebuild_collection(collection_name):
    """
    清空并重建指定集合的索引（适用于 Chroma 调试/回归）。

    请求参数 (JSON，可选):
    {
        "source_configs": [...],          // 可选，格式与 build_knowledge_base 一致；不传则尝试从 collections.json 读取
        "chunking_strategy": "default",   // 可选
        "clear_first": true               // 可选，默认 true
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

        data = request.get_json(silent=True) or {}
        source_configs = data.get("source_configs")
        chunking_strategy = data.get("chunking_strategy")
        clear_first = data.get("clear_first", True)

        # 优先使用请求传入的 source_configs；否则从 KnowledgeBase 已记录的集合信息中读取
        if not source_configs:
            kb_collection = getattr(rag.knowledge_base, "collections", {}).get(collection_name) or {}
            source_configs = kb_collection.get("source_configs")

        if not source_configs:
            return jsonify({
                "code": 400,
                "message": "缺少 source_configs，且 collections.json 中未找到该集合的历史 source_configs，无法重建",
                "data": {
                    "collection_name": collection_name
                }
            }), 400

        # 先清空集合，避免脏向量影响调试
        if clear_first:
            try:
                rag.knowledge_base.delete_collection(collection_name)
            except Exception as e:
                # 如果集合不存在，允许继续重建；其他错误返回
                msg = str(e)
                if "does not exist" not in msg.lower() and "not found" not in msg.lower() and "不存在" not in msg:
                    current_app.logger.error(f"清空集合失败: {e}")
                    return jsonify({
                        "code": 500,
                        "message": f"清空集合失败: {msg}",
                        "data": {
                            "collection_name": collection_name
                        }
                    }), 500

        # 重建索引（复用 build_knowledge_base）
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            build_result = loop.run_until_complete(
                rag.build_knowledge_base(
                    source_configs=source_configs,
                    collection_name=collection_name,
                    chunking_strategy=chunking_strategy
                )
            )
        finally:
            loop.close()

        if build_result.get("status") != "success":
            return jsonify({
                "code": 500,
                "message": f"重建失败: {build_result.get('message') or build_result.get('error') or '未知错误'}",
                "data": build_result
            }), 500

        return jsonify({
            "code": 200,
            "message": "重建成功",
            "data": build_result
        }), 200

    except Exception as e:
        current_app.logger.error(f"重建集合异常: {e}")
        return jsonify({
            "code": 500,
            "message": f"服务器内部错误: {str(e)}",
            "data": None
        }), 500

@rag_document_opt.route('/business_modules', methods=['GET'])
def get_business_modules():
    """获取可用的业务模块列表"""
    try:
        rag = get_rag_service()
        if not rag:
            return jsonify({
                "code": 500,
                "message": "RAG服务初始化失败",
                "data": None
            }), 500

        modules = rag.get_business_modules()

        # 格式化返回数据
        formatted_modules = []
        for module_key, module_info in modules.items():
            formatted_modules.append({
                "key": module_key,
                "name": module_info.get("name", module_key),
                "description": module_info.get("description", ""),
                "category": module_info.get("category", ""),
                "enabled": module_info.get("enabled", True)
            })

        return jsonify({
            "code": 200,
            "message": "获取成功",
            "data": {
                "modules": formatted_modules,
                "total_count": len(formatted_modules)
            }
        }), 200

    except Exception as e:
        current_app.logger.error(f"获取业务模块列表异常: {e}")
        return jsonify({
            "code": 500,
            "message": f"服务器内部错误: {str(e)}",
            "data": None
        }), 500


@rag_document_opt.route('/stats', methods=['GET'])
def get_system_stats():
    """获取系统统计信息"""
    try:
        rag = get_rag_service()
        if not rag:
            return jsonify({
                "code": 500,
                "message": "RAG服务初始化失败",
                "data": None
            }), 500

        # 获取集合列表和统计信息
        collections = rag.list_collections()

        # 计算总体统计
        total_collections = len(collections)
        total_chunks = sum(col.get('total_chunks', 0) for col in collections)

        # 按业务模块统计
        module_stats = {}
        for collection in collections:
            # 这里需要从实际存储的数据中统计，暂时用模拟数据
            # 实际实现需要查询向量数据库中的元数据
            pass

        # 获取向量数据库统计
        vector_db_stats = get_vector_db_stats(rag)

        # 获取存储空间信息
        storage_stats = get_storage_stats()

        return jsonify({
            "code": 200,
            "message": "获取成功",
            "data": {
                "overview": {
                    "total_collections": total_collections,
                    "total_chunks": total_chunks,
                    "total_documents": sum(len(rag.list_collections()) for _ in collections),  # 近似值
                    "vector_dimensions": vector_db_stats.get("dimensions", 768)
                },
                "collections": collections,
                "business_modules": get_business_module_stats(rag),
                "vector_database": vector_db_stats,
                "storage": storage_stats,
                "last_updated": datetime.now().isoformat()
            }
        }), 200

    except Exception as e:
        current_app.logger.error(f"获取系统统计异常: {e}")
        return jsonify({
            "code": 500,
            "message": f"服务器内部错误: {str(e)}",
            "data": None
        }), 500


@rag_document_opt.route('/collections/<collection_name>/stats', methods=['GET'])
def get_collection_stats(collection_name):
    """获取指定集合的详细统计信息"""
    try:
        rag = get_rag_service()
        if not rag:
            return jsonify({
                "code": 500,
                "message": "RAG服务初始化失败",
                "data": None
            }), 500

        # 获取集合基本信息
        collection_info = rag.knowledge_base.get_collection_info(collection_name)
        if not collection_info:
            return jsonify({
                "code": 404,
                "message": f"集合 {collection_name} 不存在",
                "data": None
            }), 404

        # 获取向量数据库中的详细统计
        vector_stats = get_detailed_vector_stats(rag, collection_name)

        return jsonify({
            "code": 200,
            "message": "获取成功",
            "data": {
                "collection_name": collection_name,
                "basic_info": collection_info,
                "vector_stats": vector_stats,
                "last_updated": datetime.now().isoformat()
            }
        }), 200

    except Exception as e:
        current_app.logger.error(f"获取集合统计异常: {e}")
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


def get_vector_db_stats(rag):
    """获取向量数据库统计信息"""
    try:
        # 获取向量数据库的基本信息
        vector_config = rag.vector_db_config

        stats = {
            "db_type": vector_config.db_type,
            "dimensions": getattr(vector_config, 'dimension', 768),
            "host": getattr(vector_config, 'host', 'localhost'),
            "collection_count": len(rag.list_collections())
        }

        # 如果是ChromaDB，获取更多信息
        if vector_config.db_type == "chroma":
            try:
                chroma_client = rag.knowledge_base.vector_indexer.chroma_client
                # 这里可以添加更详细的ChromaDB统计
                stats["persistence_enabled"] = True
                stats["storage_path"] = "./chroma_data"
            except:
                pass

        return stats

    except Exception as e:
        current_app.logger.error(f"获取向量数据库统计失败: {e}")
        return {"error": str(e)}


def get_storage_stats():
    """获取存储空间统计信息"""
    try:
        import os
        import psutil

        stats = {
            "chroma_data_size": 0,
            "uploads_size": 0,
            "cache_size": 0,
            "logs_size": 0,
            "total_rag_size": 0
        }

        def get_dir_size(path):
            """计算目录大小"""
            if not os.path.exists(path):
                return 0
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except OSError:
                        pass
            return total_size

        # 计算各目录大小
        stats["chroma_data_size"] = get_dir_size("./chroma_data")
        stats["uploads_size"] = get_dir_size("./uploads")
        stats["cache_size"] = get_dir_size("./cache")
        stats["logs_size"] = get_dir_size("./logs")

        # 计算总大小
        stats["total_rag_size"] = (
            stats["chroma_data_size"] +
            stats["uploads_size"] +
            stats["cache_size"] +
            stats["logs_size"]
        )

        # 转换为MB
        for key in stats:
            if key != "total_rag_size":  # total_rag_size是字节和，需要最后转换
                stats[key] = round(stats[key] / (1024 * 1024), 2)  # MB
        stats["total_rag_size"] = round(stats["total_rag_size"] / (1024 * 1024), 2)

        # 获取系统磁盘信息
        try:
            disk = psutil.disk_usage('/')
            stats["system_disk"] = {
                "total": round(disk.total / (1024**3), 2),  # GB
                "used": round(disk.used / (1024**3), 2),    # GB
                "free": round(disk.free / (1024**3), 2),    # GB
                "percent": disk.percent
            }
        except:
            stats["system_disk"] = {"error": "无法获取磁盘信息"}

        return stats

    except Exception as e:
        current_app.logger.error(f"获取存储统计失败: {e}")
        return {"error": str(e)}


def get_business_module_stats(rag):
    """获取业务模块统计信息"""
    try:
        modules_config = rag.business_modules_config.get("modules", {})

        # 获取所有集合的统计信息
        collections = rag.list_collections()

        # 初始化模块统计
        module_stats = {}
        for module_key, module_info in modules_config.items():
            module_stats[module_key] = {
                "module_key": module_key,
                "name": module_info.get("name", module_key),
                "category": module_info.get("category", ""),
                "enabled": module_info.get("enabled", True),
                "document_count": 0,
                "chunk_count": 0,
                "collections": [],
                "last_updated": datetime.now().isoformat()
            }

        # 统计每个集合中的业务模块分布
        # 注意：这里是简化实现，实际应该从向量数据库查询元数据
        for collection in collections:
            collection_name = collection.get('name', '')

            # 对于ChromaDB，我们可以尝试查询元数据
            if rag.vector_db_config.db_type == "chroma":
                try:
                    chroma_collection = rag.knowledge_base.vector_indexer.collection
                    if chroma_collection.name == collection_name:
                        # 查询所有文档的元数据
                        results = chroma_collection.get(include=['metadatas'])
                        if results and results.get('metadatas'):
                            for metadata in results['metadatas']:
                                if metadata and 'business_module' in metadata:
                                    module_key = metadata['business_module']
                                    if module_key in module_stats:
                                        module_stats[module_key]['chunk_count'] += 1
                                        if collection_name not in module_stats[module_key]['collections']:
                                            module_stats[module_key]['collections'].append(collection_name)
                except Exception as e:
                    current_app.logger.warning(f"查询ChromaDB元数据失败: {e}")

        # 计算文档数量（每个集合算一个文档）
        for module_key in module_stats:
            module_stats[module_key]['document_count'] = len(module_stats[module_key]['collections'])

        return list(module_stats.values())

    except Exception as e:
        current_app.logger.error(f"获取业务模块统计失败: {e}")
        return []


def get_detailed_vector_stats(rag, collection_name):
    """获取集合的详细向量统计信息"""
    try:
        # 获取基本统计
        basic_stats = rag.knowledge_base.vector_indexer.get_collection_stats(collection_name)

        # 扩展统计信息
        detailed_stats = {
            "collection_name": collection_name,
            "total_entities": basic_stats.get("num_entities", 0),
            "vector_dimensions": rag.vector_db_config.dimension,
            "index_type": getattr(rag.vector_db_config, 'index_type', 'default'),
            "metric_type": getattr(rag.vector_db_config, 'metric_type', 'cosine')
        }

        # 如果是ChromaDB，添加更多信息
        if rag.vector_db_config.db_type == "chroma":
            try:
                collection = rag.knowledge_base.vector_indexer.collection
                detailed_stats["chroma_info"] = {
                    "collection_name": collection.name,
                    "collection_id": getattr(collection, 'id', 'unknown'),
                    "metadata": getattr(collection, 'metadata', {})
                }
            except Exception as e:
                detailed_stats["chroma_info"] = {"error": str(e)}

        return detailed_stats

    except Exception as e:
        current_app.logger.error(f"获取详细向量统计失败: {e}")
        return {"error": str(e)}


@rag_document_opt.route('/collections/<collection_name>/visualize', methods=['GET'])
def visualize_vectors(collection_name):
    """获取集合向量的降维可视化数据"""
    try:
        rag = get_rag_service()
        if not rag:
            return jsonify({
                "code": 500,
                "message": "RAG服务初始化失败",
                "data": None
            }), 500

        # 获取查询参数
        algo = request.args.get('algo', 'umap')  # umap 或 tsne
        n = min(int(request.args.get('n', 2000)), 10000)  # 最大10000个样本
        dim = int(request.args.get('dim', 2))  # 2D 或 3D
        sample_strategy = request.args.get('sample_strategy', 'random')  # random 或 top_k
        business_module = request.args.get('module')  # 业务模块过滤
        seed = request.args.get('seed')
        if seed:
            seed = int(seed)

        # 验证参数
        if algo not in ['umap', 'tsne']:
            return jsonify({
                "code": 400,
                "message": "algo参数必须是 'umap' 或 'tsne'",
                "data": None
            }), 400

        if dim not in [2, 3]:
            return jsonify({
                "code": 400,
                "message": "dim参数必须是 2 或 3",
                "data": None
            }), 400

        if sample_strategy not in ['random', 'top_k']:
            return jsonify({
                "code": 400,
                "message": "sample_strategy参数必须是 'random' 或 'top_k'",
                "data": None
            }), 400

        # 验证业务模块（如果指定）
        if business_module and not rag.validate_business_module(business_module):
            available_modules = list(rag.get_business_modules().keys())
            return jsonify({
                "code": 400,
                "message": f"无效的业务模块: {business_module}。可用的模块: {', '.join(available_modules)}",
                "data": None
            }), 400

        # 获取可视化数据
        try:
            vis_data = get_visualization_data(
                rag, collection_name, algo, n, dim, sample_strategy, business_module, seed
            )

            return jsonify({
                "code": 200,
                "message": "ok",
                "data": vis_data
            }), 200

        except Exception as e:
            current_app.logger.error(f"生成可视化数据失败: {e}")
            return jsonify({
                "code": 500,
                "message": f"生成可视化数据失败: {str(e)}",
                "data": None
            }), 500

    except Exception as e:
        current_app.logger.error(f"可视化接口异常: {e}")
        return jsonify({
            "code": 500,
            "message": f"服务器内部错误: {str(e)}",
            "data": None
        }), 500


@rag_document_opt.route('/visualize/jobs', methods=['POST'])
def create_visualization_job():
    """创建可视化任务（异步处理大数据）"""
    try:
        rag = get_rag_service()
        if not rag:
            return jsonify({
                "code": 500,
                "message": "RAG服务初始化失败",
                "data": None
            }), 500

        data = request.get_json()
        if not data or 'collection' not in data:
            return jsonify({
                "code": 400,
                "message": "缺少collection参数",
                "data": None
            }), 400

        # 参数验证（与同步接口相同）
        collection_name = data['collection']
        algo = data.get('algo', 'umap')
        n = min(data.get('n', 2000), 10000)
        dim = data.get('dim', 2)
        sample_strategy = data.get('sample_strategy', 'random')
        business_module = data.get('module')
        seed = data.get('seed')

        # 这里可以实现异步任务队列
        # 暂时返回不支持的消息
        return jsonify({
            "code": 501,
            "message": "异步可视化任务暂未实现，请使用同步接口",
            "data": None
        }), 501

    except Exception as e:
        current_app.logger.error(f"创建可视化任务异常: {e}")
        return jsonify({
            "code": 500,
            "message": f"服务器内部错误: {str(e)}",
            "data": None
        }), 500


@rag_document_opt.route('/visualize/jobs/<job_id>', methods=['GET'])
def get_visualization_job_status(job_id):
    """获取可视化任务状态"""
    # 暂时返回不支持
    return jsonify({
        "code": 501,
        "message": "异步可视化任务暂未实现",
        "data": None
    }), 501


@rag_document_opt.route('/collections/<collection_name>/vectors', methods=['GET'])
def get_raw_vectors(collection_name):
    """获取原始向量数据（备选方案）"""
    try:
        rag = get_rag_service()
        if not rag:
            return jsonify({
                "code": 500,
                "message": "RAG服务初始化失败",
                "data": None
            }), 500

        limit = min(int(request.args.get('limit', 2000)), 5000)  # 最大5000个向量
        business_module = request.args.get('module')

        # 验证业务模块
        if business_module and not rag.validate_business_module(business_module):
            available_modules = list(rag.get_business_modules().keys())
            return jsonify({
                "code": 400,
                "message": f"无效的业务模块: {business_module}。可用的模块: {', '.join(available_modules)}",
                "data": None
            }), 400

        try:
            raw_data = get_raw_vector_data(rag, collection_name, limit, business_module)

            return jsonify({
                "code": 200,
                "message": "ok",
                "data": raw_data
            }), 200

        except Exception as e:
            current_app.logger.error(f"获取原始向量数据失败: {e}")
            return jsonify({
                "code": 500,
                "message": f"获取原始向量数据失败: {str(e)}",
                "data": None
            }), 500

    except Exception as e:
        current_app.logger.error(f"原始向量接口异常: {e}")
        return jsonify({
            "code": 500,
            "message": f"服务器内部错误: {str(e)}",
            "data": None
        }), 500


def get_visualization_data(rag, collection_name, algo, n, dim, sample_strategy, business_module, seed):
    """生成可视化数据"""
    try:
        import numpy as np
        from sklearn.manifold import TSNE
        import umap

        # 从向量数据库获取向量数据
        vectors_data = get_sampled_vectors(rag, collection_name, n, sample_strategy, business_module, seed)

        if not vectors_data:
            return {
                "algo": algo,
                "dim": dim,
                "n": 0,
                "coords": [],
                "summary": {
                    "total": 0,
                    "collection": collection_name,
                    "error": "未找到向量数据"
                }
            }

        vectors = np.array([item['vector'] for item in vectors_data])

        # 执行降维
        if algo == 'umap':
            reducer = umap.UMAP(
                n_components=dim,
                random_state=seed,
                n_neighbors=min(15, len(vectors) - 1),
                min_dist=0.1
            )
        elif algo == 'tsne':
            reducer = TSNE(
                n_components=dim,
                random_state=seed,
                perplexity=min(30, len(vectors) - 1),
                max_iter=1000
            )

        # 降维计算
        coords_2d = reducer.fit_transform(vectors)

        # 构建返回数据
        coords = []
        for i, (coord, vector_data) in enumerate(zip(coords_2d, vectors_data)):
            coord_item = {
                "id": vector_data['id'],
                "case_id": vector_data.get('case_id', f"item_{i}"),
                "x": float(coord[0]),
                "y": float(coord[1]),
                "label": vector_data.get('business_module', 'unknown'),
                "cluster": vector_data.get('cluster', 0),
                "meta": {
                    "doc_id": vector_data.get('doc_id', ''),
                    "chunk_idx": vector_data.get('chunk_idx', 0),
                    "collection": collection_name
                }
            }

            if dim == 3:
                coord_item["z"] = float(coord[2]) if len(coord) > 2 else 0.0

            coords.append(coord_item)

        return {
            "algo": algo,
            "dim": dim,
            "n": len(coords),
            "coords": coords,
            "summary": {
                "total": len(coords),
                "collection": collection_name,
                "sample_strategy": sample_strategy,
                "business_module": business_module or "all"
            }
        }

    except Exception as e:
        current_app.logger.error(f"生成可视化数据异常: {e}")
        raise


def get_sampled_vectors(rag, collection_name, n, sample_strategy, business_module, seed):
    """获取采样向量数据"""
    try:
        import numpy as np

        # 这里需要从向量数据库中获取向量数据
        # 由于向量数据库的具体实现不同，这里提供一个通用接口

        vectors_data = []

        # 对于ChromaDB的实现
        if rag.vector_db_config.db_type == "chroma":
            try:
                chroma_client = rag.knowledge_base.vector_indexer.chroma_client

                # 获取集合
                collection = chroma_client.get_collection(name=collection_name)

                # 获取所有数据
                results = collection.get(include=['embeddings', 'metadatas'])

                if results and results.get('embeddings'):
                    embeddings = results['embeddings']
                    metadatas = results.get('metadatas', [])

                    # 构建向量数据列表
                    for i, (embedding, metadata) in enumerate(zip(embeddings, metadatas)):
                        # 业务模块过滤
                        if business_module and metadata.get('business_module') != business_module:
                            continue

                        vectors_data.append({
                            'id': i,
                            'vector': embedding,
                            'business_module': metadata.get('business_module', 'unknown'),
                            'doc_id': metadata.get('document_id', ''),
                            'chunk_idx': metadata.get('chunk_index', 0),
                            'case_id': f"{metadata.get('document_id', 'doc')}_{metadata.get('chunk_index', 0)}",
                            'cluster': hash(metadata.get('business_module', 'unknown')) % 10  # 简单聚类
                        })

                    # 采样
                    if len(vectors_data) > n:
                        if sample_strategy == 'random':
                            np.random.seed(seed)
                            indices = np.random.choice(len(vectors_data), n, replace=False)
                            vectors_data = [vectors_data[i] for i in indices]
                        elif sample_strategy == 'top_k':
                            # 简单按顺序取前n个
                            vectors_data = vectors_data[:n]

            except Exception as e:
                current_app.logger.warning(f"从ChromaDB获取向量数据失败: {e}")

        return vectors_data

    except Exception as e:
        current_app.logger.error(f"获取采样向量数据异常: {e}")
        return []


def get_raw_vector_data(rag, collection_name, limit, business_module):
    """获取原始向量数据"""
    try:
        vectors_data = get_sampled_vectors(rag, collection_name, limit, 'random', business_module, None)

        # 转换为前端需要的格式
        raw_data = []
        for item in vectors_data:
            raw_data.append({
                "id": item['id'],
                "case_id": item['case_id'],
                "vector": item['vector'],
                "label": item['business_module'],
                "meta": {
                    "doc_id": item['doc_id'],
                    "chunk_idx": item['chunk_idx']
                }
            })

        return raw_data

    except Exception as e:
        current_app.logger.error(f"获取原始向量数据异常: {e}")
        raise


