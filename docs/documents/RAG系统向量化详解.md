# RAG系统向量化存储和查询详解

## 📖 引言：什么是RAG和向量化？

### RAG（Retrieval-Augmented Generation）是什么？
RAG是一种AI技术，通过检索相关文档来增强大语言模型的回答质量。它不是让AI凭空生成答案，而是先从知识库中找到相关信息，再基于这些信息生成回答。

### 向量化是什么？
向量化是将文本转换为数值向量（数组）的过程。相似的内容会被转换为相似的向量，这样可以通过数学计算（如余弦相似度）来衡量文本的相似性。

## 🏗️ 系统架构总览

```
RAG系统架构：
├── 数据采集层 (DataCollector)
├── 文档处理层 (DocumentProcessor)
├── 向量化层 (VectorIndexer)
├── 向量存储层 (VectorStore)
└── 查询处理层 (SearchEngine)
```

## 📥 详细的存储流程

### 阶段1：数据采集 (DataCollector.collect_from_multiple_sources)

**位置**: `common/rag/core/data_collector.py`

**功能**: 从各种数据源采集原始文档

**输入参数**:
```python
source_configs: List[Dict[str, Any]] = [
    {
        "source_type": "file",           # 数据源类型：file/database/api等
        "paths": ["/path/to/document.pdf"], # 文件路径列表
        "extensions": [".pdf"],         # 文件扩展名
        "recursive": False,             # 是否递归搜索子目录
        "metadata": {                   # 元数据
            "document_id": "doc_001",
            "document_title": "用户手册",
            "document_type": "product_requirement",
            "tags": ["manual", "user"],
            "upload_time": "2024-01-01T10:00:00",
            "file_size": 1024000
        }
    }
]
```

**输出**: `List[Document]` - 标准化的文档对象列表

**工作流程**:
1. **文件连接器** (`FileConnector`): 读取本地文件系统
2. **数据库连接器** (`DatabaseConnector`): 从数据库查询数据
3. **API连接器** (`APIConnector`): 调用外部API获取数据
4. **统一格式化**: 将各种数据源转换为标准 `Document` 对象

**核心代码**:
```python
# 采集结果示例
documents = [
    Document(
        id="doc_001",
        content="这是文档的完整文本内容...",
        source_type="file",
        source_uri="/uploads/manual.pdf",
        doc_type=DocumentType.PRODUCT_REQ,
        metadata={"title": "用户手册", "size": 1024000}
    )
]
```

---

### 阶段2：文档处理 (DocumentProcessor.process_documents)

**位置**: `common/rag/core/document_processor.py`

**功能**: 对原始文档进行清洗、分块和预处理

**输入参数**:
```python
documents: List[Document]          # 从数据采集阶段获得的文档列表
chunking_strategy: str = "recursive"  # 分块策略：fixed/semantic/recursive
```

**输出**: `List[DocumentChunk]` - 分块后的文档片段列表

#### 2.1 文本清洗 (_clean_text)

**输入**: 原始文本字符串
**输出**: 清洗后的文本字符串

**清洗步骤**:
1. **编码统一**: 确保UTF-8编码
2. **换行符统一**: 统一为 `\n`
3. **空白字符处理**: 合并多个空白为单个空格
4. **噪音过滤**: 去除不可见字符、多余标点
5. **内容过滤**: 删除纯数字行、过短的行

#### 2.2 智能分块 (_chunk_document)

**分块策略**:

**A. 递归字符分块 (RecursiveCharacterTextSplitter)**
```
输入文本: "第一章 引言\n\n这是引言内容。第二章 功能介绍\n\n这是功能介绍..."
分隔符优先级: ["\n\n", "\n", ".", "!", "?", ";", ":", "。", "！", "？", "；", "："]
块大小: 1000字符
重叠: 200字符

输出块:
块1: "第一章 引言\n\n这是引言内容。"
块2: "第二章 功能介绍\n\n这是功能介绍..."
```

**B. 语义分块 (Semantic Chunking)**
- 使用句子变换器计算句子相似度
- 在语义边界处分割文本
- 保持语义完整性

**C. 固定长度分块**
- 简单地将文本按固定字符数分割
- 效率高但可能割裂语义

**输出示例**:
```python
chunks = [
    DocumentChunk(
        chunk_id="chunk_0_doc001",
        parent_doc_id="doc001",
        content="第一章 引言\n\n这是引言内容。",
        chunk_index=0,
        start_pos=0,
        end_pos=150,
        doc_type=DocumentType.PRODUCT_REQ
    ),
    DocumentChunk(
        chunk_id="chunk_1_doc001",
        parent_doc_id="doc001",
        content="第二章 功能介绍\n\n这是功能介绍...",
        chunk_index=1,
        start_pos=130,  # 注意重叠部分
        end_pos=280
    )
]
```

#### 2.3 去重和过滤

**去重逻辑**:
- 计算内容哈希值
- 去除完全重复的块
- 合并高度相似的块

**过滤条件**:
- 最小块长度: 50字符
- 最大块长度: 2000字符
- 去除纯标点或数字的块

