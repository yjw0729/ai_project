"""自测脚本：验证 Mock Service 模块可以正常加载"""
import sys
sys.path.insert(0, r"D:\pythonProject\pytest_sxp")

# 测试导入
print("测试1: 导入 MockRule...")
from mock_service.server import MockRule
print("  MockRule 导入成功")

print("测试2: 导入 MockServer...")
from mock_service.server import MockServer
print("  MockServer 导入成功")

print("测试3: 导入 fixtures...")
from mock_service.server import mock_server, mock_rule
print("  fixtures 导入成功")

print("测试4: 创建 MockRule 实例...")
rule = MockRule(
    id="test_rule",
    method="GET",
    url_pattern=r"/api/test/\d+",
    response_status=200,
    response_body={"message": "ok"},
    response_headers={"Content-Type": "application/json"},
    priority=1,
    delay=0.5
)
print(f"  MockRule 创建成功: {rule.id}")

print("测试5: 创建 MockServer 实例...")
server = MockServer()
print("  MockServer 创建成功")

print("测试6: 注册规则...")
server.register(rule)
print("  规则注册成功")

print("测试7: 匹配请求...")
matched_rule = server.match_request("GET", "/api/test/123")
print(f"  匹配结果: {matched_rule is not None}")

print("测试8: 获取响应...")
response = server.get_response(matched_rule)
print(f"  响应状态: {response['status']}")
print(f"  响应体: {response['body']}")

print("测试9: 模拟完整请求...")
result = server.simulate_request("GET", "/api/test/456")
print(f"  模拟结果: {result is not None}")

print("测试10: 统计信息...")
stats = server.get_statistics()
print(f"  总规则数: {stats['total_rules']}")
print(f"  总调用次数: {stats['total_calls']}")

print("测试11: 动态响应...")
def dynamic_handler(request):
    return {"dynamic": True, "path": request.get("url")}
server.register(
    MockRule(
        id="dynamic_rule",
        method="POST",
        url_pattern="/api/dynamic",
        response_status=200,
        response_body={},
        response_headers={"Content-Type": "application/json"},
        priority=1
    ),
    dynamic_response=dynamic_handler
)
result = server.simulate_request("POST", "/api/dynamic")
print(f"  动态响应: {result['body']}")

print("测试12: 清除规则...")
server.clear()
print("  清除成功")

print("\n========== 所有测试通过 ==========")
