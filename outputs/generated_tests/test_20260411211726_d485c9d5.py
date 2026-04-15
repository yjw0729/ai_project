# ============================================================
# Auto-generated pytest test file
# execution_id: 20260411211726_d485c9d5
# generated_at: 2026-04-11T21:17:26.494154
# base_url: http://22.50.8.21:8080
# retry_times: 0
# timeout: 30s
# ============================================================

# ---- sys.path：确保能 import common 包 ----
import sys
import os
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_PARENT_ROOT = os.path.dirname(_PROJECT_ROOT)
if _PARENT_ROOT not in sys.path:
    sys.path.insert(0, _PARENT_ROOT)

import pytest
import requests
import json
import time
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---- 全局配置 ----
BASE_URL = "http://22.50.8.21:8080"
REQUEST_TIMEOUT = 30
EXECUTION_ID = "20260411211726_d485c9d5"

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
    """统一的 HTTP 请求方法，自动拼接 BASE_URL。"""
    url = BASE_URL.rstrip("/") + "/" + path.lstrip("/")
    _headers = {"Content-Type": "application/json"}
    if headers:
        _headers.update(headers)

    _req_body_str = json.dumps(json_body, ensure_ascii=False)[:1000] if json_body is not None else "None"
    _req_params_str = json.dumps(params, ensure_ascii=False)[:500] if params else "None"
    _req_lines = [
        "\n" + "=" * 30 + " HTTP REQUEST " + "=" * 30,
        "  [地址] " + url,
        "  [方法] " + method.upper(),
        "  [请求头] " + json.dumps(_headers, ensure_ascii=False)[:600],
        "  [Query] " + _req_params_str,
        "  [请求体] " + _req_body_str,
        "  [超时] " + str(timeout) + "s",
        "=" * 60 + "\n",
    ]
    print("\n".join(_req_lines))

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
        _resp_body_str = resp.text[:2000] if resp.text else "空响应"
        _resp_lines = [
            "\n" + "=" * 30 + " HTTP RESPONSE " + "=" * 30,
            "  [状态码] " + str(resp.status_code),
            "  [响应头] " + json.dumps(dict(resp.headers), ensure_ascii=False)[:600],
            "  [响应体] " + _resp_body_str,
            "=" * 60 + "\n",
        ]
        print("\n".join(_resp_lines))
        return resp
    except requests.exceptions.Timeout:
        raise AssertionError("请求超时 [" + method + "] " + url + ": 超过 " + str(timeout) + "s")
    except requests.exceptions.ConnectionError as e:
        raise AssertionError("连接失败 [" + method + "] " + url + ": " + str(e))

# ---- 结果收集：捕获每个用例的详细执行结果 ----
_test_results = {}
_test_context = {}  # 存储每个用例的响应上下文

def _store_test_context(func_name, resp):
    """存储测试上下文（响应信息），供 pytest hook 使用"""
    try:
        body = resp.text[:5000] if resp.text else ''
    except Exception:
        body = '无法读取响应体'
    try:
        _resp_json = resp.json()
    except Exception:
        _resp_json = None
    _test_context[func_name] = {
        'response': {
            'status_code': resp.status_code,
            'headers': dict(resp.headers),
            'body': body,
            'json': _resp_json,
        },
    }
    logger.info('[Context] 已保存用例 %s 响应: status=%d', func_name, resp.status_code)

def pytest_runtest_logreport(report):
    """pytest hook: 每个测试用例执行完成后记录结果"""
    import sys
    if report.when == 'call':
        test_name = report.nodeid
        func_name = test_name.split('::')[-1] if '::' in test_name else test_name
        context = _test_context.get(func_name, {})
        print(f'[pytest_hook] 处理用例: {func_name}, failed={report.failed}, passed={report.passed}', file=sys.stderr)
        if report.failed:
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
            print(f'[pytest_hook] 失败信息: {failure_msg[:200]}', file=sys.stderr)
            _test_results[func_name] = {
                'status': 'failed',
                'message': failure_msg[:2000],
            }
        elif report.passed:
            _test_results[func_name] = {
                'status': 'passed',
                'message': '',
            }

