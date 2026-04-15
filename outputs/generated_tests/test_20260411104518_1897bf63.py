# ============================================================
# Auto-generated pytest test file
# execution_id: 20260411104518_1897bf63
# generated_at: 2026-04-11T10:45:18.378768
# base_url: http://22.50.10.94:8080
# retry_times: 0
# timeout: 30s
# ============================================================

import pytest
import requests
import json
import time
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---- 全局配置 ----
BASE_URL = "http://22.50.10.94:8080"
REQUEST_TIMEOUT = 30
EXECUTION_ID = "20260411104518_1897bf63"
RESULT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".test_results.json")

# ---- 结果收集：捕获每个用例的详细执行结果 ----
_test_results = {}
_test_context = {}  # 存储每个用例的响应上下文

def pytest_runtest_logreport(report):
    """pytest hook: 每个测试用例执行完成后记录结果"""
    if report.when == 'call':
        test_name = report.nodeid
        # 从 nodeid 提取函数名: module.py::test_func
        func_name = test_name.split('::')[-1] if '::' in test_name else test_name
        # 获取该用例的响应上下文
        context = _test_context.get(func_name, {})
        if report.failed:
            # 收集失败信息
            longrepr = getattr(report, 'longrepr', None)
            if longrepr:
                if hasattr(longrepr, 'reprcrash'):
                    failure_msg = str(longrepr.reprcrash.message)
                else:
                    failure_msg = str(longrepr)
            else:
                failure_msg = '用例执行失败'
            # 失败时返回完整响应信息
            resp_info = context.get('response', {})
            failure_msg += '\n响应状态码: ' + str(resp_info.get('status_code', 'N/A'))
            failure_msg += '\n响应体: ' + str(resp_info.get('body', 'N/A'))[:1000]
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
    try:
        with open(RESULT_FILE, 'w', encoding='utf-8') as f:
            json.dump(_test_results, f, ensure_ascii=False)
    except Exception:
        pass

