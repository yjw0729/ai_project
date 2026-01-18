# 业务模块功能使用指南

## 📋 功能概述

系统现在支持按业务模块对文档进行分类管理，实现更精确的检索和查询。支持四个核心业务模块：

- **跨境开户** (`cross_border_opening`) - 跨境业务开户相关文档
- **跨境交易** (`cross_border_trading`) - 跨境业务交易相关文档
- **互联网开户** (`internet_opening`) - 互联网业务开户相关文档
- **互联网交易** (`internet_trading`) - 互联网业务交易相关文档

## 🏗️ 系统架构

```
业务模块系统：
├── 配置层: business_modules.json (模块定义)
├── 数据层: Document.business_module (文档分类)
├── API层: /upload, /query, /business_modules (接口支持)
├── 检索层: 按模块过滤查询结果
└── 管理层: 动态模块配置和权限管理
```

## ⚙️ 配置说明

### 1. 业务模块配置文件

位置：`app/config/rag/business_modules.json`

```json
{
  "modules": {
    "cross_border_opening": {
      "name": "跨境开户",
      "description": "跨境业务开户相关文档",
      "category": "cross_border",
      "sub_category": "opening",
      "enabled": true
    },
    "cross_border_trading": {
      "name": "跨境交易",
      "description": "跨境业务交易相关文档",
      "category": "cross_border",
      "sub_category": "trading",
      "enabled": true
    },
    "internet_opening": {
      "name": "互联网开户",
      "description": "互联网业务开户相关文档",
      "category": "internet",
      "sub_category": "opening",
      "enabled": true
    },
    "internet_trading": {
      "name": "互联网交易",
      "description": "互联网业务交易相关文档",
      "category": "internet",
      "sub_category": "trading",
      "enabled": true
    }
  },
  "categories": {
    "cross_border": {
      "name": "跨境业务",
      "description": "跨境相关业务模块"
    },
    "internet": {
      "name": "互联网业务",
      "description": "互联网相关业务模块"
    }
  },
  "settings": {
    "allow_custom_modules": false,
    "default_module": null,
    "require_module_specification": true
  }
}
```

### 2. 动态配置

可以通过修改配置文件来：
- 添加新的业务模块
- 启用/禁用现有模块
- 修改模块描述信息
- 调整模块分类

## 📤 API使用指南

### 1. 获取可用业务模块列表

```bash
GET /rag_service/business_modules
```

**响应示例：**
```json
{
  "code": 200,
  "message": "获取成功",
  "data": {
    "modules": [
      {
        "key": "cross_border_opening",
        "name": "跨境开户",
        "description": "跨境业务开户相关文档",
        "category": "cross_border",
        "enabled": true
      },
      {
        "key": "cross_border_trading",
        "name": "跨境交易",
        "description": "跨境业务交易相关文档",
        "category": "cross_border",
        "enabled": true
      }
    ],
    "total_count": 4
  }
}
```

### 2. 上传文档到指定业务模块

```bash
POST /rag_service/upload
Content-Type: multipart/form-data
```

**请求参数：**
- `file`: 文档文件 (必需)
- `business_module`: 业务模块 (必需) - 如 "cross_border_opening"
- `collection_name`: 集合名称 (可选)
- `document_title`: 文档标题 (可选)
- `document_type`: 文档类型 (可选)
- `tags`: 标签列表 (可选)

**curl示例：**
```bash
curl -X POST "http://localhost:8015/rag_service/upload" \
  -F "file=@account_opening.pdf" \
  -F "business_module=cross_border_opening" \
  -F "document_title=跨境开户指南" \
  -F "document_type=technical_specification" \
  -F "tags=[\"guide\", \"opening\"]"
```

**成功响应：**
```json
{
  "code": 200,
  "message": "文档上传并处理成功",
  "data": {
    "document_id": "uuid-string",
    "collection_name": "documents",
    "business_module": "cross_border_opening",
    "status": "completed",
    "chunks_count": 15,
    "file_path": "/uploads/rag_docs/uuid.pdf"
  }
}
```

### 3. 按业务模块查询

```bash
POST /rag_service/query
Content-Type: application/json
```

**请求参数：**
```json
{
  "query": "如何进行开户？",
  "business_module": "cross_border_opening",  // 可选：按业务模块过滤
  "collection_name": "documents",             // 可选：集合名称
  "top_k": 5,                                // 可选：返回结果数量
  "filters": {                               // 可选：额外过滤条件
    "document_type": "technical_specification",
    "tags": ["guide"]
  }
}
```

