import json
import os
import tempfile

from common.llm.ai_case_generator import generate_api_test_cases
from common.llm.llm_client import LLMClient


class FakeLLM(LLMClient):
    """固定返回预置JSON的假客户端，用于单元测试。"""

    def __init__(self, payload):
        self.payload = payload

    def complete(self, prompt: str, **kwargs) -> str:
        return json.dumps(self.payload, ensure_ascii=False)


def test_generate_cases_normalized_and_persisted():
    mock_cases = [
        {
            "title": "缺失必填字段name",
            "priority": "p1",
            "request": {"method": "POST", "path": "/api/user/create", "body": {}},
            "status_code": 400,
            "assertions": [{"path": "code", "equals": "MISSING_NAME"}],
        },
        {
            "id": "case-002",
            "title": "合法创建用户",
            "priority": "P0",
            "request": {"method": "POST", "path": "/api/user/create", "body": {"name": "张三", "age": 18}},
            "status_code": 200,
            "assertions": [{"path": "data.id", "exists": True}],
        },
    ]
    client = FakeLLM(mock_cases)
    with tempfile.TemporaryDirectory() as tmpdir:
        result = generate_api_test_cases(
            api_name="创建用户",
            api_desc="创建用户接口",
            http_method="POST",
            path="/api/user/create",
            params_example={"name": "张三", "age": 18},
            headers={"Authorization": "Bearer token"},
            llm_client=client,
            persist_dir=tmpdir,
            max_cases=5,
        )

        assert result["review_id"]
        assert len(result["cases"]) == 2
        # 校验补全与格式标准化
        case0 = result["cases"][0]
        assert case0["priority"] == "P1"
        assert case0["request"]["headers"] == {}
        # 校验落盘
        assert os.path.exists(result["persist_path"])
        with open(result["persist_path"], "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["review_id"] == result["review_id"]
        assert len(saved["cases"]) == 2




