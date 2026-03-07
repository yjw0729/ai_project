# RAG 文档审核服务 API 接口文档

> 用于前端工程师对接接口

## 1. 接口概览

### 基础信息
- **服务地址**: `http://<服务器IP>:8016/rag_service`
- **接口前缀**: `/rag_service`

---

## 2. 审核记录列表接口

### 2.1 获取审核记录列表

获取文档审核记录列表（从汇总表查询，高效返回）

**请求路径**: `GET /rag_service/list_reviews`

**Query 参数**:
| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| status | string | 否 | - | 审核状态过滤：`pending` / `approved` / `rejected` |
| business_module | string | 否 | - | 业务模块过滤 |
| limit | int | 否 | 100 | 每页返回条数 |
| offset | int | 否 | 0 | 偏移量（分页用） |

**请求示例**:
```bash
GET /rag_service/list_reviews?status=pending&limit=20&offset=0
```

**响应格式**:
```json
{
  "code": 200,
  "message": "获取成功",
  "data": {
    "total": 50,
    "limit": 20,
    "offset": 0,
    "list": [
      {
        "id": 1,
        "doc_id": "a1b2c3d4-e5f6-...",
        "document_title": "用户登录接口文档",
        "business_module": "用户中心",
        "interface_count": 5,
        "image_count": 3,
        "general_image_count": 1,
        "test_case_count": 10,
        "status": "pending",
        "xmind_file_path": "/outputs/xxx.xmind",
        "creator": "system",
        "reviewer": null,
        "review_comment": null,
        "created_time": "2026-03-06T10:30:00",
        "updated_time": "2026-03-06T10:30:00"
      }
    ]
  }
}
```

**响应字段说明**:
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | 记录ID |
| doc_id | string | 文档唯一标识UUID |
| document_title | string | 文档标题 |
| business_module | string | 业务模块名称 |
| interface_count | int | 识别的接口数量 |
| image_count | int | 提取的图片总数 |
| general_image_count | int | 知识类图片数量（未匹配到接口） |
| test_case_count | int | 生成的测试用例数量 |
| status | string | 审核状态：`pending`(待审核) / `approved`(已通过) / `rejected`(已拒绝) |
| xmind_file_path | string | 生成的XMind文件路径（可能为null） |
| creator | string | 创建人 |
| reviewer | string | 审核人（可能为null） |
| review_comment | string | 审核意见（可能为null） |
| created_time | string | 创建时间（ISO 8601格式） |
| updated_time | string | 更新时间（ISO 8601格式） |

---

## 3. 审核记录详情接口

### 3.1 获取审核记录详情

根据 doc_id 获取某条文档的完整审核信息（包括接口详情、图片信息等）

**请求路径**: `GET /rag_service/get_review/<doc_id>`

**路径参数**:
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| doc_id | string | 是 | 文档唯一标识UUID |

**请求示例**:
```bash
GET /rag_service/get_review/a1b2c3d4-e5f6-...
```

**响应格式**:
```json
{
  "code": 200,
  "message": "获取成功",
  "data": {
    "id": 1,
    "doc_id": "a1b2c3d4-e5f6-...",
    "document_title": "用户登录接口文档",
    "business_module": "用户中心",
    "project_background": "项目背景内容...",
    "business_summary": "业务摘要内容...",
    "interface_name": "用户登录接口",
    "interface_method": "POST",
    "interface_path": "/api/user/login",
    "interface_description": "用于用户登录验证",
    "request_params": "username, password",
    "response_params": "token, userInfo",
    "process_flow": "1. 验证参数 2. 查询数据库 3. 返回结果",
    "flow_chart_desc": "流程图描述...",
    "detail_flow_analysis": "详细流程分析文本...",
    "record_type": "interface",
    "status": "pending",
    "xmind_file_path": "/outputs/xxx.xmind",
    "test_case_count": 10,
    "creator": "system",
    "reviewer": null,
    "review_comment": null,
    "created_time": "2026-03-06T10:30:00",
    "updated_time": "2026-03-06T10:30:00",
    "flow_chart_analysis": [
      {
        "source": "text",
        "analysis": "流程图分析文本..."
      },
      {
        "source": "image",
        "source_type": "flow_chart",
        "filename": "flow1.png",
        "analysis": "图片流程分析..."
      }
    ],
    "image_analysis": [
      {
        "success": true,
        "filename": "flow1.png",
        "image_index": 0,
        "analysis": "图片分析结果..."
      }
    ],
    "api_section": "API部分原始内容...",
    "document_content": "完整文档内容..."
  }
}
```

