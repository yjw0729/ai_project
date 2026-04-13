import os
from utils.email.send_email import send_email
import pytest


def pytest_sessionfinish(session, exitstatus):
    report_dir = r"D:\pythonProject\pytest_sxp\reports"
    if not os.path.exists(report_dir):
        os.makedirs(report_dir)
    # 邮件发送保留（后续可按需调整）
    send_email()
