"""
Pytest 配置和钩子（供 outputs/generated_tests/ 下的测试文件使用）

提供:
- 结果收集: _test_results / _test_context / _extract_fields_by_config / _store_test_context
- pytest_sessionfinish 钩子写入 .test_results.json
"""

import pytest
import os
import sys
import json
import logging
import traceback

logger = logging.getLogger(__name__)

# 确保项目根目录在 sys.path 中，使 generated_tests 可以 import common 包
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ==================== 结果收集: 全局数据 ====================

_test_results = {}   # {func_name: {status, message, success_response/fail_response, extract_fields}}
_test_context = {}  # {func_name: {response: {status_code, headers, body, json}, extract_fields}}


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
            match_list = [m.value for m in json_path_expr.find(resp_body)]
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
    config.addinivalue_line("markers", "case_id: 用例ID标记")


def _get_func_name_from_item(item) -> str:
    node_id = item.nodeid
    if "::" in node_id:
        return node_id.split("::")[-1]
    return node_id


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if hasattr(report, 'rerun'):
        item.retry_count = getattr(item, 'retry_count', 0) + 1

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
            'success_response': json.dumps(resp_json, ensure_ascii=False) if resp_json else '',
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
        logger.info('[pytest_hook] 失败: %s, msg=%s', func_name, failure_msg[:200])


def pytest_sessionfinish(session, exitstatus):
    """所有测试执行完成后，将结果写入测试文件同目录的 .test_results.json"""
    _start_dir = getattr(session, 'startpath', None)
    if _start_dir is not None:
        if hasattr(_start_dir, 'as_posix'):
            _start_dir = str(_start_dir)
    else:
        _start_dir = os.getcwd()

    _result_dir = os.path.join(_start_dir, "outputs", "generated_tests")
    if not os.path.exists(_result_dir):
        _result_dir = os.path.join(_start_dir, "tests")
        _result_dir = os.path.dirname(_result_dir)
        _result_dir = os.path.join(_result_dir, "outputs", "generated_tests")

    _result_file = os.path.join(_result_dir, ".test_results.json")

    logger.info('[pytest_sessionfinish] exitstatus=%s, 结果数=%d, 结果文件=%s',
                exitstatus, len(_test_results), _result_file)

    try:
        os.makedirs(_result_dir, exist_ok=True)
        with open(_result_file, 'w', encoding='utf-8') as f:
            json.dump(_test_results, f, ensure_ascii=False)
        logger.info('[结果] 已写入 %s, 共 %d 个用例: %s',
                    _result_file, len(_test_results), list(_test_results.keys()))
    except Exception as e:
        logger.error('[结果] 写入失败: %s\n%s', e, traceback.format_exc())
        try:
            _alt_file = os.path.join(os.getcwd(), '.test_results_backup.json')
            with open(_alt_file, 'w', encoding='utf-8') as f:
                json.dump(_test_results, f, ensure_ascii=False)
            logger.info('[结果] 备用写入成功: %s', _alt_file)
        except Exception as e2:
            logger.error('[结果] 备用写入也失败: %s', e2)
