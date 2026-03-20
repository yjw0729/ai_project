# API自动化测试 - 前端对接接口文档

## 一、接口总览

| 接口 | 方法 | 路径 | 描述 |
|------|------|------|------|
| 上传文档 | POST | `/api/auto_test/upload` | 上传OpenAPI或接口说明文档 |
| 生成用例 | POST | `/api/auto_test/generate` | 根据文档生成测试用例 |
| 执行测试 | POST | `/api/auto_test/execute` | 执行选定的测试用例 |
| 查询结果 | GET | `/api/auto_test/results/{execution_id}` | 获取执行结果详情 |
| 下载报告 | GET | `/api/auto_test/report/{execution_id}` | 下载HTML测试报告 |
| 健康检查 | GET | `/api/auto_test/health` | 服务健康状态检查 |

---

## 二、详细接口

### 2.1 上传文档

**请求**

```
POST /api/auto_test/upload
Content-Type: multipart/form-data

file: [文件]
doc_type: openapi | api_doc | flowchart
system_name: 普通收单系统（可选）
flowchart_description: 流程图描述文本（仅flowchart类型时可选）
```

**doc_type 说明**

| doc_type | 支持文件类型 | 说明 |
|----------|-------------|------|
| openapi | .json, .yaml, .yml | OpenAPI 3.0 / Swagger 2.0 文档 |
| api_doc | .docx, .pdf | 接口说明文档（Word/PDF） |
| flowchart | .png, .jpg, .jpeg, .bmp | 业务流程图 |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "doc_id": "uuid-xxx",
    "doc_type": "openapi",
    "system_name": "普通收单系统",
    "parsed_interfaces": [
      {
        "interface_name": "创建客户",
        "method": "POST",
        "path": "/api/customer/create",
        "request_params_count": 5,
        "response_params_count": 3
      }
    ],
    "flowchart_nodes": [
      {"id": "1", "name": "创建客户", "next": ["2"]},
      {"id": "2", "name": "绑定银行卡", "next": ["3"]},
      {"id": "3", "name": "下单", "next": []}
    ]
  }
}
```

**错误码**

- `400`: 不支持的文件类型
- `500`: 解析失败

---

### 2.2 生成测试用例

**请求**

```
POST /api/auto_test/generate
Content-Type: application/json

{
  "doc_id": "uuid-xxx",
  "system_name": "普通收单系统",
  "options": {
    "generate_mode": "comprehensive",
    "include_boundary": true,
    "include_error": true,
    "priority_filter": ["P0", "P1", "P2"]
  }
}
```

**options 参数说明**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| generate_mode | string | comprehensive | 生成模式：normal / comprehensive |
| include_boundary | boolean | true | 是否包含边界值测试 |
| include_error | boolean | true | 是否包含异常测试 |
| priority_filter | string[] | ["P0","P1","P2"] | 优先级过滤，留空则包含所有 |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "doc_id": "uuid-xxx",
    "case_ids": [101, 102, 103, 104, 105],
    "case_count": 5,
    "cases": [
      {"id": 101, "name": "创建客户_必填参数正常", "priority": "P0", "tags": ["正向"]},
      {"id": 102, "name": "创建客户_身份证号格式错误", "priority": "P1", "tags": ["异常"]}
    ],
    "report": {
      "total": 5,
      "by_priority": {"P0": 1, "P1": 2, "P2": 2},
      "by_tag": {"正向": 1, "异常": 2, "边界": 2}
    }
  }
}
```

**错误码**

- `400`: 缺少 doc_id
- `404`: 文档不存在或已过期

---

### 2.3 执行测试

**请求**

```
POST /api/auto_test/execute
Content-Type: application/json

{
  "case_ids": [101, 102, 103],
  "env_id": 1,
  "concurrency": 5,
  "mode": "parallel"
}
```

**参数说明**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| case_ids | int[] | 是 | 要执行的用例ID列表 |
| env_id | int | 否 | 环境配置ID（不传则使用默认环境） |
| concurrency | int | 否 | 并发数，默认5，最大20 |
| mode | string | 否 | parallel（并发）/ serial（串行） |

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "execution_id": "exec-xxx",
    "status": "completed",
    "summary": {
      "total": 3,
      "passed": 2,
      "failed": 1,
      "success_rate": 66.67
    },
    "report_url": "/api/auto_test/report/exec-xxx",
    "results_preview": [
      {"case_id": 101, "case_name": "创建客户_必填参数正常", "status": "passed", "duration_ms": 120.5}
    ]
  }
}
```

**错误码**

- `400`: 缺少 case_ids
- `404`: 未找到测试用例

---

### 2.4 查询执行结果

**请求**

```
GET /api/auto_test/results/exec-xxx
```

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "execution_id": "exec-xxx",
    "status": "completed",
    "start_time": "2026-03-20 10:00:00",
    "summary": {
      "total": 3,
      "passed": 2,
      "failed": 1,
      "error": 0,
      "total_duration_ms": 1250.5,
      "success_rate": 66.67
    },
    "results": [
      {
        "case_id": 101,
        "case_name": "创建客户_必填参数正常",
        "status": "passed",
        "duration_ms": 120.5,
        "response_time_ms": 85,
        "status_code": 200,
        "assertions": [
          {"name": "status_code == 200", "passed": true, "expected": 200, "actual": 200},
          {"name": "response.code == 0", "passed": true, "expected": 0, "actual": 0}
        ]
      },
      {
        "case_id": 102,
        "case_name": "创建客户_身份证号格式错误",
        "status": "failed",
        "duration_ms": 85.2,
        "response_time_ms": 72,
        "status_code": 200,
        "error": "断言失败",
        "assertions": [
          {"name": "status_code == 400", "passed": false, "expected": 400, "actual": 200}
        ]
      }
    ],
    "report_url": "/api/auto_test/report/exec-xxx"
  }
}
```

**错误码**

- `404`: 执行记录不存在

---

### 2.5 下载测试报告

**请求**

```
GET /api/auto_test/report/exec-xxx
```

**响应**

返回HTML格式的测试报告页面，可直接在浏览器打开或作为附件下载。

---

### 2.6 健康检查

**请求**

```
GET /api/auto_test/health
```

**响应**

```json
{
  "code": 200,
  "message": "API自动化测试服务正常",
  "data": {
    "status": "ok",
    "upload_dir": "uploads/api_auto_test",
    "report_dir": "outputs/reports",
    "config": {
      "llm_model": "qwen-plus",
      "default_concurrency": 5
    }
  }
}
```

---

## 三、错误码说明

| 错误码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误（缺少必要参数、文件类型不支持等） |
| 404 | 资源不存在（文档过期、执行记录不存在等） |
| 500 | 服务器内部错误（数据库异常、LLM调用失败等） |

---

## 四、业务流程

```
[前端] --上传文档--> [API层] --解析--> [RAG层] --提取接口--> [LLM层] --生成用例--> [数据层] --插入DB
[前端] --执行测试--> [API层] --加载用例--> [执行器] --并发执行--> [API层] --生成报告--> [前端]
```

---

## 五、注意事项

1. **doc_id有效期**: 上传的文档解析结果会在服务端保存，但建议及时调用 generate 接口
2. **并发控制**: 建议并发数不超过20，避免服务端压力
3. **文件大小**: 单个上传文件建议不超过50MB
4. **报告清理**: 历史报告文件需要定期清理，避免占用过多磁盘空间
5. **case_type**: 自动生成的用例会自动设置 `case_type="auto_generated"`，便于和手动用例区分
6. **优先级说明**: P0=核心流程, P1=重要功能, P2=一般功能, P3=边缘场景
