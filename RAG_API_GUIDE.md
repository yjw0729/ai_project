# RAG文档处理系统 - API使用指南

## 📋 概述

本系统提供完整的RAG（检索增强生成）文档处理功能，支持Word文档的智能上传、处理和查询。

## 🚀 快速开始

### 1. 启动服务

```bash
# 启动Flask应用
python app/application.py
```

服务将在 `http://localhost:8080` 启动（根据配置调整端口）

### 2. 健康检查

```bash
curl http://localhost:8080/rag_service/health
```

### 3. 上传文档

```bash
# 使用curl上传Word文档
curl -X POST http://localhost:8080/rag_service/upload \
  -F "file=@your_document.docx" \
  -F "document_title=产品设计文档" \
  -F "document_type=product_design" \
  -F "collection_name=product_docs"
```

### 4. 查询文档

```bash
# 查询相关内容
curl -X POST http://localhost:8080/rag_service/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "产品主要功能是什么？",
    "collection_name": "product_docs",
    "top_k": 3
  }'
```

## 📤 API接口详解

### 文档上传接口

**POST** `/rag_service/upload`

**请求参数（multipart/form-data）：**
- `file` (必填): Word文档文件 (.docx, .doc)
- `collection_name` (可选): 集合名称，默认 "documents"
- `document_title` (可选): 文档标题
- `document_type` (可选): 文档类型
  - `product_design`: 产品设计文档
  - `api_doc`: API文档
  - `user_manual`: 用户手册
  - `other`: 其他
- `tags` (可选): 标签数组，JSON字符串格式

**响应示例：**
```json
{
  "code": 200,
  "message": "文档上传并处理成功",
  "data": {
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "collection_name": "product_docs",
    "status": "completed",
    "chunks_count": 15,
    "document_title": "智能测试管理系统设计文档",
    "document_type": "product_design",
    "tags": ["产品设计", "重要文档"]
  }
}
```

### 文档查询接口

**POST** `/rag_service/query`

**请求参数（JSON）：**
```json
{
  "query": "查询问题",
  "collection_name": "product_docs",
  "top_k": 5,
  "filters": {
    "document_type": "product_design",
    "tags": ["重要"]
  }
}
```

**响应示例：**
```json
{
  "code": 200,
  "message": "查询成功",
  "data": {
    "query": "产品主要功能是什么？",
    "answer": "根据文档内容，这个产品的主要功能包括：...",
    "sources": [
      {
        "content": "相关内容片段...",
        "score": 0.87,
        "source": "智能测试管理系统设计文档",
        "metadata": {
          "section_title": "产品概述",
          "document_type": "product_design"
        }
      }
    ],
    "retrieved_count": 3,
    "elapsed_seconds": 1.2
  }
}
```

### 集合管理接口

#### 获取所有集合
**GET** `/rag_service/collections`

#### 获取集合详情
**GET** `/rag_service/collection/{collection_name}`

#### 删除集合
**DELETE** `/rag_service/collection/{collection_name}`

## 📄 Word文档处理策略

### 智能分割算法

系统采用多层次的文档分割策略：

#### 1. 章节识别
- **标题模式识别**：
  - Markdown风格：`# ## ###`
  - 数字编号：`1. 1.1 1.1.1`
  - 中文章节：`第一章 第一节`
  - 字母编号：`A. a. (1)`

- **产品文档专用模式**：
  - 产品概述、功能介绍
  - 技术架构、系统架构
  - 数据库设计、API设计
  - 部署方案、使用说明

#### 2. 内容分割
- **短章节**：直接作为一个块
- **长章节**：按段落智能分割
  - 最大块大小：1500字符
  - 重叠区域：200字符
  - 智能断点：句号、段落边界

#### 3. 元数据增强
每个文档块包含丰富元数据：
```json
{
  "document_id": "uuid",
  "document_title": "文档标题",
  "document_type": "product_design",
  "section_title": "章节标题",
  "section_level": 2,
  "chunk_type": "section",
  "chunk_index": 0,
  "tags": ["标签1", "标签2"]
}
```

## 🔍 向量化策略

### 支持的Embedding方式

#### 1. 本地Embedding（推荐）
```json
{
  "embedding_provider": "local",
  "embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
}
```

**优势**：
- 无需API密钥
- 支持中文
- 完全本地化
- 隐私保护

