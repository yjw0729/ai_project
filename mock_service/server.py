"""
Mock Server 模块。

提供模拟依赖接口服务，支持：
- 规则注册和管理
- 请求匹配（支持正则 URL）
- 响应生成（支持延迟模拟）
- 动态响应（支持函数生成响应）

使用示例：
    from mock_service.server import MockServer, MockRule

    server = MockServer()
    rule = MockRule(
        id="rule_001",
        method="GET",
        url_pattern=r"/api/users/\\d+",
        response_status=200,
        response_body={"id": 1, "name": "test"},
        response_headers={"Content-Type": "application/json"},
        priority=1,
        delay=0.5
    )
    server.register(rule)

    # 模拟请求
    result = server.match_request("GET", "/api/users/123")
    if result:
        response = server.get_response(result)
"""

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
from threading import Lock

import pytest


@dataclass
class MockRule:
    """
    Mock 规则实体类。

    用于定义模拟接口的规则，包括请求匹配条件和响应内容。

    Attributes:
        id: 规则唯一标识
        method: HTTP 方法（如 GET、POST、PUT、DELETE）
        url_pattern: URL 匹配模式，支持正则表达式
        response_status: HTTP 响应状态码
        response_body: 响应体内容，可以是任意类型
        response_headers: 响应头字典
        priority: 规则优先级，数字越大优先级越高
        delay: 延迟响应时间（秒），默认 0
        call_count: 调用次数，默认 0
    """
    id: str
    method: str
    url_pattern: str
    response_status: int
    response_body: Any
    response_headers: Dict[str, str]
    priority: int
    delay: float = 0
    call_count: int = 0

    def __post_init__(self):
        """初始化后验证和转换"""
        # 编译正则表达式
        try:
            self._regex = re.compile(self.url_pattern)
        except re.error:
            self._regex = re.compile(re.escape(self.url_pattern))

    def match(self, method: str, url: str) -> bool:
        """
        检查请求是否匹配此规则。

        Args:
            method: HTTP 方法
            url: 请求 URL

        Returns:
            是否匹配
        """
        return (
            self.method.upper() == method.upper()
            and self._regex.match(url) is not None
        )

    def increment_call_count(self) -> None:
        """增加调用次数"""
        self.call_count += 1


