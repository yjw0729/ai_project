import json
import os
from typing import Dict, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RAGConfig:
    '''RAG的配置类'''
    top_k: int = 5
    score_threshold: float = 0.7
    max_context_length: int = 4000
    overlap_size: int = 200
    chunk_size:int = 1000
    chunk_overlap: int = 200
    embedding_model: str = "text-embedding-v2"
    embedding_provider: str = "tongyi"
    llm_model:str = "qwen-turbo"
    llm_provider: str = "tongyi"
    temperature: float = 0.7
    max_tokens: int = 2000
    enable_cache: bool = True
    cache_ttl: int = 3600
    enable_metrics: bool = False
    metrics_port: int = 9090


@dataclass
class VectorDBConfig:
    '''向量数据库配置类'''
    db_type: str = "google_cloud"
    collection_name: str = "test_agent_knowledge"
    dimension: int = 768
    metric_type: str = "COSINE"
    index_type: str = "IVF_FLAT"
    host: str = ""
    port: int = 0
    project_id: str = None
    region: str = "us-central1"
    instance_id: str = "test-agent-vector-db"
    database_id: str = "test_agent"
    index_params: Dict[str, Any] = None
    search_params: Dict[str, Any] = None
    max_connections: int = 10
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600
    enable_compression: bool = False
    enable_cache: bool = True
    cache_size: int = 1000
    enable_monitoring: bool = False
    fallback_to_memory: bool = True


class ConfigManager:
    def __init__(self, config_dir: str = "app/config"):
        self.config_dir = Path(config_dir) if isinstance(config_dir, str) else config_dir
        self.rag_config = None
        self.vector_db_config = None
        self.api_key = None  # 从ai_config.json加载

    def load_configs(self):
        '''加载配置'''
        # 先加载ai_config.json获取api_key
        ai_config_path = self.config_dir / "app" / "ai_config.json"
        if ai_config_path.exists():
            with open(ai_config_path, 'r', encoding='utf-8') as f:
                ai_data = json.load(f)
                self.api_key = ai_data.get('api_key')
        rag_config_path = self.config_dir / "rag" / "rag.json"
        if rag_config_path.exists():
            with open(rag_config_path, 'r', encoding='utf-8') as f:
                rag_data = json.load(f)
            self.rag_config = RAGConfig(**rag_data)
        else:
            self.rag_config = RAGConfig()

        #加载向量数据库配置
        vector_config_path = self.config_dir / "vector_db" / "vector_db.json"
        if vector_config_path.exists():
            with open(vector_config_path, 'r', encoding='utf-8') as f:
                vector_data = json.load(f)
            self.vector_db_config = VectorDBConfig(**vector_data)
        else:
            self.vector_db_config = VectorDBConfig()

        return self

    def get_rag_config(self) -> RAGConfig:
        '''获取RAG配置'''
        if not self.rag_config:
            self.load_configs()
        return self.rag_config

    def get_vector_db_config(self):
        if not self.vector_db_config:
            self.load_configs()
        return self.vector_db_config
