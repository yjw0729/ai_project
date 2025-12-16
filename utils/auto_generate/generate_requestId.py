import random
from datetime import datetime
import string


def generate_random_string(length: int = 10) -> str:
    """生成随机字符串"""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


def generate_timestamp()->str:
    '''生成时间戳'''
    return datetime.now().strftime("%Y%m%d%H%M%S")


def generate_request_id()->str:
    '''生成请求id'''
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = generate_random_string(6)
    return f"{timestamp}{random_suffix}"


def generate_business_order_no()->str:
    """生成业务订单号"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = generate_random_string(8)
    return f"BC{timestamp}{random_suffix}"


def generate_business_sub_order_no() -> str:
    """生成子业务订单号"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = generate_random_string(6)
    return f"SBC{timestamp}{random_suffix}"


def generate_business_trade_order_no() -> str:
    """生成交易订单号"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = generate_random_string(8)
    return f"TBC{timestamp}{random_suffix}"


def generate_payee_bank_ac_name() -> str:
    """生成收款人银行账户名称（示例数据）"""
    return "MG4CIDw9LfeesXebXrqHEZaSqFvhp9hoVu8l5kkBjWv5aAP9AiBcO/F5krD5axl+I+ZvWypQ8OX9KAPH2gStq7h+M4Xb7gQgHF3DAyd7ORzSQACnxhjdUW6DVsNjry73xFb8aeuC40MEBkEO3asQNQ=="



def generate_payee_bank_ac_no() -> str:
    """生成收款人银行账号（示例数据）"""
    return "MHoCIQDtmyRfuTFkGHufgvOTgI0NUYkajTsNwjX8fnqD7SJurQIhAO3k0wkLD0SSxVnk8lIvxwnnB01il269bp/DOssbb96jBCChZUMxlyPZJTS7qFsY9vF86ny61Ci6e3LKw/j20mz5wAQQO4TaIfBy3moxESEoENuC6g=="

