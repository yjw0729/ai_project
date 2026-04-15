"""
测试：响应字段提取功能完整性验证
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unittest.mock import MagicMock


def test_dataclass_extract_fields():
    from common.test_executor.test_case_executor import TestCaseExecutionData

    extract_cfg = [
        {"name": "orderId", "path": "$.data.orderId"},
        {"name": "userId", "path": "$.data.userId"},
    ]
    case = TestCaseExecutionData(
        case_id="TEST_001", db_id=1, name="测试", module="m", priority="P1",
        method="POST", path="/api", extract_fields=extract_cfg,
    )
    assert case.extract_fields == extract_cfg
    d = case.to_dict()
    assert "extract_fields" in d
    print("  [PASS] dataclass extract_fields 支持正常")


def test_executor_parse():
    from common.test_executor.test_case_executor import TestCaseExecutor
    executor = TestCaseExecutor()

    er1 = {"extract_fields": [{"name": "orderId", "path": "$.data.orderId"}]}
    result1 = executor._parse_extract_fields(er1)
    assert len(result1) == 1
    assert result1[0]["name"] == "orderId"

    er2 = {"extract": [{"name": "txnId", "path": "$.result.txnId"}]}
    result2 = executor._parse_extract_fields(er2)
    assert len(result2) == 1

    assert executor._parse_extract_fields({}) == []
    print("  [PASS] extract_fields 配置解析正常")


def test_pytest_generator_extract():
    from common.test_executor.pytest_generator import PytestGenerator
    from common.test_executor.test_case_executor import TestCaseExecutionData

    gen = PytestGenerator(output_dir="outputs/test_extract")
    case = TestCaseExecutionData(
        case_id="TEST_001", db_id=1, name="创建订单", module="m", priority="P1",
        method="POST", path="/api/createOrder",
        request_body={"productId": "P100"},
        extract_fields=[
            {"name": "orderId", "path": "$.data.orderId"},
            {"name": "feeAmount", "path": "$.data.feeAmount"},
        ],
    )
    code = gen._build_one_test_function(case, 0, "http://test.com", MagicMock())

    assert "extract_from_response" in code
    assert "orderId" in code
    assert "feeAmount" in code
    assert "$.data.orderId" in code
    assert "$.data.feeAmount" in code
    assert "_get_session_context" in code

    req_idx = code.index("【发送请求】开始发送HTTP请求")
    resp_var_idx = code.index("【响应变量替换】检查请求数据中的")
    assert resp_var_idx < req_idx
    print("  [PASS] PytestGenerator 生成 extract_fields 代码正常")


def test_response_extract_fixture():
    from common.test_executor.response_extract import extract_from_response, clear_extracted

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "code": "000000",
        "data": {
            "billId": "542dbb40e3784d5f95eb3ac497577f5e",
            "feeAmount": 2.10,
        }
    }
    cfg = [
        {"name": "billId", "path": "$.data.billId"},
        {"name": "feeAmount", "path": "$.data.feeAmount"},
    ]
    ctx = {}
    result = extract_from_response(mock_resp, cfg, context=ctx, case_id="TEST_BILL")
    assert result["billId"] == "542dbb40e3784d5f95eb3ac497577f5e"
    assert result["feeAmount"] == 2.10
    assert ctx["billId"] == "542dbb40e3784d5f95eb3ac497577f5e"
    clear_extracted(ctx)
    assert len(ctx) == 0
    print("  [PASS] response_extract 夹具功能正常")


def test_parameter_resolver():
    """测试 ParameterResolver 支持 ${RESPONSE.xxx} 占位符（直接测内部方法避免 shell 转义）"""
    from common.test_executor.parameter_resolver import ParameterResolver

    resolver = ParameterResolver(global_variables={"base": "http://test.com"})

    # 直接调用 _resolve_string，原始字符串精确传入
    test_value = "${RESPONSE.billId}"
    resolved_str = resolver._resolve_string(test_value)

    # 验证：占位符被保留
    assert resolved_str == "${RESPONSE.billId}", f"期望保留占位符，实际: {resolved_str}"

    # 验证：replaced_vars 中有 response_extract 记录
    replaced = resolver.get_replaced_vars()
    resp_vars = [v for v in replaced if v.get("source") == "response_extract"]
    assert len(resp_vars) >= 1
    assert resp_vars[0]["var_name"] == "billId"

    # 测试完整 resolve
    data = {
        "billId": "${RESPONSE.billId}",
        "feeAmount": "${RESPONSE.feeAmount}",
        "static": "value",
        "globalRef": "{{base}}",
    }
    resolved = resolver.resolve(data)
    assert resolved["billId"] == "${RESPONSE.billId}"
    assert resolved["feeAmount"] == "${RESPONSE.feeAmount}"
    assert resolved["static"] == "value"
    assert resolved["globalRef"] == "http://test.com"

    print("  [PASS] ParameterResolver 支持 ${RESPONSE.xxx} 占位符")


def test_end_to_end():
    from common.test_executor.pytest_generator import PytestGenerator
    from common.test_executor.test_case_executor import TestCaseExecutionData

    gen = PytestGenerator(output_dir="outputs/test_extract")

    case1 = TestCaseExecutionData(
        case_id="CASE_BILL", db_id=1, name="获取账单", module="m", priority="P1",
        method="POST", path="/api/bill",
        extract_fields=[
            {"name": "billId", "path": "$.data.billId"},
            {"name": "feeAmount", "path": "$.data.feeAmount"},
        ],
    )
    case2 = TestCaseExecutionData(
        case_id="CASE_PAY", db_id=2, name="支付", module="m", priority="P1",
        method="POST", path="/api/pay",
        request_body={"billId": "${RESPONSE.billId}", "amount": "${RESPONSE.feeAmount}"},
    )
    code1 = gen._build_one_test_function(case1, 0, "http://test.com", MagicMock())
    code2 = gen._build_one_test_function(case2, 1, "http://test.com", MagicMock())

    assert "extract_from_response" in code1
    assert "$.data.billId" in code1
    assert "$.data.feeAmount" in code1
    assert "【响应变量替换】" in code2
    assert "${RESPONSE.billId}" in code2
    assert "_get_session_context" in code2
    print("  [PASS] 端到端流程正常（用例1提取 -> 用例2引用）")


def main():
    print("\n" + "=" * 50)
    print("响应字段提取功能 - 完整性验证")
    print("=" * 50)
    tests = [
        test_dataclass_extract_fields,
        test_executor_parse,
        test_pytest_generator_extract,
        test_response_extract_fixture,
        test_parameter_resolver,
        test_end_to_end,
    ]
    passed = failed = 0
    for fn in tests:
        try:
            print(f"\n>>> {fn.__name__}")
            fn()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            import traceback; traceback.print_exc()
            failed += 1
    print("\n" + "=" * 50)
    print(f"结果: {passed}/{passed+failed} 通过")
    if failed == 0:
        print("所有测试通过！")
    else:
        print(f"失败 {failed} 个测试")
        sys.exit(1)


if __name__ == "__main__":
    main()
