# `generate_testcases_from_doc` 接口测试方案

## 一、接口概述

### 基本信息

| 项目 | 内容 |
|------|------|
| **接口路径** | `POST /ai_service/ai/generate_testcases_from_doc` |
| **完整 URL** | `http://{host}:{port}/ai_service/ai/generate_testcases_from_doc` |
| **所属 Blueprint** | `doc_parser_opt`（注册在 `app/application.py`） |
| **请求方式** | `POST` |
| **Content-Type** | `multipart/form-data` 或 `application/json` |

### 入参说明

#### 必填字段

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `api_name` | string | 接口名称 |
| `http_method` | string | HTTP 方法，如 `GET`, `POST`, `PUT`, `DELETE` |
| `path` | string | 接口路径，如 `/api/users` |

#### 知识来源（至少提供一种）

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `documents` | file[] | 文档文件（form-data 多文件上传），支持 docx/pdf 等 |
| `texts` | string[] | 纯文本内容数组（form-data 多字段或 JSON 数组） |
| `images` | string[] | Base64 编码的图片列表（仅 JSON 模式） |

#### 可选字段

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `api_desc` | string | 接口描述 |
| `max_cases` | int | 最大生成用例数 |
| `persist` | bool | 是否持久化到数据库（默认 `false`） |
| `module` | string | 所属模块 |
| `system` | string | 所属系统 |

### 响应格式

```json
{
    "code": 200,
    "msg": "success",
    "data": {
        "task_id": "61eecf60-22b3-443f-8f5e-2e02a51a3ee2",
        "status": "pending",
        "message": "任务已创建，请通过 GET /api/tasks/{task_id} 轮询状态"
    }
}
```

---

## 二、测试文件

测试代码位于：`tests/test_generate_testcases_from_doc.py`

---

## 三、测试用例

### 前置条件

- Flask 服务已启动（默认 `http://127.0.0.1:5000`，可通过环境变量 `TEST_BASE_URL` 覆盖）
- 测试文档和图片文件使用项目 `docs/` 目录下的固定文件：
  - 文档：`docs/created_challenge_api.docx`
  - 图片：`docs/flow_check_solo_challenge.png`
- 可通过环境变量 `DOCS_DIR` 指定 docs 目录路径

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `TEST_BASE_URL` | `http://127.0.0.1:5000` | 服务基础 URL |
| `DOCS_DIR` | `{项目根目录}/docs` | 文档目录路径 |

---

### TC-01：正向流程 - multipart/form-data 上传文档创建任务

**目的**：验证使用 form-data 上传文档文件时，接口正常创建任务并返回 `task_id`

**前置条件**：服务正常运行

**测试步骤**：

1. 读取 `docs/created_challenge_api.docx` 文件内容
2. 构造 `POST /ai_service/ai/generate_testcases_from_doc` 请求（multipart/form-data）
3. 设置必填字段：`api_name=创建挑战接口`, `http_method=POST`, `path=/api/challenges`
4. 上传文档文件到 `documents` 字段
5. 发送请求，记录响应
6. 从响应中提取 `task_id`

**预期结果**：

- HTTP 状态码为 `200`
- 响应 JSON 中 `code == 200`
- 响应 `data` 中包含 `task_id`（UUID 格式）
- `data.status == "pending"`
- `data.message` 包含轮询提示信息

**请求示例**（curl）：

```bash
curl -X POST "http://127.0.0.1:5000/ai_service/ai/generate_testcases_from_doc" \
  -F "api_name=创建挑战接口" \
  -F "http_method=POST" \
  -F "path=/api/challenges" \
  -F "documents=@docs/created_challenge_api.docx"
```

---

### TC-02：正向流程 - JSON 模式上传文本知识创建任务

**目的**：验证 JSON 模式下通过 `texts` 字段传入文本知识，接口正常创建任务

**前置条件**：服务正常运行

**测试步骤**：

1. 构造 JSON 请求体：
   ```json
   {
       "api_name": "查询挑战详情",
       "http_method": "GET",
       "path": "/api/challenges/{id}",
       "api_desc": "根据挑战ID查询挑战详细信息",
       "texts": [
           "挑战接口用于创建新的挑战记录",
           "请求参数：title(必填,string), description(选填,string), difficulty(枚举: easy/medium/hard)"
       ]
   }
   ```
2. 发送 `POST` 请求，`Content-Type: application/json`
3. 提取 `task_id`

**预期结果**：

- HTTP 状态码为 `200`
- `code == 200`
- `data.task_id` 存在且为有效 UUID

---

### TC-03：正向流程 - 组合模式（文档+文本）创建任务

**目的**：验证同时上传文档文件和文本内容时，接口正常处理

**前置条件**：服务正常运行，`docs/created_challenge_api.docx` 和 `docs/flow_check_solo_challenge.png` 存在

