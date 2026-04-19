"""
断言自动生成模块

提供基于响应自动生成断言的功能:
- AssertionGenerator: 根据HTTP响应自动生成断言列表
"""

import json
import logging
from typing import Any, Dict, List, Optional

from common.assertion.validators import AssertionExecutor

logger = logging.getLogger(__name__)


class AssertionGenerator:
    """断言自动生成器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.default_status_codes = self.config.get("default_status_codes", [200, 201, 204])
        self.default_response_time_ms = self.config.get("default_response_time_ms", 5000)
        self.include_status_code = self.config.get("include_status_code", True)
        self.include_response_time = self.config.get("include_response_time", True)
        self.include_json_path = self.config.get("include_json_path", True)
        self.include_contains = self.config.get("include_contains", False)
        self.include_schema = self.config.get("include_schema", False)

    def generate_from_response(
        self,
        response: Any,
        response_time_ms: Optional[float] = None,
        expected_status_code: int = 200,
    ) -> List[Dict[str, Any]]:
        assertions = []
        status_code = self._get_status_code(response)
        body = self._get_body(response)
        headers = self._get_headers(response)

        if self.include_status_code:
            assertions.append({
                "type": "status_code",
                "expected": expected_status_code,
            })

        if self.include_response_time and response_time_ms is not None:
            assertions.append({
                "type": "response_time",
                "max_ms": self.default_response_time_ms,
                "response_time_ms": response_time_ms,
            })

        if self.include_json_path and body:
            json_assertions = self._generate_json_path_assertions(body)
            assertions.extend(json_assertions)

        if self.include_contains and body:
            contains_assertions = self._generate_contains_assertions(body, headers)
            assertions.extend(contains_assertions)

        if self.include_schema and body:
            schema_assertions = self._generate_schema_assertions(body)
            assertions.extend(schema_assertions)

        return assertions

    def generate_from_sample(
        self,
        sample_response: Dict[str, Any],
        expected_status_code: int = 200,
    ) -> List[Dict[str, Any]]:
        assertions = []
        if self.include_status_code:
            assertions.append({"type": "status_code", "expected": expected_status_code})
        body = sample_response.get("body") or sample_response
        headers = sample_response.get("headers", {})
        if self.include_json_path and body:
            assertions.extend(self._generate_json_path_assertions(body))
        if self.include_contains:
            assertions.extend(self._generate_contains_assertions(body, headers))
        if self.include_schema:
            assertions.extend(self._generate_schema_assertions(body))
        return assertions

    def generate_from_api_spec(self, api_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        assertions = []
        responses = api_spec.get("responses", {})
        for status_code, response_spec in responses.items():
            if not status_code.isdigit():
                continue
            code = int(status_code)
            if code < 200 or code >= 300:
                continue
            content = response_spec.get("content", {})
            if not content:
                continue
            json_content = content.get("application/json")
            if not json_content:
                continue
            schema = json_content.get("schema")
            if schema:
                assertions.append({
                    "type": "schema",
                    "schema": schema,
                    "description": f"响应状态码 {code} 的Schema验证",
                })
        return assertions

    def _generate_json_path_assertions(self, body: Any, path_prefix: str = "$") -> List[Dict[str, Any]]:
        assertions = []
        if isinstance(body, dict):
            for key, value in body.items():
                current_path = f"{path_prefix}.{key}"
                if key in ("code", "status", "ret", "resultCode", "errorCode"):
                    assertions.append({
                        "type": "json_path",
                        "path": current_path,
                        "expected": 0,
                        "description": f"验证 {key} 为成功状态",
                    })
                elif key in ("message", "msg", "errorMessage", "errorMsg"):
                    assertions.append({
                        "type": "contains",
                        "expected": "success",
                        "path": current_path,
                        "case_sensitive": False,
                        "description": f"验证 {key} 包含成功消息",
                    })
                elif isinstance(value, dict):
                    assertions.extend(self._generate_json_path_assertions(value, current_path))
                elif isinstance(value, list) and value:
                    first_item = value[0]
                    if isinstance(first_item, dict):
                        item_path = f"{current_path}[0]"
                        assertions.extend(self._generate_json_path_assertions(first_item, item_path))
        return assertions

    def _generate_contains_assertions(self, body: Any, headers: Dict[str, str]) -> List[Dict[str, Any]]:
        assertions = []
        content_type = headers.get("Content-Type", headers.get("content-type", ""))
        if "application/json" in content_type:
            assertions.append({
                "type": "header",
                "header": "Content-Type",
                "expected": "application/json",
            })
        return assertions

    def _generate_schema_assertions(self, body: Any) -> List[Dict[str, Any]]:
        if not isinstance(body, dict):
            return []
        schema = self._generate_schema_from_response(body)
        if schema:
            return [{"type": "schema", "schema": schema, "description": "响应体Schema验证"}]
        return []

    def _generate_schema_from_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(response, dict):
            return {}
        properties = {}
        required = []
        for key, value in response.items():
            schema_type, value_schema = self._get_json_schema_type(value)
            properties[key] = value_schema
            if key in ("code", "status", "message", "msg"):
                required.append(key)
        if not properties:
            return {}
        schema = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        return schema

    def _get_json_schema_type(self, value: Any) -> tuple:
        if value is None:
            return "null", {"type": "null"}
        if isinstance(value, bool):
            return "boolean", {"type": "boolean"}
        if isinstance(value, int):
            return "integer", {"type": "integer"}
        if isinstance(value, float):
            return "number", {"type": "number"}
        if isinstance(value, str):
            return "string", {"type": "string"}
        if isinstance(value, list):
            if value:
                _, item_schema = self._get_json_schema_type(value[0])
                return "array", {"type": "array", "items": item_schema}
            return "array", {"type": "array"}
        if isinstance(value, dict):
            properties = {}
            for k, v in value.items():
                _, prop_schema = self._get_json_schema_type(v)
                properties[k] = prop_schema
            return "object", {"type": "object", "properties": properties}
        return "string", {"type": "string"}

    def _get_status_code(self, response: Any) -> int:
        if hasattr(response, "status_code"):
            return response.status_code
        if isinstance(response, dict):
            return response.get("status_code", 0)
        return 0

    def _get_body(self, response: Any) -> Any:
        if hasattr(response, "json"):
            try:
                return response.json()
            except Exception:
                pass
        if hasattr(response, "text"):
            text = response.text
            try:
                return json.loads(text)
            except Exception:
                return text
        if isinstance(response, dict):
            return response.get("body", response)
        return response

    def _get_headers(self, response: Any) -> Dict[str, str]:
        if hasattr(response, "headers"):
            return dict(response.headers)
        if isinstance(response, dict):
            return response.get("headers", {})
        return {}

    def generate_assertions_for_test_case(self, test_case: Dict[str, Any]) -> List[Dict[str, Any]]:
        assertions = []
        test_data = test_case.get("test_data", {})
        expected = test_case.get("expect", "")
        assertions.append({"type": "status_code", "expected": test_case.get("status_code", 200)})
        if expected:
            assertions.append({"type": "contains", "expected": expected, "case_sensitive": False})
        return assertions


class SmartAssertionGenerator(AssertionGenerator):
    """智能断言生成器 - 基于AI的更智能的断言生成"""

    def __init__(self, config: Optional[Dict[str, Any]] = None, llm_client=None):
        super().__init__(config)
        self.llm_client = llm_client

    def generate_smart_assertions(
        self,
        response: Any,
        response_time_ms: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        base_assertions = self.generate_from_response(response, response_time_ms)
        if not self.llm_client:
            return base_assertions
        try:
            ai_assertions = self._generate_ai_assertions(response, context)
            base_assertions.extend(ai_assertions)
        except Exception as e:
            logger.warning(f"AI断言生成失败: {e}")
        return base_assertions

    def _generate_ai_assertions(self, response: Any, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        body = self._get_body(response)
        headers = self._get_headers(response)
        prompt = self._build_assertion_prompt(body, headers, context)
        try:
            llm_response = self.llm_client.complete(prompt, max_tokens=1024)
            return self._parse_ai_response(llm_response)
        except Exception as e:
            logger.error(f"AI断言生成异常: {e}")
            return []

    def _build_assertion_prompt(self, body: Any, headers: Dict[str, str], context: Optional[Dict[str, Any]] = None) -> str:
        body_str = json.dumps(body, ensure_ascii=False, indent=2)
        headers_str = json.dumps(headers, ensure_ascii=False, indent=2)
        prompt = f"""你是一个API测试专家。基于以下API响应，生成适合的断言列表。

响应头:
{headers_str}

响应体:
{body_str}
"""
        if context:
            prompt += f"""
上下文信息:
- API路径: {context.get('path', '')}
- 请求方法: {context.get('method', '')}
- 接口描述: {context.get('description', '')}
"""
        prompt += """
请生成JSON格式的断言列表，格式如下:
[
    {"type": "status_code", "expected": 200},
    {"type": "json_path", "path": "$.code", "expected": 0},
    {"type": "contains", "expected": "success"},
    {"type": "schema", "schema": {...}}
]

只输出JSON数组，不要其他文字。
"""
        return prompt

    def _parse_ai_response(self, response: str) -> List[Dict[str, Any]]:
        try:
            data = json.loads(response)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
        import re
        match = re.search(r'\[[\s\S]*\]', response)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return []


def create_assertion_executor(assertions: Optional[List[Dict[str, Any]]] = None) -> AssertionExecutor:
    """创建断言执行器的便捷函数"""
    return AssertionExecutor(assertions)


def generate_assertions(
    response: Any,
    response_time_ms: Optional[float] = None,
    expected_status_code: int = 200,
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """生成断言的便捷函数"""
    generator = AssertionGenerator(config)
    return generator.generate_from_response(response, response_time_ms, expected_status_code)
