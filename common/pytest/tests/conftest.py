"""
Pytest 配置和钩子

提供:
- 全局 fixtures (http_session, env_config)
- 测试重试支持 (pytest-rerunfailures)
- 结果收集: _test_results / _test_context / _extract_fields_by_config / _store_test_context
"""

import pytest
import requests
import os
import sys
import json
import logging
import traceback

logger = logging.getLogger(__name__)

# 确保项目根目录在 path 中
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ==================== Fixtures ====================

@pytest.fixture(scope="session")
def http_session():
    """会话级 HTTP Session，复用连接池"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "Pytest-AutoTest/1.0"
    })
    yield session
    session.close()


@pytest.fixture(scope="session")
def env_base_url():
    """API 基础 URL，从环境变量读取"""
    return os.environ.get("TEST_BASE_URL", "http://localhost:5000")


@pytest.fixture(scope="session")
def execution_config():
    """执行配置（从 JSON 文件读取）"""
    config_path = os.environ.get("EXECUTION_CONFIG_PATH", "")
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("加载执行配置失败: %s", e)
    return {
        "timeout": 30,
        "max_retry_times": 2,
        "base_url": os.environ.get("TEST_BASE_URL", "http://localhost:5000"),
    }


# ==================== 结果收集: 全局数据 ====================

_test_results = {}       # {func_name: {status, message, fail_response/fail_response, extract_fields}}
_test_context = {}      # {func_name: {response: {status_code, headers, body, json}, extract_fields}}


# ==================== 结果收集: 辅助函数 ====================

def _extract_fields_by_config(resp, extract_fields):
    """按配置提取响应字段，供后续用例引用或写入测试结果"""
    import jsonpath_ng
    extract_result = {}
    try:
        resp_body = resp.json()
    except Exception:
        return extract_result
    for field_item in extract_fields:
        field_name = field_item.get('name')
        json_path = field_item.get('path')
        if not field_name or not json_path:
            continue
        try:
            json_path_expr = jsonpath_ng.parse(json_path)
            match_list = [match.value for match in json_path_expr.find(resp_body)]
            field_value = match_list[0] if match_list else None
            extract_result[field_name] = field_value
        except Exception:
            extract_result[field_name] = None
    return extract_result


def _store_test_context(func_name, resp, extract_result=None):
    """存储测试上下文（响应信息+提取结果），供 pytest hook 使用"""
    try:
        body = resp.text[:5000] if resp.text else ''
    except Exception:
        body = '无法读取响应体'
    try:
        resp_json = resp.json()
    except Exception:
        resp_json = None
    _test_context[func_name] = {
        'response': {
            'status_code': resp.status_code,
            'headers': dict(resp.headers),
            'body': body,
            'json': resp_json,
        },
        'extract_fields': extract_result if extract_result else {},
    }
    logger.info('[Context] 已保存用例 %s 响应: status=%d, 提取字段数=%d',
                func_name, resp.status_code, len(extract_result) if extract_result else 0)


# ==================== Pytest 钩子 ====================

def pytest_configure(config):
    """Pytest 配置钩子 - 注册自定义 markers"""
    config.addinivalue_line(
        "markers",
        "case_id: 用例ID标记"
    )


def _get_func_name_from_item(item) -> str:
    """从 pytest item 提取函数名（去掉 nodeid 前缀）"""
    # item.nodeid 格式: D:/path/to/test_xxx.py::test_func_name
    # 或者: test_xxx.py::test_func_name
    node_id = item.nodeid
    if "::" in node_id:
        return node_id.split("::")[-1]
    return node_id


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    测试结果报告钩子。

    在 call 阶段收集每个用例的通过/失败结果，
    写入 _test_results，供 pytest_sessionfinish 写入文件。
    """
    outcome = yield
    report = outcome.get_result()

    # 记录重试次数
    if hasattr(report, 'rerun'):
        item.retry_count = getattr(item, 'retry_count', 0) + 1

    # 仅在 call 阶段处理
    if report.when != "call":
        return

    func_name = _get_func_name_from_item(item)
    context = _test_context.get(func_name, {})

    if report.passed:
        _extracted = context.get('extract_fields', {}) if context else {}
        resp_json = context.get('response', {}).get('json') if context else None
        _test_results[func_name] = {
            'status': 'passed',
            'message': '',
            'success_response': json.dumps(resp_json, ensure_ascii=False) if _extracted else '',
            'extract_fields': _extracted,
        }
        logger.info('[pytest_hook] 成功: %s, 提取字段数=%d', func_name, len(_extracted) if _extracted else 0)

    elif report.failed:
        longrepr = getattr(report, 'longrepr', None)
        if longrepr:
            if hasattr(longrepr, 'reprcrash'):
                failure_msg = str(longrepr.reprcrash.message)
            else:
                failure_msg = str(longrepr)
        else:
            failure_msg = '用例执行失败'

        resp_info = context.get('response', {})
        if resp_info:
            status_code = resp_info.get('status_code', 'N/A')
            resp_body = resp_info.get('body', 'N/A')
            if status_code != 'N/A' or resp_body != 'N/A':
                failure_msg = f'[HTTP {status_code}] {failure_msg}\n响应体: {str(resp_body)[:2000]}'

        resp_json = None
        _extracted = {}
        if context:
            resp_json = context.get('response', {}).get('json')
            _extracted = context.get('extract_fields', {})

        _test_results[func_name] = {
            'status': 'failed',
            'message': failure_msg[:2000],
            'fail_response': json.dumps(resp_json, ensure_ascii=False) if resp_json else '',
            'extract_fields': _extracted,
        }
        logger.info('[pytest_hook] 失败: %s, 提取字段数=%d, msg=%s',
                    func_name, len(_extracted) if _extracted else 0, failure_msg[:200])


