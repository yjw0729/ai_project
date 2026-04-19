"""
修改审核记录的脚本
同时更新 crosstest_review_record 和 crosstest_review_summary 两个表
将状态从 rejected 改为 pending
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


def update_review_record_table(doc_id, new_status="pending", reviewer="", comment=""):
    """更新 crosstest_review_record 表"""
    engine = get_db_connection()
    with engine.connect() as conn:
        sql = text("""
            UPDATE crosstest_review_record
            SET status = :status,
                reviewer = :reviewer,
                review_comment = :comment,
                updated_time = NOW()
            WHERE doc_id = :doc_id
        """)
        result = conn.execute(sql, {
            "status": new_status,
            "reviewer": reviewer,
            "comment": comment,
            "doc_id": doc_id
        })
        return result.rowcount


def update_review_summary_table(doc_id, new_status="pending", reviewer="", comment=""):
    """更新 crosstest_review_summary 表"""
    engine = get_db_connection()
    with engine.connect() as conn:
        sql = text("""
            UPDATE crosstest_review_summary
            SET status = :status,
                reviewer = :reviewer,
                review_comment = :comment,
                updated_time = NOW()
            WHERE doc_id = :doc_id
        """)
        result = conn.execute(sql, {
            "status": new_status,
            "reviewer": reviewer,
            "comment": comment,
            "doc_id": doc_id
        })
        return result.rowcount


def check_doc_exists(doc_id):
    """检查 doc_id 在哪些表中有记录"""
    engine = get_db_connection()
    with engine.connect() as conn:
        in_summary = False
        in_record = False
        
        # 检查 summary 表
        sql_summary = text("SELECT 1 FROM crosstest_review_summary WHERE doc_id = :doc_id LIMIT 1")
        result = conn.execute(sql_summary, {"doc_id": doc_id})
        in_summary = result.fetchone() is not None
        
        # 检查 record 表
        sql_record = text("SELECT 1 FROM crosstest_review_record WHERE doc_id = :doc_id LIMIT 1")
        result = conn.execute(sql_record, {"doc_id": doc_id})
        in_record = result.fetchone() is not None
        
        return in_summary, in_record


def main():
    print("=" * 80)
    print("修改审核记录状态: rejected -> pending")
    print("=" * 80)

    # 指定的 doc_id 列表
    target_doc_ids = [
        "97bdf0c9-e78e-4d96-a6a9-cfd5ea68bfbf",
        "a0181781-0d43-4d26-b8a4-c10d76791958"
    ]

    print(f"\n准备修改 {len(target_doc_ids)} 个文档...")
    print("-" * 80)

    success_count = 0
    for doc_id in target_doc_ids:
        in_summary, in_record = check_doc_exists(doc_id)
        
        print(f"\ndoc_id: {doc_id}")
        print(f"  - crosstest_review_summary: {'有' if in_summary else '无'}记录")
        print(f"  - crosstest_review_record: {'有' if in_record else '无'}记录")
        
        try:
            rows_summary = 0
            rows_record = 0
            
            # 更新 summary 表（如果有记录）
            if in_summary:
                rows_summary = update_review_summary_table(doc_id, "pending", "", "")
                print(f"  - summary 表更新成功，影响 {rows_summary} 条")
            
            # 更新 record 表（如果有记录）
            if in_record:
                rows_record = update_review_record_table(doc_id, "pending", "", "")
                print(f"  - record 表更新成功，影响 {rows_record} 条")
            
            if not in_summary and not in_record:
                print(f"  [跳过] 两张表都没有该文档的记录")
            else:
                success_count += 1
                print(f"  [成功]")
                
        except Exception as e:
            print(f"  [失败] {e}")

    print("\n" + "=" * 80)
    print(f"修改完成! 成功: {success_count}/{len(target_doc_ids)}")
    print("=" * 80)


if __name__ == "__main__":
    main()
