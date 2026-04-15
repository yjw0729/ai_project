"""
`generate_testcases_from_doc` 接口测试

覆盖正向流程（任务创建、状态轮询、列表查询、知识查询、取消任务）
和反向流程（必填字段校验、知识来源校验、任务不存在等）。
"""

import base64
import os
import uuid

import pytest
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:5000")
DOCS_DIR = os.environ.get(
    "DOCS_DIR",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs"),
)

DOC_API_DOCX = os.path.join(DOCS_DIR, "created_challenge_api.docx")
DOC_FLOW_PNG = os.path.join(DOCS_DIR, "flow_check_solo_challenge.png")

CREATE_TASK_ENDPOINT = "/ai_service/ai/generate_testcases_from_doc"
GET_TASK_ENDPOINT = "/api/tasks/{task_id}"
LIST_TASKS_ENDPOINT = "/api/tasks/list"
CANCEL_TASK_ENDPOINT = "/api/tasks/{task_id}"
GET_KNOWLEDGE_ENDPOINT = "/api/tasks/{task_id}/knowledge"


def full_url(path: str) -> str:
    return f"{BASE_URL.rstrip('/')}{path}"


def read_file_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def image_to_base64(path: str) -> str:
    return base64.b64encode(read_file_bytes(path)).decode("utf-8")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def docs_exist():
    """Verify test fixture files exist before running any test."""
    missing = []
    if not os.path.exists(DOC_API_DOCX):
        missing.append(DOC_API_DOCX)
    if not os.path.exists(DOC_FLOW_PNG):
        missing.append(DOC_FLOW_PNG)
    if missing:
        pytest.skip(f"测试文件不存在: {', '.join(missing)}")
    return True


