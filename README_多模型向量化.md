# 多模型向量化功能说明

## 功能概述

系统现在支持根据不同文档类型自动选择最适合的向量化模型，提升检索质量和相关性。

## 支持的文档类型与模型映射

### 📋 标准文档类型

| 文档类型 | 枚举值 | 推荐模型 | 向量维度 | 适用场景 |
|---------|--------|---------|---------|---------|
| 产品需求文档 | `PRODUCT_REQ` | 通义千问通用模型 | 768 | 业务需求描述 |
| 设计文档 | `DESIGN_DOC` | 通义千问通用模型 | 768 | 系统设计说明 |
| API文档 | `API_DOC` | 通义千问专用模型 | 1536 | 接口规范、API文档 |
| 技术规范 | `TECH_SPEC` | 通义千问专用模型 | 1536 | 技术标准、规范文档 |
| 测试用例 | `TEST_CASE` | 通义千问通用模型 | 768 | 测试场景描述 |
| 缺陷报告 | `BUG_REPORT` | 通义千问通用模型 | 768 | 问题描述 |

### 🔧 自定义模型

| 模型标识 | 提供商 | 模型名称 | 适用场景 |
|---------|--------|---------|---------|
| `code_aware` | HuggingFace | microsoft/codebert-base | 包含代码片段的文档 |
| `multilingual_large` | 通义千问 | text-embedding-v3 | 大型多语言模型，更好的语义理解 |

## 配置说明

### 1. 模型配置文件

位置：`app/config/rag/embedding_models.json`

```json
{
  "default": {
    "provider": "tongyi",
    "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "dimension": 768
  },
  "by_document_type": {
    "api_documentation": {
      "provider": "tongyi",
      "model": "text-embedding-v2",
      "dimension": 1536,
      "description": "API文档，使用通义千问专用模型"
    }
    // ... 其他文档类型配置
  },
  "custom_models": {
    "code_aware": {
      "provider": "huggingface",
      "model": "microsoft/codebert-base",
      "dimension": 768,
      "description": "代码感知模型"
    }
  }
}
```

### 2. API使用方式

上传文档时指定文档类型：

```bash
curl -X POST "http://localhost:8015/rag_service/upload" \
  -F "file=@api_document.pdf" \
  -F "document_type=api_documentation" \
  -F "collection_name=docs"
```

### 3. 系统日志

系统会自动记录使用的模型信息：

```
生成向量中... 文档类型: api_documentation, 使用模型: tongyi/text-embedding-v2
```

## 模型选择逻辑

1. **优先级1**: 根据文档类型查找专用模型配置
2. **优先级2**: 如果未找到，使用默认模型配置
3. **兜底机制**: 如果专用模型失败，自动回退到通用模型

## 性能优化建议

### 1. 向量维度选择
- **通用场景**: 768维（速度快，占用空间小）
- **专业场景**: 1536维或更高（语义理解更准确）

### 2. 模型选择建议
- **中文文档**: 推荐通义千问系列模型
- **多语言文档**: 推荐`paraphrase-multilingual`系列
- **代码相关**: 推荐`codebert`或专用代码模型
- **API文档**: 推荐专用技术文档模型

### 3. 成本考虑
- **通义千问通用模型**: 性价比最高
- **专用模型**: 在特定领域表现更好，但成本略高
- **HuggingFace本地模型**: 无API调用成本，但需要更多计算资源

## 测试验证

运行测试脚本验证功能：

```bash
python test_embedding_models.py
```

## 注意事项

1. **向后兼容**: 未指定文档类型的文档仍使用默认模型
2. **动态配置**: 可以随时修改`embedding_models.json`配置文件，无需重启
3. **错误处理**: 如果专用模型失败，系统会自动回退到通用模型
4. **混合集合**: 同一集合中可以包含不同类型的文档，它们会使用各自最适合的模型

## 扩展开发

### 添加新的文档类型

1. 在`DocumentType`枚举中添加新类型
2. 在`embedding_models.json`中配置对应的模型
3. 系统会自动识别并应用

### 添加新的模型提供商

1. 在`VectorIndexer`中实现对应的`_generate_*_embeddings`方法
2. 在配置中添加新的provider支持
3. 更新`generate_embeddings`方法的分发逻辑

这样你就可以根据不同的文档特点选择最适合的向量化模型了！🎯


