import requests
import pytest
from selenium import webdriver
import time
import requests
'''
测试类和方法都需要以test开头
'''


@pytest.mark.parametrize('url',["http://www.baidu.com", "http://cn.bing.com"])
def test_baidu_api(url):
    response = requests.get(url)
    assert response.status_code == 200
    print(f"{url}进入成功")


def test_web():
    driver = webdriver.Chrome()
    driver.get("http://www.baidu.com")
    time.sleep(1)
    pass


def test_request(url, method, **kwargs):
    response = requests.request(method=method, url=url, **kwargs)

    request_info = {
        f"请求头: {kwargs.get('header', {})}\n",
        f"请求方式: {method}\n",
        f"请求地址: {url}\n",
        f"请求体: {kwargs.get('bodu', kwargs.get('../data', 'null'))}"
    }



if __name__ == '__main__':
    test_web()








