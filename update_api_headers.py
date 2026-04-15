"""
更新 crosstest_api_config 表的 headers 字段
"""
import json
from common.datacase_function.contect_db import db_session
from common.db_enitiy.api_config import ApiConfig

headers = {
    "user-info": json.dumps({
        "id": "20250625151835001664133640",
        "userPhone": "11908312323",
        "userEmail": "11908312323@qq.com",
        "userStatus": "2",
        "inMno": "603250625000506",
        "merchantRegion": "HK",
        "countryCode": "CN",
        "jhMno": "M001200000003196",
        "mecTypeCode": "15",
        "userType": 1,
        "subjectArea": "HK",
        "merType": "00",
        "agentFlag": False,
        "dataIsolation": 0,
        "accountServiceFlag": "00",
        "loginSource": "PC"
    }, ensure_ascii=False),
    "Content-Type": "application/json"
}

with db_session() as session:
    count = session.query(ApiConfig).filter(ApiConfig.name == '询价').update({"headers": headers})
    print(f"更新了 {count} 条记录")

# 验证
with db_session() as session:
    from sqlalchemy import inspect
    row = session.query(ApiConfig).filter(ApiConfig.name == '询价').first()
    if row:
        print(f"接口名称: {row.name}")
        print(f"headers: {row.headers}")
    else:
        print("未找到 '询价' 接口")
