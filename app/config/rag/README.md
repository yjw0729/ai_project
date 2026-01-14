# RAG业务配置

## 📋 概述

本目录包含RAG（Retrieval-Augmented Generation）系统的业务逻辑配置文件，用于配置检索参数、AI模型、文本处理等。

## 📁 文件说明

- **`rag.json`** - RAG系统参数配置

## 🔧 配置说明

### 检索配置

```json
{
  "top_k": 5,                    // 返回最相似的结果数量
  "score_threshold": 0.7,        // 相似度阈值
  "max_context_length": 4000,    // 最大上下文长度
  "overlap_size": 200            // 上下文重叠大小
}
```

### 文本处理配置

```json
{
  "chunk_size": 1000,            // 文本分块大小
  "chunk_overlap": 200,          // 分块重叠大小
  "embedding_model": "text-embedding-ada-002",
  "embedding_provider": "openai"
}
```

### AI模型配置

```json
{
  "llm_model": "gpt-3.5-turbo",
  "llm_provider": "openai",
  "temperature": 0.7,
  "max_tokens": 2000
}
```

### 缓存和监控配置

```json
{
  "enable_cache": true,
  "cache_ttl": 3600,
  "enable_metrics": false,
  "metrics_port": 9090
}
```

## 📝 环境变量

```bash
# 检索配置
RAG_TOP_K=5
RAG_SCORE_THRESHOLD=0.7
RAG_MAX_CONTEXT_LENGTH=4000

# 文本处理
RAG_CHUNK_SIZE=1000
RAG_CHUNK_OVERLAP=200

# AI模型
EMBEDDING_MODEL=text-embedding-ada-002
LLM_MODEL=gpt-3.5-turbo
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2000

# 缓存和监控
RAG_ENABLE_CACHE=true
RAG_CACHE_TTL=3600
RAG_ENABLE_METRICS=false
```

## 🎯 参数调优建议

### 检索参数

- **`top_k`**: 根据应用场景调整，搜索类应用可设为10-20，对话类可设为3-5
- **`score_threshold`**: 相似度阈值，建议0.7-0.8，根据测试结果调整
- **`max_context_length`**: 根据LLM上下文窗口调整，GPT-4为8192，GPT-3.5为4096

### 文本处理参数

- **`chunk_size`**: 建议500-2000，根据文档类型调整
- **`chunk_overlap`**: 建议分块大小的10-20%，确保上下文连续性

### 性能优化

- **启用缓存** (`enable_cache=true`) 可显著提升响应速度
- **合理设置TTL** 根据数据更新频率调整缓存过期时间

