# ============================================================
# Auto-generated pytest test file
# execution_id: 20260416140403_7da3b9aa
# generated_at: 2026-04-16T14:04:03.663768
# base_url: http://22.50.10.94:8080
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

# ---- 响应字段提取：session 级上下文（供后续用例引用）----
from common.test_executor.response_extract import _get_session_context
from outputs.generated_tests.conftest import _extract_fields_by_config, _store_test_context

logger = logging.getLogger(__name__)

# ---- 全局配置 ----
BASE_URL = "http://22.50.10.94:8080"
REQUEST_TIMEOUT = 30
EXECUTION_ID = "20260416140403_7da3b9aa"

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

@pytest.fixture(scope='session')
def response_context():
    """Session 级响应提取上下文 fixture。"""
    ctx = _get_session_context()
    logger.info("[Fixture] response_context session 开始，已提取变量: %s", list(ctx.keys()))
    yield ctx
    logger.info("[Fixture] response_context session 结束，已提取变量: %s", list(ctx.keys()))
def test_1_TEST_CASE_000000104():
    """
    付款请求

    Case ID: TEST_CASE_000000104
    Priority: P0
    Method: POST /v6/api/cashout/payment/payment
    """
    logger.info("=" * 60)
    logger.info("【用例开始】%s | %s", EXECUTION_ID, __name__)
    logger.info("【用例信息】ID=%s, 名称=%s, 模块=%s", "TEST_CASE_000000104", "付款-test", "交易模块")
    logger.info("【变量配置】无 preconditions 变量配置")
    logger.info("=" * 60)
    logger.info("【请求地址】base_url=%s, 接口路径=%s, 完整URL=%s", BASE_URL, "/v6/api/cashout/payment/payment", BASE_URL.rstrip("/") + "/" + "/v6/api/cashout/payment/payment".lstrip("/"))
    _raw_headers_json = '{"user_info": "{\\"id\\": \\"20250625151835001664133640\\", \\"userPhone\\": \\"11908312323\\", \\"userEmail\\": \\"11908312323@qq.com\\", \\"userStatus\\": \\"2\\", \\"inMno\\": \\"603250625000506\\", \\"merchantRegion\\": \\"HK\\", \\"countryCode\\": \\"CN\\", \\"jhMno\\": \\"M001200000003196\\", \\"mecTypeCode\\": \\"15\\", \\"userType\\": 1, \\"subjectArea\\": \\"HK\\", \\"merType\\": \\"00\\", \\"agentFlag\\": false, \\"dataIsolation\\": 0, \\"accountServiceFlag\\": \\"00\\", \\"loginSource\\": \\"PC\\"}", "Content-Type": "application/json"}'
    logger.info("【请求头】%s", _raw_headers_json)
    logger.info("【Query参数】无Query参数")
    _raw_body = {"acNo": "f53e59a107a045e3a7663daf2592401f", "uuid": "c4ef84959dfa44dc851f7f55d733b328", "billId": "6221b94de033412b89f03bf93e83754b", "rateId": "c279027d7e884a4699d5cacb029da295", "ruleId": None, "sesAmt": "1.00", "routeId": 36, "authType": "PAYMENT_PASS_WORD", "chargeType": "SHA", "paymentAmt": "1.00", "paymentWay": "SWIFT", "supplierId": 11516, "accCurrency": "USD", "paymentType": "1", "sesAmtTotal": 11, "realNameFlag": "1", "deductFeeMode": "OUTER", "customShopList": [], "vaBusinessType": "B2C", "paymentCurrency": "USD", "paymentPassword": "ihcNNnjuiDbEezW/4pTZk7QaMpWFFUAFIfOT3bAkj0mpZsmQOU1+7hrmx2pevQyL+q0lGRKLv9FJHREFKVG2/j4pa6ege5brvlNQQLeftavbCiR9rqTEcx4FuF1uImi+vBhq9XRohDz677FcTYytkFGE+hRAv44wP26kz0986vA=", "localSettleMethod": None, "supplierOrderType": "1", "supplierAccountUuid": "b0bbeb3ea97f42c2a61c49250b9e49b5"}
    _resolved_body = _raw_body
    logger.info("【请求体-原始】%s", _raw_body)
    logger.info("【请求体-变量替换后】%s (无变量，未变更)", _resolved_body)
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
    logger.info("    URL: %s", BASE_URL.rstrip("/") + "/" + "/v6/api/cashout/payment/payment".lstrip("/"))
    logger.info("    Method: %s", "POST")
    logger.info("    Headers(替换后): %s", {"user_info": "{\"id\": \"20250625151835001664133640\", \"userPhone\": \"11908312323\", \"userEmail\": \"11908312323@qq.com\", \"userStatus\": \"2\", \"inMno\": \"603250625000506\", \"merchantRegion\": \"HK\", \"countryCode\": \"CN\", \"jhMno\": \"M001200000003196\", \"mecTypeCode\": \"15\", \"userType\": 1, \"subjectArea\": \"HK\", \"merType\": \"00\", \"agentFlag\": false, \"dataIsolation\": 0, \"accountServiceFlag\": \"00\", \"loginSource\": \"PC\"}", "Content-Type": "application/json"})
    logger.info("    Query(替换后): %s", None)
    logger.info("    Body(替换后): %s", str(_resolved_body)[:500] if _resolved_body is not None else "None")
    logger.info("【发送请求】开始发送HTTP请求...")
    _request_url = BASE_URL.rstrip("/") + "/" + "/v6/api/cashout/payment/payment".lstrip("/")
    logger.info("【发送请求】即将发送: %s %s", "POST", _request_url)
    logger.info("【发送请求】完整请求: method=%s, url=%s, headers=%s, params=%s, body=%s", "POST", _request_url, {"user_info": "{\"id\": \"20250625151835001664133640\", \"userPhone\": \"11908312323\", \"userEmail\": \"11908312323@qq.com\", \"userStatus\": \"2\", \"inMno\": \"603250625000506\", \"merchantRegion\": \"HK\", \"countryCode\": \"CN\", \"jhMno\": \"M001200000003196\", \"mecTypeCode\": \"15\", \"userType\": 1, \"subjectArea\": \"HK\", \"merType\": \"00\", \"agentFlag\": false, \"dataIsolation\": 0, \"accountServiceFlag\": \"00\", \"loginSource\": \"PC\"}", "Content-Type": "application/json"}, None, json.dumps(_resolved_body, ensure_ascii=False)[:500] if _resolved_body is not None else "None")
    resp = _request(
        method="POST",
        path="/v6/api/cashout/payment/payment",
        headers={"user_info": "{\"id\": \"20250625151835001664133640\", \"userPhone\": \"11908312323\", \"userEmail\": \"11908312323@qq.com\", \"userStatus\": \"2\", \"inMno\": \"603250625000506\", \"merchantRegion\": \"HK\", \"countryCode\": \"CN\", \"jhMno\": \"M001200000003196\", \"mecTypeCode\": \"15\", \"userType\": 1, \"subjectArea\": \"HK\", \"merType\": \"00\", \"agentFlag\": false, \"dataIsolation\": 0, \"accountServiceFlag\": \"00\", \"loginSource\": \"PC\"}", "Content-Type": "application/json"},
        params=None,
        json_body={"acNo": "f53e59a107a045e3a7663daf2592401f", "uuid": "c4ef84959dfa44dc851f7f55d733b328", "billId": "6221b94de033412b89f03bf93e83754b", "rateId": "c279027d7e884a4699d5cacb029da295", "ruleId": None, "sesAmt": "1.00", "routeId": 36, "authType": "PAYMENT_PASS_WORD", "chargeType": "SHA", "paymentAmt": "1.00", "paymentWay": "SWIFT", "supplierId": 11516, "accCurrency": "USD", "paymentType": "1", "sesAmtTotal": 11, "realNameFlag": "1", "deductFeeMode": "OUTER", "customShopList": [], "vaBusinessType": "B2C", "paymentCurrency": "USD", "paymentPassword": "ihcNNnjuiDbEezW/4pTZk7QaMpWFFUAFIfOT3bAkj0mpZsmQOU1+7hrmx2pevQyL+q0lGRKLv9FJHREFKVG2/j4pa6ege5brvlNQQLeftavbCiR9rqTEcx4FuF1uImi+vBhq9XRohDz677FcTYytkFGE+hRAv44wP26kz0986vA=", "localSettleMethod": None, "supplierOrderType": "1", "supplierAccountUuid": "b0bbeb3ea97f42c2a61c49250b9e49b5"},
        timeout=30,
    )
    _extracted_data = {}
    _store_test_context("test_1_TEST_CASE_000000104", resp, None)
    logger.info("【发送请求】请求已发送，等待响应...")
    logger.info("【响应信息】状态码=%s, 响应时间=%.2fms", resp.status_code, resp.elapsed.total_seconds() * 1000)
    logger.info("    响应Headers: %s", json.dumps(dict(resp.headers), ensure_ascii=False)[:500])
    logger.info("    响应体(前500字符): %s", resp.text[:500] if resp.text else "空响应")
    logger.info("【提取字段】无提取配置")
    logger.info("【响应解析】尝试解析响应体...")
    try:
        _response_json = resp.json()
        logger.info("    响应JSON: %s", json.dumps(_response_json, ensure_ascii=False)[:500])
    except Exception as _e:
        logger.warning("    响应体非JSON格式: %s", str(_e))
        _response_json = None
    logger.info("=" * 60)
    logger.info("【断言信息】")
    logger.info("    用例ID: TEST_CASE_000000104")
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
