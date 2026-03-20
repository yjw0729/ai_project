#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档解析对比实验API
用于测试不同文档解析策略的效果对比

策略对比：
1. LLM结构化解析（原有方式）：调用大模型将文档拆分为4部分
2. 切片策略解析（优化方式）：使用语义/递归/层级切片策略
"""

import os
import re
import json
import uuid
import asyncio
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, make_response
from werkzeug.utils import secure_filename
from pathlib import Path

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.rag.processors.multi_level_parser import (
    MultiLevelDocumentParser,
    AdaptiveParser,
    parse_document,
    adaptive_parse
)
from common.rag.processors.adaptive_processor import AdaptiveDocumentProcessor
from common.rag.processors.document_classifier import DocumentClassifier, DocumentType
from common.rag.core.vector_indexer import VectorIndexer
from api.http_rag_document import get_rag_service, UPLOAD_FOLDER, ALLOWED_EXTENSIONS

logger = logging.getLogger(__name__)

BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COMPARISON_OUTPUT_DIR = BASE_DIR / "outputs" / "comparison_results"
COMPARISON_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

comparison_bp = Blueprint("comparison", __name__)


def json_response(body, status=200):
    """返回JSON响应"""
    resp = make_response(jsonify(body), status)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_document_content(file_path: str, file_ext: str) -> str:
    """提取文档内容"""
    content = ""
    
    if file_ext in ['docx', 'doc']:
        try:
            from docx import Document
            doc = Document(file_path)
            for para in doc.paragraphs:
                content += para.text + "\n"
            # 提取表格
            for table in doc.tables:
                for row in table.rows:
                    row_data = [cell.text for cell in row.cells]
                    content += " | ".join(row_data) + "\n"
        except Exception as e:
            logger.warning(f"docx解析失败: {e}")
    
    elif file_ext == 'pdf':
        try:
            import PyPDF2
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    content += page.extract_text() + "\n"
        except Exception as e:
            logger.warning(f"PDF解析失败: {e}")
    
    elif file_ext in ['txt', 'md', 'markdown']:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"文本文件解析失败: {e}")
    
    return content


def extract_images_from_docx(file_path: str) -> list:
    """从Word文档中提取图片"""
    images = []
    try:
        from docx import Document
        from docx.oxml.ns import qn
        import io
        import base64
        
        doc = Document(file_path)
        
        # 处理每个图片
        for rel in doc.part.rels.values():
            if "image" in rel.target_ref:
                image = rel.target_part
                image_bytes = image.blob
                image_type = image.content_type
                
                # 转换为base64
                b64 = base64.b64encode(image_bytes).decode('utf-8')
                images.append({
                    "type": image_type,
                    "data": b64,
                    "size": len(image_bytes)
                })
        
        logger.info(f"从文档中提取了 {len(images)} 张图片")
    except Exception as e:
        logger.warning(f"图片提取失败: {e}")
    
    return images


def analyze_with_llm(content: str, prompt_type: str = "structure") -> dict:
    """
    使用LLM分析文档
    
    Args:
        content: 文档内容
        prompt_type: 提示词类型 (structure, api_extract, image_ocr)
    
    Returns:
        分析结果
    """
    rag = get_rag_service()
    if not rag:
        return {"error": "RAG服务未初始化"}
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        if prompt_type == "structure":
            prompt = f"""你是资深技术文档分析师。请仔细阅读下面的技术文档，并将其结构化地拆分为4大部分：

【文档内容】
{content[:60000]}

【任务】
请将文档拆分并返回如下 JSON 结构（严格JSON，不要有其他内容）：
{{
    "basic_knowledge": "基础知识部分",
    "service_content": "服务内容部分",
    "template_config": "模板配置部分",
    "api_section": "核心API应用部分"
}}

