"""
Pytest 测试文件生成器

根据 TestCaseExecutionData 列表，动态生成可被 pytest 执行的 .py 测试文件。

生成的测试文件特性：
|- 使用 pytest 标准函数式测试风格
|- 支持 Allure 报告装饰器
|- 内置断言辅助函数（json_path、status_code、contains 等）
|- 支持重试机制（pytest-rerunfailures 兼容）
|- 支持变量替换（从环境/全局上下文），生成阶段自动解析
"""

import json
import os
import re
import textwrap
from datetime import datetime
from typing import Any, Dict, List, Optional

from common.test_executor.parameter_resolver import ParameterResolver

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
            global_variables={"token": "abc123", "user_id": 100},
        )
        # test_file == "outputs/generated_tests/test_exec_abc123.py"
    """

    def __init__(
        self,
        output_dir: str = "outputs/generated_tests",
    ):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def _json_dumps(self, obj: Any, ensure_ascii: bool = False) -> str:
        """
        生成 Python 代码兼容的 JSON 字符串，将 null 替换为 None

        原因：Python 代码中 None 是 null 的等价形式，
        而 json.dumps 输出的 'null' 在运行时会被当作字符串 'null' 而非 Python None。
        """
        result = json.dumps(obj, ensure_ascii=ensure_ascii)
        return result.replace('null', 'None')

    def generate(
        self,
        cases: List[Any],
        execution_id: str,
        base_url: str = "http://localhost:5000",
        retry_times: int = 0,
        timeout: int = 30,
        global_variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        生成 pytest 测试文件。

        Args:
            cases: TestCaseExecutionData 实例列表
            execution_id: 执行ID，用于文件命名
            base_url: API base URL
            retry_times: 失败重试次数
            timeout: 单用例超时秒数
            global_variables: 全局变量字典，用于变量替换（如 {"token": "xxx", "user_id": 123}）

        Returns:
            生成的 .py 文件绝对路径
        """
        if not cases:
            raise ValueError("cases list cannot be empty")

        safe_id = re.sub(r"[^a-zA-Z0-9]", "_", execution_id)
        filename = f"test_{safe_id}.py"
        filepath = os.path.join(self.output_dir, filename)

        # 初始化变量解析器
        resolver = ParameterResolver(global_variables=global_variables or {})

        content = self._build_content(
            cases, execution_id, base_url, retry_times, timeout, resolver
        )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(
            "【PytestGenerator】生成测试文件: %s (%d cases), 全局变量数量: %d",
            filepath, len(cases), len(global_variables or {})
        )
        return filepath

    def _build_content(
        self,
        cases: List[Any],
        execution_id: str,
        base_url: str,
        retry_times: int,
        timeout: int,
        resolver: ParameterResolver,
    ) -> str:
        """构建完整的测试文件内容"""
        header = self._build_header(execution_id, base_url, retry_times, timeout)
        helpers = self._build_assertion_helpers()
        fixtures = self._build_fixtures()
        test_functions = self._build_test_functions(cases, base_url, resolver)

        return header + "\n" + helpers + "\n" + fixtures + "\n" + test_functions + "\n"

    def _build_header(
        self,
        execution_id: str,
        base_url: str,
        retry_times: int,
        timeout: int,
    ) -> str:
        """生成文件头部：imports + pytest配置"""
        timestamp = datetime.now().isoformat()
        lines = [
            "# ============================================================",
            f"# Auto-generated pytest test file",
            f"# execution_id: {execution_id}",
            f"# generated_at: {timestamp}",
            f"# base_url: {base_url}",
            f"# retry_times: {retry_times}",
            f"# timeout: {timeout}s",
            "# ============================================================",
            "",
            "import pytest",
            "import requests",
            "import json",
            "import time",
            "import logging",
            "import os",
            "from typing import Any, Dict, Optional",
            "",
            "logger = logging.getLogger(__name__)",
            "",
            "# ---- 全局配置 ----",
            f'BASE_URL = "{base_url}"',
            f"REQUEST_TIMEOUT = {timeout}",
            f'EXECUTION_ID = "{execution_id}"',
            f'RESULT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".test_results.json")',
            "",
            "# ---- 结果收集：捕获每个用例的详细执行结果 ----",
            "_test_results = {}",
            "_test_context = {}  # 存储每个用例的响应上下文",
            "",
            "def pytest_runtest_logreport(report):",
            "    \"\"\"pytest hook: 每个测试用例执行完成后记录结果\"\"\"",
            "    import sys",
            "    if report.when == 'call':",
            "        test_name = report.nodeid",
            "        # 从 nodeid 提取函数名: module.py::test_func",
            "        func_name = test_name.split('::')[-1] if '::' in test_name else test_name",
            "        # 获取该用例的响应上下文",
            "        context = _test_context.get(func_name, {})",
            "        print(f'[pytest_hook] 处理用例: {func_name}, failed={report.failed}, passed={report.passed}', file=sys.stderr)",
            "        if report.failed:",
            "            # 收集失败信息",
            "            longrepr = getattr(report, 'longrepr', None)",
            "            if longrepr:",
            "                if hasattr(longrepr, 'reprcrash'):",
            "                    failure_msg = str(longrepr.reprcrash.message)",
            "                else:",
            "                    failure_msg = str(longrepr)",
            "            else:",
            "                failure_msg = '用例执行失败'",
            "            # 失败时返回完整响应信息（优先使用 _store_test_context 保存的响应）",
            "            resp_info = context.get('response', {})",
            "            if resp_info:",
            "                status_code = resp_info.get('status_code', 'N/A')",
            "                resp_body = resp_info.get('body', 'N/A')",
            "                if status_code != 'N/A' or resp_body != 'N/A':",
            "                    failure_msg = f'[HTTP {status_code}] {failure_msg}\\n响应体: {str(resp_body)[:2000]}'",
            "            print(f'[pytest_hook] 失败信息: {failure_msg[:200]}', file=sys.stderr)",
            "            _test_results[func_name] = {",
            "                'status': 'failed',",
            "                'message': failure_msg[:2000],",
            "            }",
            "        elif report.passed:",
            "            _test_results[func_name] = {",
            "                'status': 'passed',",
            "                'message': '',",
            "            }",
            "        # 处理 setup/teardown 失败的情况",
            "        elif report.failed and report.when != 'call':",
            "            _test_results[func_name] = {",
            "                'status': 'failed',",
            "                'message': f'[setup/teardown] {str(getattr(report, \"longrepr\", \"用例失败\"))}'[:2000],",
            "            }",
            "",
            "def pytest_sessionfinish(session, exitstatus):",
            "    \"\"\"pytest hook: 所有测试执行完成后写入结果文件\"\"\"",
            "    import traceback",
            "    import sys",
            "    print(f'[pytest_sessionfinish] exitstatus={exitstatus}, _test_results={len(_test_results)}', file=sys.stderr)",
            "    try:",
            "        with open(RESULT_FILE, 'w', encoding='utf-8') as f:",
            "            json.dump(_test_results, f, ensure_ascii=False)",
            "        print(f'[结果] 已写入 {RESULT_FILE}, 共 {len(_test_results)} 个用例: {list(_test_results.keys())}', file=sys.stderr)",
            "    except Exception as e:",
            "        print(f'[结果] 写入失败: {e}\\n{traceback.format_exc()}', file=sys.stderr)",
            "        # 尝试使用备用路径",
            "        try:",
            "            alt_path = os.path.join(os.getcwd(), '.test_results_backup.json')",
            "            with open(alt_path, 'w', encoding='utf-8') as f:",
            "                json.dump(_test_results, f, ensure_ascii=False)",
            "            print(f'[结果] 备用写入成功: {alt_path}', file=sys.stderr)",
            "        except Exception as e2:",
            "            print(f'[结果] 备用写入也失败: {e2}', file=sys.stderr)",
            "",
            "def _store_test_context(func_name, resp):",
            "    \"\"\"存储测试上下文（响应信息），供 pytest hook 使用\"\"\"",
            "    try:",
            "        body = resp.text[:5000] if resp.text else ''",
            "    except Exception:",
            "        body = '无法读取响应体'",
            "    _test_context[func_name] = {",
            "        'response': {",
            "            'status_code': resp.status_code,",
            "            'body': body,",
            "        }",
            "    }",
            "",
            "# ---- requests Session（支持 keep-alive）----",
            "_session = requests.Session()",
            "",
            "def _request(",
            "    method: str,",
            "    path: str,",
            "    headers: Optional[Dict] = None,",
            "    params: Optional[Dict] = None,",
            "    json_body: Any = None,",
            "    data_body: Any = None,",
            "    timeout: int = REQUEST_TIMEOUT,",
            ") -> requests.Response:",
            '    """统一的 HTTP 请求方法，自动拼接 BASE_URL。"""',
            '    url = BASE_URL.rstrip("/") + "/" + path.lstrip("/")',
            '    _headers = {"Content-Type": "application/json"}',
            "    if headers:",
            "        _headers.update(headers)",
            "",
            '    logger.info("[_request] 实际发送: method=%s, url=%s, headers=%s, params=%s, body=%s",',
            '                method.upper(), url, json.dumps(_headers, ensure_ascii=False),',
            '                json.dumps(params, ensure_ascii=False) if params else "None",',
            '                json.dumps(json_body, ensure_ascii=False)[:500] if json_body is not None else "None")',
            "",
            "    try:",
            "        resp = _session.request(",
            "            method=method.upper(),",
            "            url=url,",
            "            headers=_headers,",
            "            params=params or None,",
            "            json=json_body,",
            "            data=data_body,",
            "            timeout=timeout,",
            "        )",
            "        return resp",
            '    except requests.exceptions.Timeout:',
            '        raise AssertionError("请求超时 [" + method + "] " + url + ": 超过 " + str(timeout) + "s")',
            '    except requests.exceptions.ConnectionError as e:',
            '        raise AssertionError("连接失败 [" + method + "] " + url + ": " + str(e))',
        ]
        return "\n".join(lines)

    def _build_assertion_helpers(self) -> str:
        """生成断言辅助函数"""
        lines = [
            "",
            "def _assert_single(resp, path_str, expected, a_type, a_name):",
            '    """执行单个 json_path 断言"""',
            "    import jsonpath_ng",
            "    try:",
            "        body = resp.json()",
            "    except Exception:",
            "        body = {}",
            "    try:",
            "        expr = jsonpath_ng.parse(path_str)",
            "        matches = [m.value for m in expr.find(body)]",
            "    except Exception:",
            "        matches = []",
            "    actual = matches[0] if matches else None",
            "    if a_type in ('equals', 'json_path'):",
            "        assert actual == expected, '[' + a_name + '] path=' + path_str + ': expected=' + repr(expected) + ', actual=' + repr(actual)",
            "    elif a_type == 'not_equals':",
            "        assert actual != expected, '[' + a_name + '] path=' + path_str + ': should not be ' + repr(expected)",
            "    elif a_type == 'regex':",
            "        import re",
            "        assert re.search(expected, str(actual) or ''), '[' + a_name + '] path=' + path_str + ': not match ' + repr(expected)",
            "    elif a_type == 'not_empty':",
            "        assert actual is not None and actual != '' and actual != [], '[' + a_name + '] path=' + path_str + ': is empty'",
            "    elif a_type == 'length':",
            "        assert len(actual) == expected, '[' + a_name + '] path=' + path_str + ': len=' + str(len(actual)) + ', expected=' + str(expected)",
            "    elif a_type == 'greater_than':",
            "        assert actual > expected, '[' + a_name + '] path=' + path_str + ': ' + str(actual) + ' <= ' + str(expected)",
            "    elif a_type == 'less_than':",
            "        assert actual < expected, '[' + a_name + '] path=' + path_str + ': ' + str(actual) + ' >= ' + str(expected)",
            "    elif a_type == 'in_list':",
            "        assert actual in expected, '[' + a_name + '] path=' + path_str + ': ' + str(actual) + ' not in ' + str(expected)",
            "    elif a_type == 'not_in_list':",
            "        assert actual not in expected, '[' + a_name + '] path=' + path_str + ': ' + str(actual) + ' in ' + str(expected)",
        ]
        return "\n".join(lines)

    def _build_fixtures(self) -> str:
        """生成 pytest fixtures"""
        lines = [
            "",
            "@pytest.fixture(scope='session', autouse=True)",
            "def session_setup_teardown():",
            '    """Session 级 fixture。"""',
            '    logger.info("[Fixture] 测试会话开始: %s", EXECUTION_ID)',
            "    yield",
            '    logger.info("[Fixture] 测试会话结束: %s", EXECUTION_ID)',
            "",
            "@pytest.fixture",
            "def api_client():",
            '    """每个测试用例的 API 客户端 fixture。"""',
            "    return _session",
        ]
        return "\n".join(lines)

    def _build_test_functions(
        self,
        cases: List[Any],
        base_url: str,
        resolver: ParameterResolver,
    ) -> str:
        """生成所有 test_ 函数"""
        lines = []
        for idx, case in enumerate(cases):
            func = self._build_one_test_function(case, idx, base_url, resolver)
            lines.append(func)
        return "\n\n".join(lines)

    def _build_one_test_function(
        self,
        case: Any,
        idx: int,
        base_url: str,
        resolver: ParameterResolver,
    ) -> str:
        """生成单个测试函数"""
        lines = []  # 方法内部的局部变量

        case_id = getattr(case, "case_id", f"DB_{getattr(case, 'db_id', idx)}")
        name = getattr(case, "name", f"test_case_{idx + 1}")
        method = getattr(case, "method", "GET").upper()
        path = getattr(case, "path", "/")
        priority = getattr(case, "priority", "P2")
        description = getattr(case, "description", "")
        timeout = getattr(case, "timeout", 30)

        headers = getattr(case, "headers", {}) or {}
        query_params = getattr(case, "query_params", {}) or {}
        request_body = getattr(case, "request_body", None)
        assertions = getattr(case, "assertions", []) or []
        # 数据库断言配置
        post_script = getattr(case, "post_script", []) or []
        db_checks = getattr(case, "db_checks", []) or []
        module = getattr(case, "module", "API测试")

        # ========== 变量替换阶段 ==========
        # 获取用例的 preconditions 变量
        case_variables = getattr(case, 'case_variables', {}) or {}

        # 合并全局变量和用例变量（用例变量优先级更高）
        all_vars_for_case = dict(resolver.global_variables)  # 复制全局变量
        all_vars_for_case.update(case_variables)  # 用例变量覆盖

        # 创建用例专用的解析器
        case_resolver = ParameterResolver(global_variables=all_vars_for_case)

        # 记录原始数据（用于日志对比）
        raw_headers = headers
        raw_query_params = query_params
        raw_request_body = request_body

        # 执行变量替换
        resolved_headers = case_resolver.resolve(raw_headers)
        resolved_query_params = case_resolver.resolve(raw_query_params)
        resolved_request_body = case_resolver.resolve(raw_request_body)

        # 检测是否有变量被替换
        headers_changed = self._has_changes(raw_headers, resolved_headers)
        query_changed = self._has_changes(raw_query_params, resolved_query_params)
        body_changed = self._has_changes(raw_request_body, resolved_request_body)

        # 获取替换日志信息
        replaced_vars = case_resolver.get_replaced_vars()
        auto_generated_vars = case_resolver.get_auto_generated_vars()

        # 函数签名和文档
        func_name = f"test_{idx + 1}_{self._safe_name(case_id)}"
        lines.append(f"def {func_name}():")
        lines.append(f'    """')
        lines.append(f"    {description or name}")
        lines.append(f"")
        lines.append(f"    Case ID: {case_id}")
        lines.append(f"    Priority: {priority}")
        lines.append(f'    Method: {method} {path}')
        lines.append(f'    """')

        # ====== 详细日志1: 用例基本信息 ======
        lines.extend([
            '    logger.info("=" * 60)',
            '    logger.info("【用例开始】%s | %s", EXECUTION_ID, __name__)',
            '    logger.info("【用例信息】ID=%s, 名称=%s, 模块=%s", '
            f'"{case_id}", "{name}", "{module}")',
        ])

        # ====== 详细日志1.1: preconditions 变量配置 ======
        if case_variables:
            variables_json = self._json_dumps(case_variables)
            lines.extend([
                f'    logger.info("【变量配置】从 preconditions 加载 {len(case_variables)} 个变量: %s", "{{variables_json}}")',
            ])
        else:
            lines.append('    logger.info("【变量配置】无 preconditions 变量配置")')

        lines.append('    logger.info("=" * 60)')

        # ====== 详细日志2: 请求地址信息 ======
        full_url_line = '    logger.info("【请求地址】base_url=%s, 接口路径=%s, 完整URL=%s", BASE_URL, "{path}", BASE_URL.rstrip("/") + "/" + "{path}".lstrip("/"))'.format(path=path)
        lines.append(full_url_line)

        # ====== 详细日志3: 请求头（原始 + 变量替换后对比）=======
        if raw_headers:
            raw_headers_json = self._json_dumps(raw_headers)
            if headers_changed:
                resolved_headers_json = self._json_dumps(resolved_headers)
                lines.extend([
                    f'    logger.info("【请求头-原始】%s", "{{raw_headers_json}}")',
                    f'    logger.info("【请求头-变量替换后】%s", "{{resolved_headers_json}}")',
                    '    logger.info("【请求头-变量替换】已执行变量替换")',
                ])
            else:
                lines.extend([
                    f'    logger.info("【请求头】%s", "{{raw_headers_json}}")',
                ])
        else:
            lines.append('    logger.info("【请求头】无自定义请求头，使用默认Content-Type")')

        # ====== 详细日志4: Query参数（原始 + 变量替换后对比）=======
        if raw_query_params:
            raw_params_json = self._json_dumps(raw_query_params)
            if query_changed:
                resolved_params_json = self._json_dumps(resolved_query_params)
                lines.extend([
                    f'    logger.info("【Query参数-原始】%s", "{{raw_params_json}}")',
                    f'    logger.info("【Query参数-变量替换后】%s", "{{resolved_params_json}}")',
                    '    logger.info("【Query参数-变量替换】已执行变量替换")',
                ])
            else:
                lines.extend([
                    f'    logger.info("【Query参数】%s", "{{raw_params_json}}")',
                ])
        else:
            lines.append('    logger.info("【Query参数】无Query参数")')

        # ====== 详细日志5: 请求体（原始 + 变量替换后对比）=======
        if raw_request_body is not None:
            if isinstance(raw_request_body, dict):
                raw_body_json = self._json_dumps(raw_request_body)
            else:
                raw_body_json = repr(raw_request_body)

            if body_changed:
                if isinstance(resolved_request_body, dict):
                    resolved_body_json = self._json_dumps(resolved_request_body)
                else:
                    resolved_body_json = repr(resolved_request_body)

                # 构建替换详情日志
                if replaced_vars:
                    replaced_info = "; ".join([f"{v['placeholder']}->{v['value']}" for v in replaced_vars])
                    lines.append(f'    logger.info("【请求体-变量替换详情】%s", "{replaced_info}")')
                if auto_generated_vars:
                    auto_info = "; ".join([f"{v['placeholder']}->{v['value']}(自动生成)" for v in auto_generated_vars])
                    lines.append(f'    logger.info("【请求体-变量缺失警告】以下变量未配置，自动生成: %s", "{auto_info}")')

                lines.extend([
                    f'    _raw_body = {raw_body_json}',
                    f'    _resolved_body = {resolved_body_json}',
                    '    logger.info("【请求体-原始】%s", _raw_body)',
                    '    logger.info("【请求体-变量替换后】%s", _resolved_body)',
                    '    logger.info("【请求体-变量替换】已执行变量替换，替换数=%d, 自动生成数=%d", '
                    f'{len(replaced_vars)}, {len(auto_generated_vars)})',
                    '    logger.info("【请求体-类型】%s", type(_resolved_body).__name__)',
                ])
            else:
                lines.extend([
                    f'    _raw_body = {raw_body_json}',
                    '    _resolved_body = _raw_body',
                    '    logger.info("【请求体-原始】%s", _raw_body)',
                    '    logger.info("【请求体-变量替换后】%s (无变量，未变更)", _resolved_body)',
                    '    logger.info("【请求体-类型】%s", type(_resolved_body).__name__)',
                ])
        else:
            lines.extend([
                '    _raw_body = None',
                '    _resolved_body = None',
                '    logger.info("【请求体】无请求体")',
            ])

        # ====== 详细日志6: 完整请求信息汇总（使用替换后的数据）=======
        resolved_headers_code = self._json_dumps(resolved_headers) if resolved_headers else "{}"
        resolved_params_code = self._json_dumps(resolved_query_params) if resolved_query_params else "None"

        lines.extend([
            '    logger.info("【完整请求】")',
            '    logger.info("    URL: %s", BASE_URL.rstrip("/") + "/" + "{path}".lstrip("/"))'.format(path=path),
            '    logger.info("    Method: %s", "{method}")'.format(method=method),
            '    logger.info("    Headers(替换后): %s", {headers_code})'.format(
                headers_code=resolved_headers_code),
            '    logger.info("    Query(替换后): %s", {params_code})'.format(
                params_code=resolved_params_code),
            '    logger.info("    Body(替换后): %s", str(_resolved_body)[:500] if _resolved_body is not None else "None")',
        ])

        # ====== 发送请求 + 响应（使用替换后的数据）======
        lines.append('    logger.info("【发送请求】开始发送HTTP请求...")')
        lines.append(
            '    _request_url = BASE_URL.rstrip("/") + "/" + "{path}".lstrip("/")'.format(path=path)
        )
        lines.append(
            '    logger.info("【发送请求】即将发送: %s %s", "{method}", _request_url)'.format(
                method=method
            )
        )
        lines.append(
            '    logger.info("【发送请求】完整请求: method=%s, url=%s, headers=%s, params=%s, body=%s", '
            '"{method}", _request_url, {headers_code}, {params_code}, '
            'json.dumps(_resolved_body, ensure_ascii=False)[:500] if _resolved_body is not None else "None")'.format(
                method=method,
                headers_code=resolved_headers_code,
                params_code=resolved_params_code,
            )
        )

        # 使用 _resolved_body 作为最终请求体
        lines.append(f'    resp = _request(')
        lines.append(f'        method="{method}",')
        lines.append(f'        path="{path}",')
        lines.append(f'        headers={resolved_headers_code},')
        lines.append(f'        params={resolved_params_code},')
        if resolved_request_body is not None:
            if isinstance(resolved_request_body, dict):
                lines.append(f'        json_body={self._json_dumps(resolved_request_body)},')
            else:
                lines.append(f'        json_body={repr(resolved_request_body)},')
        else:
            lines.append('        json_body=None,')
        lines.append(f'        timeout={timeout},')
        lines.append('    )')

        # 存储测试上下文（响应信息），供失败时使用
        lines.append(f'    _store_test_context("{func_name}", resp)')

        lines.append('    logger.info("【发送请求】请求已发送，等待响应...")')

        # ====== 详细日志7: 响应信息 ======
        lines.extend([
            '    logger.info("【响应信息】状态码=%s, 响应时间=%.2fms")',
            '    logger.info("    响应体(前500字符): %s", resp.text[:500] if resp.text else "空响应")',
        ])

        # ====== 详细日志8: 响应体解析 ======
        lines.extend([
            '    logger.info("【响应解析】尝试解析响应体...")',
            '    try:',
            '        _response_json = resp.json()',
            '        logger.info("    响应JSON: %s", json.dumps(_response_json, ensure_ascii=False)[:500])',
            '    except Exception as _e:',
            '        logger.warning("    响应体非JSON格式: %s", str(_e))',
            '        _response_json = None',
        ])

        # ====== 详细日志9: 断言信息 ======
        lines.append('    logger.info("=" * 60)')
        lines.append('    logger.info("【断言信息】")')
        lines.append(f'    logger.info("    用例ID: {case_id}")')
        lines.append(f'    logger.info("    断言数量: {len(assertions)}")')

        if assertions:
            for i, a in enumerate(assertions):
                a_type = a.get("type", "unknown")
                a_name = a.get("name", f"assertion_{i + 1}")
                expected = a.get("expected")
                path_str = a.get("path", "")
                lines.append(f'    logger.info("    断言{i + 1}: 类型={a_type}, 名称={a_name}, 期望值={expected}, 路径={path_str}")')
        else:
            lines.append('    logger.info("    无自定义断言，使用默认状态码断言")')

        lines.append('    logger.info("=" * 60)')

        # 断言代码已包含正确的缩进（4空格），直接追加
        lines.append('    logger.info("【执行断言】开始执行断言...")')
        assertions_code = self._build_assertions_code(assertions)
        lines.append(assertions_code)

        # 数据库断言代码已包含正确的缩进（4空格），直接追加
        if post_script or db_checks:
            db_assertion_code = self._build_db_assertions_code(post_script, db_checks)
            lines.append(db_assertion_code)

        # ====== 详细日志10: 用例结束 ======
        lines.extend([
            '    logger.info("【用例结束】%s 执行完成", __name__)',
            '    logger.info("=" * 60)',
        ])

        return "\n".join(lines)

    def _has_changes(self, original: Any, resolved: Any) -> bool:
        """判断变量替换前后是否有变化"""
        orig_str = json.dumps(original, sort_keys=True, ensure_ascii=False) if original is not None else "null"
        res_str = json.dumps(resolved, sort_keys=True, ensure_ascii=False) if resolved is not None else "null"
        return orig_str != res_str

    def _build_assertions_code(self, assertions: List[Dict]) -> str:
        """
        生成断言代码。

        自动追加业务 code 检查：
        - HTTP 状态码 200 时，检查响应 body 中 code 是否为成功码
        - 支持多种成功码格式：000000(6位), 00000000(8位), 0, success, SUCCESS
        - 若业务 code 不为成功码，抛出包含完整响应内容的 AssertionError
        - 确保请求通了但业务失败时（如 {code:330000007}）能被正确捕获为用例失败
        """
        # 始终插入自动业务 code 检查在最前面
        # 支持多种成功码格式
        success_codes = repr(['000000', '00000000', '0', 'success', 'SUCCESS'])
        lines = [
            "    # ---- 自动检查：业务 code 是否为成功码 ----",
            "    try:",
            "        _biz_resp = resp.json()",
            "    except Exception:",
            "        _biz_resp = {}",
            "    _biz_code = _biz_resp.get('code') if isinstance(_biz_resp, dict) else None",
            f"    _success_codes = {success_codes}",
            "    # 同时检查内层 data.code（部分接口在 data 里也有 code）",
            "    _inner_code = None",
            "    if isinstance(_biz_resp.get('data'), dict):",
            "        _inner_code = _biz_resp['data'].get('code')",
            "    _is_success = _biz_code in _success_codes or _inner_code in _success_codes",
            "    if resp.status_code == 200 and not _is_success and _biz_code is not None:",
            "        _fail_msg = '[业务code失败] code=' + str(_biz_code)",
            "        _fail_msg += ', message=' + str(_biz_resp.get('message'))",
            "        _fail_msg += ', 响应体=' + json.dumps(_biz_resp, ensure_ascii=False)",
            "        logger.error('【断言失败】%s', _fail_msg)",
            "        raise AssertionError(_fail_msg)",
            "    if _is_success:",
            "        logger.info('【业务code检查】code=%s (成功), HTTP状态码=%d, 通过', _biz_code, resp.status_code)",
            "    else:",
            "        logger.info('【业务code检查】code=%s (非标准成功码), HTTP状态码=%d', _biz_code, resp.status_code)",
            "",
        ]

        for i, a in enumerate(assertions):
            a_type = a.get("type", "status_code")
            a_name = a.get("name", f"assertion_{i + 1}")
            expected = a.get("expected")
            path = a.get("path", "")
            max_ms = a.get("max_ms")

            if a_type == "status_code":
                lines.append(f'    assert resp.status_code == {expected}, "[{a_name}] HTTP状态码: " + str(resp.status_code)')
            elif a_type == "response_time":
                limit = max_ms or expected or 5000
                lines.append(f'    assert resp.elapsed.total_seconds() * 1000 <= {limit}, "[{a_name}] 响应时间超限: " + str(resp.elapsed.total_seconds() * 1000) + "ms"')
            elif a_type == "contains":
                lines.append(f'    assert {repr(expected)} in resp.text, "[{a_name}] 响应体不包含: " + {repr(expected)}')
            elif a_type == "not_contains":
                lines.append(f'    assert {repr(expected)} not in resp.text, "[{a_name}] 响应体不应包含: " + {repr(expected)}')
            elif a_type in ("equals", "json_path", "not_equals", "regex",
                            "not_empty", "length", "greater_than", "less_than",
                            "in_list", "not_in_list"):
                path_str = repr(path) if path else '""'
                if expected is None:
                    exp_code = "None"
                else:
                    exp_code = json.dumps(expected, ensure_ascii=False)
                lines.append(f'    _assert_single(resp, {path_str}, {exp_code}, "{a_type}", "{a_name}")')
            elif a_type == "header":
                header_name = a.get("header", "")
                lines.append(f'    assert "{header_name}" in resp.headers, "[{a_name}] 响应头缺失: {header_name}"')
            else:
                lines.append(f'    # [{a_name}] 未知断言类型: {a_type} (跳过)')

        return "\n".join(lines)

    def _build_db_assertions_code(
        self,
        post_script: List[Dict],
        db_checks: List[Dict],
    ) -> str:
        """
        生成数据库断言代码

        Args:
            post_script: 后置脚本配置
            db_checks: 数据库断言配置

        Returns:
            str: 数据库断言代码
        """
        lines = []

        if not post_script and not db_checks:
            return ""

        lines.append('    logger.info("【数据库断言】开始执行...")')

        # 导入数据库断言模块
        lines.append('        from common.test_executor.db_check_runner import get_db_check_runner')
        lines.append('        from common.test_executor.db_query_executor import VariableResolver')
        lines.append('')

        # 生成上下文变量
        lines.append('        _db_context = {')
        lines.append('            "response": {')
        lines.append('                "json": _response_json if "_response_json" in dir() else None,')
        lines.append('                "status_code": resp.status_code if "resp" in dir() else None,')
        lines.append('                "headers": dict(resp.headers) if "resp" in dir() else {},')
        lines.append('            },')
        lines.append('            "request": {')
        lines.append('                "body": _resolved_body if "_resolved_body" in dir() else None,')
        lines.append('            },')
        lines.append('            "variables": {},')
        lines.append('        }')
        lines.append('')

        # 序列化配置为 JSON
        post_script_json = self._json_dumps(post_script)
        db_checks_json = self._json_dumps(db_checks)

        lines.append(f'        _post_script = {post_script_json}')
        lines.append(f'        _db_checks = {db_checks_json}')
        lines.append('')

        # 执行数据库断言
        lines.append('        logger.info("【数据库断言】post_script=%d个, db_checks=%d个", len(_post_script), len(_db_checks))')
        lines.append('')
        lines.append('        _db_runner = get_db_check_runner()')
        lines.append('        _db_result = _db_runner.execute(')
        lines.append('            post_script=_post_script,')
        lines.append('            db_checks=_db_checks,')
        lines.append('            context=_db_context,')
        lines.append('        )')
        lines.append('')

        # 记录数据库断言结果
        lines.append('        _db_result_dict = _db_result.to_dict()')
        lines.append('        logger.info("【数据库断言】结果: %s", json.dumps(_db_result_dict, ensure_ascii=False)[:500])')
        lines.append('')

        # 生成每个 db_check 的详细断言
        for check in db_checks:
            check_id = check.get("id", "unknown")
            assertions = check.get("assertions", [])
            for assertion in assertions:
                field = assertion.get("field", "")

                lines.append(f'        # db_check: {check_id}, 字段: {field}')
                lines.append(f'        logger.info("【数据库断言】执行检查 {check_id} - 字段 {field}")')

        lines.append('')
        lines.append('        logger.info("【数据库断言】执行完成: all_passed=%s, checks=%d, passed=%d, fields=%d, passed=%d",')
        lines.append('            _db_result.all_passed, _db_result.total_checks, _db_result.passed_checks,')
        lines.append('            _db_result.total_fields, _db_result.passed_fields)')

        # 最终断言
        lines.append('')
        lines.append('        if not _db_result.all_passed:')
        lines.append('            _failed_details = []')
        lines.append('            for _check_result in _db_result.results:')
        lines.append('                if not _check_result.passed:')
        lines.append('                    _failed_fields = [_f.field for _f in _check_result.field_results if not _f.passed]')
        lines.append('                    _failed_details.append(f"{_check_result.id}: {{_failed_fields}}")')
        lines.append('            _error_msg = "数据库断言失败: " + "; ".join(_failed_details)')
        lines.append('            logger.error("【数据库断言】失败: %s", _error_msg)')
        lines.append('            raise AssertionError(_error_msg)')
        lines.append('')
        lines.append('        logger.info("【数据库断言】全部通过")')

        return "\n".join(lines)

    def _safe_name(self, case_id: str) -> str:
        """将 case_id 转换为合法的 Python 函数名"""
        return re.sub(r"[^a-zA-Z0-9_]", "_", str(case_id))[:50]
