'''
使用方法1：进行接口自动化验证

'''

import pytest
import requests


class TestBusinessAPI:

    BASE_URL = "http://22.50.8.21:8080/businessAction/commonBusiness"
    TEST_DATA = [("/BASIC_TMZZ",
                     {"format": "123123","version": "OPTS-1.1","timestamp": "2003-02-14 13:23:21","data": {"requestId": "20255317045306dxsxmehfqiidfku","orderExpired": "90","notifyUrl": "http://mqhjshjkr.bm/ihb","frontUrl": "链接","rootMchId": "600600011000072","transferMno": "600600011000072","payerAcType": "YXH","remark": "同名转账备注",
"batchActionList": [{"outTradeNo": "BS20255317045306hobqdhztqj","payeeAcType": "XJH","transferAmount": 2.99,"remark": "备注","productInfos": [{"orderNo": "3131312312","orderAmount": 22,"productName": "电卡","productCount": 1,"productNo": "432423423","remark": "ullamco sunt minim nulla nisi"}]}]}},
         200,
{"code":"000000","data":{"code":"000000","message":"成功"},"businessOrderResponse":[{"status":"processing"}]}),
        ("/BASIC_TMZZ",
         {"format": "123123", "version": "OPTS-1.1", "timestamp": "2003-02-14 13:23:21","data": {"requestId": "20255317045306dxsxmehfqiidfku", "orderExpired": "90","notifyUrl": "http://mqhjshjkr.bm/ihb", "frontUrl": "链接",
"rootMchId": "600600011000072", "transferMno": "600600011000072","payerAcType": "YXH", "remark": "同名转账备注","batchActionList": [{"outTradeNo": "BS20255317045306hobqdhztqj", "payeeAcType": "XJH","transferAmount": 2.99, "remark": "备注", "productInfos": [
{"orderNo": "3131312312", "orderAmount": 22, "productName": "电卡","productCount": 1, "productNo": "432423423","remark": "ullamco sunt minim nulla nisi"}]}]}},
            200,
            {"code": "000000", "data": {"code": "000000", "message": "成功"},"businessOrderResponse": [{"status": "processing"}]}
        )
    ]

@pytest.mark.parametrize("path, payload, expected_status, expected_response", TestBusinessAPI.TEST_DATA)
def test_poset_api(path, payload, expected_status, expected_response):
    url = f"{TestBusinessAPI.BASE_URL}{path}"

    response = requests.post(
        url = url,
        json = payload,
        timeout = 5
    )

    assert response.status_code == expected_status,\
        f"预期状态码{expected_status},实际返回{response.status_code}"

    try:
        response_json = response.json()
    except ValueError:
        pytest.fail(f"响应不是有效的JSON格式:{response.text}")

    for key, expected_value in expected_response.items():
        assert key in response_json, f"响应中缺少关键字段 '{key}'"
        assert response_json[key] == expected_value, \
            f"字段 '{key}' 预期值: {expected_value}, 实际值: {response_json[key]}"





