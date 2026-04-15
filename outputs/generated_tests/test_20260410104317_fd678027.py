# -*- coding: utf-8 -*-
# ============================================================
# pytest 测试文件 - execution_id: 20260410104317_fd678027
# 生成时间: 2026-04-10 10:43:17
# base_url: http://22.50.10.94:8080
# ============================================================

import pytest
import requests

# pytest fixtures (复用项目中的配置)
BASE_URL = "http://22.50.10.94:8080"
REQUEST_TIMEOUT = 30

# 测试用例参数化数据
CASES =         [
                {
                        "case_id": "TEST_CASE_000000006",
                        "name": "询价",
                        "method": "POST",
                        "path": "/v6/api/cashout/payment/common-payment-price",
                        "priority": "P0",
                        "headers": {
                                "Content-Type": "application/json"
                        },
                        "params": null,
                        "body": {
                                "uuid": "59a13dfe60724428b61a2eb333785089",
                                "sesAmt": 11,
                                "accuntId": 11221,
                                "txnModel": "1",
                                "accountNo": "db701ea8062e405facfbf36eafd0bd0d",
                                "reqSource": "WEB",
                                "chargeType": "SHA",
                                "paymentAmt": 11,
                                "paymentWay": "SWIFT",
                                "accCurrency": "USD",
                                "realNameFlag": "1",
                                "deductFeeMode": "OUTER",
                                "paymentCountry": "CN",
                                "paymentWayName": "跨境SWIFT",
                                "vaBusinessType": "B2B",
                                "paymentCurrency": "USD",
                                "localSettleMethod": null,
                                "supplierOrderType": "1"
                        },
                        "assertions": []
                }
        ]

# ===== Fixtures =====

@pytest.fixture(scope='session')
def http_session():
    """会话级 HTTP Session，复用连接池"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "Pytest-AutoTest/1.0"
    })
    yield session
    session.close()

@pytest.fixture(scope='session')
def execution_config():
    """执行配置"""
    return {
        "timeout": 30,
        "base_url": "http://22.50.10.94:8080",
    }

# ===== 测试用例 =====

@pytest.mark.parametrize('case', [{'case_id': 'TEST_CASE_000000006', 'name': '询价', 'method': 'POST', 'path': '/v6/api/cashout/payment/common-payment-price', 'priority': 'P0', 'headers': {'Content-Type': 'application/json'}, 'params': None, 'body': {'uuid': '59a13dfe60724428b61a2eb333785089', 'sesAmt': 11, 'accuntId': 11221, 'txnModel': '1', 'accountNo': 'db701ea8062e405facfbf36eafd0bd0d', 'reqSource': 'WEB', 'chargeType': 'SHA', 'paymentAmt': 11, 'paymentWay': 'SWIFT', 'accCurrency': 'USD', 'realNameFlag': '1', 'deductFeeMode': 'OUTER', 'paymentCountry': 'CN', 'paymentWayName': '跨境SWIFT', 'vaBusinessType': 'B2B', 'paymentCurrency': 'USD', 'localSettleMethod': None, 'supplierOrderType': '1'}, 'assertions': []}])
def test_api(http_session, execution_config, case):
    """参数化测试用例"""
    case_id = case['case_id']
    name = case['name']
    method = case['method']
    path = case['path']
    headers = case.get('headers')
    params = case.get('params')
    body = case.get('body')
    assertions = case.get('assertions', [])
    priority = case.get('priority', 'P2')

    # 构建请求
    url = BASE_URL.rstrip('/') + '/' + path.lstrip('/')
    req_headers = {'Content-Type': 'application/json'}
    if headers:
        req_headers.update(headers)

    print(f"[{priority}] {case_id} - {name}")
    print(f"[Request] {method} {url}")

    # 发送请求
    resp = http_session.request(
        method=method,
        url=url,
        headers=req_headers,
        params=params,
        json=body,
        timeout=REQUEST_TIMEOUT,
    )

    print(f"[Response] {resp.status_code} - {resp.elapsed.total_seconds()*1000:.0f}ms")

    # 执行断言
    _execute_assertions(resp, assertions)


def _execute_assertions(resp, assertions):
    """执行断言逻辑"""
    if not assertions:
        # 默认断言：状态码 200
        assert resp.status_code == 200, "status code error: " + str(resp.status_code)
        return

    for a in assertions:
        a_type = a.get('type', 'status_code')
        a_name = a.get('name', 'assertion')
        expected = a.get('expected')
        path_str = a.get('path', '')
        max_ms = a.get('max_ms')

        if a_type == 'status_code':
            assert resp.status_code == expected, f'[{a_name}] status: {resp.status_code}'

        elif a_type == 'response_time':
            limit = max_ms or expected or 5000
            actual_ms = resp.elapsed.total_seconds() * 1000
            assert actual_ms <= limit, f'[{a_name}] response time: {actual_ms:.0f}ms > {limit}ms'

        elif a_type == 'contains':
            assert expected in resp.text, f'[{a_name}] response body not contains: {expected}'

        elif a_type == 'not_contains':
            assert expected not in resp.text, f'[{a_name}] response body should not contain: {expected}'

        elif a_type in ('equals', 'json_path', 'not_equals', 'regex',
                       'not_empty', 'length', 'greater_than', 'less_than',
                       'in_list', 'not_in_list'):
            _assert_json_path(resp, path_str, expected, a_type, a_name)

        elif a_type == 'header':
            header_name = a.get('header', '')
            assert header_name in resp.headers, f'[{a_name}] header missing: {header_name}'

        else:
            print(f"[Warning] unknown assertion type: {a_type}")


def _assert_json_path(resp, path_str, expected, a_type, a_name):
    """json_path 断言辅助函数"""
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
        assert actual == expected, f'[{a_name}] path={path_str}: expected={expected}, actual={actual}'
    elif a_type == 'not_equals':
        assert actual != expected, f'[{a_name}] path={path_str}: should not be {expected}'
    elif a_type == 'regex':
        import re
        assert re.search(expected, str(actual) or ''), f'[{a_name}] path={path_str}: not match {expected}'
    elif a_type == 'not_empty':
        assert actual is not None and actual != '' and actual != [], f'[{a_name}] path={path_str}: is empty'
    elif a_type == 'length':
        assert len(actual) == expected, f'[{a_name}] path={path_str}: len={len(actual)}, expected={expected}'
    elif a_type == 'greater_than':
        assert actual > expected, f'[{a_name}] path={path_str}: {actual} <= {expected}'
    elif a_type == 'less_than':
        assert actual < expected, f'[{a_name}] path={path_str}: {actual} >= {expected}'
    elif a_type == 'in_list':
        assert actual in expected, f'[{a_name}] path={path_str}: {actual} not in {expected}'
    elif a_type == 'not_in_list':
        assert actual not in expected, f'[{a_name}] path={path_str}: {actual} in {expected}'