def _store_test_context(func_name, resp):
    """存储测试上下文（响应信息），供 pytest hook 使用"""
    try:
        body = resp.text[:5000] if resp.text else ''
    except Exception:
        body = '无法读取响应体'
    _test_context[func_name] = {
        'response': {
            'status_code': resp.status_code,
            'body': body,
        }
    }

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

    logger.info("[_request] 实际发送: method=%s, url=%s, headers=%s, params=%s, body=%s",
                method.upper(), url, json.dumps(_headers, ensure_ascii=False),
                json.dumps(params, ensure_ascii=False) if params else "None",
                json.dumps(json_body, ensure_ascii=False)[:500] if json_body is not None else "None")

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
        raise AssertionError("请求超时 [" + method + "] " + url + ": 超过 " + str(timeout) + "s")
    except requests.exceptions.ConnectionError as e:
        raise AssertionError("连接失败 [" + method + "] " + url + ": " + str(e))

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
def test_1_TEST_CASE_000000006():
    """
    付款前前置操作

    Case ID: TEST_CASE_000000006
    Priority: P0
    Method: POST /v6/api/cashout/payment/common-payment-price
    """
    logger.info("=" * 60)
    logger.info("【用例开始】%s | %s", EXECUTION_ID, __name__)
    logger.info("【用例信息】ID=%s, 名称=%s, 模块=%s", "TEST_CASE_000000006", "询价", "交易模块")
    logger.info("【变量配置】无 preconditions 变量配置")
    logger.info("=" * 60)
    logger.info("【请求地址】base_url=%s, 接口路径=%s, 完整URL=%s", BASE_URL, "/v6/api/cashout/payment/common-payment-price", BASE_URL.rstrip("/") + "/" + "/v6/api/cashout/payment/common-payment-price".lstrip("/"))
    logger.info("【请求头】%s", "{raw_headers_json}")
    logger.info("【Query参数】无Query参数")
    _raw_body = {"uuid": "59a13dfe60724428b61a2eb333785089", "sesAmt": 11, "accuntId": 11221, "txnModel": "1", "accountNo": "ff813c70da4a4d5cb3e52fb72ed615d9", "reqSource": "WEB", "chargeType": "SHA", "paymentAmt": 11, "paymentWay": "SWIFT", "accCurrency": "USD", "realNameFlag": "1", "deductFeeMode": "OUTER", "paymentCountry": "CN", "paymentWayName": "跨境SWIFT", "vaBusinessType": "B2B", "paymentCurrency": "USD", "localSettleMethod": None, "supplierOrderType": "1"}
    _resolved_body = _raw_body
    logger.info("【请求体-原始】%s", _raw_body)
    logger.info("【请求体-变量替换后】%s (无变量，未变更)", _resolved_body)
    logger.info("【请求体-类型】%s", type(_resolved_body).__name__)
    logger.info("【完整请求】")
    logger.info("    URL: %s", BASE_URL.rstrip("/") + "/" + "/v6/api/cashout/payment/common-payment-price".lstrip("/"))
    logger.info("    Method: %s", "POST")
    logger.info("    Headers(替换后): %s", {"user-info": "{\"id\": \"20250625151835001664133640\", \"userPhone\": \"11908312323\", \"userEmail\": \"11908312323@qq.com\", \"userStatus\": \"2\", \"inMno\": \"603250625000506\", \"merchantRegion\": \"HK\", \"countryCode\": \"CN\", \"jhMno\": \"M001200000003196\", \"mecTypeCode\": \"15\", \"userType\": 1, \"subjectArea\": \"HK\", \"merType\": \"00\", \"agentFlag\": false, \"dataIsolation\": 0, \"accountServiceFlag\": \"00\", \"loginSource\": \"PC\"}", "Content-Type": "application/json"})
    logger.info("    Query(替换后): %s", None)
    logger.info("    Body(替换后): %s", str(_resolved_body)[:500] if _resolved_body is not None else "None")
    logger.info("【发送请求】开始发送HTTP请求...")
    _request_url = BASE_URL.rstrip("/") + "/" + "/v6/api/cashout/payment/common-payment-price".lstrip("/")
    logger.info("【发送请求】即将发送: %s %s", "POST", _request_url)
    logger.info("【发送请求】完整请求: method=%s, url=%s, headers=%s, params=%s, body=%s", "POST", _request_url, {"user-info": "{\"id\": \"20250625151835001664133640\", \"userPhone\": \"11908312323\", \"userEmail\": \"11908312323@qq.com\", \"userStatus\": \"2\", \"inMno\": \"603250625000506\", \"merchantRegion\": \"HK\", \"countryCode\": \"CN\", \"jhMno\": \"M001200000003196\", \"mecTypeCode\": \"15\", \"userType\": 1, \"subjectArea\": \"HK\", \"merType\": \"00\", \"agentFlag\": false, \"dataIsolation\": 0, \"accountServiceFlag\": \"00\", \"loginSource\": \"PC\"}", "Content-Type": "application/json"}, None, json.dumps(_resolved_body, ensure_ascii=False)[:500] if _resolved_body is not None else "None")
    resp = _request(
        method="POST",
        path="/v6/api/cashout/payment/common-payment-price",
        headers={"user-info": "{\"id\": \"20250625151835001664133640\", \"userPhone\": \"11908312323\", \"userEmail\": \"11908312323@qq.com\", \"userStatus\": \"2\", \"inMno\": \"603250625000506\", \"merchantRegion\": \"HK\", \"countryCode\": \"CN\", \"jhMno\": \"M001200000003196\", \"mecTypeCode\": \"15\", \"userType\": 1, \"subjectArea\": \"HK\", \"merType\": \"00\", \"agentFlag\": false, \"dataIsolation\": 0, \"accountServiceFlag\": \"00\", \"loginSource\": \"PC\"}", "Content-Type": "application/json"},
        params=None,
        json_body={"uuid": "59a13dfe60724428b61a2eb333785089", "sesAmt": 11, "accuntId": 11221, "txnModel": "1", "accountNo": "ff813c70da4a4d5cb3e52fb72ed615d9", "reqSource": "WEB", "chargeType": "SHA", "paymentAmt": 11, "paymentWay": "SWIFT", "accCurrency": "USD", "realNameFlag": "1", "deductFeeMode": "OUTER", "paymentCountry": "CN", "paymentWayName": "跨境SWIFT", "vaBusinessType": "B2B", "paymentCurrency": "USD", "localSettleMethod": None, "supplierOrderType": "1"},
        timeout=30,
    )
    _store_test_context("test_1_TEST_CASE_000000006", resp)
    logger.info("【发送请求】请求已发送，等待响应...")
    logger.info("【响应信息】状态码=%s, 响应时间=%.2fms")
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
    logger.info("    用例ID: TEST_CASE_000000006")
    logger.info("    断言数量: 0")
    logger.info("    无自定义断言，使用默认状态码断言")
    logger.info("=" * 60)
    logger.info("【执行断言】开始执行断言...")
    # ---- 自动检查：业务 code 是否为成功码 ----
    try:
        _biz_resp = resp.json()
    except Exception:
        _biz_resp = {}
    _biz_code = _biz_resp.get('code') if isinstance(_biz_resp, dict) else None
    _success_codes = ['000000', '00000000', '0', 'success', 'SUCCESS']
    # 同时检查内层 data.code（部分接口在 data 里也有 code）
    _inner_code = None
    if isinstance(_biz_resp.get('data'), dict):
        _inner_code = _biz_resp['data'].get('code')
    _is_success = _biz_code in _success_codes or _inner_code in _success_codes
    if resp.status_code == 200 and not _is_success and _biz_code is not None:
        _fail_msg = '[业务code失败] code=' + str(_biz_code)
        _fail_msg += ', message=' + str(_biz_resp.get('message'))
        _fail_msg += ', 响应体=' + json.dumps(_biz_resp, ensure_ascii=False)
        logger.error('【断言失败】%s', _fail_msg)
        raise AssertionError(_fail_msg)
    if _is_success:
        logger.info('【业务code检查】code=%s (成功), HTTP状态码=%d, 通过', _biz_code, resp.status_code)
    else:
        logger.info('【业务code检查】code=%s (非标准成功码), HTTP状态码=%d', _biz_code, resp.status_code)

    logger.info("【用例结束】%s 执行完成", __name__)
    logger.info("=" * 60)
