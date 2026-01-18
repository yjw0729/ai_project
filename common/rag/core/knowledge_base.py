# app/core/knowledge_base.py
import asyncio
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
import hashlib

from common.rag.core.config_manager import ConfigManager
from common.rag.core.data_collector import DataCollector
from common.rag.core.document_processor import DocumentProcessor, ChunkingConfig
from common.rag.core.vector_indexer import VectorIndexer
from common.rag.core.models import Document, DocumentChunk, CollectionStats

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """知识库构建与管理层"""

    def __init__(self, config_dir: str = "app/config"):
        """
        初始化知识库管理器

        Args:
            config_dir: 配置文件目录
        """
        # 加载配置
        self.config_manager = ConfigManager(config_dir).load_configs()
        self.rag_config = self.config_manager.get_rag_config()
        self.vector_db_config = self.config_manager.get_vector_db_config()

        # 初始化组件
        self.data_collector = DataCollector(self._get_connector_configs())
        self.document_processor = DocumentProcessor(
            ChunkingConfig(
                chunk_size=self.rag_config.chunk_size,
                chunk_overlap=self.rag_config.chunk_overlap
            )
        )
        self.vector_indexer = VectorIndexer(self.config_manager)

        # 缓存和状态
        self.collections = {}  # 集合名称 -> 统计信息
        self._load_collections()

        logger.info("知识库管理器初始化完成")

    def _get_connector_configs(self) -> Dict[str, Any]:
        """获取连接器配置"""
        # 这里可以从配置文件或环境变量加载连接器配置
        configs = {
            "file": {
                "max_file_size": 100 * 1024 * 1024,  # 100MB
            },
            "database": {
                "db_type": "mysql",  # 默认
                "host": "localhost",
                "port": 3306,
            }
        }

        # 从环境变量加载
        import os
        if os.getenv('DATABASE_HOST'):
            configs["database"]["host"] = os.getenv('DATABASE_HOST')
        if os.getenv('DATABASE_PORT'):
            configs["database"]["port"] = int(os.getenv('DATABASE_PORT'))

        return configs

    def _load_collections(self):
        """加载已存在的集合信息"""
        try:
            collections_file = Path("collections.json")
            if collections_file.exists():
                with open(collections_file, 'r', encoding='utf-8') as f:
                    self.collections = json.load(f)
                logger.info(f"已加载 {len(self.collections)} 个集合信息")
        except Exception as e:
            logger.warning(f"加载集合信息失败: {e}")

    def _save_collections(self):
        """保存集合信息"""
        try:
            collections_file = Path("collections.json")
            with open(collections_file, 'w', encoding='utf-8') as f:
                json.dump(self.collections, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存集合信息失败: {e}")

    async def build_knowledge_base(
            self,
            source_configs: List[Dict[str, Any]],
            collection_name: str = None,
            chunking_strategy: str = None
    ) -> Dict[str, Any]:
        """
        构建知识库完整流程

        Args:
            source_configs: 数据源配置列表
            collection_name: 集合名称，如果为None则使用配置中的名称
            chunking_strategy: 分块策略

        Returns:
            构建结果统计
        """
        start_time = datetime.now()

        try:
            # 1. 数据采集
            logger.info("=" * 60)
            logger.info("开始数据采集...")
            documents = await self.data_collector.collect_from_multiple_sources(source_configs)

            if not documents:
                logger.warning("未采集到任何文档")
                return {
                    "status": "error",
                    "message": "未采集到任何文档",
                    "elapsed_seconds": (datetime.now() - start_time).total_seconds()
                }

            logger.info(f"数据采集完成: {len(documents)} 个文档")

            # 2. 文档处理
            logger.info("开始文档处理...")
            chunks = self.document_processor.process_documents(
                documents,
                chunking_strategy=chunking_strategy
            )

            if not chunks:
                logger.warning("文档处理后未生成任何文档块")
                return {
                    "status": "error",
                    "message": "文档处理后未生成任何文档块",
                    "elapsed_seconds": (datetime.now() - start_time).total_seconds()
                }

            logger.info(f"文档处理完成: {len(chunks)} 个文档块")

            # 3. 构建索引
            logger.info("开始构建向量索引...")
            stats = await self.vector_indexer.build_index(chunks, collection_name)

            # 4. 保存集合信息
            collection_name = collection_name or self.vector_db_config.collection_name
            self.collections[collection_name] = {
                "collection_name": stats.collection_name,
                "total_chunks": stats.total_chunks,
                "vector_dim": stats.vector_dim,
                "index_type": stats.index_type,
                "created_at": stats.created_at.isoformat(),
                "last_updated": datetime.now().isoformat(),
                "source_configs": source_configs
            }
            self._save_collections()

            # 5. 返回结果
            end_time = datetime.now()
            elapsed = (end_time - start_time).total_seconds()

            result = {
                "status": "success",
                "collection_name": stats.collection_name,
                "total_documents": len(documents),
                "total_chunks": len(chunks),
                "elapsed_seconds": elapsed,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "stats": {
                    "vector_dim": stats.vector_dim,
                    "index_type": stats.index_type,
                    "index_params": stats.index_params
                }
            }

            logger.info("=" * 60)
            logger.info(f"知识库构建完成: {result}")
            logger.info("=" * 60)

            return result

        except Exception as e:
            logger.error(f"构建知识库失败: {e}")
            return {
                "status": "error",
                "error": str(e),
                "elapsed_seconds": (datetime.now() - start_time).total_seconds(),
                "timestamp": datetime.now().isoformat()
            }

    async def search(
            self,
            query: str,
            collection_name: str = None,
            top_k: int = None,
            score_threshold: float = None,
            filters: Dict[str, Any] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        搜索知识库

        Args:
            query: 查询文本
            collection_name: 集合名称
            top_k: 返回数量
            score_threshold: 相似度阈值
            filters: 过滤条件 (如 {"business_module": "cross_border_opening"})

        Returns:
            相关文档块列表
        """
        try:
            logger.info(f"搜索查询: {query}, 过滤条件: {filters}")

            # 使用配置值或参数值
            top_k = top_k or self.rag_config.top_k
            score_threshold = score_threshold or self.rag_config.score_threshold

            results = await self.vector_indexer.search_similar(
                query=query,
                top_k=top_k,
                score_threshold=score_threshold,
                filters=filters
            )

            logger.info(f"搜索完成: 找到 {len(results)} 个相关结果")
            return results

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []

    async def add_documents(
            self,
            documents: List[Document],
            collection_name: str = None,
            chunking_strategy: str = None
    ) -> Dict[str, Any]:
        """
        向知识库添加文档

        Args:
            documents: 文档列表
            collection_name: 集合名称
            chunking_strategy: 分块策略

        Returns:
            添加结果
        """
        try:
            logger.info(f"开始添加 {len(documents)} 个文档到知识库")

            # 处理文档
            chunks = self.document_processor.process_documents(
                documents,
                chunking_strategy=chunking_strategy
            )

            if not chunks:
                return {
                    "status": "error",
                    "message": "未生成有效文档块"
                }

            # 添加到索引
            stats = await self.vector_indexer.build_index(chunks, collection_name)

            # 更新集合信息
            collection_name = collection_name or self.vector_db_config.collection_name
            if collection_name in self.collections:
                self.collections[collection_name]["total_chunks"] += len(chunks)
                self.collections[collection_name]["last_updated"] = datetime.now().isoformat()
            else:
                self.collections[collection_name] = {
                    "collection_name": collection_name,
                    "total_chunks": len(chunks),
                    "vector_dim": stats.vector_dim,
                    "index_type": stats.index_type,
                    "created_at": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat()
                }

            self._save_collections()

            logger.info(f"成功添加 {len(chunks)} 个文档块到集合 {collection_name}")

            return {
                "status": "success",
                "added_chunks": len(chunks),
                "collection_name": collection_name,
                "total_chunks": self.collections[collection_name]["total_chunks"]
            }

        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    def get_collection_info(self, collection_name: str = None) -> Dict[str, Any]:
        """获取集合信息"""
        collection_name = collection_name or self.vector_db_config.collection_name

        if collection_name in self.collections:
            return self.collections[collection_name]
        else:
            return self.vector_indexer.get_collection_stats(collection_name)

    def delete_collection(self, collection_name: str = None):
        """删除集合"""
        collection_name = collection_name or self.vector_db_config.collection_name

        try:
            self.vector_indexer.delete_collection(collection_name)

            if collection_name in self.collections:
                del self.collections[collection_name]
                self._save_collections()

            logger.info(f"已删除集合: {collection_name}")

        except Exception as e:
            logger.error(f"删除集合失败: {e}")
            raise

    def list_collections(self) -> List[Dict[str, Any]]:
        """列出所有集合"""
        collections_list = []

        for name, info in self.collections.items():
            collections_list.append({
                "name": name,
                "total_chunks": info.get("total_chunks", 0),
                "created_at": info.get("created_at", ""),
                "last_updated": info.get("last_updated", "")
            })

        return collections_list

    async def query_with_context(
            self,
            query: str,
            collection_name: str = None,
            top_k: int = None,
            score_threshold: float = None
    ) -> Dict[str, Any]:
        """
        查询知识库并返回上下文

        Args:
            query: 查询文本
            collection_name: 集合名称
            top_k: 返回数量
            score_threshold: 相似度阈值

        Returns:
            查询结果，包含相关上下文
        """
        start_time = datetime.now()

        try:
            # 搜索相关文档
            search_results = await self.search(
                query=query,
                collection_name=collection_name,
                top_k=top_k,
                score_threshold=score_threshold
            )

            if not search_results:
                return {
                    "query": query,
                    "results": [],
                    "total_results": 0,
                    "message": "未找到相关文档",
                    "elapsed_seconds": (datetime.now() - start_time).total_seconds()
                }

            # 格式化结果
            formatted_results = []
            for chunk, score in search_results:
                formatted_results.append({
                    "content": chunk.content,
                    "score": float(score),
                    "source": chunk.source_uri,
                    "metadata": chunk.metadata,
                    "chunk_id": chunk.chunk_id
                })

            result = {
                "query": query,
                "results": formatted_results,
                "total_results": len(formatted_results),
                "elapsed_seconds": (datetime.now() - start_time).total_seconds(),
                "collection": collection_name or self.vector_db_config.collection_name
            }

            return result

        except Exception as e:
            logger.error(f"查询上下文失败: {e}")
            return {
                "query": query,
                "error": str(e),
                "elapsed_seconds": (datetime.now() - start_time).total_seconds()
            }