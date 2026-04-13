# -*- coding: utf-8 -*-
"""
数据库迁移脚本：为 crosstest_test_case 表添加 extract_fields 字段

执行时间: 2026-04-13
"""

from sqlalchemy import text
from common.datacase_function.contect_db import db_session

def migrate_add_extract_fields():
    """添加 extract_fields 字段到 crosstest_test_case 表"""
    sql = text("""
        ALTER TABLE crosstest_test_case
        ADD COLUMN IF NOT EXISTS extract_fields JSON COMMENT '响应字段提取配置(JSON数组)'
    """)

    try:
        with db_session() as session:
            session.execute(sql)
            session.commit()
        print("[迁移成功] extract_fields 字段已添加到 crosstest_test_case 表")
        return True
    except Exception as e:
        error_msg = str(e)
        if "Duplicate column" in error_msg or "已存在" in error_msg:
            print("[跳过] extract_fields 字段已存在，无需重复添加")
            return True
        print(f"[迁移失败] {error_msg}")
        return False

def rollback_extract_fields():
    """回滚：删除 extract_fields 字段"""
    sql = text("""
        ALTER TABLE crosstest_test_case
        DROP COLUMN IF EXISTS extract_fields
    """)

    try:
        with db_session() as session:
            session.execute(sql)
            session.commit()
        print("[回滚成功] extract_fields 字段已从 crosstest_test_case 表删除")
        return True
    except Exception as e:
        print(f"[回滚失败] {e}")
        return False

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        print("开始回滚迁移...")
        rollback_extract_fields()
    else:
        print("开始迁移...")
        migrate_add_extract_fields()