class MockServer:
    """
    Mock 服务器类。

    提供模拟 HTTP 服务的核心功能，支持规则管理、请求匹配、
    响应生成和延迟模拟。

    Attributes:
        rules: 已注册的规则列表
        _lock: 线程锁，用于并发安全
    """

    def __init__(self):
        """
        初始化 MockServer。
        """
        self.rules: List[MockRule] = []
        self._lock = Lock()
        self._dynamic_response_handlers: Dict[str, Callable] = {}

    def register(
        self,
        rule: MockRule,
        dynamic_response: Optional[Callable] = None
    ) -> None:
        """
        注册 Mock 规则。

        Args:
            rule: MockRule 实例
            dynamic_response: 可选的动态响应函数，签名为 func(request) -> response
        """
        with self._lock:
            # 检查是否已存在相同 ID 的规则
            existing = [r for r in self.rules if r.id == rule.id]
            if existing:
                self.rules.remove(existing[0])

            self.rules.append(rule)

            if dynamic_response:
                self._dynamic_response_handlers[rule.id] = dynamic_response

            # 按优先级排序
            self.rules.sort(key=lambda r: r.priority, reverse=True)

    def unregister(self, rule_id: str) -> bool:
        """
        注销指定 ID 的规则。

        Args:
            rule_id: 规则 ID

        Returns:
            是否成功注销
        """
        with self._lock:
            for rule in self.rules:
                if rule.id == rule_id:
                    self.rules.remove(rule)
                    self._dynamic_response_handlers.pop(rule_id, None)
                    return True
            return False

    def match_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Any] = None
    ) -> Optional[MockRule]:
        """
        匹配请求到规则。

        Args:
            method: HTTP 方法
            url: 请求 URL
            headers: 请求头（可选）
            body: 请求体（可选）

        Returns:
            匹配的 MockRule，如果没有匹配的规则返回 None
        """
        with self._lock:
            for rule in self.rules:
                if rule.match(method, url):
                    rule.increment_call_count()
                    return rule
            return None

    def get_response(
        self,
        rule: MockRule,
        request: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        获取规则对应的响应。

        Args:
            rule: 匹配的 MockRule
            request: 请求信息（可选），包含 method, url, headers, body

        Returns:
            响应字典，包含 status, body, headers, delay
        """
        response = {
            "status": rule.response_status,
            "body": rule.response_body,
            "headers": rule.response_headers,
            "delay": rule.delay
        }

        # 检查是否有动态响应处理器
        if rule.id in self._dynamic_response_handlers:
            handler = self._dynamic_response_handlers[rule.id]
            try:
                dynamic_body = handler(request or {})
                response["body"] = dynamic_body
            except Exception as e:
                response["body"] = {"error": str(e)}
                response["status"] = 500

        return response

    def simulate_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Any] = None
    ) -> Optional[Dict[str, Any]]:
        """
        模拟完整的请求-响应流程。

        Args:
            method: HTTP 方法
            url: 请求 URL
            headers: 请求头（可选）
            body: 请求体（可选）

        Returns:
            响应字典，如果没有匹配的规则返回 None
        """
        request = {
            "method": method,
            "url": url,
            "headers": headers or {},
            "body": body
        }

        rule = self.match_request(method, url, headers, body)
        if rule is None:
            return None

        response = self.get_response(rule, request)

        # 模拟延迟
        if response["delay"] > 0:
            time.sleep(response["delay"])

        return response

    def get_rule(self, rule_id: str) -> Optional[MockRule]:
        """
        根据 ID 获取规则。

        Args:
            rule_id: 规则 ID

        Returns:
            MockRule 实例，如果不存在返回 None
        """
        with self._lock:
            for rule in self.rules:
                if rule.id == rule_id:
                    return rule
            return None

    def get_all_rules(self) -> List[MockRule]:
        """
        获取所有已注册的规则。

        Returns:
            规则列表
        """
        with self._lock:
            return list(self.rules)

    def clear(self) -> None:
        """
        清除所有已注册的规则。
        """
        with self._lock:
            self.rules.clear()
            self._dynamic_response_handlers.clear()

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取 Mock 服务器统计信息。

        Returns:
            统计信息字典
        """
        with self._lock:
            total_calls = sum(rule.call_count for rule in self.rules)
            return {
                "total_rules": len(self.rules),
                "total_calls": total_calls,
                "rules": [
                    {
                        "id": rule.id,
                        "method": rule.method,
                        "url_pattern": rule.url_pattern,
                        "priority": rule.priority,
                        "call_count": rule.call_count
                    }
                    for rule in self.rules
                ]
            }

    def create_rule(
        self,
        method: str,
        url_pattern: str,
        response_status: int = 200,
        response_body: Any = None,
        response_headers: Optional[Dict[str, str]] = None,
        priority: int = 0,
        delay: float = 0,
        name: Optional[str] = None
    ) -> MockRule:
        """
        创建并注册规则。

        Args:
            method: HTTP 方法
            url_pattern: URL 匹配模式
            response_status: 响应状态码
            response_body: 响应体
            response_headers: 响应头
            priority: 优先级
            delay: 延迟时间
            name: 规则名称

        Returns:
            创建的 MockRule 实例
        """
        rule_id = str(uuid.uuid4())[:8]
        if name:
            rule_id = name

        rule = MockRule(
            id=rule_id,
            method=method,
            url_pattern=url_pattern,
            response_status=response_status,
            response_body=response_body or {},
            response_headers=response_headers or {"Content-Type": "application/json"},
            priority=priority,
            delay=delay
        )

        self.register(rule)
        return rule


# ==================== Pytest Fixtures ====================

@pytest.fixture
def mock_server():
    """
    Mock Server Pytest Fixture。

    提供一个干净的 MockServer 实例，测试完成后自动清理。

    Usage:
        def test_example(mock_server):
            rule = MockRule(
                id="test_rule",
                method="GET",
                url_pattern="/api/test",
                response_status=200,
                response_body={"message": "ok"},
                response_headers={"Content-Type": "application/json"},
                priority=1
            )
            mock_server.register(rule)

            result = mock_server.simulate_request("GET", "/api/test")
            assert result["status"] == 200
            assert result["body"]["message"] == "ok"

    Yields:
        MockServer: MockServer 实例
    """
    server = MockServer()
    yield server
    server.clear()


@pytest.fixture
def mock_rule():
    """
    创建测试用 MockRule 的 Fixture。

    Args:
        method: HTTP 方法
        url_pattern: URL 模式
        response_status: 响应状态码
        response_body: 响应体

    Returns:
        MockRule: 配置好的规则实例
    """
    def _create_rule(
        method: str = "GET",
        url_pattern: str = "/api/test",
        response_status: int = 200,
        response_body: Any = None,
        **kwargs
    ) -> MockRule:
        return MockRule(
            id=str(uuid.uuid4())[:8],
            method=method,
            url_pattern=url_pattern,
            response_status=response_status,
            response_body=response_body or {"test": "data"},
            response_headers=kwargs.get("response_headers", {"Content-Type": "application/json"}),
            priority=kwargs.get("priority", 0),
            delay=kwargs.get("delay", 0)
        )
    return _create_rule


# ==================== 模块导出 ====================

__all__ = [
    "MockRule",
    "MockServer",
    "mock_server",
    "mock_rule",
]
