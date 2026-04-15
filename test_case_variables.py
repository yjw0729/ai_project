"""测试 case_variables 是否正确传递"""
from common.test_executor.test_case_executor import TestCaseExecutor, TestCaseExecutionData

# 创建测试用例数据
print("=== 测试 TestCaseExecutionData ===")

# 模拟一个 case 对象
class MockCase:
    def __init__(self):
        self.id = 1
        self.case_id = "TEST_CASE_000000001"
        self.name = "测试用例"
        self.module = "测试模块"
        self.priority = "P0"
        self.api_config_id = 1
        self.expected_results = {}
        self.test_data = None
        self.timeout = 30
        self.max_retry_times = 0
        self.tags = []
        self.case_status = "enabled"
        self.description = "测试描述"
        self.test_steps = None
        self.preconditions = '{"payeeMno": "600600010996929", "rootMchId": "123456"}'

# 模拟 api_config
class MockApiConfig:
    def __init__(self):
        self.id = 1
        self.name = "测试接口"
        self.module = "测试模块"
        self.api_path = "/test/api"
        self.method = "POST"
        self.description = ""
        self.request_type = "json"
        self.headers = None
        self.default_params = None
        self.request_body_template = None
        self.is_encryption = False
        self.encryption_config = None
        self.expected_response = None
        self.timeout = 30
        self.retry_times = 0
        self.is_deprecated = False

# 测试
executor = TestCaseExecutor()

# 模拟获取 case
mock_case = MockCase()
mock_api_config = MockApiConfig()
api_configs = {1: mock_api_config}

# 调用 _build_execution_data
exec_data = executor._build_execution_data(mock_case, api_configs, None)

print(f"case_id: {exec_data.case_id}")
print(f"request_body: {exec_data.request_body}")
print(f"case_variables: {exec_data.case_variables}")
print(f"preconditions: {exec_data.preconditions}")

# 检查 dataclass 字段
print("\n=== dataclass 字段检查 ===")
print(f"hasattr request_body: {hasattr(exec_data, 'request_body')}")
print(f"request_body type: {type(exec_data.request_body)}")
print(f"request_body is None: {exec_data.request_body is None}")

# 检查 case_variables 是否被正确传递
print("\n=== case_variables 检查 ===")
print(f"hasattr case_variables: {hasattr(exec_data, 'case_variables')}")
print(f"case_variables type: {type(exec_data.case_variables)}")
print(f"case_variables: {exec_data.case_variables}")

# 测试 getattr
print("\n=== getattr 测试 ===")
request_body_via_getattr = getattr(exec_data, "request_body", None)
case_variables_via_getattr = getattr(exec_data, "case_variables", None)
print(f"getattr request_body: {request_body_via_getattr}")
print(f"getattr case_variables: {case_variables_via_getattr}")
