import os
import pytest
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# 获取项目根目录
# ROOT_DIR = r"D:\pythonProject\pytest_sxp\testcases"

# 报告目录设置为根目录下的 report 文件夹
# REPORT_DIR = os.path.join(ROOT_DIR, "reports")
REPORT_DIR = r"D:\pythonProject\pytest_sxp\testcases\reports"

ALLURE_RESULTS_DIR = r"D:\pythonProject\pytest_sxp\testcases\temps"


def send_email():
    smtp_server = "smtp.163.com"
    smtp_port = 465
    sender_email = "yjw2304771795@163.com"
    sender_password = "MDwy2vDGnXCGQfbK"
    receiver_email = "2304771795@qq.com"

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = '自动化测试报告'

    body = '测试完成，请查看附件'
    msg.attach(MIMEText(body, 'plain'))

    report_file = os.path.join(REPORT_DIR, "index.html")
    if os.path.exists(report_file):
        with open(report_file, 'rb') as f:
            part = MIMEApplication(f.read(), Name = "test_report.html")
        part['Content-Disposition'] = 'attachment; filename="test_report.html"'
        msg.attach(part)

    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
            print("邮件发送成功")
    except Exception as e:
        print(f"邮件发送失败: {e}")

