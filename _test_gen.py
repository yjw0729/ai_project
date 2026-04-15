"""测试 PytestGenerator 的 null 处理"""
import sys
sys.path.insert(0, r'd:\pythonProject\pytest_sxp')
from common.test_executor.pytest_generator import PytestGenerator

class MockCase:
    case_id = 'T001'
    name = 'test'
    method = 'POST'
    path = '/test'
    priority = 'P1'
    timeout = 30
    headers = {}
    query_params = {}
    request_body = {'x': None, 'y': 'value', 'z': [None, 1]}
    assertions = []
    post_script = []
    db_checks = []
    case_variables = {}

g = PytestGenerator(output_dir='outputs/generated_tests')
tf = g.generate(
    cases=[MockCase()],
    execution_id='test_null_fix',
    base_url='http://localhost:8080'
)
print(f'Generated: {tf}')
content = open(tf, encoding='utf-8').read()
print('HAS null:', 'null' in content)
print('HAS None:', 'None' in content)
# Print first 1000 chars
print('=== CONTENT ===')
print(content[:1000])