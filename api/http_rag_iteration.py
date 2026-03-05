#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG文档处理API接口 - 版本迭代场景
适用于版本迭代场景下，测试案例的生成
"""

import os
import json
import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

# 导入RAG服务
try:
    from common.rag.services.rag_services import RAGService
    from common.rag.core.word_document_processor import WordDocumentProcessor
except ImportError as e:
    current_app.logger.error(f"RAG模块导入失败: {e}")
    RAGService = None

# 创建蓝图
rag_iteration_opt = Blueprint('rag_iteration_opt', __name__)

# 全局RAG服务实例
rag_service = None

# 配置
UPLOAD_FOLDER = 'uploads/rag_docs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 版本迭代场景的提示词模板
ITERATION_PROMPT_TEMPLATES = {
    "new_feature": """你是一个专业的测试工程师。请根据以下版本迭代的新增功能需求，参考已有的技术文档上下文，生成测试案例。

## 版本迭代需求
{increment_content}

## 参考的技术文档上下文
{context_content}

## 要求
1. 分析新增功能，理解与现有系统的关系
2. 结合参考上下文，生成完整的测试案例
3. 重点关注：
   - 新功能与现有功能的集成测试
   - 回归测试（验证现有功能未受影响）
   - 新功能的边界和异常情况
   
4. 测试案例格式：
   - title: 测试案例标题
   - module: 功能模块名称
   - priority: 优先级 (P0/P1/P2/P3)
   - test_type: 测试类型
   - precondition: 前置条件
   - steps: 测试步骤列表
   - expected_result: 预期结果

5. 请以JSON数组格式返回

请生成测试案例：""",

    "bug_fix": """你是一个专业的测试工程师。请根据以下Bug修复需求，参考已有的技术文档上下文，生成测试案例。

## Bug修复需求
{increment_content}

## 参考的技术文档上下文
{context_content}

## 要求
1. 分析Bug原因，理解修复逻辑
2. 结合参考上下文，生成验证修复的测试案例
3. 重点关注：
   - 修复后的功能验证
   - 回归测试（验证修复未引入新问题）
   - 边界条件
   
4. 测试案例格式：
   - title: 测试案例标题
   - module: 功能模块名称
   - priority: 优先级 (P0/P1/P2/P3)
   - test_type: 测试类型
   - precondition: 前置条件
   - steps: 测试步骤列表
   - expected_result: 预期结果

5. 请以JSON数组格式返回

请生成测试案例：""",

    "optimization": """你是一个专业的测试工程师。请根据以下性能优化需求，参考已有的技术文档上下文，生成测试案例。

## 性能优化需求
{increment_content}

## 参考的技术文档上下文
{context_content}

## 要求
1. 分析优化点，理解性能指标要求
2. 结合参考上下文，生成性能测试案例
3. 重点关注：
   - 性能指标验证（响应时间、吞吐量等）
   - 负载测试
   - 资源使用情况
   
4. 测试案例格式：
   - title: 测试案例标题
   - module: 功能模块名称
   - priority: 优先级 (P0/P1/P2/P3)
   - test_type: 测试类型
   - precondition: 前置条件
   - steps: 测试步骤列表
   - expected_result: 预期结果

5. 请以JSON数组格式返回

