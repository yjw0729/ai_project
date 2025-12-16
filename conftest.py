import os
from utils.email.send_email import send_email
import pytest


def pytest_sessionfinish(session, exitstatus):
    # ROOT_DIR = r"D:\pythonProject\pytest_sxp\testcases"

    report_dir = r"D:\pythonProject\pytest_sxp\reports"
    if not os.path.exists(report_dir):
        os.makedirs(report_dir)

    print("测试会话结束钩子触发")  # 调试输出
    if os.path.exists("./temps"):
        os.system(f"allure generate ./temps -o {report_dir} --clean")
        send_email()
        os.system(f"allure open {report_dir}/")
