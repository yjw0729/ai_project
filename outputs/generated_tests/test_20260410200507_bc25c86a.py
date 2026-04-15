# ============================================================
# Auto-generated pytest test file
# execution_id: 20260410200507_bc25c86a
# generated_at: 2026-04-10T20:05:07.156572
# base_url: http://22.50.10.94:8080
# retry_times: 0
# timeout: 30s
# ============================================================

import pytest
import requests
import json
import time
import allure
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---- 全局配置 ----
BASE_URL = "http://22.50.10.94:8080"
REQUEST_TIMEOUT = 30
EXECUTION_ID = "20260410200507_bc25c86a"

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
@allure.severity(allure.severity_level.BLOCKER)
@allure.feature("交易模块")
@allure.story("TEST_CASE_000000006")
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
    logger.info("【请求头】%s", {"X-User-Info": "user123", "Content-Type": "application/json"})
    allure.attach('{"X-User-Info": "user123", "Content-Type": "application/json"}', name="headers", attachment_type=allure.attachment_type.JSON)
    logger.info("【Query参数】无Query参数")
    _raw_body = {"uuid": "59a13dfe60724428b61a2eb333785089", "sesAmt": 11, "accuntId": 11221, "txnModel": "1", "accountNo": "db701ea8062e405facfbf36eafd0bd0d", "reqSource": "WEB", "chargeType": "SHA", "paymentAmt": 11, "paymentWay": "SWIFT", "accCurrency": "USD", "realNameFlag": "1", "deductFeeMode": "OUTER", "paymentCountry": "CN", "paymentWayName": "跨境SWIFT", "vaBusinessType": "B2B", "paymentCurrency": "USD", "localSettleMethod": null, "supplierOrderType": "1"}
    _resolved_body = _raw_body
    logger.info("【请求体-原始】%s", _raw_body)
    logger.info("【请求体-变量替换后】%s (无变量，未变更)", _resolved_body)
    logger.info("【请求体-类型】%s", type(_resolved_body).__name__)
    allure.attach(json.dumps(_raw_body, ensure_ascii=False, indent=2), name="body-raw", attachment_type=allure.attachment_type.JSON)
    logger.info("【完整请求】")
    logger.info("    URL: %s", BASE_URL.rstrip("/") + "/" + "/v6/api/cashout/payment/common-payment-price".lstrip("/"))
    logger.info("    Method: %s", "POST")
    logger.info("    Headers(替换后): %s", {"X-User-Info": "user123", "Content-Type": "application/json"})
    logger.info("    Query(替换后): %s", None)
    logger.info("    Body(替换后): %s", str(_resolved_body)[:500] if _resolved_body is not None else "None")
    with allure.step("请求信息: POST /v6/api/cashout/payment/common-payment-price"):
        allure.attach('{"X-User-Info": "user123", "Content-Type": "application/json"}', name="headers", attachment_type=allure.attachment_type.JSON)
        allure.attach('{"uuid": "59a13dfe60724428b61a2eb333785089", "sesAmt": 11, "accuntId": 11221, "txnModel": "1", "accountNo": "db701ea8062e405facfbf36eafd0bd0d", "reqSource": "WEB", "chargeType": "SHA", "paymentAmt": 11, "paymentWay": "SWIFT", "accCurrency": "USD", "realNameFlag": "1", "deductFeeMode": "OUTER", "paymentCountry": "CN", "paymentWayName": "跨境SWIFT", "vaBusinessType": "B2B", "paymentCurrency": "USD", "localSettleMethod": null, "supplierOrderType": "1"}', name="body", attachment_type=allure.attachment_type.JSON)
    with allure.step("发送请求"):
        logger.info("【发送请求】开始发送HTTP请求...")
        _request_url = BASE_URL.rstrip("/") + "/" + "/v6/api/cashout/payment/common-payment-price".lstrip("/")
        logger.info("【发送请求】即将发送: %s %s", "POST", _request_url)
        logger.info("【发送请求】完整请求: method=%s, url=%s, headers=%s, params=%s, body=%s",             "POST", _request_url, {"X-User-Info": "user123", "Content-Type": "application/json"}, None,             json.dumps(_resolved_body, ensure_ascii=False)[:500] if _resolved_body is not None else "None")
        resp = _request(
            method="POST",
            path="/v6/api/cashout/payment/common-payment-price",
            headers={"X-User-Info": "user123", "Content-Type": "application/json"},
            params=None,
            json_body={"uuid": "59a13dfe60724428b61a2eb333785089", "sesAmt": 11, "accuntId": 11221, "txnModel": "1", "accountNo": "db701ea8062e405facfbf36eafd0bd0d", "reqSource": "WEB", "chargeType": "SHA", "paymentAmt": 11, "paymentWay": "SWIFT", "accCurrency": "USD", "realNameFlag": "1", "deductFeeMode": "OUTER", "paymentCountry": "CN", "paymentWayName": "跨境SWIFT", "vaBusinessType": "B2B", "paymentCurrency": "USD", "localSettleMethod": null, "supplierOrderType": "1"},
            timeout=30,
        )
        logger.info("【发送请求】请求已发送，等待响应...")
        logger.info("=" * 60)
        logger.info("【响应信息】")
        logger.info("    状态码: %s", resp.status_code)
        logger.info("    响应头: %s", dict(resp.headers))
        logger.info("    响应体(前500字符): %s", resp.text[:500] if resp.text else "空响应")
        logger.info("    响应时间: %s ms", resp.elapsed.total_seconds() * 1000)
        logger.info("=" * 60)
        allure.attach(
            json.dumps({
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "body": resp.text[:2000],
            }, ensure_ascii=False, indent=2),
            name="response",
            attachment_type=allure.attachment_type.JSON,
        )
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
    with allure.step("执行断言"):
            assert resp.status_code == 200, "状态码错误: " + str(resp.status_code)
    logger.info("【用例结束】%s 执行完成", __name__)
    logger.info("=" * 60)