---

## 4. 审核操作接口

### 4.1 提交审核（更新状态）

**请求路径**: `POST /rag_service/update_review_status`

**请求体 (JSON)**:
```json
{
  "doc_id": "a1b2c3d4-e5f6-...",
  "status": "approved",
  "reviewer": "张三",
  "review_comment": "审核通过，接口文档完整"
}
```

**字段说明**:
| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| doc_id | string | 是 | 文档唯一标识UUID |
| status | string | 是 | 审核状态：`approved` / `rejected` |
| reviewer | string | 否 | 审核人姓名 |
| review_comment | string | 否 | 审核意见 |

**响应格式**:
```json
{
  "code": 200,
  "message": "更新成功",
  "data": {
    "doc_id": "a1b2c3d4-e5f6-...",
    "status": "approved"
  }
}
```

---

### 4.2 删除审核记录

**请求路径**: `DELETE /rag_service/delete_review/<doc_id>`

**路径参数**:
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| doc_id | string | 是 | 文档唯一标识UUID |

**请求示例**:
```bash
DELETE /rag_service/delete_review/a1b2c3d4-e5f6-...
```

**响应格式**:
```json
{
  "code": 200,
  "message": "删除成功",
  "data": {
    "doc_id": "a1b2c3d4-e5f6-..."
  }
}
```

---

## 5. 通用响应格式

所有接口统一返回以下 JSON 格式：

```json
{
  "code": 200,           // 状态码：200成功，400参数错误，404未找到，500服务器错误
  "message": "成功消息",  // 提示信息
  "data": { ... }        // 业务数据
}
```

---

## 6. 错误码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 参数错误 |
| 404 | 数据不存在 |
| 500 | 服务器内部错误 |

---

## 7. 典型调用示例

### 7.1 JavaScript (fetch)

```javascript
// 获取审核列表
async function getReviewList(status = 'pending', page = 1, pageSize = 20) {
  const offset = (page - 1) * pageSize;
  const response = await fetch(
    `http://172.16.46.138:8016/rag_service/list_reviews?status=${status}&limit=${pageSize}&offset=${offset}`
  );
  const result = await response.json();
  return result.data;
}

// 提交审核
async function submitReview(docId, status, reviewer, comment) {
  const response = await fetch(
    'http://172.16.46.138:8016/rag_service/update_review_status',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        doc_id: docId,
        status: status,
        reviewer: reviewer,
        review_comment: comment
      })
    }
  );
  return response.json();
}
```

### 7.2 Vue 3 (axios)

```javascript
import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'http://172.16.46.138:8016',
  timeout: 30000
});

// 获取列表
export const getReviewList = (params) => 
  apiClient.get('/rag_service/list_reviews', { params });

// 获取详情
export const getReviewDetail = (docId) => 
  apiClient.get(`/rag_service/get_review/${docId}`);

// 更新状态
export const updateReviewStatus = (data) => 
  apiClient.post('/rag_service/update_review_status', data);

// 删除记录
export const deleteReview = (docId) => 
  apiClient.delete(`/rag_service/delete_review/${docId}`);
```

---

## 8. 注意事项

1. **分页**: 使用 `limit` 和 `offset` 参数进行分页
2. **状态过滤**: 可选 `pending`、`approved`、`rejected` 三种状态
3. **业务模块**: 可按 `business_module` 字段过滤
4. **文件路径**: `xmind_file_path` 为服务器上的相对路径，前端如需下载需要拼接完整URL

---

> 如有疑问请联系后端工程师