def pytest_sessionfinish(session, exitstatus):
    """pytest hook: 所有测试执行完成后写入结果文件"""
    import traceback
    import sys
    print(f'[pytest_sessionfinish] exitstatus={exitstatus}, _test_results={len(_test_results)}', file=sys.stderr)
    try:
        result_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.test_results.json')
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(_test_results, f, ensure_ascii=False)
        print(f'[结果] 已写入 {result_file}, 共 {len(_test_results)} 个用例: {list(_test_results.keys())}', file=sys.stderr)
    except Exception as e:
        print(f'[结果] 写入失败: {e}\n{traceback.format_exc()}', file=sys.stderr)
        try:
            alt_path = os.path.join(os.getcwd(), '.test_results_backup.json')
            with open(alt_path, 'w', encoding='utf-8') as f:
                json.dump(_test_results, f, ensure_ascii=False)
            print(f'[结果] 备用写入成功: {alt_path}', file=sys.stderr)
        except Exception as e2:
            print(f'[结果] 备用写入也失败: {e2}', file=sys.stderr)


def _assert_single(resp, path_str, expected, a_type, a_name):
    """执行单个 json_path 断言"""
    import jsonpath_ng
    try:
        body = resp.json()
    except Exception:
        body = {}
    try:
        expr = jsonpath_ng.parse(path_str)
        matches = [m.value for m in expr.find(body)]
    except Exception:
        matches = []
    actual = matches[0] if matches else None
    if a_type in ('equals', 'json_path'):
        assert actual == expected, '[' + a_name + '] path=' + path_str + ': expected=' + repr(expected) + ', actual=' + repr(actual)
    elif a_type == 'not_equals':
        assert actual != expected, '[' + a_name + '] path=' + path_str + ': should not be ' + repr(expected)
    elif a_type == 'regex':
        import re
        assert re.search(expected, str(actual) or ''), '[' + a_name + '] path=' + path_str + ': not match ' + repr(expected)
    elif a_type == 'not_empty':
        assert actual is not None and actual != '' and actual != [], '[' + a_name + '] path=' + path_str + ': is empty'
    elif a_type == 'length':
        assert len(actual) == expected, '[' + a_name + '] path=' + path_str + ': len=' + str(len(actual)) + ', expected=' + str(expected)
    elif a_type == 'greater_than':
        assert actual > expected, '[' + a_name + '] path=' + path_str + ': ' + str(actual) + ' <= ' + str(expected)
    elif a_type == 'less_than':
        assert actual < expected, '[' + a_name + '] path=' + path_str + ': ' + str(actual) + ' >= ' + str(expected)
    elif a_type == 'in_list':
        assert actual in expected, '[' + a_name + '] path=' + path_str + ': ' + str(actual) + ' not in ' + str(expected)
    elif a_type == 'not_in_list':
        assert actual not in expected, '[' + a_name + '] path=' + path_str + ': ' + str(actual) + ' in ' + str(expected)

@pytest.fixture(scope='session', autouse=True)
def session_setup_teardown():
    """Session 级 fixture。"""
    logger.info("[Fixture] 测试会话开始: %s", EXECUTION_ID)
    yield
    logger.info("[Fixture] 测试会话结束: %s", EXECUTION_ID)

@pytest.fixture
def api_client():
    """每个测试用例的 API 客户端 fixture。"""
    return _session

# ---- 响应字段提取：session 级上下文（供后续用例引用）----
from common.test_executor.response_extract import _get_session_context

@pytest.fixture(scope='session')
def response_context():
    """Session 级响应提取上下文 fixture。"""
    ctx = _get_session_context()
    logger.info("[Fixture] response_context session 开始，已提取变量: %s", list(ctx.keys()))
    yield ctx
    logger.info("[Fixture] response_context session 结束，已提取变量: %s", list(ctx.keys()))