@pytest.fixture
def fresh_task_id(docs_exist) -> str:
    """
    Helper fixture: creates a task via the real endpoint and returns its task_id.
    Tests that need a valid task_id can depend on this.
    """
    with open(DOC_API_DOCX, "rb") as f:
        files = {"documents": (os.path.basename(DOC_API_DOCX), f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        data = {
            "api_name": "创建挑战接口",
            "http_method": "POST",
            "path": "/api/challenges",
        }
        resp = requests.post(full_url(CREATE_TASK_ENDPOINT), files=files, data=data, timeout=30)

    assert resp.status_code == 200, f"创建任务失败: {resp.text}"
    body = resp.json()
    assert body.get("code") == 200, f"业务错误: {body}"
    task_id = body["data"]["task_id"]
    assert task_id, "task_id 不应为空"
    return task_id


# ---------------------------------------------------------------------------
# TC-01: multipart/form-data 上传文档创建任务
# ---------------------------------------------------------------------------

def test_tc01_create_task_with_docx(docs_exist):
    """正向 - form-data 上传 docx 文档，接口应返回 200 及 task_id."""
    with open(DOC_API_DOCX, "rb") as f:
        files = {
            "documents": (
                os.path.basename(DOC_API_DOCX),
                f,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        data = {
            "api_name": "创建挑战接口",
            "http_method": "POST",
            "path": "/api/challenges",
        }
        resp = requests.post(
            full_url(CREATE_TASK_ENDPOINT),
            files=files,
            data=data,
            timeout=30,
        )

    assert resp.status_code == 200, f"HTTP 状态码应为 200，实际为 {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("code") == 200, f"业务 code 应为 200: {body}"
    assert "data" in body, f"响应缺少 data 字段: {body}"
    assert "task_id" in body["data"], f"data 缺少 task_id: {body}"
    assert "status" in body["data"], f"data 缺少 status: {body}"
    assert body["data"]["status"] == "pending", f"初始状态应为 pending: {body['data']}"
    # task_id 应为有效 UUID
    task_id = body["data"]["task_id"]
    try:
        uuid.UUID(task_id)
    except ValueError:
        pytest.fail(f"task_id 不是有效的 UUID: {task_id}")


# ---------------------------------------------------------------------------
# TC-02: JSON 模式上传文本知识创建任务
# ---------------------------------------------------------------------------

def test_tc02_create_task_with_texts_json(docs_exist):
    """正向 - JSON 模式通过 texts 字段传文本，接口应返回 200."""
    payload = {
        "api_name": "查询挑战详情",
        "http_method": "GET",
        "path": "/api/challenges/{id}",
        "api_desc": "根据挑战ID查询挑战详细信息",
        "texts": [
            "挑战接口用于创建新的挑战记录",
            "请求参数：title(必填,string), description(选填,string), difficulty(枚举: easy/medium/hard)",
        ],
    }
    resp = requests.post(
        full_url(CREATE_TASK_ENDPOINT),
        json=payload,
        timeout=30,
    )

    assert resp.status_code == 200, f"HTTP 状态码应为 200: {resp.text}"
    body = resp.json()
    assert body.get("code") == 200, f"业务 code 应为 200: {body}"
    assert "task_id" in body["data"], f"data 缺少 task_id: {body}"
    task_id = body["data"]["task_id"]
    try:
        uuid.UUID(task_id)
    except ValueError:
        pytest.fail(f"task_id 不是有效的 UUID: {task_id}")


# ---------------------------------------------------------------------------
# TC-03: 组合模式（文档 + Base64 图片）创建任务
# ---------------------------------------------------------------------------

def test_tc03_create_task_with_doc_and_image(docs_exist):
    """正向 - 同时传文档和 Base64 图片，接口应正常处理."""
    img_b64 = image_to_base64(DOC_FLOW_PNG)
    payload = {
        "api_name": "流程检查单挑战",
        "http_method": "POST",
        "path": "/api/flow-check",
        "texts": ["这是流程检查的描述信息"],
        "images": [img_b64],
    }
    resp = requests.post(
        full_url(CREATE_TASK_ENDPOINT),
        json=payload,
        timeout=30,
    )

    assert resp.status_code == 200, f"HTTP 状态码应为 200: {resp.text}"
    body = resp.json()
    assert body.get("code") == 200, f"业务 code 应为 200: {body}"
    assert "task_id" in body["data"], f"data 缺少 task_id: {body}"


# ---------------------------------------------------------------------------
# TC-04: 任务创建后轮询状态
# ---------------------------------------------------------------------------

def test_tc04_get_task_status(fresh_task_id):
    """正向 - 查询刚创建的任务状态，应返回完整字段."""
    resp = requests.get(full_url(GET_TASK_ENDPOINT.format(task_id=fresh_task_id)), timeout=30)

    assert resp.status_code == 200, f"HTTP 状态码应为 200: {resp.text}"
    body = resp.json()
    assert body.get("code") == 200, f"业务 code 应为 200: {body}"
    data = body.get("data", {})
    assert data.get("task_id") == fresh_task_id, f"task_id 不匹配: {data}"
    assert data.get("task_type") == "case_generation", f"task_type 应为 case_generation: {data}"
    assert data.get("status") in ("pending", "running", "completed", "failed"), \
        f"status 值非法: {data.get('status')}"
    assert "progress" in data, f"data 缺少 progress: {data}"
    assert "params" in data, f"data 缺少 params: {data}"
    assert "created_at" in data, f"data 缺少 created_at: {data}"
    assert "updated_at" in data, f"data 缺少 updated_at: {data}"


# ---------------------------------------------------------------------------
# TC-05: 任务列表查询
# ---------------------------------------------------------------------------

def test_tc05_list_tasks(fresh_task_id):
    """正向 - 查询任务列表，应包含分页信息和任务数组."""
    resp = requests.get(
        full_url(LIST_TASKS_ENDPOINT),
        params={"page": 1, "page_size": 10},
        timeout=30,
    )

    assert resp.status_code == 200, f"HTTP 状态码应为 200: {resp.text}"
    body = resp.json()
    assert body.get("code") == 200, f"业务 code 应为 200: {body}"
    data = body.get("data", {})
    assert "total" in data, f"data 缺少 total: {data}"
    assert "tasks" in data, f"data 缺少 tasks: {data}"
    assert isinstance(data["tasks"], list), f"tasks 应为数组: {type(data['tasks'])}"
    # 刚才创建的任务应该在列表中
    task_ids = [t["task_id"] for t in data["tasks"]]
    assert fresh_task_id in task_ids, f"刚创建的任务 {fresh_task_id} 未在列表中找到"


# ---------------------------------------------------------------------------
# TC-06: 查询任务关联知识
# ---------------------------------------------------------------------------

def test_tc06_get_task_knowledge(fresh_task_id):
    """正向 - 查询任务关联的知识内容，应返回 knowledge 数组."""
    resp = requests.get(
        full_url(GET_KNOWLEDGE_ENDPOINT.format(task_id=fresh_task_id)),
        timeout=30,
    )

    assert resp.status_code == 200, f"HTTP 状态码应为 200: {resp.text}"
    body = resp.json()
    assert body.get("code") == 200, f"业务 code 应为 200: {body}"
    data = body.get("data", {})
    assert "knowledge" in data, f"data 缺少 knowledge: {data}"
    assert isinstance(data["knowledge"], list), f"knowledge 应为数组: {type(data['knowledge'])}"
    if data["knowledge"]:
        first = data["knowledge"][0]
        assert "id" in first, f"knowledge 条目缺少 id: {first}"
        assert "knowledge_type" in first, f"knowledge 条目缺少 knowledge_type: {first}"
        assert "created_at" in first, f"knowledge 条目缺少 created_at: {first}"


# ---------------------------------------------------------------------------
# TC-07: 缺少必填字段 api_name
# ---------------------------------------------------------------------------

def test_tc07_missing_api_name():
    """反向 - 缺少 api_name，接口应返回错误."""
    with open(DOC_API_DOCX, "rb") as f:
        files = {"documents": (os.path.basename(DOC_API_DOCX), f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        data = {
            "http_method": "POST",
            "path": "/api/challenges",
        }
        resp = requests.post(
            full_url(CREATE_TASK_ENDPOINT),
            files=files,
            data=data,
            timeout=30,
        )

    assert resp.status_code in (200, 400), f"HTTP 状态码应为 200 或 400: {resp.status_code}"
    body = resp.json()
    # code 不应为 200，或者 HTTP 直接返回 400
    if resp.status_code == 200:
        assert body.get("code") != 200, f"缺少必填字段不应返回成功: {body}"
        assert "api_name" in body.get("msg", "").lower(), f"错误信息应提及 api_name: {body}"


# ---------------------------------------------------------------------------
# TC-08: 缺少必填字段 http_method
# ---------------------------------------------------------------------------

def test_tc08_missing_http_method():
    """反向 - 缺少 http_method，接口应返回错误."""
    payload = {
        "api_name": "测试接口",
        "path": "/api/test",
    }
    resp = requests.post(full_url(CREATE_TASK_ENDPOINT), json=payload, timeout=30)

    assert resp.status_code in (200, 400), f"HTTP 状态码应为 200 或 400: {resp.status_code}"
    body = resp.json()
    if resp.status_code == 200:
        assert body.get("code") != 200, f"缺少必填字段不应返回成功: {body}"


# ---------------------------------------------------------------------------
# TC-09: 缺少必填字段 path
# ---------------------------------------------------------------------------

def test_tc09_missing_path():
    """反向 - 缺少 path，接口应返回错误."""
    payload = {
        "api_name": "测试接口",
        "http_method": "GET",
    }
    resp = requests.post(full_url(CREATE_TASK_ENDPOINT), json=payload, timeout=30)

    assert resp.status_code in (200, 400), f"HTTP 状态码应为 200 或 400: {resp.status_code}"
    body = resp.json()
    if resp.status_code == 200:
        assert body.get("code") != 200, f"缺少必填字段不应返回成功: {body}"


# ---------------------------------------------------------------------------
# TC-10: 未提供任何知识来源
# ---------------------------------------------------------------------------

def test_tc10_no_knowledge_source():
    """反向 - 不提供 documents/texts/images，接口应返回错误."""
    payload = {
        "api_name": "测试接口",
        "http_method": "GET",
        "path": "/api/test",
    }
    resp = requests.post(full_url(CREATE_TASK_ENDPOINT), json=payload, timeout=30)

    assert resp.status_code in (200, 400), f"HTTP 状态码应为 200 或 400: {resp.status_code}"
    body = resp.json()
    if resp.status_code == 200:
        assert body.get("code") != 200, f"无知识来源不应返回成功: {body}"
        assert "知识" in body.get("msg", ""), f"错误信息应提及知识: {body}"


# ---------------------------------------------------------------------------
# TC-11: 任务 ID 不存在
# ---------------------------------------------------------------------------

def test_tc11_task_not_found():
    """反向 - 查询不存在的 task_id，应返回 404."""
    fake_id = f"{uuid.uuid4()}"
    resp = requests.get(full_url(GET_TASK_ENDPOINT.format(task_id=fake_id)), timeout=30)

    assert resp.status_code == 404, f"HTTP 状态码应为 404: {resp.status_code}"
    body = resp.json()
    assert body.get("code") == 404, f"业务 code 应为 404: {body}"
    assert "不存在" in body.get("msg", ""), f"错误信息应包含'不存在': {body}"


# ---------------------------------------------------------------------------
# TC-12: 取消 pending 状态任务
# ---------------------------------------------------------------------------

def test_tc12_cancel_pending_task(fresh_task_id):
    """正向 - 取消 pending 状态的任务，应返回 cancelled."""
    resp = requests.delete(
        full_url(CANCEL_TASK_ENDPOINT.format(task_id=fresh_task_id)),
        timeout=30,
    )

    assert resp.status_code == 200, f"HTTP 状态码应为 200: {resp.text}"
    body = resp.json()
    assert body.get("code") == 200, f"业务 code 应为 200: {body}"
    assert body.get("data", {}).get("status") == "cancelled", \
        f"任务状态应为 cancelled: {body}"


# ---------------------------------------------------------------------------
# TC-13: 取消已不存在任务
# ---------------------------------------------------------------------------

def test_tc13_cancel_nonexistent_task():
    """反向 - 取消不存在的任务，应返回 404."""
    fake_id = f"{uuid.uuid4()}"
    resp = requests.delete(
        full_url(CANCEL_TASK_ENDPOINT.format(task_id=fake_id)),
        timeout=30,
    )

    assert resp.status_code == 404, f"HTTP 状态码应为 404: {resp.status_code}"
    body = resp.json()
    assert body.get("code") == 404, f"业务 code 应为 404: {body}"
