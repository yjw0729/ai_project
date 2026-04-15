"""
删除并重建 test_suite 相关的两个表
- crosstest_test_suite
- crosstest_test_suite_case
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from common.datacase_function.contect_db import get_engine


def drop_and_recreate_suite_tables():
    engine = get_engine("default")

    # 检查表是否存在
    with engine.connect() as conn:
        result = conn.execute(text("SHOW TABLES LIKE 'crosstest_test_suite_case'"))
        case_exists = result.fetchone() is not None
        result = conn.execute(text("SHOW TABLES LIKE 'crosstest_test_suite'"))
        suite_exists = result.fetchone() is not None

        print(f"crosstest_test_suite_case 存在: {case_exists}")
        print(f"crosstest_test_suite 存在: {suite_exists}")

    # 删除表
    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        conn.commit()

        if case_exists:
            conn.execute(text("DROP TABLE IF EXISTS `crosstest_test_suite_case`"))
            conn.commit()
            print("已删除 crosstest_test_suite_case")

        if suite_exists:
            conn.execute(text("DROP TABLE IF EXISTS `crosstest_test_suite`"))
            conn.commit()
            print("已删除 crosstest_test_suite")

        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        conn.commit()

    # 重建表 - 直接用 CREATE TABLE
    with engine.connect() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS `crosstest_test_suite` (
            `id` INTEGER NOT NULL AUTO_INCREMENT,
            `name` VARCHAR(200) NOT NULL,
            `description` VARCHAR(1000),
            `suite_type` ENUM('smoke','regression','function','performance','custom') NOT NULL DEFAULT 'custom',
            `module` VARCHAR(100),
            `tags` JSON,
            `config` JSON,
            `last_execution_status` ENUM('not_run','running','passed','failed','stopped') NOT NULL DEFAULT 'not_run',
            `last_execution_time` DATETIME,
            `last_execution_id` VARCHAR(50),
            `total_executions` INTEGER NOT NULL DEFAULT 0,
            `success_rate` NUMERIC(5,2) NOT NULL DEFAULT 0.00,
            `case_default_config` JSON,
            `status` ENUM('active','inactive') NOT NULL DEFAULT 'active',
            `creator` VARCHAR(50) NOT NULL,
            `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
            `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uk_name` (`name`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='测试套件表'
        """))
        conn.commit()
        print("已创建 crosstest_test_suite")

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS `crosstest_test_suite_case` (
            `id` INTEGER NOT NULL AUTO_INCREMENT,
            `suite_id` INTEGER NOT NULL,
            `case_id` INTEGER NOT NULL,
            `execution_order` INTEGER DEFAULT 0,
            `enabled` TINYINT(1) DEFAULT 1,
            `url` VARCHAR(500),
            `request_headers` JSON,
            `request_params` JSON,
            `request_body` JSON,
            `timeout` INTEGER DEFAULT 30,
            `assertions` JSON,
            `config` JSON,
            `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
            `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_suite_id` (`suite_id`),
            KEY `idx_case_id` (`case_id`),
            KEY `idx_suite_case` (`suite_id`,`case_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='测试套件与用例关联表'
        """))
        conn.commit()
        print("已创建 crosstest_test_suite_case")

    # 验证
    with engine.connect() as conn:
        result = conn.execute(text("SHOW TABLES LIKE 'crosstest_test_suite'"))
        suite_ok = result.fetchone() is not None
        result = conn.execute(text("SHOW TABLES LIKE 'crosstest_test_suite_case'"))
        case_ok = result.fetchone() is not None
        print(f"\n验证: crosstest_test_suite 存在: {suite_ok}")
        print(f"验证: crosstest_test_suite_case 存在: {case_ok}")

    print("\n操作完成。")


if __name__ == "__main__":
    drop_and_recreate_suite_tables()