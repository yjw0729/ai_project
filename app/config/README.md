# 应用配置管理

## 📋 概述

本目录统一管理整个应用的配置文件，采用**功能分类**的设计原则，将不同类型的配置按功能分组管理。

## 📁 目录结构

```
app/config/
├── __init__.py           # 配置包导出
├── vector_db/            # 🗄️ 向量数据库配置
│   └── vector_db.json
├── rag/                  # 🤖 RAG业务配置
│   └── rag.json
├── app/                  # ⚙️ 应用相关配置
│   ├── ai_config.json
│   ├── db_config.json
│   ├── yjw_ai_config.json
│   └── application.xml
├── docker/               # 🐳 Docker配置
│   └── docker-compose.yml
├── logging/              # 📝 日志配置
│   └── eqlog.xml
└── README.md             # 本文档
```

## 🔧 配置类型

### 1. 向量数据库配置 (`vector_db.json`)

**职责范围**：向量数据库连接、索引和性能配置

```json
{
  "db_type": "google_cloud|milvus",
  "collection_name": "test_agent_knowledge",
  "dimension": 768,
  "metric_type": "COSINE",
  "host": "localhost",
  "port": 19530,
  "database_name": "",
  "username": null,
  "password": null,
  "api_key": null,
  "project_id": null,
  "region": "us-central1",
  "instance_id": "test-agent-vector-db",
  "database_id": "test_agent",
  "index_params": {},
  "search_params": {},
  "max_connections": 10,
  "timeout": 30,
  "retry_attempts": 3,
  "retry_delay": 1.0,
  "pool_size": 5,
  "max_overflow": 10,
  "pool_timeout": 30,
  "pool_recycle": 3600,
  "enable_compression": false,
  "enable_cache": true,
  "cache_size": 1000,
  "enable_monitoring": false
}
```

### 2. RAG业务配置 (`rag.json`)

**职责范围**：检索参数、AI模型、文本处理配置

```json
{
  "top_k": 5,
  "score_threshold": 0.7,
  "max_context_length": 4000,
  "overlap_size": 200,
  "chunk_size": 1000,
  "chunk_overlap": 200,
  "embedding_model": "text-embedding-ada-002",
  "embedding_provider": "openai",
  "llm_model": "gpt-3.5-turbo",
  "llm_provider": "openai",
  "temperature": 0.7,
  "max_tokens": 2000,
  "enable_cache": true,
  "cache_ttl": 3600,
  "enable_metrics": false,
  "metrics_port": 9090
}
```

## 💻 使用方式

### 编程式使用

```python
# 导入配置
from app.config import get_vector_db_config, get_rag_config, get_unified_config

# 获取向量数据库配置
vector_config = get_vector_db_config()

# 获取RAG配置
rag_config = get_rag_config()

# 获取统一配置
unified_config = get_unified_config()
```

### 环境变量配置

```bash
# 向量数据库配置
export VECTOR_DB_TYPE=milvus
export VECTOR_DB_HOST=localhost
export VECTOR_DB_PORT=19530

# RAG配置
export RAG_TOP_K=5
export RAG_SCORE_THRESHOLD=0.7
export EMBEDDING_MODEL=text-embedding-ada-002
```

## 🔄 配置加载优先级

1. **环境变量** (最高优先级)
2. **JSON配置文件**
3. **默认值** (最低优先级)

## 🛠️ 配置管理

### 创建默认配置

```python
from app.config import create_default_vector_db_config, create_default_rag_config

# 创建默认向量数据库配置
vector_config_path = create_default_vector_db_config()

# 创建默认RAG配置
rag_config_path = create_default_rag_config()
```

### 修改配置

```python
from app.config import get_vector_db_config, VectorDBConfigManager

# 加载配置
config = get_vector_db_config()

# 修改配置
config.collection_name = "new_collection"
config.dimension = 1024

# 保存配置
manager = VectorDBConfigManager()
manager.save_to_file(config)
```

## ✅ 配置验证

```python
from common.rag.validators import validate_config

# 验证配置
result = validate_config(unified_config)
if not result.is_valid:
    print("配置错误:", result.errors)
else:
    print("配置验证通过 ✓")
```

## 🔒 安全注意事项

1. **敏感信息**：API密钥、密码等敏感信息应使用环境变量
2. **权限控制**：配置文件应有适当的文件权限
3. **版本控制**：敏感配置不应提交到版本控制系统

## 📝 更新日志

- **v1.0.0**: 初始版本，支持Google Cloud和Milvus配置分离
