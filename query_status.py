"""
查询审核记录状态分布
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


def query_all_statuses():
    """查询所有状态分布"""
    engine = get_db_connection()
    with engine.connect() as conn:
        sql = text("""
            SELECT status, COUNT(*) as count
            FROM crosstest_review_record
            GROUP BY status
            ORDER BY count DESC
        """)
        result = conn.execute(sql)
        print("\n当前审核记录状态分布:")
        print("-" * 30)
        for row in result:
            print(f"  {row[0]}: {row[1]} 条")


def query_recent_records(limit=10):
    """查询最近的记录"""
    engine = get_db_connection()
    with engine.connect() as conn:
        sql = text("""
            SELECT id, doc_id, document_title, status, created_time
            FROM crosstest_review_record
            ORDER BY created_time DESC
            LIMIT :limit
        """)
        result = conn.execute(sql, {"limit": limit})
        print("\n最近的审核记录:")
        print("-" * 100)
        print(f"{'ID':<6} {'doc_id':<36} {'状态':<12} {'创建时间':<20} {'标题':<30}")
        print("-" * 100)
        for row in result:
            title = (row[2] or "")[:28] if row[2] else ""
            print(f"{row[0]:<6} {row[1]:<36} {row[3]:<12} {str(row[4])[:19]:<20} {title}")


if __name__ == "__main__":
    query_all_statuses()
    query_recent_records(20)