---

### 阶段3：向量化处理 (VectorIndexer.generate_embeddings)

**位置**: `common/rag/core/vector_indexer.py`

**功能**: 将文本块转换为高维向量

**输入参数**:
```python
texts: List[str] = ["第一章 引言\n\n这是引言内容。", "第二章 功能介绍..."]
embedding_config: Dict[str, Any] = {
    "provider": "tongyi",                    # 提供商：tongyi/openai/huggingface
    "model": "text-embedding-v2",           # 模型名称
    "dimension": 1536                       # 向量维度
}
```

**输出**: `List[List[float]]` - 向量列表

#### 3.1 模型选择逻辑 (_get_embedding_config_for_document)

**根据文档类型自动选择模型**:
```python
def _get_embedding_config_for_document(self, doc_type: str) -> Dict[str, Any]:
    # 优先级：专用模型 > 默认模型
    if doc_type == "api_documentation":
        return {"provider": "tongyi", "model": "text-embedding-v2", "dimension": 1536}
    elif doc_type == "product_requirement":
        return {"provider": "tongyi", "model": "sentence-transformers/...", "dimension": 768}
    else:
        return self.embedding_models_config.get("default")
```

#### 3.2 向量生成实现

**通义千问向量化 (_generate_tongyi_embeddings)**:
```python
# API调用示例
response = TextEmbedding.call(
    model="text-embedding-v2",           # 模型名称
    input=["文本内容1", "文本内容2"]     # 批量处理
)

# 返回格式
{
    "status_code": 200,
    "output": {
        "embeddings": [
            {"embedding": [0.1, 0.2, 0.3, ...]},  # 1536维向量
            {"embedding": [0.4, 0.5, 0.6, ...]}
        ]
    }
}
```

**输出示例**:
```python
vectors = [
    [0.1234, 0.5678, 0.9012, ..., 0.3456],  # 1536个浮点数
    [0.2345, 0.6789, 0.0123, ..., 0.4567]   # 第二个文本的向量
]
```

---

### 阶段4：向量存储 (VectorIndexer.build_index)

**位置**: `common/rag/core/vector_indexer.py`

**功能**: 将向量和元数据存储到向量数据库

**输入参数**:
```python
chunks: List[DocumentChunk]     # 分块后的文档片段
collection_name: str = "test_agent_knowledge"  # 集合名称
```

**输出**: `CollectionStats` - 集合统计信息

#### 4.1 数据准备

```python
# 准备存储数据
texts = [chunk.content for chunk in chunks]        # 原始文本
metadatas = [chunk.to_index_dict() for chunk in chunks]  # 元数据
vectors = await self.generate_embeddings(texts)    # 生成向量

# 生成唯一ID
ids = []
for i, chunk in enumerate(chunks):
    content_hash = hashlib.md5(chunk.content.encode()).hexdigest()[:16]
    chunk_id = f"chunk_{i}_{content_hash}"
    ids.append(chunk_id)
```

#### 4.2 存储到向量数据库

**以ChromaDB为例 (_store_chroma)**:
```python
# 添加到Chroma集合
self.collection.add(
    ids=ids,                    # 唯一标识符列表
    embeddings=vectors,         # 向量列表
    metadatas=metadatas,        # 元数据列表
    documents=texts             # 原始文本列表
)
```

**存储的数据结构**:
```
ChromaDB存储格式:
├── id: "chunk_0_abc123def456"
├── embedding: [0.123, 0.456, 0.789, ...]  # 向量
├── metadata: {
│   ├── "chunk_id": "chunk_0_abc123def456"
│   ├── "parent_doc_id": "doc001"
│   ├── "chunk_index": 0
│   ├── "doc_type": "api_documentation"
│   └── "content": "文本内容..."
│   }
└── document: "第一章 引言\n\n这是引言内容。"  # 原始文本
```

## 🔍 详细的查询流程

### 阶段1：查询预处理

**位置**: `common/rag/services/rag_services.py` - `query` 方法

**输入参数**:
```python
question: str = "如何使用登录功能？"        # 用户查询
collection_name: str = "documents"        # 集合名称（可选）
top_k: int = 5                           # 返回结果数量
filters: Dict = {}                       # 过滤条件（可选）
```

### 阶段2：生成查询向量 (VectorIndexer.generate_embeddings)

**与存储时使用相同的方法**:
```python
# 将查询文本转换为向量
query_vectors = await self.generate_embeddings([question])
query_vector = query_vectors[0]  # 取第一个向量
```

### 阶段3：相似度搜索 (VectorIndexer.search_similar)

**位置**: `common/rag/core/vector_indexer.py`

**核心算法 - 余弦相似度**:
```
余弦相似度公式: similarity = (A·B) / (|A|×|B|)

向量A: [0.1, 0.2, 0.3]     查询向量
向量B: [0.1, 0.2, 0.4]     文档向量

相似度 = (0.1*0.1 + 0.2*0.2 + 0.3*0.4) / (sqrt(0.14) * sqrt(0.21))
        = 0.23 / (0.374 * 0.458) ≈ 0.85 (85%相似)
```

