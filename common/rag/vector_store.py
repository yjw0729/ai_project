"""
VectorStore 向量存储模块

提供向量检索（RAG）的核心功能，支持多种向量数据库后端。
"""

import json
import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """文档块"""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    chunk_index: int = 0
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'content': self.content,
            'metadata': self.metadata,
            'chunk_index': self.chunk_index,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'DocumentChunk':
        created_at = data.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            id=data['id'],
            content=data['content'],
            metadata=data.get('metadata', {}),
            embedding=data.get('embedding'),
            chunk_index=data.get('chunk_index', 0),
            created_at=created_at or datetime.now(),
        )


@dataclass
class SearchResult:
    """检索结果"""
    chunk: DocumentChunk
    score: float
    distance: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            'chunk': self.chunk.to_dict(),
            'score': self.score,
            'distance': self.distance,
        }


class VectorStore:
    """向量存储基类"""

    def __init__(
        self,
        collection_name: str = "default",
        embedding_model: Optional[str] = None,
        embedding_fn: Optional[Callable] = None,
        **kwargs
    ):
        """
        初始化向量存储

        Args:
            collection_name: 集合名称
            embedding_model: embedding模型名称
            embedding_fn: embedding函数
            **kwargs: 其他配置参数
        """
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.embedding_fn = embedding_fn
        self.config = kwargs
        self._initialized = False

    def initialize(self):
        """初始化向量存储"""
        self._initialized = True
        logger.info(f"向量存储初始化完成: collection={self.collection_name}")

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

    def add_documents(
        self,
        documents: List[DocumentChunk],
        batch_size: int = 100
    ) -> List[str]:
        """
        添加文档块

        Args:
            documents: 文档块列表
            batch_size: 批量大小

        Returns:
            文档ID列表
        """
        if not self._initialized:
            self.initialize()

        ids = []
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            batch_ids = self._add_batch(batch)
            ids.extend(batch_ids)

        logger.info(f"添加文档完成: {len(ids)} 个文档块")
        return ids

    def _add_batch(self, documents: List[DocumentChunk]) -> List[str]:
        """批量添加文档（子类实现）"""
        raise NotImplementedError

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_cond: Optional[Dict] = None,
        **kwargs
    ) -> List[SearchResult]:
        """
        检索文档

        Args:
            query: 查询文本
            top_k: 返回结果数量
            filter_cond: 过滤条件
            **kwargs: 其他参数

        Returns:
            检索结果列表
        """
        if not self._initialized:
            self.initialize()

        # 生成查询向量
        query_embedding = self._get_embedding(query)

        # 执行检索
        results = self._search_vector(
            query_embedding,
            top_k=top_k,
            filter_cond=filter_cond,
            **kwargs
        )

        return results

    def _get_embedding(self, text: str) -> List[float]:
        """获取文本的embedding向量"""
        if self.embedding_fn:
            return self.embedding_fn(text)

        # 默认返回随机向量（实际使用时应配置真实的embedding函数）
        import random
        dim = self.config.get('embedding_dim', 768)
        return [random.random() for _ in range(dim)]

    def _search_vector(
        self,
        query_embedding: List[float],
        top_k: int,
        filter_cond: Optional[Dict],
        **kwargs
    ) -> List[SearchResult]:
        """执行向量检索（子类实现）"""
        raise NotImplementedError

    def delete(self, ids: List[str]):
        """删除文档"""
        raise NotImplementedError

    def count(self) -> int:
        """获取文档数量"""
        raise NotImplementedError

    def clear(self):
        """清空所有文档"""
        raise NotImplementedError


class ChromaVectorStore(VectorStore):
    """ChromaDB向量存储实现"""

    def __init__(
        self,
        collection_name: str = "default",
        persist_directory: Optional[str] = None,
        embedding_fn: Optional[Callable] = None,
        **kwargs
    ):
        """
        初始化ChromaDB向量存储

        Args:
            collection_name: 集合名称
            persist_directory: 持久化目录
            embedding_fn: embedding函数
        """
        super().__init__(
            collection_name=collection_name,
            embedding_fn=embedding_fn,
            **kwargs
        )
        self.persist_directory = persist_directory or "./chroma_data"
        self._client = None
        self._collection = None

    def initialize(self):
        """初始化ChromaDB"""
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError:
            logger.error("ChromaDB未安装，请运行: pip install chromadb")
            raise ImportError("ChromaDB未安装")

        self._client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )

        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": f"Collection: {self.collection_name}"}
        )

        self._initialized = True
        logger.info(f"ChromaDB初始化完成: collection={self.collection_name}, persist={self.persist_directory}")

    def _add_batch(self, documents: List[DocumentChunk]) -> List[str]:
        """批量添加文档到ChromaDB"""
        ids = [doc.id for doc in documents]
        contents = [doc.content for doc in documents]
        metadatas = [doc.metadata for doc in documents]

        # 获取或生成embeddings
        embeddings = []
        for doc in documents:
            if doc.embedding:
                embeddings.append(doc.embedding)
            else:
                embeddings.append(self._get_embedding(doc.content))

        self._collection.add(
            ids=ids,
            documents=contents,
            metadatas=metadatas,
            embeddings=embeddings
        )

        return ids

    def _search_vector(
        self,
        query_embedding: List[float],
        top_k: int,
        filter_cond: Optional[Dict],
        **kwargs
    ) -> List[SearchResult]:
        """在ChromaDB中执行向量检索"""
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filter_cond,
            include=["documents", "metadatas", "distances"]
        )

        search_results = []
        if results and results.get('ids'):
            ids = results['ids'][0]
            documents = results['documents'][0]
            metadatas = results.get('metadatas', [[]])[0]
            distances = results.get('distances', [[]])[0]

            for i, doc_id in enumerate(ids):
                chunk = DocumentChunk(
                    id=doc_id,
                    content=documents[i] if i < len(documents) else '',
                    metadata=metadatas[i] if i < len(metadatas) else {},
                    chunk_index=i
                )
                distance = distances[i] if i < len(distances) else 0.0
                score = 1.0 - distance  # 转换距离为相似度

                search_results.append(SearchResult(
                    chunk=chunk,
                    score=score,
                    distance=distance
                ))

        return search_results

    def delete(self, ids: List[str]):
        """删除文档"""
        if self._collection:
            self._collection.delete(ids=ids)
            logger.info(f"删除文档: {len(ids)} 个")

    def count(self) -> int:
        """获取文档数量"""
        if self._collection:
            return self._collection.count()
        return 0

    def clear(self):
        """清空所有文档"""
        if self._client and self._collection:
            self._client.delete_collection(name=self.collection_name)
            self._collection = self._client.get_or_create_collection(name=self.collection_name)
            logger.info(f"清空集合: {self.collection_name}")


def create_vector_store(
    store_type: str = "chroma",
    **kwargs
) -> VectorStore:
    """
    创建向量存储实例

    Args:
        store_type: 存储类型 ('chroma', 'memory', 'qdrant')
        **kwargs: 其他参数

    Returns:
        VectorStore实例
    """
    if store_type == "chroma":
        return ChromaVectorStore(**kwargs)
    elif store_type == "memory":
        return VectorStore(**kwargs)  # 简化实现
    else:
        raise ValueError(f"不支持的向量存储类型: {store_type}")
