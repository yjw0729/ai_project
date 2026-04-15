"""测试 PytestGenerator 获取 request_body"""
import sys
sys.path.insert(0, r"d:\pythonProject\pytest_sxp")

from common.test_executor.pytest_generator import PytestGenerator
from common.test_executor.parameter_resolver import ParameterResolver
from common.test_executor.test_case_executor import TestCaseExecutionData
import json

# 创建测试用例数据
case = TestCaseExecutionData(
    case_id="TEST_CASE_000000001",
    db_id=1,
    name="测试用例",
    module="测试模块",
    priority="P0",
    method="POST",
    path="/test/api",
    headers={"Content-Type": "application/json"},
    query_params={},
    request_body={
        "data": {
            "bankCode": "",
            "payeeMno": "{{payeeMno}}",  # 需要被替换
            "rootMchId": "123456"
        },
        "requestId": "${RANDOM}",
        "timestamp": "${TIMESTAMP}"
    },
    assertions=[],
    post_script=[],
    db_checks=[],
    timeout=30,
    max_retry_times=0,
    tags=[],
    case_status="enabled",
    description="测试描述",
    preconditions='{"payeeMno": "ALIPAY", "rootMchId": "123456"}',
    case_variables={"payeeMno": "ALIPAY", "rootMchId": "123456"},
)

print("=== 测试 case 数据 ===")
print(f"case.request_body: {json.dumps(case.request_body, ensure_ascii=False)}")
print(f"case.case_variables: {case.case_variables}")

# 模拟 PytestGenerator 的获取方式
request_body = getattr(case, "request_body", None)
print(f"\ngetattr(case, 'request_body', None): {request_body}")

# 模拟变量替换
resolver = ParameterResolver(global_variables={})
all_vars = dict(resolver.global_variables)
all_vars.update(case.case_variables)
print(f"\n合并后的变量: {all_vars}")

case_resolver = ParameterResolver(global_variables=all_vars)
resolved_request_body = case_resolver.resolve(request_body)
print(f"\n变量替换后的请求体: {json.dumps(resolved_request_body, ensure_ascii=False)}")

# 检查是否被替换了
if resolved_request_body != request_body:
    print("\n✓ 变量替换成功！")
    print(f"  原始 payeeMno: {request_body.get('data', {}).get('payeeMno')}")
    print(f"  替换后 payeeMno: {resolved_request_body.get('data', {}).get('payeeMno')}")
else:
    print("\n✗ 变量没有被替换！")
