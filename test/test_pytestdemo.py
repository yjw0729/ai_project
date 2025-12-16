import pytest
import requests
import allure
import json
import os


@allure.step("发送{method}请求到{url}")
def send_request(method, url, **kwargs):
    '''
    实现一个http接口请求，包含请求和断言还有报告
    '''
    response = requests.request(method=method, url=url, **kwargs)

    # 构建请求信息字符串
    request_info = (
        f"请求URL: {url}\n"
        f"请求方法: {method}\n"
        f"请求头: {kwargs.get('headers', {})}\n"
        f"请求体: {kwargs.get('json', kwargs.get('../data', '无'))}"
    )

    # 请求内容记录到allure报告
    allure.attach(
        request_info,
        name="请求详情",
        attachment_type=allure.attachment_type.TEXT
    )

    try:
        response_body = response.json()
        allure.attach(
            #dumps将python对象转为json.dump需要传入文件Python对象转换成JSON字符串并写入文件
            json.dumps(response_body, indent=2),
            name='响应内容-json',
            attachment_type=allure.attachment_type.JSON
        )
    except:
        allure.attach(
            response.text,
            name='响应内容-text',
            attachment_type=allure.attachment_type.TEXT
        )

    # 构建响应摘要字符串
    response_summary = (
        f"状态码: {response.status_code}\n"
        f"响应时间: {response.elapsed.total_seconds()}秒"
    )

    allure.attach(
        response_summary,
        name="响应码值&时间",
        attachment_type=allure.attachment_type.TEXT
    )

    return response


@allure.step("验证响应状态码字段，期望{expected_code}")
def assert_request(response, field, expected_value, expected_code):  # 修正：函数名拼写错误
    assert response.status_code == expected_code, \
        f"状态码不匹配，期望为{expected_code},实际是{response.status_code}"

    try:
        data = response.json()  # 修正：需要调用 json() 方法
    except:
        pytest.fail("响应报文不是JSON格式")

    keys = field.split('.')
    actual = data
    for key in keys:
        if key not in actual:
            pytest.fail(f"字段 '{key}' 不存在于响应中")
        actual = actual[key]

    assert actual == expected_value, \
        f"字段 {field}: 期望 {expected_value}, 实际 {actual}"


@allure.feature("用户测试API")
class TestUserApi:
    BASE_URL = "https://jsonplaceholder.typicode.com"  # 修正：使用有效的URL

    @allure.story("获取用户信息")
    @allure.title("成功获取信息")
    def test_get_user(self):
        response = send_request('GET', f"{self.BASE_URL}/users/1")  # 修正：使用 self.BASE_URL
        assert_request(response, "name", "Leanne Graham", 200)

    @allure.story("创建用户")
    @allure.title("成功创建新用户")
    def test_create_user(self):
        user_data = {
            "name": "Test User",
            "email": "test@example.com"
        }
        response = send_request('POST', f"{self.BASE_URL}/users", json=user_data)  # 修正：端点应该是 /users
        # 创建用户通常返回201状态码，且响应包含创建的数据
        assert_request(response, "name", "Test User", 201)  # 修正：期望值和状态码


if __name__ == '__main__':
    # 修正：pytest.main 参数应该是一个列表，包含所有参数
    pytest.main([__file__, "--alluredir=allure-results", "-v"])
    os.system("allure generate allure-results -o allure-report --clean")

