import logging
import hashlib
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from common.rag.core.models import Document,DocumentType


class BaseConnector(ABC):
    '''基础连接器抽象类'''

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._init_connection()

    def _init_connection(self):
        pass

    @abstractmethod
    def collect(self, source_config: Dict[str,Any]) -> List[Document]:
        '''
        从数据源采集数据
        :param source_config: 数据源配置
        :return: 文档列表
        '''
        pass

    def test_connection(self) -> bool:
        '''测试连接是否可用'''
        try:
            return self._test_connection_internal()
        except Exception as e:
            self.logger.error(f"连接测试失败:{e}")
            return False

    def _test_connection_internal(self) ->bool:
        return True

    def close(self):
        pass

    def _generate_document_id(self, content: str, source_uri: str) -> str:
        '''生成文档id'''
        combined = f"{source_uri}:{content[:1000]}"
        return hashlib.md5(combined.encode()).hexdigest()

    def _create_document(
            self,
            content: str,
            source_type: str,
            source_uri: str,
            doc_type: Optional[DocumentType] = None,
            metadata: Optional[Dict[str, Any]] = None
    ) -> Document:
        '''创建文档对象'''
        if not content or not isinstance(content, str):
            self.logger.warning(f"无效内容{content}")
            return None

        #自动检测文档类型
        if not doc_type:
            doc_type = self._generate_document_id(content, source_uri)

        #生成文档id
        doc_id = self._generate_document_id(content, source_uri)

        #基础元数据
        base_metadata = {
            "connector_type": self.__class__.__name__,
            "source_uri": source_uri,
            "collection_time": datetime.now().isoformat(),
            "content_length": len(content),
            "content_hash": hashlib.md5(content.encode()).hexdigest()
        }

        #合并用户元数据
        if metadata:
            base_metadata.update(metadata)

        return Document(
            id= doc_id,
            content=content,
            source_type=source_type,
            source_uri=source_uri,
            doc_type=doc_type,
            metadata=base_metadata
        )

    def _detect_document_type(
            self,
            content: str,
            source_uri: str
    ) -> DocumentType:
        '''自动检测文档类型'''
        content_lower = content.lower()
        source_lower = source_uri.lower()

        #基于文件路径/uri的关键词检测
        if any(keyword in source_lower for keyword in ['test', '测试','testcase', '用例']):
            return DocumentType.TEST_CASE
        elif any(keyword in source_lower for keyword in ['api', '接口', 'rest', 'swagger']):
            return DocumentType.API_DOC
        elif any(keyword in source_lower for keyword in ['design', '设计', '架构']):
            return DocumentType.DESIGN_DOC
        elif any(keyword in source_lower for keyword in ['requirement', '需求', 'spec', '规格']):
            return DocumentType.PRODUCT_REQ
        elif any(keyword in source_lower for keyword in ['bug', '缺陷', 'issue']):
            return DocumentType.BUG_REPORT
        elif any(keyword in source_lower for keyword in ['tech', '技术', 'spec']):
            return DocumentType.TECH_SPEC
        # 基于内容的关键词检测
        if 'def test_' in content_lower or 'test_' in content_lower or '测试用例' in content:
            return DocumentType.TEST_CASE
        elif 'http' in content_lower or 'api' in content_lower or '接口' in content:
            return DocumentType.API_DOC
        elif 'class diagram' in content_lower or '架构图' in content or '设计模式' in content:
            return DocumentType.DESIGN_DOC

        return DocumentType.TECH_SPEC

    def __enter__(self):
        '''上下文管理入口'''
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        '''上下文管理器退出'''
        self.close()