def test_1_TEST_CASE_000000005():
    """
    普通收单交易

    Case ID: TEST_CASE_000000005
    Priority: P0
    Method: POST /businessAction/commonBusiness/BASIC_PTSD
    """
    logger.info("=" * 60)
    logger.info("【用例开始】%s | %s", EXECUTION_ID, __name__)
    logger.info("【用例信息】ID=%s, 名称=%s, 模块=%s", "TEST_CASE_000000005", "普通收单-验证前置", "交易模块")
    logger.info("【变量配置】从 preconditions 加载 1 个变量: {"payeeMno": "600600010996929"}")
    logger.info("=" * 60)
    logger.info("【请求地址】base_url=%s, 接口路径=%s, 完整URL=%s", BASE_URL, "/businessAction/commonBusiness/BASIC_PTSD", BASE_URL.rstrip("/") + "/" + "/businessAction/commonBusiness/BASIC_PTSD".lstrip("/"))
    logger.info("【请求头】无自定义请求头，使用默认Content-Type")
    logger.info("【Query参数】无Query参数")
    logger.info("【请求体-变量替换详情】%s", "${TIMESTAMP}->1775913446")
    _raw_body = {"data": {"bankCode": "", "notifyUrl": "http://mqhjshjkr.bm/ihb", "payMethod": "", "requestId": "${RANDOM}", "rootMchId": "600600010996929", "batchActionList": [{"amount": "30", "bindId": "", "userId": "U3141383309692437", "payeeMno": "{{payeeMno}}", "payerMno": "", "contractNo": "OTSSH1000000111", "outTradeNo": "${TIMESTAMP}", "productInfos": [{"remark": "Lorem ipsum dolor sit amet", "orderNo": "OTNPRODUCT0001", "productNo": "iph1234", "orderAmount": 15, "productName": "iPhone X", "productCount": 1}], "divideAccountType": "00"}]}, "format": "123123", "version": "1.2", "requestId": "${RANDOM}", "timestamp": "${TIMESTAMP}"}
    _resolved_body = {"data": {"bankCode": "", "notifyUrl": "http://mqhjshjkr.bm/ihb", "payMethod": "", "requestId": "248984", "rootMchId": "600600010996929", "batchActionList": [{"amount": "30", "bindId": "", "userId": "U3141383309692437", "payeeMno": "600600010996929", "payerMno": "", "contractNo": "OTSSH1000000111", "outTradeNo": "1775913446", "productInfos": [{"remark": "Lorem ipsum dolor sit amet", "orderNo": "OTNPRODUCT0001", "productNo": "iph1234", "orderAmount": 15, "productName": "iPhone X", "productCount": 1}], "divideAccountType": "00"}]}, "format": "123123", "version": "1.2", "requestId": "738962", "timestamp": "1775913446"}
    logger.info("【请求体-原始】%s", _raw_body)
    logger.info("【请求体-变量替换后】%s", _resolved_body)
    logger.info("【请求体-变量替换】已执行变量替换，替换数=%d, 自动生成数=%d", 1, 0)
    logger.info("【请求体-类型】%s", type(_resolved_body).__name__)
    logger.info("【响应变量替换】检查请求数据中的 ${RESPONSE.xxx} 占位符...")
    _session_ctx = _get_session_context()
    _resp_vars_found = []
    def _resolve_resp_vars(d):
        """递归替换字典中的 ${RESPONSE.xxx} 占位符"""
        nonlocal _resp_vars_found
        if isinstance(d, dict):
            for k, v in d.items():
                d[k] = _resolve_resp_vars(v)
        elif isinstance(d, list):
            for i, item in enumerate(d):
                d[i] = _resolve_resp_vars(item)
        elif isinstance(d, str):
            import re as _re
            for m in _re.finditer(r"\$\{RESPONSE\.([^}]+)\}", d):
                var_name = m.group(1)
                ctx_val = _session_ctx.get(var_name)
                if ctx_val is not None:
                    d = d.replace(m.group(0), str(ctx_val))
                    if var_name not in _resp_vars_found:
                        _resp_vars_found.append(var_name)
                        logger.info("【响应变量替换】%s = %s", var_name, str(ctx_val)[:100])
                else:
                    logger.warning("【响应变量替换】变量 %s 未在 session 上下文中找到 (当前已有: %s)", var_name, list(_session_ctx.keys()))
        return d
    _resolved_body = _resolve_resp_vars(_resolved_body) if _resolved_body else None
    if _resp_vars_found:
        logger.info("【响应变量替换】共替换 %d 个响应变量: %s", len(_resp_vars_found), _resp_vars_found)
    else:
        logger.info("【响应变量替换】无响应变量占位符")
    logger.info("【完整请求】")
    logger.info("    URL: %s", BASE_URL.rstrip("/") + "/" + "/businessAction/commonBusiness/BASIC_PTSD".lstrip("/"))
    logger.info("    Method: %s", "POST")
    logger.info("    Headers(替换后): %s", {})
    logger.info("    Query(替换后): %s", None)
    logger.info("    Body(替换后): %s", str(_resolved_body)[:500] if _resolved_body is not None else "None")
    logger.info("【发送请求】开始发送HTTP请求...")
    _request_url = BASE_URL.rstrip("/") + "/" + "/businessAction/commonBusiness/BASIC_PTSD".lstrip("/")
    logger.info("【发送请求】即将发送: %s %s", "POST", _request_url)
    logger.info("【发送请求】完整请求: method=%s, url=%s, headers=%s, params=%s, body=%s", "POST", _request_url, {}, None, json.dumps(_resolved_body, ensure_ascii=False)[:500] if _resolved_body is not None else "None")
    resp = _request(
        method="POST",
        path="/businessAction/commonBusiness/BASIC_PTSD",
        headers={},
        params=None,
        json_body={"data": {"bankCode": "", "notifyUrl": "http://mqhjshjkr.bm/ihb", "payMethod": "", "requestId": "248984", "rootMchId": "600600010996929", "batchActionList": [{"amount": "30", "bindId": "", "userId": "U3141383309692437", "payeeMno": "600600010996929", "payerMno": "", "contractNo": "OTSSH1000000111", "outTradeNo": "1775913446", "productInfos": [{"remark": "Lorem ipsum dolor sit amet", "orderNo": "OTNPRODUCT0001", "productNo": "iph1234", "orderAmount": 15, "productName": "iPhone X", "productCount": 1}], "divideAccountType": "00"}]}, "format": "123123", "version": "1.2", "requestId": "738962", "timestamp": "1775913446"},
        timeout=30,
    )
    _store_test_context("test_1_TEST_CASE_000000005", resp)
    logger.info("【发送请求】请求已发送，等待响应...")
    logger.info("【响应信息】状态码=%s, 响应时间=%.2fms", resp.status_code, resp.elapsed.total_seconds() * 1000)
    logger.info("    响应Headers: %s", json.dumps(dict(resp.headers), ensure_ascii=False)[:500])
    logger.info("    响应体(前500字符): %s", resp.text[:500] if resp.text else "空响应")
    logger.info("【响应解析】尝试解析响应体...")
    try:
        _response_json = resp.json()
        logger.info("    响应JSON: %s", json.dumps(_response_json, ensure_ascii=False)[:500])
    except Exception as _e:
        logger.warning("    响应体非JSON格式: %s", str(_e))
        _response_json = None
    logger.info("=" * 60)
    logger.info("【断言信息】")
    logger.info("    用例ID: TEST_CASE_000000005")
    logger.info("    断言数量: 0")
    logger.info("    无自定义断言，使用默认状态码断言")
    logger.info("=" * 60)
    logger.info("【执行断言】开始执行断言...")
    # ---- 自动检查：业务 code 是否为成功码 ----
    try:
        _biz_resp = resp.json()
    except Exception:
        _biz_resp = {}
    _biz_code = _biz_resp.get("code") if isinstance(_biz_resp, dict) else None
    _success_codes = ["000000", "00000000", "0", "success", "SUCCESS"]
    # 同时检查内层 data.code（部分接口在 data 里也有 code）
    _inner_code = None
    if isinstance(_biz_resp.get("data"), dict):
        _inner_code = _biz_resp["data"].get("code")
    _is_success = _biz_code in _success_codes or _inner_code in _success_codes
    if resp.status_code == 200 and not _is_success and _biz_code is not None:
        _fail_msg = "[业务code失败] code=" + str(_biz_code)
        _fail_msg += ", message=" + str(_biz_resp.get("message"))
        _fail_msg += ", 响应体=" + json.dumps(_biz_resp, ensure_ascii=False)
        logger.error("【断言失败】%s", _fail_msg)
        raise AssertionError(_fail_msg)
    if _is_success:
        logger.info("【业务code检查】code=%s (成功), HTTP状态码=%d, 通过", _biz_code, resp.status_code)
    else:
        logger.info("【业务code检查】code=%s (非标准成功码), HTTP状态码=%d", _biz_code, resp.status_code)
    assert resp.status_code == 200, "HTTP状态码错误: " + str(resp.status_code)
    logger.info("【用例结束】%s 执行完成", __name__)
    logger.info("=" * 60)
