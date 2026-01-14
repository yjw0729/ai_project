# 向量数据库配置

## 📋 概述

本目录包含向量数据库相关的所有配置文件，用于配置RAG系统的向量存储后端。

## 📁 文件说明

- **`vector_db.json`** - 向量数据库连接和参数配置

## 🔧 配置说明

### 支持的数据库类型

#### 1. ChromaDB (`chroma`) - 推荐 ⭐⭐⭐⭐⭐
**优点**: 简单易用，持久化存储，支持本地和服务器模式，完全免费
```json
{
  "db_type": "chroma",
  "host": "localhost",
  "port": 8000,
  "collection_name": "test_agent_knowledge"
}
```

#### 2. Pinecone (`pinecone`) - 云服务 ⭐⭐⭐⭐
**优点**: 托管服务，高性能，全球CDN
**免费层**: 每月1GB存储，100万向量读取
```json
{
  "db_type": "pinecone",
  "collection_name": "your-index-name",
  "api_key": "your-pinecone-api-key"
}
```

#### 3. Qdrant (`qdrant`) - 自托管 ⭐⭐⭐⭐
**优点**: 高性能，功能丰富，完全免费
```json
{
  "db_type": "qdrant",
  "host": "localhost",
  "port": 6333,
  "collection_name": "test_agent_knowledge"
}
```

#### 4. Google Cloud Vector Search (`google_cloud`)
**优点**: 企业级，集成Google生态
**缺点**: 配置复杂，需要付费
```json
{
  "db_type": "google_cloud",
  "project_id": "your-project-id",
  "region": "us-central1",
  "instance_id": "test-agent-vector-db"
}
```

#### 5. 内存存储 (`memory`) - 仅用于测试
```json
{
  "db_type": "memory",
  "collection_name": "test_agent_knowledge"
}
```

### 配置示例

```json
{
  "db_type": "google_cloud",
  "collection_name": "test_agent_knowledge",
  "dimension": 768,
  "metric_type": "COSINE",
  "project_id": "your-project-id",
  "region": "us-central1",
  "instance_id": "test-agent-vector-db",
  "api_key": "your-api-key"
}
```

## 📝 环境变量

```bash
# 数据库类型
VECTOR_DB_TYPE=google_cloud

# 连接信息
VECTOR_DB_HOST=localhost
VECTOR_DB_PORT=19530
VECTOR_DB_COLLECTION=test_agent_knowledge

# 认证信息
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_API_KEY=your-api-key
```

## 🚀 快速开始 - ChromaDB

### 1. 安装ChromaDB
```bash
pip install chromadb
```

### 2. 启动ChromaDB服务器
```bash
# 在新终端运行
chroma run --host 0.0.0.0 --port 8000
```

### 3. 配置应用
```json
// vector_db.json
{
  "db_type": "chroma",
  "host": "localhost",
  "port": 8000,
  "collection_name": "test_agent_knowledge"
}
```

### 4. 测试运行
```bash
python common/rag/test.py
```

## 🔄 切换数据库

要切换向量数据库，只需修改 `db_type` 字段和相应配置，无需修改代码：

```json
// 切换到Qdrant
{
  "db_type": "qdrant",
  "host": "localhost",
  "port": 6333,
  "collection_name": "test_agent_knowledge"
}
```

## 📊 性能对比

| 数据库 | 安装难度 | 维护成本 | 性能 | 免费额度 | 推荐指数 |
|--------|----------|----------|------|----------|----------|
| ChromaDB | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | 完全免费 | ⭐⭐⭐⭐⭐ |
| Pinecone | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | 每月1GB | ⭐⭐⭐⭐ |
| Qdrant | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | 完全免费 | ⭐⭐⭐⭐ |
| Google Cloud | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 付费 | ⭐⭐⭐ |

## 💡 推荐选择

- **开发/测试**: ChromaDB（最简单）
- **生产/小规模**: Pinecone（托管服务）
- **生产/大规模**: Qdrant或Google Cloud（自托管/云服务）

