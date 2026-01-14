# Google Cloud Vector Search 配置指南

## 📋 概述

如果您想要使用Google Cloud Vector Search而不是本地ChromaDB，需要进行以下配置：

## 🔧 完整配置步骤

### 1. 创建Google Cloud项目

1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建新项目或选择现有项目
3. 记录项目ID（格式如：`my-rag-project-12345`）

### 2. 启用必要的API

在Google Cloud Console中启用以下API：
- **Vertex AI API**
- **Cloud Resource Manager API**

### 3. 创建服务账号

1. 进入 **IAM & Admin** > **Service Accounts**
2. 点击 **Create Service Account**
3. 填写服务账号详情：
   - Name: `rag-vector-search-sa`
   - Description: `Service account for RAG vector search`
4. 授予角色：
   - **Vertex AI Administrator**
   - **Storage Admin** (如果需要)
5. 创建密钥：
   - 点击服务账号 > **Keys** > **Add Key** > **JSON**
   - 下载JSON密钥文件

### 4. 创建Vertex AI Vector Search索引

1. 进入 **Vertex AI** > **Vector Search**
2. 点击 **Create Index**
3. 配置索引：
   - **Index name**: `rag-knowledge-index`
   - **Region**: `us-central1` (或您偏好的区域)
   - **Dimensions**: `768` (与您的embedding模型匹配)
   - **Distance measure**: `Cosine` (余弦相似度)
4. 等待索引创建完成

### 5. 创建Vertex AI Vector Search端点

1. 在Vector Search页面，进入 **Endpoints**
2. 点击 **Create Endpoint**
3. 配置端点：
   - **Endpoint name**: `rag-knowledge-endpoint`
   - **Region**: 与索引相同的区域
4. 将索引部署到端点

### 6. 配置应用

#### 6.1 修改向量数据库配置

编辑 `app/config/vector_db/vector_db.json`：

```json
{
  "db_type": "google_cloud",
  "collection_name": "rag-knowledge-index",
  "dimension": 768,
  "metric_type": "COSINE",
  "project_id": "your-project-id-12345",
  "region": "us-central1",
  "instance_id": "rag-knowledge-endpoint",
  "database_id": "your-database-id",
  "index_params": {},
  "search_params": {},
  "max_connections": 10,
  "timeout": 30,
  "retry_attempts": 3,
  "retry_delay": 1.0
}
```

#### 6.2 设置Google Cloud认证

**方法1：环境变量**
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

**方法2：Python代码中设置**
```python
import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/path/to/service-account-key.json'
```

### 7. 安装依赖

```bash
pip install google-cloud-aiplatform
```

### 8. 测试配置

运行测试脚本验证配置：

```bash
python test_rag_api.py
```

## ⚠️ 注意事项

### 费用考虑
- **Vertex AI Vector Search**: 按存储和查询次数收费
- **存储费用**: ≈$0.2/GB/月
- **查询费用**: 按每次查询收费

### 延迟问题
- Google Cloud服务可能有网络延迟
- 建议在生产环境中使用就近区域

### 配额限制
- 新项目可能有API配额限制
- 可以申请提高配额

## 🔄 切换回本地存储

如果不想使用Google Cloud，可以随时切换回本地ChromaDB：

```json
// app/config/vector_db/vector_db.json
{
  "db_type": "chroma",
  "host": "localhost",
  "port": 8000,
  "collection_name": "test_agent_knowledge"
}
```

## 🚀 推荐配置

对于大多数用户，**本地ChromaDB** 是最佳选择：

| 特性 | ChromaDB (本地) | Google Cloud |
|------|----------------|--------------|
| 费用 | ✅ 完全免费 | ❌ 按量收费 |
| 速度 | ✅ 本地快速 | ⚠️ 网络延迟 |
| 维护 | ✅ 无需管理 | ❌ 需要配置 |
| 隐私 | ✅ 本地安全 | ⚠️ 云端存储 |

**建议**：从ChromaDB开始，数据量大时再考虑云服务。

## ❓ 常见问题

### Q: 为什么选择Google Cloud而不是其他云服务？
A: Vertex AI提供了强大的AI原生向量搜索功能，与Google生态集成良好。

### Q: 可以和其他云服务集成吗？
A: 是的，代码支持Pinecone、Qdrant等其他向量数据库。

### Q: 本地存储够用吗？
A: 对于大多数RAG应用，本地ChromaDB完全够用，支持数百万向量。
