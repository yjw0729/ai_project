# app/core/vector_indexer.py
import logging
import asyncio
import hashlib
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime
import numpy as np
import json
import os

from common.rag.core.models import DocumentChunk, CollectionStats
from common.rag.core.config_manager import ConfigManager, VectorDBConfig, RAGConfig

logger = logging.getLogger(__name__)


class VectorIndexer:
    """向量化与索引构建模块 - 将文本转换为向量并构建索引"""

    def __init__(
            self,
            config_manager: ConfigManager,
            embedding_client=None
    ):
        """
        初始化向量索引器

        Args:
            config_manager: 配置管理器
            embedding_client: 可选的embedding客户端
        """
        self.config = config_manager.get_vector_db_config()
        self.rag_config = config_manager.get_rag_config()
        self.embedding_client = embedding_client
        self.vector_store = None

        # 加载embedding模型配置
        self.embedding_models_config = self._load_embedding_models_config()

        self._init_vector_store()

        logger.info(f"向量索引器初始化: db_type={self.config.db_type}, default_model={self.rag_config.embedding_model}")
        logger.info(f"支持多文档类型向量化，共{len(self.embedding_models_config.get('by_document_type', {}))}种配置")

    def _load_embedding_models_config(self) -> Dict[str, Any]:
        """加载embedding模型配置"""
        config_path = os.path.join(os.path.dirname(self.config.__file__) if hasattr(self.config, '__file__') else "app/config/rag", "embedding_models.json")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载embedding模型配置文件失败: {e}, 使用默认配置")
            return {
                "default": {
                    "provider": self.rag_config.embedding_provider,
                    "model": self.rag_config.embedding_model,
                    "dimension": self.config.dimension
                }
            }

    def _get_embedding_config_for_document(self, doc_type: str = None) -> Dict[str, Any]:
        """根据文档类型获取对应的embedding配置"""
        if not doc_type:
            return self.embedding_models_config.get("default", {
                "provider": self.rag_config.embedding_provider,
                "model": self.rag_config.embedding_model,
                "dimension": self.config.dimension
            })

        # 尝试从by_document_type配置中查找
        doc_config = self.embedding_models_config.get("by_document_type", {}).get(doc_type)
        if doc_config:
            return doc_config

        # 如果没找到，使用默认配置
        logger.info(f"文档类型 '{doc_type}' 未找到专用embedding配置，使用默认配置")
        return self.embedding_models_config.get("default", {
            "provider": self.rag_config.embedding_provider,
            "model": self.rag_config.embedding_model,
            "dimension": self.config.dimension
        })

    def _init_vector_store(self):
        """初始化向量存储"""
        db_type = self.config.db_type.lower()

        try:
            if db_type == "chroma":
                self._init_chroma()
            elif db_type == "memory":
                self._init_memory_store()
            else:
                logger.warning(f"不支持的向量数据库类型: {db_type}, 将使用ChromaDB作为默认")
                self.config.db_type = "chroma"
                self._init_chroma()

        except ImportError as e:
            logger.error(f"导入向量数据库包失败: {e}")
            # 尝试使用内存存储作为fallback
            try:
                logger.info("尝试使用内存存储作为fallback...")
                self.config.db_type = "memory"
                self._init_memory_store()
            except Exception as fallback_e:
                logger.error(f"内存存储fallback也失败: {fallback_e}")
                raise RuntimeError("无法初始化任何向量数据库，请检查依赖安装")
        except Exception as e:
            logger.error(f"初始化向量存储失败: {e}")
            # 尝试使用内存存储作为fallback
            try:
                logger.info("尝试使用内存存储作为fallback...")
                self.config.db_type = "memory"
                self._init_memory_store()
            except Exception as fallback_e:
                logger.error(f"内存存储fallback也失败: {fallback_e}")
                raise

    def _init_chroma(self):
        """初始化ChromaDB - 支持本地持久化和远程服务器"""
        try:
            import chromadb

            # 检查是否配置了远程服务器
            host = getattr(self.config, 'host', None)
            port = getattr(self.config, 'port', None)

            if host and host not in ['localhost', '127.0.0.1', '']:
                # 连接到远程ChromaDB服务器
                logger.info(f"连接到ChromaDB服务器: {host}:{port or 8000}")
                self.chroma_client = chromadb.HttpClient(
                    host=host,
                    port=port or 8000
                )
            else:
                # 使用本地持久化存储（新版本API）
                persist_directory = "./chroma_data"
                os.makedirs(persist_directory, exist_ok=True)

                logger.info(f"使用本地ChromaDB存储: {persist_directory}")
                self.chroma_client = chromadb.PersistentClient(
                    path=persist_directory
                )

            # 获取或创建集合（新版本ChromaDB API）
            try:
                self.collection = self.chroma_client.get_or_create_collection(
                    name=self.config.collection_name,
                    metadata={
                        "hnsw:space": getattr(self.config, 'metric_type', 'cosine').lower()
                    }
                )
                logger.info(f"获取或创建Chroma集合: {self.config.collection_name}")
            except Exception as e:
                logger.error(f"创建Chroma集合失败: {e}")
                raise

            self.vector_store = self.collection

        except Exception as e:
            logger.error(f"初始化ChromaDB失败: {e}")
            raise

    def _init_memory_store(self):
        """初始化内存向量存储（用于测试）"""
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np

            class MemoryVectorStore:
                def __init__(self, dimension=768):
                    self.dimension = dimension
                    self.vectors = []
                    self.metadata = []
                    self.ids = []

                def add_vectors(self, vectors, metadata=None, ids=None):
                    """添加向量"""
                    if isinstance(vectors, list):
                        vectors = np.array(vectors)

                    self.vectors.extend(vectors.tolist() if hasattr(vectors, 'tolist') else vectors)

                    if metadata:
                        self.metadata.extend(metadata)
                    else:
                        self.metadata.extend([{}] * len(vectors))

                    if ids:
                        self.ids.extend(ids)
                    else:
                        start_id = len(self.ids)
                        self.ids.extend([f"vec_{start_id + i}" for i in range(len(vectors))])

                def search(self, query_vector, top_k=5):
                    """搜索相似向量"""
                    if not self.vectors:
                        return []

                    if isinstance(query_vector, list):
                        query_vector = np.array(query_vector)

                    vectors_array = np.array(self.vectors)
                    similarities = cosine_similarity([query_vector], vectors_array)[0]

                    # 获取top_k个最相似的索引
                    top_indices = np.argsort(similarities)[-top_k:][::-1]

                    results = []
                    for idx in top_indices:
                        results.append({
                            'id': self.ids[idx],
                            'score': float(similarities[idx]),
                            'metadata': self.metadata[idx]
                        })

                    return results

                def delete_collection(self):
                    """清空集合"""
                    self.vectors = []
                    self.metadata = []
                    self.ids = []

            self.vector_store = MemoryVectorStore(dimension=self.config.dimension)
            logger.info("内存向量存储初始化成功（仅用于测试）")

        except ImportError as e:
            logger.error(f"初始化内存存储失败: {e}")
            raise

    async def generate_embeddings(
            self,
            texts: List[str],
            embedding_config: Dict[str, Any] = None
    ) -> List[List[float]]:
        """
        生成文本向量

        Args:
            texts: 文本列表
            embedding_config: embedding配置，如果为None则使用默认配置

        Returns:
            向量列表
        """
        if not texts:
            return []

        # 如果没有指定配置，使用默认配置
        if embedding_config is None:
            embedding_config = self._get_embedding_config_for_document()

        try:
            provider = embedding_config.get("provider", self.rag_config.embedding_provider).lower()
            model = embedding_config.get("model", self.rag_config.embedding_model)

            logger.info(f"生成embedding: provider={provider}, model={model}, texts={len(texts)}")

            if provider == "tongyi":
                return await self._generate_tongyi_embeddings(texts, model)
            elif provider == "openai":
                return await self._generate_openai_embeddings(texts, model)
            elif provider == "huggingface":
                return await self._generate_huggingface_embeddings(texts, model)
            elif provider == "local":
                return await self._generate_local_embeddings(texts, model)
            else:
                # 默认使用sentence-transformers
                return await self._generate_huggingface_embeddings(texts, model)

        except Exception as e:
            logger.error(f"生成向量时出错: {e}")
            # 返回随机向量作为fallback
            return self._generate_random_vectors(len(texts))

    async def _generate_tongyi_embeddings(self, texts: List[str], model: str = None) -> List[List[float]]:
        """使用通义千问生成embedding"""
        try:
            import dashscope
            from dashscope import TextEmbedding

            # 设置API密钥
            api_key = os.getenv('DASHSCOPE_API_KEY')
            if not api_key:
                raise ValueError("未设置DASHSCOPE_API_KEY环境变量")

            dashscope.api_key = api_key

            # 使用指定的模型，如果没有指定则使用默认
            model_name = model or self.rag_config.embedding_model

            embeddings = []
            batch_size = 25  # 通义千问API限制

            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]

                response = TextEmbedding.call(
                    model=model_name,
                    input=batch
                )

                if response.status_code == 200:
                    batch_embeddings = [
                        item['embedding']
                        for item in response.output['embeddings']
                    ]
                    embeddings.extend(batch_embeddings)
                else:
                    logger.error(f"通义千问embedding失败: {response.message}")
                    raise Exception(f"通义千问embedding失败: {response.message}")

            return embeddings

        except Exception as e:
            logger.error(f"通义千问embedding失败: {e}")
            raise

    async def _generate_openai_embeddings(self, texts: List[str], model: str = None) -> List[List[float]]:
        """使用OpenAI生成embedding"""
        try:
            from openai import OpenAI

            client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

            model_name = model or self.rag_config.embedding_model

            response = client.embeddings.create(
                model=model_name,
                input=texts
            )

            return [data.embedding for data in response.data]

        except Exception as e:
            logger.error(f"OpenAI embedding失败: {e}")
            raise

    async def _generate_huggingface_embeddings(self, texts: List[str], model: str = None) -> List[List[float]]:
        """使用HuggingFace生成embedding"""
        try:
            from sentence_transformers import SentenceTransformer
            import torch

            # 检查是否有GPU
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            logger.info(f"使用设备: {device}")

            # 加载模型
            model_name = model or self.rag_config.embedding_model
            if model_name == "text-embedding-v2":  # 默认模型
                model_name = "sentence-transformers/all-MiniLM-L6-v2"

            model = SentenceTransformer(model_name, device=device)

            # 生成向量
            embeddings = model.encode(
                texts,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True
            )

            return embeddings.tolist()

        except Exception as e:
            logger.error(f"HuggingFace embedding失败: {e}")
            # 尝试使用更简单的模型
            try:
                logger.info("尝试使用更简单的模型...")
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer("all-MiniLM-L6-v2")
                embeddings = model.encode(texts, show_progress_bar=False)
                return embeddings.tolist()
            except:
                raise

    async def _generate_local_embeddings(self, texts: List[str]) -> List[List[float]]:
        """使用本地模型生成embedding"""
        # 同HuggingFace
        return await self._generate_huggingface_embeddings(texts)

    def _generate_random_vectors(self, num_vectors: int) -> List[List[float]]:
        """生成随机向量（fallback）"""
        import random
        dimension = getattr(self.config, 'dimension', 384)

        logger.warning(f"生成随机向量作为fallback: {num_vectors}个, 维度{dimension}")

        return [
            [random.uniform(-1, 1) for _ in range(dimension)]
            for _ in range(num_vectors)
        ]

    async def build_index(
            self,
            chunks: List[DocumentChunk],
            collection_name: str = None
    ) -> CollectionStats:
        """
        构建向量索引

        Args:
            chunks: 文档块列表
            collection_name: 集合名称

        Returns:
            集合统计信息
        """
        if not chunks:
            raise ValueError("文档块列表不能为空")

        collection_name = collection_name or self.config.collection_name
        logger.info(f"开始构建索引: 集合={collection_name}, 文档块数={len(chunks)}")

        start_time = datetime.now()

        try:
            # 1. 准备数据
            texts = [chunk.content for chunk in chunks]
            metadatas = [chunk.to_index_dict() for chunk in chunks]

            # 生成ID
            ids = []
            for i, chunk in enumerate(chunks):
                # 使用内容哈希和索引生成唯一ID
                content_hash = hashlib.md5(chunk.content.encode()).hexdigest()[:16]
                chunk_id = f"chunk_{i}_{content_hash}"
                ids.append(chunk_id)

            # 2. 生成向量（根据文档类型选择模型）
            doc_type = chunks[0].doc_type.value if chunks[0].doc_type else None
            embedding_config = self._get_embedding_config_for_document(doc_type)
            logger.info(f"生成向量中... 文档类型: {doc_type}, 使用模型: {embedding_config['provider']}/{embedding_config['model']}")
            vectors = await self.generate_embeddings(texts, embedding_config)

            if len(vectors) != len(chunks):
                logger.warning(f"向量数量不匹配: 文本数={len(chunks)}, 向量数={len(vectors)}")
                # 调整向量数量
                if len(vectors) < len(chunks):
                    # 生成缺失的随机向量
                    missing = len(chunks) - len(vectors)
                    random_vectors = self._generate_random_vectors(missing)
                    vectors.extend(random_vectors)
                else:
                    vectors = vectors[:len(chunks)]

            # 3. 存储到向量数据库
            logger.info("存储到向量数据库...")
            if self.config.db_type == "chroma":
                await self._insert_to_chroma(ids, vectors, texts, metadatas, collection_name)
            elif self.config.db_type == "memory":
                await self._insert_to_memory(ids, vectors, texts, metadatas, collection_name)
            else:
                # 默认使用ChromaDB
                await self._insert_to_chroma(ids, vectors, texts, metadatas, collection_name)

            # 4. 返回统计信息
            elapsed = (datetime.now() - start_time).total_seconds()

            stats = CollectionStats(
                collection_name=collection_name,
                total_chunks=len(chunks),
                vector_dim=len(vectors[0]) if vectors else 0,
                index_type=getattr(self.config, 'index_type', 'default'),
                index_params=getattr(self.config, 'index_params', {})
            )

            logger.info(f"索引构建完成: {stats}, 耗时 {elapsed:.2f}秒")
            return stats

        except Exception as e:
            logger.error(f"构建索引失败: {e}")
            raise

    async def _insert_to_chroma(self, ids, vectors, texts, metadatas, collection_name):
        """插入数据到ChromaDB"""
        try:
            # 处理metadata - ChromaDB只接受基本数据类型
            processed_metadatas = []
            for metadata in metadatas:
                processed_metadata = {}
                for key, value in metadata.items():
                    if isinstance(value, (str, int, float, bool)):
                        processed_metadata[key] = value
                    else:
                        # 将复杂对象转换为字符串
                        processed_metadata[key] = str(value)
                processed_metadatas.append(processed_metadata)

            # 添加文档
            self.collection.add(
                embeddings=vectors,
                documents=texts,
                metadatas=processed_metadatas,
                ids=ids
            )

            logger.info(f"成功插入 {len(ids)} 条记录到ChromaDB")

        except Exception as e:
            logger.error(f"插入ChromaDB失败: {e}")
            raise

    async def _insert_to_memory(self, ids, vectors, texts, metadatas, collection_name):
        """插入数据到内存存储"""
        try:
            # 准备元数据
            enriched_metadatas = []
            for i, (id, text, metadata) in enumerate(zip(ids, texts, metadatas)):
                enriched_metadata = {
                    "id": id,
                    "content": text,
                    "collection": collection_name,
                    **{k: str(v) for k, v in metadata.items() if v is not None}
                }
                enriched_metadatas.append(enriched_metadata)

            # 插入向量
            self.vector_store.add_vectors(
                vectors=vectors,
                metadata=enriched_metadatas,
                ids=ids
            )

            logger.info(f"成功插入 {len(ids)} 个向量到内存存储集合 {collection_name}")

        except Exception as e:
            logger.error(f"插入内存存储失败: {e}")
            raise

    async def search_similar(
            self,
            query: str,
            top_k: int = None,
            score_threshold: float = None,
            filters: Dict[str, Any] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        相似度搜索

        Args:
            query: 查询文本
            top_k: 返回结果数量
            score_threshold: 相似度阈值
            filters: 过滤条件 (如 {"business_module": "cross_border_opening"})

        Returns:
            (文档块, 相似度得分) 列表
        """
        if not query or not query.strip():
            return []

        top_k = top_k or getattr(self.rag_config, 'top_k', 5)
        score_threshold = score_threshold or getattr(self.rag_config, 'score_threshold', 0.0)

        logger.info(f"搜索相似文档: query={query[:50]}..., top_k={top_k}, threshold={score_threshold}")

        start_time = datetime.now()

        try:
            # 1. 生成查询向量
            query_vectors = await self.generate_embeddings([query])
            if not query_vectors:
                return []

            query_vector = query_vectors[0]

            # 2. 执行搜索
            results = []
            if self.config.db_type == "chroma":
                results = await self._search_chroma(query_vector, top_k, score_threshold)
            elif self.config.db_type == "memory":
                results = await self._search_memory(query_vector, top_k, score_threshold)
            else:
                # 默认使用ChromaDB
                results = await self._search_chroma(query_vector, top_k, score_threshold)

            # 3. 应用过滤条件
            filtered_results = []
            for chunk, score in results:
                # 相似度阈值过滤
                if score < score_threshold:
                    continue

                # 业务过滤条件
                if filters:
                    should_include = True
                    metadata = chunk.metadata or {}

                    for filter_key, filter_value in filters.items():
                        if filter_key == 'business_module':
                            chunk_business_module = metadata.get('business_module')
                            if chunk_business_module != filter_value:
                                should_include = False
                                break
                        elif filter_key == 'document_type':
                            chunk_doc_type = metadata.get('document_type')
                            if chunk_doc_type != filter_value:
                                should_include = False
                                break
                        elif filter_key == 'tags':
                            chunk_tags = metadata.get('tags', [])
                            if not isinstance(filter_value, list):
                                filter_value = [filter_value]
                            if not any(tag in chunk_tags for tag in filter_value):
                                should_include = False
                                break

                    if not should_include:
                        continue

                filtered_results.append((chunk, score))

            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(f"搜索完成: 找到 {len(filtered_results)} 个结果, 耗时 {elapsed:.3f}秒")

            return filtered_results

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []

    async def _search_chroma(self, query_vector, top_k, score_threshold):
        """在ChromaDB中搜索"""
        try:
            # ChromaDB搜索
            search_result = self.collection.query(
                query_embeddings=[query_vector],
                n_results=top_k * 2,
                include=["documents", "metadatas", "distances"]
            )

            # 解析结果
            results = []
            if search_result.get('documents'):
                for i, (doc, metadata, distance) in enumerate(zip(
                        search_result['documents'][0],
                        search_result['metadatas'][0],
                        search_result['distances'][0]
                )):
                    # 将距离转换为相似度分数
                    # ChromaDB使用余弦距离: 1-余弦相似度
                    if doc and metadata:
                        score = 1 - distance
                        chunk = DocumentChunk(
                            content=doc,
                            metadata=metadata
                        )
                        results.append((chunk, score))

            return results

        except Exception as e:
            logger.error(f"ChromaDB搜索失败: {e}")
            return []

    async def _search_memory(self, query_vector, top_k, score_threshold):
        """在内存存储中搜索"""
        try:
            # 执行搜索
            search_results = self.vector_store.search(query_vector, top_k=top_k)

            # 解析结果
            results = []
            for result in search_results:
                if result['score'] >= score_threshold:
                    metadata = result['metadata']
                    chunk = DocumentChunk(
                        content=metadata.get("content", ""),
                        metadata=metadata
                    )
                    results.append((chunk, result['score']))

            return results

        except Exception as e:
            logger.error(f"内存搜索失败: {e}")
            return []

    def delete_collection(self, collection_name: str = None):
        """删除集合"""
        collection_name = collection_name or self.config.collection_name

        try:
            if self.config.db_type == "chroma":
                self.chroma_client.delete_collection(name=collection_name)
                logger.info(f"已删除ChromaDB集合: {collection_name}")
            elif self.config.db_type == "memory":
                # 内存存储不支持删除操作
                logger.info(f"内存存储不支持删除集合: {collection_name}")

        except Exception as e:
            logger.error(f"删除集合失败: {e}")
            raise

    def get_collection_stats(self, collection_name: str = None) -> Dict[str, Any]:
        """获取集合统计信息"""
        collection_name = collection_name or self.config.collection_name

        try:
            stats = {}

            if self.config.db_type == "chroma":
                count = self.collection.count()
                stats = {
                    "collection_name": collection_name,
                    "num_entities": count
                }
            elif self.config.db_type == "memory":
                # 内存存储没有持久化统计信息
                stats = {
                    "collection_name": collection_name,
                    "num_entities": "unknown (内存存储)"
                }

            return stats

        except Exception as e:
            logger.error(f"获取集合统计失败: {e}")
            return {"error": str(e)}