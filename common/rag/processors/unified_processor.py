#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一智能文档处理器
根据文档类型自动选择最佳处理策略

功能：
1. 自动识别文档类型
2. 调用对应的专用处理器
3. 统一输出格式
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

from common.rag.processors.document_classifier import DocumentClassifier, DocumentType
from common.rag.processors.api_doc_processor import APIDocumentProcessor
from common.rag.processors.product_doc_processor import ProductDocumentProcessor
from common.rag.core.document_processor import DocumentProcessor, ChunkingConfig
from common.rag.core.models import Document, DocumentChunk

logger = logging.getLogger(__name__)


class UnifiedDocumentProcessor:
    """
    统一智能文档处理器
    
    使用流程：
    1. 接收原始文档内容
    2. 自动识别文档类型
    3. 选择最佳处理策略
    4. 调用专用处理器
    5. 返回标准化文本块
    """
    
    def __init__(self, chunking_config: ChunkingConfig = None):
        """
        初始化统一处理器
        
        Args:
            chunking_config: 分块配置（可选）
        """
        # 初始化分类器
        self.classifier = DocumentClassifier()
        
        # 初始化专用处理器
        self.api_processor = APIDocumentProcessor()
        self.product_processor = ProductDocumentProcessor()
        
        # 初始化通用处理器（用于无法识别的情况）
        self.default_processor = chunking_config or ChunkingConfig()
        self.generic_processor = DocumentProcessor(self.default_processor)
        
        # 统计信息
        self.stats = {
            'total_processed': 0,
            'by_type': {}
        }
        
        logger.info("统一智能文档处理器初始化完成")
    
    def process(
        self, 
        content: str, 
        filename: str = "",
        metadata: Dict = None,
        force_type: DocumentType = None
    ) -> Tuple[List[DocumentChunk], Dict]:
        """
        处理文档（自动识别类型）
        
        Args:
            content: 文档内容
            filename: 文件名（用于辅助识别）
            metadata: 元数据
            force_type: 强制指定文档类型（可选）
            
        Returns:
            (文本块列表, 处理元数据)
        """
        # 1. 自动识别文档类型
        if force_type:
            doc_type = force_type
            confidence = 1.0
        else:
            doc_type, confidence, scores = self.classifier.classify(content, filename, metadata)
        
        logger.info(f"文档类型识别结果: {doc_type.value}, 置信度: {confidence:.2f}")
        
        # 2. 更新统计
        self.stats['total_processed'] += 1
        type_key = doc_type.value
        self.stats['by_type'][type_key] = self.stats['by_type'].get(type_key, 0) + 1
        
        # 3. 选择处理策略
        processing_metadata = {
            'detected_type': doc_type.value,
            'confidence': confidence,
            'filename': filename,
        }
        
        if metadata:
            processing_metadata.update(metadata)
        
        # 4. 调用对应处理器
        if doc_type == DocumentType.API_DOC:
            return self._process_api_doc(content, processing_metadata)
        elif doc_type == DocumentType.PRODUCT_DESIGN:
            return self._process_product_doc(content, processing_metadata)
        elif doc_type == DocumentType.TECHNICAL_SPEC:
            return self._process_tech_doc(content, processing_metadata)
        elif doc_type == DocumentType.TEST_CASE:
            return self._process_test_doc(content, processing_metadata)
        elif doc_type == DocumentType.USER_GUIDE:
            return self._process_guide_doc(content, processing_metadata)
        elif doc_type == DocumentType.REQUIREMENT:
            return self._process_requirement_doc(content, processing_metadata)
        else:
            return self._process_generic_doc(content, processing_metadata)
    
    def _process_api_doc(self, content: str, metadata: Dict) -> Tuple[List, Dict]:
        """处理API文档"""
        chunks_data, extracted_meta = self.api_processor.process(content, metadata)
        
        # 转换为标准格式
        chunks = self._convert_to_chunks(chunks_data, extracted_meta)
        
        logger.info(f"API文档处理完成: {len(chunks)} 个块")
        return chunks, extracted_meta
    
    def _process_product_doc(self, content: str, metadata: Dict) -> Tuple[List, Dict]:
        """处理产品文档"""
        chunks_data, extracted_meta = self.product_processor.process(content, metadata)
        
        # 转换为标准格式
        chunks = self._convert_to_chunks(chunks_data, extracted_meta)
        
        logger.info(f"产品文档处理完成: {len(chunks)} 个块")
        return chunks, extracted_meta
    
    def _process_tech_doc(self, content: str, metadata: Dict) -> Tuple[List, Dict]:
        """处理技术文档"""
        # 技术文档使用层次化分块
        metadata['chunking_strategy'] = 'hierarchical'
        
        # 转换为Document对象
        doc = Document(
            content=content,
            source_uri=metadata.get('source_uri', ''),
            doc_type='technical_spec',
            metadata=metadata
        )
        
        # 使用通用处理器
        chunks = self.generic_processor.process_documents([doc], 'hierarchical')
        
        # 更新元数据
        extracted_meta = {**metadata, 'doc_type': 'technical_spec'}
        
        logger.info(f"技术文档处理完成: {len(chunks)} 个块")
        return chunks, extracted_meta
    
    def _process_test_doc(self, content: str, metadata: Dict) -> Tuple[List, Dict]:
        """处理测试文档"""
        # 测试文档使用语义分块
        metadata['chunking_strategy'] = 'semantic'
        
        doc = Document(
            content=content,
            source_uri=metadata.get('source_uri', ''),
            doc_type='test_case',
            metadata=metadata
        )
        
        chunks = self.generic_processor.process_documents([doc], 'semantic')
        extracted_meta = {**metadata, 'doc_type': 'test_case'}
        
        logger.info(f"测试文档处理完成: {len(chunks)} 个块")
        return chunks, extracted_meta
    
    def _process_guide_doc(self, content: str, metadata: Dict) -> Tuple[List, Dict]:
        """处理用户指南"""
        # 用户指南使用步骤化分块
        metadata['chunking_strategy'] = 'semantic'
        
        doc = Document(
            content=content,
            source_uri=metadata.get('source_uri', ''),
            doc_type='user_guide',
            metadata=metadata
        )
        
        chunks = self.generic_processor.process_documents([doc], 'semantic')
        extracted_meta = {**metadata, 'doc_type': 'user_guide'}
        
        logger.info(f"用户指南处理完成: {len(chunks)} 个块")
        return chunks, extracted_meta
    
    def _process_requirement_doc(self, content: str, metadata: Dict) -> Tuple[List, Dict]:
        """处理需求文档"""
        # 需求文档使用语义分块
        metadata['chunking_strategy'] = 'semantic'
        
        doc = Document(
            content=content,
            source_uri=metadata.get('source_uri', ''),
            doc_type='requirement',
            metadata=metadata
        )
        
        chunks = self.generic_processor.process_documents([doc], 'semantic')
        extracted_meta = {**metadata, 'doc_type': 'requirement'}
        
        logger.info(f"需求文档处理完成: {len(chunks)} 个块")
        return chunks, extracted_meta
    
    def _process_generic_doc(self, content: str, metadata: Dict) -> Tuple[List, Dict]:
        """处理通用文档"""
        metadata['chunking_strategy'] = 'recursive'
        
        doc = Document(
            content=content,
            source_uri=metadata.get('source_uri', ''),
            doc_type='unknown',
            metadata=metadata
        )
        
        chunks = self.generic_processor.process_documents([doc], 'recursive')
        extracted_meta = {**metadata, 'doc_type': 'unknown'}
        
        logger.info(f"通用文档处理完成: {len(chunks)} 个块")
        return chunks, extracted_meta
    
    def _convert_to_chunks(self, chunks_data: List[Dict], metadata: Dict) -> List[DocumentChunk]:
        """将处理器的输出转换为标准DocumentChunk格式"""
        chunks = []
        
        for i, chunk_data in enumerate(chunks_data):
            chunk = DocumentChunk(
                content=chunk_data.get('content', ''),
                source_type=metadata.get('source_type', 'file'),
                source_uri=metadata.get('source_uri', ''),
                doc_type=metadata.get('doc_type', 'unknown'),
                metadata={**metadata, **chunk_data.get('metadata', {})}
            )
            chunks.append(chunk)
        
        return chunks
    
    def get_stats(self) -> Dict:
        """获取处理统计信息"""
        return self.stats
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'total_processed': 0,
            'by_type': {}
        }