**完整示例：**
```bash
curl -X POST "http://localhost:8015/rag_service/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "开户需要什么材料？",
    "business_module": "cross_border_opening",
    "top_k": 3
  }'
```

**响应示例：**
```json
{
  "code": 200,
  "message": "查询成功",
  "data": {
    "question": "开户需要什么材料？",
    "answer": "根据跨境开户指南，您需要准备以下材料：...",
    "sources": [
      {
        "content": "所需材料：身份证件、地址证明、收入证明、银行流水...",
        "score": 0.89,
        "source": "跨境开户指南.pdf",
        "metadata": {
          "business_module": "cross_border_opening",
          "document_type": "technical_specification"
        }
      }
    ],
    "retrieved_count": 3,
    "elapsed_seconds": 1.2
  }
}
```

## 🔍 查询过滤机制

### 1. 业务模块过滤

系统支持以下过滤方式：

```python
# 只查询跨境开户相关文档
filters = {"business_module": "cross_border_opening"}

# 组合过滤：跨境开户 + API文档
filters = {
    "business_module": "cross_border_opening",
    "document_type": "api_documentation"
}

# 标签过滤
filters = {
    "business_module": "internet_trading",
    "tags": ["guide", "manual"]
}
```

### 2. 过滤优先级

1. **业务模块过滤** - 最高优先级，只返回指定模块的文档
2. **文档类型过滤** - 在业务模块内按文档类型过滤
3. **标签过滤** - 在以上基础上按标签过滤
4. **相似度过滤** - 最后按向量相似度排序

### 3. 查询优化

- **精确匹配**: 业务模块完全匹配
- **性能优化**: 先按模块过滤，再计算向量相似度
- **缓存策略**: 支持按模块的查询缓存

## 📊 管理功能

### 1. 模块统计

可以通过以下方式查看模块使用情况：

```python
# 获取所有模块信息
modules = rag.get_business_modules()

# 验证模块是否存在
is_valid = rag.validate_business_module("cross_border_opening")
```

### 2. 动态配置

支持运行时修改模块配置：

```python
# 添加新模块（需要修改配置文件）
new_module = {
    "key": "new_business_module",
    "name": "新业务模块",
    "description": "新业务模块描述",
    "enabled": true
}

# 重启服务后生效
```

## 🧪 测试验证

运行完整的业务模块测试：

```bash
python test_business_modules.py
```

测试内容包括：
- ✅ 模块配置加载
- ✅ 文档分类上传
- ✅ 模块化查询
- ✅ 结果过滤验证
- ✅ 统计信息检查

## 💡 使用建议

### 1. 模块选择策略

- **跨境开户**: 身份验证、开户流程、合规要求
- **跨境交易**: 交易规则、风控措施、国际结算
- **互联网开户**: 在线流程、数字验证、便捷服务
- **互联网交易**: 电子交易、移动端功能、智能服务

### 2. 文档分类建议

- **按业务流程分类**: 开户→交易→服务
- **按用户类型分类**: 个人/企业，境内/境外
- **按功能模块分类**: 前端/后端，核心/外围

### 3. 查询优化

- **精确查询**: 使用业务模块过滤避免无关结果
- **组合查询**: 模块 + 类型 + 标签的多重过滤
- **缓存利用**: 相同模块的查询结果可缓存复用

## 🚨 注意事项

1. **模块必选**: 上传文档时必须指定业务模块
2. **模块验证**: 系统会验证模块是否存在且已启用
3. **权限控制**: 不同模块可设置不同访问权限
4. **数据隔离**: 模块之间数据逻辑隔离，物理存储共享
5. **扩展性**: 支持动态添加新业务模块

## 🔧 扩展开发

### 添加新的业务模块

1. **修改配置文件** `business_modules.json`
2. **添加枚举值** (如需要)
3. **更新文档和API**
4. **测试验证**

### 自定义过滤逻辑

可以扩展过滤器支持更多条件：

```python
# 时间范围过滤
filters = {
    "business_module": "cross_border_opening",
    "date_range": ["2024-01-01", "2024-12-31"]
}

# 权限级别过滤
filters = {
    "business_module": "internet_trading",
    "access_level": "internal"
}
```

这样您就可以根据不同的业务场景精确地管理和查询文档了！🎯