**测试步骤**：

1. 读取 `docs/created_challenge_api.docx`
2. 将 `docs/flow_check_solo_challenge.png` 转为 Base64
3. 构造 JSON 请求体，包含 `documents`（文件路径列表）和 `images`（Base64 列表）
4. 设置必填字段：`api_name=流程检查单挑战`, `http_method=POST`, `path=/api/flow-check`
5. 发送请求

**预期结果**：

- HTTP 状态码为 `200`
- `code == 200`
- `data.task_id` 存在
- 日志中显示知识类型计数正确

**注**：由于 JSON 模式不支持直接传文件，实际测试中可改用 form-data + 额外 texts 字段组合

---

### TC-04：正向流程 - 任务创建后轮询状态

**目的**：验证任务创建成功后，通过 `GET /api/tasks/{task_id}` 正确查询任务状态

**前置条件**：已完成 TC-01 或 TC-02 并获得有效 `task_id`

**测试步骤**：

1. 复用 TC-01/02 创建的 `task_id`
2. 发送 `GET /api/tasks/{task_id}` 请求
3. 验证响应结构和各字段

**预期结果**：

- HTTP 状态码为 `200`
- 响应 JSON 中 `code == 200`
- `data` 包含字段：`task_id`, `task_type`, `status`, `progress`, `params`, `created_at`, `updated_at`
- `data.task_type == "case_generation"`
- `data.status` 为 `pending` / `running` / `completed` / `failed` 之一

**请求示例**：

```bash
curl "http://127.0.0.1:5000/api/tasks/61eecf60-22b3-443f-8f5e-2e02a51a3ee2"
```

---

### TC-05：正向流程 - 任务列表查询

**目的**：验证 `GET /api/tasks/list` 正确返回任务列表

**前置条件**：至少存在一个任务记录

**测试步骤**：

1. 发送 `GET /api/tasks/list?page=1&page_size=10` 请求
2. 验证响应包含分页信息和任务数组

**预期结果**：

- HTTP 状态码为 `200`
- `code == 200`
- `data` 包含 `total`, `page`, `page_size`, `tasks` 字段
- `tasks` 为数组
- 支持按 `status` 和 `task_type` 过滤

---

### TC-06：正向流程 - 查询任务关联知识

**目的**：验证 `GET /api/tasks/{task_id}/knowledge` 返回任务关联的知识内容

**前置条件**：已完成 TC-01 并获得有效 `task_id`

**测试步骤**：

1. 使用 TC-01 的 `task_id`
2. 发送 `GET /api/tasks/{task_id}/knowledge`
3. 验证知识记录

**预期结果**：

- HTTP 状态码为 `200`
- `code == 200`
- `data.knowledge` 为数组，每条包含 `id`, `knowledge_type`, `content`/`file_path`, `created_at`

---

### TC-07：反向 - 缺少必填字段 `api_name`

**目的**：验证缺少 `api_name` 时，接口返回 400 错误

**测试步骤**：

1. 构造请求，只包含 `http_method=POST` 和 `path=/api/test`，缺少 `api_name`
2. 发送请求

**预期结果**：

- HTTP 状态码为 `200`（业务错误码）或 `400`
- `code != 200` 或 `code == 400`
- 错误信息中包含 `api_name` 提示

---

### TC-08：反向 - 缺少必填字段 `http_method`

**目的**：验证缺少 `http_method` 时，接口返回错误

**测试步骤**：

1. 构造请求，只包含 `api_name=测试` 和 `path=/api/test`，缺少 `http_method`
2. 发送请求

**预期结果**：

- 响应包含字段缺失提示

---

### TC-09：反向 - 缺少必填字段 `path`

**目的**：验证缺少 `path` 时，接口返回错误

**测试步骤**：

1. 构造请求，只包含 `api_name=测试` 和 `http_method=POST`，缺少 `path`
2. 发送请求

**预期结果**：

- 响应包含字段缺失提示

---

### TC-10：反向 - 未提供任何知识来源

**目的**：验证不提供任何知识来源时，接口返回错误

**测试步骤**：

1. 构造有效必填字段请求，但不提供 `documents`、`texts`、`images` 中的任何一种
2. 发送请求

**预期结果**：

- 响应错误信息包含"至少需要提供一种知识"

---

### TC-11：反向 - 任务 ID 不存在

**目的**：验证查询不存在的 `task_id` 时返回 404

**测试步骤**：

1. 发送 `GET /api/tasks/nonexistent-task-id-12345`
2. 验证 404 响应

**预期结果**：

- HTTP 状态码为 `404`
- `code == 404`
- `msg` 包含"任务不存在"

---

### TC-12：正向流程 - 取消任务

**目的**：验证取消 `pending` 状态的任务成功