注意：每一部分的content必须是原始文档中对应内容的完整提取或精简概括。"""
            
            result = loop.run_until_complete(
                rag._generate_answer(
                    prompt=prompt,
                    temperature=0.2,
                    max_tokens=8000
                )
            )
            
            # 尝试解析JSON
            try:
                json_match = re.search(r'\{[\s\S]*\}', result)
                if json_match:
                    return json.loads(json_match.group())
            except:
                pass
            
            return {"raw_result": result}
        
        elif prompt_type == "image_ocr":
            # 图片OCR识别
            prompt = f"""请仔细识别这张图片中的文字内容，并返回识别出的文本。"""
            
            # 这里假设content是base64编码的图片
            # 实际使用时需要调整
            result = loop.run_until_complete(
                rag._generate_answer(
                    prompt=prompt,
                    temperature=0.1,
                    max_tokens=4000
                )
            )
            
            return {"ocr_result": result}
    
    except Exception as e:
        logger.exception("LLM分析失败")
        return {"error": str(e)}
    finally:
        loop.close()


def chunk_by_smart_strategy(content: str, doc_type: str = "auto", strategy: str = None) -> dict:
    """
    使用智能切片策略进行文档解析
    
    Args:
        content: 文档内容
        doc_type: 文档类型 (auto, api_doc, product_doc, requirement, technical, generic)
        strategy: 切片策略 (semantic, recursive, hierarchical, hybrid, None=自动选择)
    
    Returns:
        切片结果
    """
    # 自动检测文档类型
    if doc_type == "auto":
        classifier = DocumentClassifier()
        classification = classifier.classify(content)
        doc_type = classification.doc_type.value if hasattr(classification.doc_type, 'value') else str(classification.doc_type)
        logger.info(f"自动检测文档类型: {doc_type}, 置信度: {classification.confidence}")
    
    # 根据文档类型推荐策略
    if strategy is None:
        strategy_map = {
            "api_doc": "hierarchical",
            "technical_spec": "recursive",      # 技术规格文档
            "product_design": "hybrid", 
            "requirement": "semantic",
            "user_guide": "semantic",
            "test_case": "semantic",
            "generic": "semantic"
        }
        strategy = strategy_map.get(doc_type, "semantic")
    
    logger.info(f"使用切片策略: {strategy}, 文档类型: {doc_type}")
    
    # 使用多层级解析器
    parser = MultiLevelDocumentParser(
        min_chunk_size=200,
        max_chunk_size=1500
    )
    
    result = parser.parse(content, strategy=strategy)
    
    return {
        "doc_type": doc_type,
        "strategy": strategy,
        "original_length": result.original_length,
        "total_sections": result.total_sections,
        "chunks_count": len(result.chunks),
        "chunks": result.chunks,
        "warnings": result.warnings,
        "hierarchy": result.hierarchy.to_dict() if result.hierarchy else {}
    }


def chunk_api_doc_by_table(content: str) -> dict:
    """
    针对API文档（OpenAPI/Swagger格式）的专用切片
    保持表格和端点信息的完整性
    """
    from common.rag.processors.adaptive_processor import APIDocProcessor
    
    processor = APIDocProcessor()
    
    # 模拟一个Document对象
    class MockDocument:
        def __init__(self, content):
            self.content = content
            self.source_uri = "mock"
            self.metadata = {}
    
    doc = MockDocument(content)
    
    # 处理文档
    try:
        chunks = processor.process(content, doc, None)
        
        return {
            "strategy": "api_table_oriented",
            "chunks_count": len(chunks),
            "chunks": [
                {
                    "content": chunk.content if hasattr(chunk, 'content') else str(chunk),
                    "metadata": chunk.metadata if hasattr(chunk, 'metadata') else {}
                }
                for chunk in chunks
            ]
        }
    except Exception as e:
        logger.warning(f"API专用切片失败: {e}")
        return {"error": str(e)}


@comparison_bp.route('/parse_document_comparison', methods=['POST'])
def parse_document_comparison():
    """
    文档解析对比实验接口
    
    对比两种解析方式：
    1. LLM结构化解析：调用大模型将文档拆分为4部分
    2. 切片策略解析：使用语义/递归/层级切片
    
    请求参数：
    - file: 文档文件 (multipart/form-data)
    - compare_mode: 对比模式
      - "llm_only": 仅LLM解析
      - "chunk_only": 仅切片解析  
      - "both" (默认): 两种都执行并对比
    
    返回：
    - 对比结果
    """
    try:
        # 检查文件
        if 'file' not in request.files:
            return json_response({
                "code": 400,
                "message": "未找到文件",
                "data": None
            }, 400)
        
        file = request.files['file']
        if file.filename == '':
            return json_response({
                "code": 400,
                "message": "未选择文件",
                "data": None
            }, 400)
        
        file_ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if file_ext not in ALLOWED_EXTENSIONS:
            return json_response({
                "code": 400,
                "message": f"不支持的文件类型。允许的类型: {', '.join(ALLOWED_EXTENSIONS)}",
                "data": None
            }, 400)
        
        # 获取对比模式
        compare_mode = request.form.get('compare_mode', 'both')
        
        # 获取切片策略参数
        chunk_strategy = request.form.get('chunk_strategy', None)  # semantic, recursive, hierarchical, hybrid
        doc_type = request.form.get('doc_type', 'auto')
        
        # 保存上传的文件
        doc_id = str(uuid.uuid4())
        new_filename = f"{doc_id}.{file_ext}"
        file_path = os.path.join(UPLOAD_FOLDER, new_filename)
        file.save(file_path)
        
        logger.info(f"开始文档解析对比实验: {file.filename}, mode={compare_mode}")
        
        # 提取文档内容
        document_content = extract_document_content(file_path, file_ext)
        
        if not document_content:
            return json_response({
                "code": 400,
                "message": "无法提取文档内容",
                "data": None
            }, 400)
        
        logger.info(f"文档内容提取成功，长度: {len(document_content)}")
        
        # 准备结果
        result = {
            "doc_id": doc_id,
            "filename": file.filename,
            "original_length": len(document_content),
            "compare_mode": compare_mode
        }
        
        # ===== 方式1: LLM结构化解析 =====
        if compare_mode in ['llm_only', 'both']:
            logger.info("开始LLM结构化解析...")
            llm_result = analyze_with_llm(document_content, prompt_type="structure")
            result["llm_parsing"] = {
                "method": "LLM结构化解析",
                "description": "调用大模型将文档拆分为4部分（基础知识、服务内容、模板配置、API）",
                "result": llm_result,
                "sections": list(llm_result.keys()) if isinstance(llm_result, dict) else []
            }
        
        # ===== 方式2: 切片策略解析 =====
        if compare_mode in ['chunk_only', 'both']:
            logger.info("开始切片策略解析...")
            
            # 2.1 通用智能切片
            chunk_result = chunk_by_smart_strategy(
                document_content, 
                doc_type=doc_type,
                strategy=chunk_strategy
            )
            
            # 2.2 API文档专用切片（如果是API文档）
            api_chunk_result = None
            if doc_type == 'auto':
                # 自动检测
                from common.rag.processors.document_classifier import DocumentClassifier
                classifier = DocumentClassifier()
                classification = classifier.classify(document_content)
                detected_type = classification.doc_type.value if hasattr(classification.doc_type, 'value') else str(classification.doc_type)
                if detected_type == 'api_doc':
                    api_chunk_result = chunk_api_doc_by_table(document_content)
            elif doc_type == 'api_doc':
                api_chunk_result = chunk_api_doc_by_table(document_content)
            
            result["chunk_parsing"] = {
                "method": "切片策略解析",
                "description": f"使用{chunk_result.get('strategy', '智能推荐')}策略进行文档切片",
                "doc_type": chunk_result.get("doc_type"),
                "strategy": chunk_result.get("strategy"),
                "total_sections": chunk_result.get("total_sections"),
                "chunks_count": chunk_result.get("chunks_count"),
                "original_length": chunk_result.get("original_length"),
                "warnings": chunk_result.get("warnings", []),
                "hierarchy": chunk_result.get("hierarchy"),
                "api_specific_chunk": api_chunk_result
            }
        
        # ===== 提取文档中的图片 =====
        if file_ext in ['docx', 'doc']:
            logger.info("提取文档中的图片...")
            images = extract_images_from_docx(file_path)
            result["images"] = {
                "count": len(images),
                "note": "图片需要调用LLM进行OCR识别"
            }
        
        # ===== 保存对比结果 =====
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_filename = f"{doc_id}_{timestamp}.json"
        result_path = COMPARISON_OUTPUT_DIR / result_filename
        
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        result["result_file"] = str(result_path)
        
        # ===== 生成对比摘要 =====
        if compare_mode == 'both' and 'llm_parsing' in result and 'chunk_parsing' in result:
            llm_sections = len(result["llm_parsing"].get("sections", []))
            chunk_sections = result["chunk_parsing"].get("total_sections", 0)
            
            result["comparison_summary"] = {
                "llm_method": {
                    "sections": llm_sections,
                    "pro": "语义理解好，能提取隐含信息",
                    "con": "成本高，可能丢失细节信息"
                },
                "chunk_method": {
                    "sections": chunk_sections,
                    "pro": "保留完整结构信息，成本低",
                    "con": "缺乏语义理解能力"
                },
                "recommendation": "建议：对API文档使用切片策略，对复杂需求文档使用LLM策略"
            }
        
        return json_response({
            "code": 200,
            "message": "文档解析对比完成",
            "data": result
        })
    
    except Exception as e:
        logger.exception("文档解析对比失败")
        return json_response({
            "code": 500,
            "message": f"解析失败: {str(e)}",
            "data": None
        }, 500)


@comparison_bp.route('/parse_with_strategy', methods=['POST'])
def parse_with_strategy():
    """
    使用指定策略解析文档接口
    
    请求参数：
    - file: 文档文件
    - strategy: 切片策略 (semantic, recursive, hierarchical, hybrid, api_table)
    - doc_type: 文档类型 (auto, api_doc, product_doc, requirement, technical, generic)
    - save_to_vector: 是否保存到向量库 (true/false)
    """
    try:
        if 'file' not in request.files:
            return json_response({"code": 400, "message": "未找到文件"}, 400)
        
        file = request.files['file']
        if file.filename == '':
            return json_response({"code": 400, "message": "未选择文件"}, 400)
        
        file_ext = file.filename.rsplit('.', 1)[-1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            return json_response({
                "code": 400,
                "message": f"不支持的文件类型: {file_ext}"
            }, 400)
        
        # 获取参数
        strategy = request.form.get('strategy', 'semantic')
        doc_type = request.form.get('doc_type', 'auto')
        save_to_vector = request.form.get('save_to_vector', 'false').lower() == 'true'
        
        # 保存文件
        doc_id = str(uuid.uuid4())
        new_filename = f"{doc_id}.{file_ext}"
        file_path = os.path.join(UPLOAD_FOLDER, new_filename)
        file.save(file_path)
        
        # 提取内容
        document_content = extract_document_content(file_path, file_ext)
        
        if not document_content:
            return json_response({"code": 400, "message": "无法提取文档内容"}, 400)
        
        # 根据策略解析
        if strategy == 'api_table':
            # API文档专用切片
            parse_result = chunk_api_doc_by_table(document_content)
        else:
            # 通用切片策略
            parse_result = chunk_by_smart_strategy(document_content, doc_type=doc_type, strategy=strategy)
        
        # 保存到向量库
        vector_result = None
        if save_to_vector and parse_result.get("chunks"):
            try:
                from common.rag.core.vector_indexer import VectorIndexer
                from common.rag.core.chunkers import DocumentChunk
                
                indexer = VectorIndexer()
                
                # 准备chunks
                chunks = []
                for i, chunk_data in enumerate(parse_result.get("chunks", [])):
                    chunk = DocumentChunk(
                        content=chunk_data.get("content", ""),
                        doc_type=doc_type,
                        source_uri=file.filename,
                        chunk_index=i
                    )
                    chunks.append(chunk)
                
                # 构建索引
                collection_name = f"comparison_{doc_id}"
                indexer.build_index(chunks, collection_name)
                
                vector_result = {
                    "collection": collection_name,
                    "chunks_saved": len(chunks)
                }
                
                logger.info(f"向量库保存成功: {collection_name}")
            except Exception as e:
                logger.warning(f"向量库保存失败: {e}")
                vector_result = {"error": str(e)}
        
        return json_response({
            "code": 200,
            "message": "文档解析完成",
            "data": {
                "doc_id": doc_id,
                "strategy": strategy,
                "doc_type": doc_type,
                "parse_result": parse_result,
                "vector_result": vector_result
            }
        })
    
    except Exception as e:
        logger.exception("文档解析失败")
        return json_response({
            "code": 500,
            "message": f"解析失败: {str(e)}"
        }, 500)


@comparison_bp.route('/compare_test_case_quality', methods=['POST'])
def compare_test_case_quality():
    """
    对比不同解析策略生成的测试用例质量
    
    请求参数：
    - file: 文档文件
    - llm_result: LLM解析结果（可选）
    - chunk_result: 切片解析结果（可选）
    """
    try:
        if 'file' not in request.files:
            return json_response({"code": 400, "message": "未找到文件"}, 400)
        
        file = request.files['file']
        file_ext = file.filename.rsplit('.', 1)[-1].lower()
        
        if file_ext not in ALLOWED_EXTENSIONS:
            return json_response({"code": 400, "message": "不支持的文件类型"}, 400)
        
        # 保存文件
        doc_id = str(uuid.uuid4())
        new_filename = f"{doc_id}.{file_ext}"
        file_path = os.path.join(UPLOAD_FOLDER, new_filename)
        file.save(file_path)
        
        # 提取内容
        document_content = extract_document_content(file_path, file_ext)
        
        # 分别使用两种方式解析
        # 1. LLM解析
        llm_result = analyze_with_llm(document_content, prompt_type="structure")
        
        # 2. 切片解析
        chunk_result = chunk_by_smart_strategy(document_content)
        
        # TODO: 后续可以调用LLM生成测试用例进行对比
        # 这里返回解析结果供后续分析
        
        return json_response({
            "code": 200,
            "message": "解析完成，请使用结果生成测试用例进行质量对比",
            "data": {
                "doc_id": doc_id,
                "llm_parsing": llm_result,
                "chunk_parsing": chunk_result
            }
        })
    
    except Exception as e:
        logger.exception("对比失败")
        return json_response({
            "code": 500,
            "message": f"对比失败: {str(e)}"
        }, 500)


@comparison_bp.route('/list_comparison_results', methods=['GET'])
def list_comparison_results():
    """列出所有对比结果"""
    try:
        results = []
        for f in COMPARISON_OUTPUT_DIR.glob("*.json"):
            stat = f.stat()
            results.append({
                "filename": f.name,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
            })
        
        results.sort(key=lambda x: x["created"], reverse=True)
        
        return json_response({
            "code": 200,
            "message": "查询成功",
            "data": results
        })
    
    except Exception as e:
        return json_response({
            "code": 500,
            "message": f"查询失败: {str(e)}"
        }, 500)


@comparison_bp.route('/get_comparison_result/<filename>', methods=['GET'])
def get_comparison_result(filename):
    """获取指定对比结果"""
    try:
        file_path = COMPARISON_OUTPUT_DIR / filename
        
        if not file_path.exists():
            return json_response({
                "code": 404,
                "message": "文件不存在"
            }, 404)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            result = json.load(f)
        
        return json_response({
            "code": 200,
            "message": "查询成功",
            "data": result
        })
    
    except Exception as e:
        return json_response({
            "code": 500,
            "message": f"读取失败: {str(e)}"
        }, 500)