#### 3.1 ChromaDB搜索实现 (_search_chroma)

```python
# 执行相似度搜索
results = self.collection.query(
    query_embeddings=[query_vector],     # 查询向量
    n_results=top_k,                     # 返回数量
    where={"doc_type": "api_documentation"}, # 元数据过滤
    include=["documents", "metadatas", "distances"] # 返回内容
)

# 返回格式
{
    "ids": [["chunk_0_abc", "chunk_1_def"]],
    "documents": [["相关文档内容1", "相关文档内容2"]],
    "metadatas": [[{"chunk_id": "chunk_0_abc", ...}, {...}]],
    "distances": [[0.15, 0.23]]  # 距离（越小越相似）
}
```

#### 3.2 结果处理

```python
# 转换为标准格式
search_results = []
for i, (doc_id, distance, metadata) in enumerate(zip(ids, distances, metadatas)):
    if distance <= (1.0 - score_threshold):  # 转换为相似度
        similarity_score = 1.0 - distance
        chunk = DocumentChunk.from_metadata(metadata)
        search_results.append((chunk, similarity_score))
```

### 阶段4：结果排序和过滤

**排序**: 按相似度得分降序排列
**过滤**: 去除相似度低于阈值的结果
**去重**: 去除重复或高度相似的结果

### 阶段5：生成回答

**位置**: `common/rag/services/rag_services.py` - LLM生成回答

```python
# 构建上下文
context = "\n\n".join([chunk.content for chunk, score in search_results])

# 构建提示词
prompt = f"""
基于以下参考资料回答问题：

参考资料：
{context}

问题：{question}

请提供准确、详细的回答：
"""

# 调用LLM生成回答
response = await self.llm_client.call(
    model=self.rag_config.llm_model,
    prompt=prompt,
    temperature=0.7,
    max_tokens=2000
)
```

## 📊 数据流向图

```
存储流程：
原始文档 → 数据采集 → 文档清洗 → 智能分块 → 向量化 → 向量存储
    ↓         ↓         ↓         ↓         ↓         ↓
  PDF/Word   Document   纯文本     Chunks   Vectors   ChromaDB

查询流程：
用户问题 → 查询向量化 → 相似度搜索 → 结果排序 → 上下文构建 → LLM生成
    ↓         ↓           ↓           ↓           ↓         ↓
  "问题"    QueryVector   候选文档     Top-K     Context    回答
```

## 🔧 核心配置参数

### 向量化配置 (app/config/rag/rag.json)
```json
{
  "embedding_provider": "tongyi",
  "embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
  "chunk_size": 1000,
  "chunk_overlap": 200,
  "top_k": 5,
  "score_threshold": 0.7
}
```

### 向量数据库配置 (app/config/vector_db/vector_db.json)
```json
{
  "db_type": "chroma",
  "collection_name": "test_agent_knowledge",
  "dimension": 768,
  "metric_type": "COSINE",
  "host": "localhost",
  "port": 8000
}
```

## 🎯 关键概念解释

### 1. 向量维度 (Vector Dimension)
- 表示向量的长度，如768维、1536维
- 维度越高，语义表达能力越强，但计算成本也越高
- 不同模型有固定的输出维度

### 2. 相似度得分 (Similarity Score)
- 范围: 0.0 ~ 1.0 (1.0表示完全相同)
- 余弦相似度: 两个向量夹角的余弦值
- 距离度量: 欧几里得距离、曼哈顿距离等

### 3. 分块重叠 (Chunk Overlap)
- 相邻块之间的重叠字符数
- 防止重要信息被分割在块边界
- 示例: chunk_size=1000, overlap=200

### 4. 集合 (Collection)
- 向量数据库中的"表"概念
- 可以按主题或项目分组存储向量
- 支持独立的搜索和索引

## 🚨 常见问题

### Q: 为什么需要分块？
A: 向量数据库对输入文本长度有限制，分块可以将长文档分割成可管理的片段，同时保持语义连贯性。

### Q: 向量维度怎么选择？
A: 维度越高语义表达越准确，但计算成本也越高。推荐768-1536维作为平衡点。

### Q: 相似度阈值怎么设置？
A: 根据应用场景设置，0.7-0.8适用于一般检索，0.9以上适用于精确匹配。

### Q: 为什么使用余弦相似度？
A: 余弦相似度不受向量长度影响，只关注方向差异，适合文本语义相似度计算。

## 📈 性能优化建议

1. **批量处理**: 向量化时批量处理多个文本，提高效率
2. **索引优化**: 为向量数据库创建合适的索引结构
3. **缓存机制**: 缓存常用查询结果和向量
4. **异步处理**: 使用异步IO提高并发处理能力
5. **分层检索**: 先粗粒度检索，再细粒度重排序

这篇详细讲解应该能帮你完全理解RAG系统的向量化存储和查询流程了！如果有任何疑问，随时问我。🤔



