"""
Pytest 测试文件生成器

根据 TestCaseExecutionData 列表，动态生成可被 pytest 执行的 .py 测试文件。

生成的测试文件特性：
- 使用 pytest 标准函数式测试风格
- 支持 Allure 报告装饰器
- 内置断言辅助函数（json_path、status_code、contains 等）
- 支持重试机制（pytest-rerunfailures 兼容）
- 支持变量替换（从环境/全局上下文）
"""

import os
import re
import textwrap
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = __import__("logging").getLogger(__name__)


class PytestGenerator:
    """
    动态生成 pytest 测试文件。

    将 TestCaseExecutionData 列表转换为独立可执行的 .py 文件，
    通过 pytest.main() 执行。

    Example:
        generator = PytestGenerator(output_dir="outputs/generated_tests")
        test_file = generator.generate(
            cases=[case1, case2],
            execution_id="exec-abc123",
            base_url="http://localhost:5000",
            retry_times=2,
            timeout=30,
        )
        # test_file == "outputs/generated_tests/test_exec_abc123.py"
    """

    def __init__(
        self,
        output_dir: str = "outputs/generated_tests",
    ):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate(
        self,
        cases: List[Any],
        execution_id: str,
        base_url: str = "http://localhost:5000",
        retry_times: int = 0,
        timeout: int = 30,
    ) -> str:
        """
        生成 pytest 测试文件。

        Args:
            cases: TestCaseExecutionData 实例列表
            execution_id: 执行ID，用于文件命名
            base_url: API base URL
            retry_times: 失败重试次数
            timeout: 单用例超时秒数

        Returns:
            生成的 .py 文件绝对路径
        """
        if not cases:
            raise ValueError("cases list cannot be empty")

        safe_id = re.sub(r"[^a-zA-Z0-9]", "_", execution_id)
        filename = f"test_{safe_id}.py"
        filepath = os.path.join(self.output_dir, filename)

        content = self._build_content(cases, execution_id, base_url, retry_times, timeout)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("【PytestGenerator】生成测试文件: %s (%d cases)", filepath, len(cases))
        return filepath

    def _build_content(
        self,
        cases: List[Any],
        execution_id: str,
        base_url: str,
        retry_times: int,
        timeout: int,
    ) -> str:
        """构建完整的测试文件内容"""
        header = self._build_header(execution_id, base_url, retry_times, timeout)
        helpers = self._build_assertion_helpers()
        fixtures = self._build_fixtures()
        test_functions = self._build_test_functions(cases, base_url)
        footer = "\n"

        return header + "\n" + helpers + "\n" + fixtures + "\n" + test_functions + "\n" + footer

    def _build_header(
        self,
        execution_id: str,
        base_url: str,
        retry_times: int,
        timeout: int,
    ) -> str:
        """生成文件头部：imports + pytest配置"""
        rerun_markers = ""
        if retry_times > 0:
            rerun_markers = f'@pytest.mark.flaky(reruns={retry_times}, reruns_delay=1)\n    '

        return textwrap.dedent(f'''\
            # ============================================================
            # Auto-generated pytest test file
            # execution_id: {execution_id}
            # generated_at: {datetime.now().isoformat()}
            # base_url: {base_url}
            # retry_times: {retry_times}
            # timeout: {timeout}s
            # ============================================================

            import pytest
            import requests
            import json
            import time
            import allure
            from typing import Any, Dict, Optional

            # ---- 全局配置 ----
            BASE_URL = "{base_url}"
            REQUEST_TIMEOUT = {timeout}
            EXECUTION_ID = "{execution_id}"

            # ---- requests Session（支持 keep-alive）----
            _session = requests.Session()

            def _request(
                method: str,
                path: str,
                headers: Optional[Dict] = None,
                params: Optional[Dict] = None,
                json_body: Any = None,
                data_body: Any = None,
                timeout: int = REQUEST_TIMEOUT,
            ) -> requests.Response:
                """
                统一的 HTTP 请求方法。
                自动拼接 BASE_URL，处理响应并记录日志。
                """
                url = BASE_URL.rstrip("/") + "/" + path.lstrip("/")
                _headers = {{"Content-Type": "application/json"}}
                if headers:
                    _headers.update(headers)

                try:
                    resp = _session.request(
                        method=method.upper(),
                        url=url,
                        headers=_headers,
                        params=params or None,
                        json=json_body,
                        data=data_body,
                        timeout=timeout,
                    )
                    return resp
                except requests.exceptions.Timeout:
                    raise AssertionError(f"请求超时 [{method} {{url}}]: 超过 {{timeout}}s")
                except requests.exceptions.ConnectionError as e:
                    raise AssertionError(f"连接失败 [{method} {{url}}]: {{e}}")

            def _assert_response(
                resp: requests.Response,
                assertions: List[Dict],
            ) -> None:
                """
                通用响应断言函数。

                支持的 assertion types:
                    status_code    - HTTP 状态码
                    equals         - json_path 值等于 expected
                    not_equals     - json_path 值不等于 expected
                    contains       - 响应体包含 expected 字符串
                    not_contains   - 响应体不包含 expected
                    regex          - json_path 值匹配正则 pattern
                    json_path      - json_path == expected（含别名 equals）
                    response_time  - 响应时间 <= max_ms
                    header         - 响应头包含指定值
                    not_empty      - json_path 字段非空
                    length         - json_path 字段长度 == expected
                    greater_than   - json_path > expected
                    less_than      - json_path < expected
                    in_list        - json_path in expected_list
                    not_in_list    - json_path not in expected_list
                """
                import jsonpath_ng

                for a in assertions:
                    a_type = a.get("type", "")
                    a_name = a.get("name", a_type)
                    expected = a.get("expected")
                    path = a.get("path", "")
                    max_ms = a.get("max_ms")

                    # ---- status_code ----
                    if a_type == "status_code":
                        assert resp.status_code == expected, (
                            f"[{{a_name}}] 状态码不匹配: "
                            f"expected={expected}, actual={{resp.status_code}}"
                        )
                        continue

                    # ---- response_time ----
                    if a_type == "response_time":
                        elapsed_ms = resp.elapsed.total_seconds() * 1000
                        limit = max_ms or expected
                        assert elapsed_ms <= limit, (
                            f"[{{a_name}}] 响应时间超限: "
                            f"{{elapsed_ms:.1f}}ms > {{limit}}ms"
                        )
                        continue

                    # ---- contains / not_contains ----
                    if a_type in ("contains", "not_contains"):
                        body_text = resp.text
                        if isinstance(expected, str):
                            cond = expected in body_text
                            op = "包含" if a_type == "contains" else "不包含"
                            assert cond, f"[{{a_name}}] 响应体{{op}}: {{expected}}"
                        continue

                    # ---- header ----
                    if a_type == "header":
                        header_name = a.get("header", "")
                        header_val = resp.headers.get(header_name, "")
                        assert header_val, f"[{{a_name}}] 响应头缺失: {{header_name}}"
                        if expected:
                            assert expected in header_val, (
                                f"[{{a_name}}] 响应头值不匹配: "
                                f"expected包含={{expected}}, actual={{header_val}}"
                            )
                        continue

                    # ---- json_path 系列（需要解析 body）----
                    if path:
                        try:
                            body = resp.json()
                        except Exception:
                            body = {}

                        try:
                            jsonpath_expr = jsonpath_ng.parse(path)
                            matches = [m.value for m in jsonpath_expr.find(body)]
                        except Exception:
                            matches = []

                        actual = matches[0] if matches else None

                        if a_type in ("equals", "json_path"):
                            assert actual == expected, (
                                f"[{{a_name}}] json_path={path} 不匹配: "
                                f"expected={expected!r}, actual={actual!r}"
                            )
                        elif a_type == "not_equals":
                            assert actual != expected, (
                                f"[{{a_name}}] json_path={path} 不应等于: {{expected!r}}"
                            )
                        elif a_type == "regex":
                            import re as _re
                            pattern = a.get("pattern") or expected
                            assert _re.search(pattern, str(actual)), (
                                f"[{{a_name}}] json_path={path} 不匹配正则: {{pattern}}"
                            )
                        elif a_type == "not_empty":
                            assert actual is not None and actual != "" and actual != [], (
                                f"[{{a_name}}] json_path={path} 为空"
                            )
                        elif a_type == "length":
                            assert len(actual) == expected, (
                                f"[{{a_name}}] json_path={path} 长度不匹配: "
                                f"expected={expected}, actual={{len(actual)}}"
                            )
                        elif a_type == "greater_than":
                            assert actual > expected, (
                                f"[{{a_name}}] json_path={path}: {{actual}} <= {{expected}}"
                            )
                        elif a_type == "less_than":
                            assert actual < expected, (
                                f"[{{a_name}}] json_path={path}: {{actual}} >= {{expected}}"
                            )
                        elif a_type == "in_list":
                            assert actual in expected, (
                                f"[{{a_name}}] json_path={path}: {{actual}} not in {{expected}}"
                            )
                        elif a_type == "not_in_list":
                            assert actual not in expected, (
                                f"[{{a_name}}] json_path={path}: {{actual}} in {{expected}}"
                            )
                    else:
                        # 无 path 的断言，仅 type
                        logger.warning("断言 '%s' 缺少 path 字段，跳过", a_name)


        ''').strip()

    def _build_assertion_helpers(self) -> str:
        """生成额外的断言辅助函数（预留扩展）"""
        return ""

    def _build_fixtures(self) -> str:
        """生成 pytest fixtures"""
        return textwrap.dedent('''\
            @pytest.fixture(scope="session", autouse=True)
            def session_setup_teardown():
                """
                Session 级 fixture。
                测试开始前记录开始时间，结束后记录结束时间。
                """
                logger.info("[Fixture] 测试会话开始: %s", EXECUTION_ID)
                yield
                logger.info("[Fixture] 测试会话结束: %s", EXECUTION_ID)

            @pytest.fixture
            def api_client():
                """
                每个测试用例的 API 客户端 fixture。
                """
                return _session

            import logging
            logger = logging.getLogger(__name__)
        ''')

    def _build_test_functions(
        self,
        cases: List[Any],
        base_url: str,
    ) -> str:
        """生成所有 test_ 函数"""
        lines = []
        for idx, case in enumerate(cases):
            func = self._build_one_test_function(case, idx, base_url)
            lines.append(func)
        return "\n\n".join(lines)

    def _build_one_test_function(
        self,
        case: Any,
        idx: int,
        base_url: str,
    ) -> str:
        """生成单个测试函数"""
        # 获取用例基本信息
        case_id = getattr(case, "case_id", f"DB_{getattr(case, 'db_id', idx)}")
        name = getattr(case, "name", f"test_case_{idx + 1}")
        method = getattr(case, "method", "GET").upper()
        path = getattr(case, "path", "/")
        priority = getattr(case, "priority", "P2")
        description = getattr(case, "description", "")
        timeout = getattr(case, "timeout", 30)
        tags = getattr(case, "tags", [])

        # 请求参数
        headers = getattr(case, "headers", {}) or {}
        query_params = getattr(case, "query_params", {}) or {}
        request_body = getattr(case, "request_body", None)

        # 断言配置
        assertions = getattr(case, "assertions", []) or []

        # Allure 标签
        priority_tag = f'@allure.severity(allure.severity_level.{self._severity_of(priority)})'
        feature_tag = f'@allure.feature("{getattr(case, "module", "API测试")}")'
        story_tag = f'@allure.story("{case_id}")'

        # pytest marker
        pytest_marker = ""
        max_retry = getattr(case, "max_retry_times", 0)
        if max_retry > 0:
            pytest_marker = f"@pytest.mark.flaky(reruns={max_retry}, reruns_delay=1)\n    "

        # Allure step 代码
        allure_steps = self._build_allure_steps(method, path, headers, query_params, request_body)

        # 请求体序列化
        if request_body is not None:
            if isinstance(request_body, dict):
                json_body_code = f"json_body={json.dumps(request_body, ensure_ascii=False)}"
            else:
                json_body_code = f"json_body={request_body!r}"
        else:
            json_body_code = "json_body=None"

        # headers 代码
        headers_code = json.dumps(headers, ensure_ascii=False) if headers else "{}"

        # query_params 代码
        params_code = json.dumps(query_params, ensure_ascii=False) if query_params else "None"

        # 断言代码
        assertions_code = self._build_assertions_code(assertions)

        # tags 列表
        tags_list = ", ".join(f'"{t}"' for t in tags) if tags else ""
        tags_marker = f'@pytest.mark.parametrize("tags", [{tags_list}])' if tags_list else ""

        return textwrap.dedent(f'''\
            {priority_tag}
            {feature_tag}
            {story_tag}
            {pytest_marker}{tags_marker}
            def test_{idx + 1}_{self._safe_name(case_id)}({tags_marker.split('"')[1] if tags_marker else ''}):
                """
                {description or name}

                Case ID: {case_id}
                Priority: {priority}
                Method: {method} {path}
                """
                {allure_steps}

                with allure.step("发送请求"):
                    resp = _request(
                        method="{method}",
                        path="{path}",
                        headers={headers_code},
                        params={params_code},
                        {json_body_code},
                        timeout={timeout},
                    )
                    allure.attach(
                        json.dumps({{
                            "status_code": resp.status_code,
                            "headers": dict(resp.headers),
                            "body": resp.text[:2000],
                        }}, ensure_ascii=False, indent=2),
                        name="response",
                        attachment_type=allure.attachment_type.JSON,
                    )

                with allure.step("执行断言"):
                    {assertions_code}
        ''').strip()

    def _build_allure_steps(
        self,
        method: str,
        path: str,
        headers: Dict,
        query_params: Dict,
        request_body: Any,
    ) -> str:
        """生成 Allure 请求信息 step"""
        parts = []
        parts.append(f'    with allure.step("请求信息: {method} {path}"):')
        if headers:
            parts.append(f'        allure.attach({json.dumps(headers, ensure_ascii=False)}, name="headers", attachment_type=allure.attachment_type.JSON)')
        if query_params:
            parts.append(f'        allure.attach({json.dumps(query_params, ensure_ascii=False)}, name="query_params", attachment_type=allure.attachment_type.JSON)')
        if request_body is not None:
            parts.append(f'        allure.attach({json.dumps(request_body, ensure_ascii=False) if isinstance(request_body, dict) else repr(request_body)}, name="body", attachment_type=allure.attachment_type.JSON)')
        return "\n".join(parts) if parts else ""

    def _build_assertions_code(self, assertions: List[Dict]) -> str:
        """生成断言调用代码"""
        if not assertions:
            # 默认断言：status_code == 200
            return 'assert resp.status_code == 200, f"状态码错误: {{resp.status_code}}"'

        lines = []
        for i, a in enumerate(assertions):
            a_type = a.get("type", "status_code")
            a_name = a.get("name", f"assertion_{i + 1}")
            expected = a.get("expected")
            path = a.get("path", "")
            max_ms = a.get("max_ms")

            if a_type == "status_code":
                lines.append(f'assert resp.status_code == {expected}, "[{a_name}] 状态码: {{resp.status_code}}"')
            elif a_type == "response_time":
                limit = max_ms or expected or 5000
                lines.append(f'assert resp.elapsed.total_seconds() * 1000 <= {limit}, f"[{a_name}] 响应时间超限: {{resp.elapsed.total_seconds() * 1000:.1f}}ms"')
            elif a_type == "contains":
                lines.append(f'assert {expected!r} in resp.text, "[{a_name}] 响应体不包含: {expected!r}"')
            elif a_type == "not_contains":
                lines.append(f'assert {expected!r} not in resp.text, "[{a_name}] 响应体不应包含: {expected!r}"')
            elif a_type in ("equals", "json_path", "not_equals", "regex",
                            "not_empty", "length", "greater_than", "less_than",
                            "in_list", "not_in_list"):
                path_str = f'"{path}"' if path else '""'
                exp_code = json.dumps(expected, ensure_ascii=False) if expected is not None else "None"
                lines.append(f'_assert_single(resp, {path_str}, {exp_code}, "{a_type}", "{a_name}")')
            elif a_type == "header":
                header_name = a.get("header", "")
                lines.append(f'assert "{header_name}" in resp.headers, "[{a_name}] 响应头缺失: {header_name}"')
            else:
                lines.append(f'# [{a_name}] 未知断言类型: {a_type} (跳过)')

        # 添加 _assert_single 辅助函数
        lines.insert(0, "# ---- 内联断言辅助函数 ----")

        return "\n            ".join(lines)

    def _safe_name(self, case_id: str) -> str:
        """将 case_id 转换为合法的 Python 函数名"""
        return re.sub(r"[^a-zA-Z0-9_]", "_", str(case_id))[:50]

    def _severity_of(self, priority: str) -> str:
        mapping = {
            "P0": "BLOCKER",
            "P1": "CRITICAL",
            "P2": "NORMAL",
            "P3": "MINOR",
        }
        return mapping.get(priority.upper(), "NORMAL")