**前置条件**：已完成 TC-01/02 并获得 `pending` 状态任务的 `task_id`

**测试步骤**：

1. 发送 `DELETE /api/tasks/{task_id}` 请求
2. 验证响应

**预期结果**：

- HTTP 状态码为 `200`
- `code == 200`
- `data.status == "cancelled"`

**注**：已处于 `completed` / `failed` / `cancelled` 状态的任务不可取消，接口应返回提示而非报错

---

### TC-13：反向 - 取消已结束的任务

**目的**：验证取消已完成的任务时，接口给出友好提示

**前置条件**：存在已完成（`completed` / `failed`）状态的任务

**测试步骤**：

1. 发送 `DELETE /api/tasks/{已完成任务的task_id}`
2. 验证响应

**预期结果**：

- HTTP 状态码为 `200`
- `code == 200`
- `msg` 提示任务已处于结束状态

---

## 四、执行指南

### 手动执行（curl）

```bash
# 启动服务
cd D:/pythonProject/pytest_sxp
python run_api.py

# TC-01：创建任务
curl -X POST "http://127.0.0.1:5000/ai_service/ai/generate_testcases_from_doc" \
  -F "api_name=创建挑战接口" \
  -F "http_method=POST" \
  -F "path=/api/challenges" \
  -F "documents=@docs/created_challenge_api.docx"

# TC-04：轮询任务状态
curl "http://127.0.0.1:5000/api/tasks/{替换task_id}"

# TC-05：查询任务列表
curl "http://127.0.0.1:5000/api/tasks/list?page=1&page_size=10"

# TC-06：查询任务知识
curl "http://127.0.0.1:5000/api/tasks/{替换task_id}/knowledge"

# TC-12：取消任务
curl -X DELETE "http://127.0.0.1:5000/api/tasks/{替换task_id}"
```

### Pytest 自动执行

```bash
cd D:/pythonProject/pytest_sxp
pytest tests/test_generate_testcases_from_doc.py -v
```

### 环境变量配置

```bash
# 指定服务地址
set TEST_BASE_URL=http://172.16.46.138:5173

# 指定文档目录
set DOCS_DIR=D:/pythonProject/pytest_sxp/docs

pytest tests/test_generate_testcases_from_doc.py -v
```

---

## 五、预期输出

### 任务创建成功响应示例

```json
{
    "code": 200,
    "msg": "success",
    "data": {
        "task_id": "61eecf60-22b3-443f-8f5e-2e02a51a3ee2",
        "status": "pending",
        "message": "任务已创建，请通过 GET /api/tasks/{task_id} 轮询状态"
    }
}
```

### 任务状态查询响应示例

```json
{
    "code": 200,
    "msg": "success",
    "data": {
        "task_id": "61eecf60-22b3-443f-8f5e-2e02a51a3ee2",
        "task_type": "case_generation",
        "status": "pending",
        "progress": 0,
        "params": {
            "api_name": "创建挑战接口",
            "http_method": "POST",
            "path": "/api/challenges",
            "knowledge_summary": {
                "documents_count": 1,
                "images_count": 0,
                "texts_count": 0
            }
        },
        "result": null,
        "error_message": null,
        "created_at": "2026-03-23T20:00:00",
        "updated_at": "2026-03-23T20:00:00",
        "completed_at": null
    }
}
```

---

## 六、测试数据

### 固定测试文件

| 用途 | 文件路径 |
|------|----------|
| API 文档 | `docs/created_challenge_api.docx` |
| 流程图 | `docs/flow_check_solo_challenge.png` |

### 动态测试数据

| 字段 | 测试值 |
|------|--------|
| `api_name` | `创建挑战接口`, `查询挑战详情`, `流程检查单挑战` |
| `http_method` | `POST`, `GET` |
| `path` | `/api/challenges`, `/api/challenges/{id}`, `/api/flow-check` |
| `api_desc` | `根据挑战ID查询挑战详细信息` |
| `texts[0]` | `挑战接口用于创建新的挑战记录` |
| `texts[1]` | `请求参数：title(必填,string), description(选填,string)` |

---

## 七、缺陷跟踪

| 用例编号 | 缺陷描述 | 严重程度 | 状态 | 备注 |
|----------|----------|----------|------|------|
| TC-01~TC-06 | 任务创建后未实现异步执行逻辑，任务始终处于 `pending` 状态 | 高 | 待修复 | 需在后台线程/进程中调用 LLM 生成用例 |
| TC-01~TC-06 | 文档上传路径解析可能存在问题，需确认上传目录写入正常 | 中 | 待验证 | 检查 `uploads/` 目录权限和文件写入 |
| TC-04 | 轮询 `/api/tasks/{task_id}` 返回 404（根因：`app/routes/tasks.py` 源文件缺失） | 高 | 已修复 | 已恢复源文件 |