def process_document(
    content: str, 
    filename: str = "",
    metadata: Dict = None,
    force_type: str = None
) -> Tuple[List[DocumentChunk], Dict]:
    """
    处理文档的便捷函数
    
    Args:
        content: 文档内容
        filename: 文件名
        metadata: 元数据
        force_type: 强制指定类型 (api_doc, product_design, technical_spec, test_case, user_guide, requirement)
        
    Returns:
        (文本块列表, 处理元数据)
    """
    processor = UnifiedDocumentProcessor()
    
    # 转换类型字符串
    doc_type = None
    if force_type:
        try:
            doc_type = DocumentType(force_type)
        except ValueError:
            logger.warning(f"未知的文档类型: {force_type}")
    
    return processor.process(content, filename, metadata, doc_type)


# 使用示例
if __name__ == "__main__":
    # 测试API文档处理
    api_content = """
    # 用户管理API
    
    ## 创建用户
    POST /api/v1/users
    
    ### 请求参数
    | 参数名 | 类型 | 必填 | 说明 |
    |--------|------|------|------|
    | username | string | 是 | 用户名 |
    | email | string | 是 | 邮箱 |
    
    ### 响应
    200 OK
    {
        "id": 123,
        "username": "test"
    }
    """
    
    processor = UnifiedDocumentProcessor()
    chunks, metadata = processor.process(api_content, "user_api.md")
    
    print(f"检测到的文档类型: {metadata.get('detected_type')}")
    print(f"处理后的块数量: {len(chunks)}")
    print(f"统计信息: {processor.get_stats()}")





