"""
expected_results 格式解析器

定义 test_case.expected_results 的标准格式，
并将其转换为 AssertionEngine / AssertionExecutor 可执行的断言格式。

支持的 expected_results 格式：

格式1: 简单字典（向后兼容）
{
    "code": 0,
    "message": "success"
}
→ 自动转换为 status_code + json_path 断言

格式2: 结构化断言列表（推荐）
{
    "assertions": [
        {"type": "status_code", "expected": 200},
        {"type": "json_path", "path": "$.code", "expected": 0},
        {"type": "contains", "expected": "success"}
    ]
}

格式3: 仅响应时间
{
    "response_time_ms": 500
}

格式4: 混合模式
{
    "default": {"code": 0, "message": "success"},
    "assertions": [
        {"type": "response_time", "max_ms": 500}
    ]
}
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExpectedResultsParser:
    """
    expected_results 解析器。

    将 test_case.expected_results JSON 字段解析为标准断言列表，
    格式兼容 assertion/validators.py 的 AssertionExecutor。
    """

    # 与 AssertionExecutor.VALIDATORS 保持一致
    SUPPORTED_TYPES = {
        "status_code", "equals", "not_equals", "contains", "not_contains",
        "regex", "json_path", "response_time", "schema", "header",
        "type", "length", "greater_than", "less_than",
        "in_list", "not_in_list", "not_empty",
    }

    def parse(self, expected_results: Any) -> List[Dict[str, Any]]:
        """
        将 expected_results 解析为断言列表。

        Args:
            expected_results: test_case.expected_results 字段值（dict/list/str）

        Returns:
            List[Dict]: 断言配置列表，格式兼容 AssertionExecutor
        """
        if expected_results is None:
            return []

        if isinstance(expected_results, list):
            return self._parse_assertion_list(expected_results)

        if isinstance(expected_results, dict):
            if "assertions" in expected_results:
                # 格式2: 显式断言列表
                return self._parse_assertion_list(expected_results["assertions"])

            if "default" in expected_results:
                # 格式4: 混合模式
                result = self._parse_simple_dict(expected_results["default"])
                extra = expected_results.get("assertions", [])
                if extra:
                    result.extend(self._parse_assertion_list(extra))
                return result

            # 格式3: 仅响应时间
            if "response_time_ms" in expected_results:
                return [{
                    "type": "response_time",
                    "max_ms": expected_results["response_time_ms"],
                    "name": "response_time_check",
                }]

            # 格式1: 简单字典（向后兼容）
            return self._parse_simple_dict(expected_results)

        if isinstance(expected_results, str):
            # 字符串格式：转为 contains 断言
            return [{"type": "contains", "expected": expected_results, "name": "text_contains"}]

        logger.warning("未知的 expected_results 格式: %s", type(expected_results))
        return []

    def _parse_assertion_list(self, assertions: List) -> List[Dict[str, Any]]:
        """解析显式断言列表"""
        result = []
        for a in assertions:
            if not isinstance(a, dict):
                continue

            a_type = a.get("type", "equals")
            if a_type not in self.SUPPORTED_TYPES:
                logger.warning("不支持的断言类型: %s", a_type)
                continue

            normalized = {
                "type": a_type,
                "expected": a.get("expected"),
                "path": a.get("path"),
                "name": a.get("name") or f"{a_type}:{a.get('path', '')}",
                "case_sensitive": a.get("case_sensitive", True),
                "enabled": a.get("enabled", True),
                "operator": a.get("operator"),
                "max_ms": a.get("max_ms"),
                "schema": a.get("schema"),
                "pattern": a.get("pattern"),
                "header": a.get("header"),
            }
            # 移除 None 值以保持干净
            normalized = {k: v for k, v in normalized.items() if v is not None}
            result.append(normalized)

        return result

    def _parse_simple_dict(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        将简单字典转为断言列表。

        规则：
        - status_code 字段 → status_code 断言
        - code 字段（且值为数字）→ json_path $.code 断言
        - message 字段 → contains 断言
        - data 字段（存在且非空）→ not_empty 断言
        - 其他顶层字段 → json_path equals 断言
        """
        result = []

        # status_code
        if "status_code" in data:
            result.append({
                "type": "status_code",
                "expected": data["status_code"],
                "name": "status_code_check",
            })

        # code (业务状态码)
        if "code" in data and isinstance(data["code"], (int, float)):
            result.append({
                "type": "json_path",
                "path": "$.code",
                "expected": data["code"],
                "name": "business_code_check",
            })

        # message
        if "message" in data and data["message"]:
            msg = str(data["message"])
            result.append({
                "type": "contains",
                "expected": msg,
                "name": "message_check",
            })

        # data 字段（验证非空）
        if "data" in data:
            result.append({
                "type": "not_empty",
                "path": "$.data",
                "name": "data_not_empty",
            })

        # 其他顶层字段
        skip_keys = {"status_code", "code", "message", "data", "token", "session_id"}
        for key, value in data.items():
            if key in skip_keys:
                continue
            if isinstance(value, (int, float, bool, str)):
                result.append({
                    "type": "equals",
                    "path": f"$.{key}",
                    "expected": value,
                    "name": f"field_{key}_check",
                })

        return result
