import requests

resp = requests.post('http://127.0.0.1:5000/data_service/testcase/list', json={})
data = resp.json()

print("=" * 60)
print("测试用例列表")
print("=" * 60)

for item in data.get('data', []):
    print(f"ID: {item['id']}")
    print(f"  名称: {item['name']}")
    print(f"  api_config_id: {item.get('api_config_id')}")
    print(f"  模块: {item['module']}")
    print("-" * 40)
