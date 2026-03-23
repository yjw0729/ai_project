# common/rag/processors/__init__.py
"""
文档处理器模块

包含以下组件：
- document_classifier: 智能文档分类器
- adaptive_processor: 自适应差异化文档处理器  
- content_enhancer: 内容增强器
"""

from common.rag.processors.document_classifier import (
    DocumentClassifier,
    DocumentType,
    ClassificationResult,
    classify_document
)

from common.rag.processors.adaptive_processor import (
    AdaptiveDocumentProcessor,
    APIDocProcessor,
    TechnicalDocProcessor,
    ProductDocProcessor,
    RequirementDocProcessor,
    UserGuideProcessor,
    GenericDocProcessor,
    ProcessingResult,
    process_adaptive
)

from common.rag.processors.content_enhancer import (
    ContentEnhancer,
    EnhancementConfig,
    EnhancementType,
    EnhancedChunk,
    RetrievalEnhancer,
    enhance_content,
    enhance_retrieval_results
)

__all__ = [
    # 分类器
    "DocumentClassifier",
    "DocumentType", 
    "DocumentTypeConfig",
    "ClassificationResult",
    "classify_document",
    
    # 差异化处理器
    "AdaptiveDocumentProcessor",
    "BaseTypeProcessor",
    "APIDocProcessor",
    "TechnicalDocProcessor",
    "ProductDocProcessor",
    "RequirementDocProcessor",
    "UserGuideProcessor",
    "GenericDocProcessor",
    "ProcessingResult",
    "process_adaptive",
    
    # 内容增强
    "ContentEnhancer",
    "EnhancementConfig",
    "EnhancementType", 
    "EnhancedChunk",
    "RetrievalEnhancer",
    "enhance_content",
    "enhance_retrieval_results"
]