#### 2. 通义千问Embedding
```json
{
  "embedding_provider": "tongyi",
  "embedding_model": "text-embedding-v2"
}
```

#### 3. OpenAI Embedding
```json
{
  "embedding_provider": "openai",
  "embedding_model": "text-embedding-ada-002"
}
```

### 向量数据库

#### ChromaDB（推荐）
- **持久化**：数据保存到本地 `./chroma_data/`
- **性能**：轻量级，适合中小型应用
- **部署**：支持单机和分布式

#### 其他选项
- **Pinecone**: 云端托管，适合生产环境
- **Qdrant**: 自托管，高性能
- **Milvus**: 企业级，功能丰富

## 🎯 查询策略

### 语义检索流程

```
用户查询 → 向量化 → 相似度计算 → 相关文档排序 → 生成回答
     ↓         ↓           ↓             ↓            ↓
  "问题"   Embedding    余弦相似度     Top-K        LLM
```

### 检索优化

#### 1. 相关性过滤
- **相似度阈值**：只返回相关性>0.7的结果
- **Top-K选择**：返回最相关的K个结果

#### 2. 上下文组装
- **智能排序**：按相关性分数排序
- **内容截断**：避免上下文过长
- **来源标注**：标明信息来源

#### 3. 回答生成
- **上下文注入**：将检索结果作为上下文
- **指令优化**：引导模型基于文档回答
- **引用标注**：在回答中引用来源

## 🛠️ 开发和测试

### 运行测试脚本

```bash
# 运行API功能测试
python test_rag_api.py
```

### 查看日志

```bash
# 查看应用日志
tail -f logs/app_flask.log
```

### 性能监控

```bash
# 健康检查
curl http://localhost:8080/rag_service/health
```

## 📊 性能参数

### 处理能力
- **文档大小**：最大50MB
- **并发处理**：支持多文档同时上传
- **响应时间**：查询<2秒，上传<30秒（视文档大小）

### 存储效率
- **向量维度**：768维（可配置）
- **压缩率**：文本压缩至向量，节省90%+存储空间
- **检索速度**：毫秒级相似度计算

## 🔧 配置说明

### 核心配置文件

#### 1. 向量数据库配置 (`app/config/vector_db/vector_db.json`)
```json
{
  "db_type": "chroma",
  "host": "localhost",
  "port": 8000,
  "collection_name": "documents"
}
```

#### 2. RAG配置 (`app/config/rag/rag.json`)
```json
{
  "embedding_provider": "local",
  "embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
  "llm_provider": "tongyi",
  "chunk_size": 1000,
  "chunk_overlap": 200
}
```

## 🚨 故障排除

### 常见问题

#### 1. 文档上传失败
- 检查文件格式（支持.docx, .doc）
- 检查文件大小（最大50MB）
- 查看Flask日志

#### 2. 查询无结果
- 检查embedding模型是否正确配置
- 确认文档已成功向量化
- 查看查询日志

#### 3. 服务启动失败
- 检查端口是否被占用
- 确认依赖包已安装
- 查看配置文件语法

### 调试模式

```bash
# 启用调试模式
export FLASK_DEBUG=1
python app/application.py
```

## 📈 扩展指南

### 添加新文档类型
1. 在 `WordDocumentProcessor` 中添加新的标题识别模式
2. 扩展 `DocumentType` 枚举
3. 更新文件解析器

### 自定义分割策略
1. 修改 `WordDocumentProcessor._intelligent_chunk_document()`
2. 调整 `chunk_size` 和 `chunk_overlap` 参数
3. 添加领域特定的分割规则

### 集成其他向量数据库
1. 在 `VectorIndexer` 中添加新的初始化方法
2. 实现对应的插入和搜索方法
3. 更新配置文件

---

## 🎉 总结

这个RAG系统提供了完整的文档处理解决方案：

- ✅ **智能文档处理**：自动识别章节结构，智能分割内容
- ✅ **多格式支持**：专注于Word文档的专业处理
- ✅ **高效检索**：基于语义相似度的快速搜索
- ✅ **可扩展架构**：支持多种向量数据库和Embedding模型
- ✅ **生产就绪**：包含完整的API、健康检查和监控

开始使用：上传你的第一个Word文档，体验AI驱动的文档问答系统！🚀