请生成测试案例："""
}


def get_rag_service_iteration():
    """获取RAG服务实例"""
    global rag_service
    if rag_service is None and RAGService is not None:
        try:
            base_dirs = [
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                os.getcwd(),
            ]
            
            config_dir = None
            for base_dir in base_dirs:
                test_path = os.path.join(base_dir, "app", "config", "rag", "business_modules.json")
                if os.path.exists(test_path):
                    config_dir = os.path.join(base_dir, "app", "config")
                    break
            
            if config_dir is None:
                config_dir = os.path.abspath("app/config")
            
            rag_service = RAGService(config_dir=config_dir)
            current_app.logger.info("RAG服务初始化成功")
        except Exception as e:
            current_app.logger.error(f"RAG服务初始化失败: {e}")
            return None
    return rag_service


@rag_iteration_opt.route('/generate_iteration_test_cases', methods=['POST'])
def generate_iteration_test_cases():
    """
    版本迭代场景生成测试案例
    
    请求参数 (JSON):
    {
        "increment_content": "增量需求描述",  // 必填，可以是文本或文件路径
        "increment_file": "增量文档文件",  // 可选，上传增量文档
        "iteration_type": "new_feature|bug_fix|optimization",  // 可选，默认new_feature
        "collection_name": "documents",  // 可选，向量数据库集合名称
        "business_module": "cross_border_opening",  // 可选，业务模块
        "context_top_k": 10,  // 可选，检索相关上下文数量
        "output_format": "xmind|json"  // 可选，默认xmind
    }
    
    返回：XMind文件下载 或 JSON
    """
    try:
        from common.rag.utils.xmind_generator import XMindGenerator, parse_llm_response_to_test_cases
        
        data = request.get_json()
        if not data:
            return jsonify({
                "code": 400,
                "message": "请求参数不能为空",
                "data": None
            }), 400
        
        increment_content = data.get('increment_content', '')
        increment_file = data.get('increment_file')
        iteration_type = data.get('iteration_type', 'new_feature')
        collection_name = data.get('collection_name', 'test_agent_knowledge')
        business_module = data.get('business_module')
        context_top_k = data.get('context_top_k', 10)
        output_format = data.get('output_format', 'xmind')
        
        # 处理增量文档
        if increment_file:
            increment_file_path = os.path.join(UPLOAD_FOLDER, increment_file)
            if os.path.exists(increment_file_path):
                with open(increment_file_path, 'r', encoding='utf-8') as f:
                    increment_content = f.read()
        
        if not increment_content:
            return jsonify({
                "code": 400,
                "message": "增量需求内容不能为空",
                "data": None
            }), 400
        
        # 获取RAG服务
        rag = get_rag_service_iteration()
        if not rag:
            return jsonify({
                "code": 500,
                "message": "RAG服务初始化失败",
                "data": None
            }), 500
        
        # 1. 从向量数据库检索相关上下文
        current_app.logger.info(f"开始检索相关上下文，top_k={context_top_k}")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 搜索相关文档
        search_result = loop.run_until_complete(
            rag.search_only(
                query=increment_content,
                collection_name=collection_name,
                top_k=context_top_k
            )
        )
        
        # 提取上下文内容
        context_results = search_result.get('results', [])
        context_content = "\n\n---\n\n".join([
            f"[来源{i+1}]: {r.get('content', '')[:1000]}"
            for i, r in enumerate(context_results)
        ])
        
        if not context_content:
            context_content = "未找到相关技术文档上下文"
        
        current_app.logger.info(f"检索到 {len(context_results)} 条相关上下文")
        
        # 2. 选择提示词模板
        prompt_template = ITERATION_PROMPT_TEMPLATES.get(
            iteration_type, 
            ITERATION_PROMPT_TEMPLATES["new_feature"]
        )
        
        # 3. 构建完整提示词
        prompt = prompt_template.format(
            increment_content=increment_content,
            context_content=context_content[:5000]  # 限制上下文长度
        )
        
        # 4. 调用LLM生成测试案例
        try:
            # 使用RAG服务的LLM客户端
            answer = loop.run_until_complete(
                rag._generate_answer(
                    prompt=prompt,
                    temperature=0.7,
                    max_tokens=4000
                )
            )
            
            test_cases = parse_llm_response_to_test_cases(answer)
            
        except Exception as e:
            current_app.logger.error(f"LLM调用失败: {e}")
            test_cases = []
        
        loop.close()
        
        if not test_cases:
            # 使用默认模板
            test_cases = [
                {
                    "title": f"验证{iteration_type}相关功能",
                    "module": business_module or "功能验证",
                    "priority": "P0",
                    "test_type": "功能测试",
                    "precondition": "系统正常运行",
                    "steps": ["分析需求", "设计测试用例", "执行测试"],
                    "expected_result": "测试通过"
                }
            ]
        
        # 5. 返回结果
        if output_format == 'json':
            return jsonify({
                "code": 200,
                "message": "生成成功",
                "data": {
                    "test_cases": test_cases,
                    "iteration_type": iteration_type,
                    "context_count": len(context_results),
                    "context_summary": [
                        {
                            "content": r.get('content', '')[:200],
                            "score": r.get('score', 0)
                        }
                        for r in context_results[:3]
                    ]
                }
            }), 200
        else:
            # 生成XMind文件
            xmind_gen = XMindGenerator(output_dir="outputs/test_cases")
            xmind_path = xmind_gen.generate_test_cases_xmind(
                document_title=f"迭代测试案例_{iteration_type}",
                test_cases=test_cases,
                business_module=business_module or ''
            )
            
            return send_file(
                xmind_path,
                as_attachment=True,
                download_name=os.path.basename(xmind_path),
                mimetype='application/octet-stream'
            )
    
    except Exception as e:
        current_app.logger.error(f"生成迭代测试案例失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "code": 500,
            "message": f"生成测试案例失败: {str(e)}",
            "data": None
        }), 500


@rag_iteration_opt.route('/update_vector_store', methods=['POST'])
def update_vector_store():
    """
    更新向量数据库（用于版本迭代场景）
    
    请求参数 (JSON):
    {
        "file": "新文档文件",  // 必填
        "business_module": "cross_border_opening",  // 必填
        "collection_name": "documents",  // 可选
        "document_type": "technical_specification"  // 可选
    }
    
    返回：
    {
        "code": 200,
        "message": "更新成功",
        "data": {
            "chunks_count": 10,
            "document_id": "uuid"
        }
    }
    """
    try:
        from common.rag.core.vector_indexer import VectorIndexer
        
        data = request.get_json()
        if not data:
            return jsonify({
                "code": 400,
                "message": "请求参数不能为空",
                "data": None
            }), 400
        
        file_path = data.get('file')
        business_module = data.get('business_module')
        collection_name = data.get('collection_name', 'test_agent_knowledge')
        document_type = data.get('document_type', 'technical_specification')
        
        if not file_path or not business_module:
            return jsonify({
                "code": 400,
                "message": "file和business_module不能为空",
                "data": None
            }), 400
        
        # 获取完整文件路径
        full_file_path = os.path.join(UPLOAD_FOLDER, file_path)
        if not os.path.exists(full_file_path):
            return jsonify({
                "code": 404,
                "message": "文件不存在",
                "data": None
            }), 404
        
        # 获取RAG服务
        rag = get_rag_service_iteration()
        if not rag:
            return jsonify({
                "code": 500,
                "message": "RAG服务初始化失败",
                "data": None
            }), 500
        
        # 处理文档
        document_id = str(uuid.uuid4())
        processor = WordDocumentProcessor()
        
        chunks = processor.process_word_document(full_file_path, metadata={
            "document_id": document_id,
            "document_type": document_type,
            "business_module": business_module,
            "update_time": datetime.now().isoformat()
        })
        
        # 过滤有效chunks
        valid_chunks = [c for c in chunks if c.content and 50 <= len(c.content.strip()) <= 2000]
        
        if valid_chunks:
            # 构建索引
            indexer = VectorIndexer(rag.config_manager)
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            stats = loop.run_until_complete(
                indexer.build_index(valid_chunks, collection_name)
            )
            
            loop.close()
            
            current_app.logger.info(f"向量数据库更新成功: {len(valid_chunks)} chunks")
        
        return jsonify({
            "code": 200,
            "message": "更新成功",
            "data": {
                "chunks_count": len(valid_chunks),
                "document_id": document_id,
                "collection_name": collection_name
            }
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"更新向量数据库失败: {e}")
        return jsonify({
            "code": 500,
            "message": f"更新失败: {str(e)}",
            "data": None
        }), 500


@rag_iteration_opt.route('/search_context', methods=['POST'])
def search_context():
    """
    检索相关上下文（用于版本迭代场景）
    
    请求参数 (JSON):
    {
        "query": "查询内容",  // 必填
        "collection_name": "documents",  // 可选
        "top_k": 10  // 可选
    }
    
    返回：
    {
        "code": 200,
        "message": "查询成功",
        "data": {
            "results": [
                {
                    "content": "...",
                    "score": 0.85,
                    "metadata": {}
                }
            ],
            "total": 10
        }
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "code": 400,
                "message": "请求参数不能为空",
                "data": None
            }), 400
        
        query = data.get('query')
        if not query:
            return jsonify({
                "code": 400,
                "message": "query不能为空",
                "data": None
            }), 400
        
        collection_name = data.get('collection_name', 'test_agent_knowledge')
        top_k = data.get('top_k', 10)
        
        # 获取RAG服务
        rag = get_rag_service_iteration()
        if not rag:
            return jsonify({
                "code": 500,
                "message": "RAG服务初始化失败",
                "data": None
            }), 500
        
        # 搜索
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            rag.search_only(
                query=query,
                collection_name=collection_name,
                top_k=top_k
            )
        )
        
        loop.close()
        
        return jsonify({
            "code": 200,
            "message": "查询成功",
            "data": {
                "results": result.get('results', []),
                "total": result.get('total_results', 0)
            }
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"检索上下文失败: {e}")
        return jsonify({
            "code": 500,
            "message": f"检索失败: {str(e)}",
            "data": None
        }), 500


# 导入send_file
from flask import send_file
