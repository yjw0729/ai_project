"""
检查特定 doc_id 的状态
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
import json


def get_db_connection():
    """获取数据库连接"""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "db_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        configs = json.load(f)

    conf = configs.get("default", {})
    db_type = conf.get("type", "mysql+pymysql")
    host = conf.get("host")
    port = conf.get("port")
    db_name = conf.get("db_name")
    user = conf.get("user")
    password = conf.get("password")

    engine = create_engine(
        f"{db_type}://{user}:{quote_plus(password)}@{host}:{port}/{db_name}",
        echo=False,
    )
    return engine


def check_doc_id(doc_id):
    """检查 doc_id 在两个表中的状态"""
    engine = get_db_connection()
    with engine.connect() as conn:
        # 检查 summary 表
        sql_summary = text("""
            SELECT doc_id, document_title, status, reviewer, review_comment
            FROM crosstest_review_summary
            WHERE doc_id = :doc_id
        """)
        result = conn.execute(sql_summary, {"doc_id": doc_id})
        summary = result.fetchone()
        
        # 检查 record 表
        sql_record = text("""
            SELECT COUNT(*), MAX(status) as max_status
            FROM crosstest_review_record
            WHERE doc_id = :doc_id
            GROUP BY doc_id
        """)
        result = conn.execute(sql_record, {"doc_id": doc_id})
        record = result.fetchone()
        
        print(f"\ndoc_id: {doc_id}")
        print("-" * 60)
        print("crosstest_review_summary 表:")
        if summary:
            print(f"  标题: {summary[1]}")
            print(f"  状态: {summary[2]}")
            print(f"  审核人: {summary[3]}")
            print(f"  意见: {summary[4]}")
        else:
            print("  [未找到记录]")
        
        print("\ncrosstest_review_record 表:")
        if record:
            print(f"  记录数: {record[0]}")
            print(f"  状态: {record[1]}")
        else:
            print("  [未找到记录]")


if __name__ == "__main__":
    # 检查用户提供的 doc_id
    doc_ids = [
        "97bdf0c9-e78e-4d96-a6a9-cfd5ea68bfbf",
        "a0181781-0d43-4d26-b8a4-c10d76791958"
    ]
    
    for doc_id in doc_ids:
        check_doc_id(doc_id)