def pytest_rerunfailures(reruncount, eximinfolist):
    """Called when tests are re-run. Log retry events."""
    pass


def pytest_sessionfinish(session, exitstatus):
    """pytest hook: 所有测试执行完成后写入结果文件"""
    # 计算结果文件路径：
    # - 测试文件通常在 outputs/generated_tests/test_xxx.py
    # - conftest 在 tests/conftest.py
    # - 结果文件应该写到 outputs/generated_tests/.test_results.json
    # 方案：以 session.startdir 为基准往上找到 outputs/generated_tests 目录
    _start_dir = session.startpath  # pytest 7.2+ 可用，为项目 rootdir 的 Path 对象
    if hasattr(_start_dir, 'as_posix'):
        _start_dir = str(_start_dir)

    # 优先找 outputs/generated_tests 目录
    _result_dir = os.path.join(_start_dir, "outputs", "generated_tests")
    if not os.path.exists(_result_dir):
        _result_dir = os.path.join(_start_dir, "tests")
        _result_dir = os.path.dirname(_result_dir)
        _result_dir = os.path.join(_result_dir, "outputs", "generated_tests")

    _result_file = os.path.join(_result_dir, ".test_results.json")

    logger.info('[pytest_sessionfinish] exitstatus=%s, _test_results=%s, 结果文件=%s',
                exitstatus, len(_test_results), _result_file)

    try:
        os.makedirs(_result_dir, exist_ok=True)
        with open(_result_file, 'w', encoding='utf-8') as f:
            json.dump(_test_results, f, ensure_ascii=False)
        logger.info('[结果] 已写入 %s, 共 %d 个用例: %s',
                    _result_file, len(_test_results), list(_test_results.keys()))
    except Exception as e:
        logger.error('[结果] 写入失败: %s\n%s', e, traceback.format_exc())
        # 备用：写到当前工作目录
        try:
            _alt_file = os.path.join(os.getcwd(), '.test_results_backup.json')
            with open(_alt_file, 'w', encoding='utf-8') as f:
                json.dump(_test_results, f, ensure_ascii=False)
            logger.info('[结果] 备用写入成功: %s', _alt_file)
        except Exception as e2:
            logger.error('[结果] 备用写入也失败: %s', e2)
