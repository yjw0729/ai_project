"""
迁移脚本：为 crosstest_test_suite_case 表添加缺失的字段
安全运行：只添加不存在的字段，不会影响现有数据

用法：python add_missing_suite_case_columns.py
"""
import logging
from common.datacase_function.contect_db import db_session

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def column_exists(cursor, table, column):
    """检查列是否存在"""
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = '{table}'
          AND COLUMN_NAME = '{column}'
    """)
    return cursor.fetchone()[0] > 0


def add_column_if_not_exists(cursor, table, column, definition):
    """如果列不存在则添加"""
    if column_exists(cursor, table, column):
        logger.info(f"  [跳过] 列 '{column}' 已存在")
        return False
    else:
        sql = f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}"
        cursor.execute(sql)
        logger.info(f"  [添加] 列 '{column}'")
        return True


def main():
    table = "crosstest_test_suite_case"
    added = []
    skipped = []

    with db_session() as session:
        cursor = session.connection().cursor()

        # 检查表是否存在
        if not column_exists(cursor, table, "id"):
            logger.error(f"表 '{table}' 不存在，请先创建表")
            return

        logger.info(f"检查表 '{table}' 的字段...")

        # 按顺序定义所有需要添加的列
        columns = [
            ("name", "VARCHAR(200) DEFAULT NULL COMMENT '用例名称(冗余存储)'"),
            ("case_id_str", "VARCHAR(50) DEFAULT NULL COMMENT '业务用例编号(冗余存储)'"),
            ("url", "VARCHAR(500) DEFAULT NULL COMMENT '请求URL(独立配置，为空则继承用例)'"),
            ("request_headers", "JSON DEFAULT NULL COMMENT '请求头(独立配置)'"),
            ("request_params", "JSON DEFAULT NULL COMMENT '请求参数(独立配置)'"),
            ("request_body", "JSON DEFAULT NULL COMMENT '请求体(独立配置)'"),
            ("timeout", "INT DEFAULT 30 COMMENT '超时秒数'"),
            ("assertions", "JSON DEFAULT NULL COMMENT '断言配置(独立配置)'"),
            ("preconditions", "TEXT DEFAULT NULL COMMENT '前置条件(可独立覆盖)'"),
            ("test_steps", "JSON DEFAULT NULL COMMENT '测试步骤(可独立覆盖)'"),
            ("test_data", "JSON DEFAULT NULL COMMENT '测试数据(可独立覆盖)'"),
        ]

        for col_name, col_def in columns:
            if add_column_if_not_exists(cursor, table, col_name, col_def):
                added.append(col_name)
            else:
                skipped.append(col_name)

        session.connection().commit()

    logger.info(f"\n迁移完成:")
    logger.info(f"  新增字段: {len(added)} 个 - {added}")
    logger.info(f"  已存在字段: {len(skipped)} 个 - {skipped}")

    if not added:
        logger.info("没有新的字段需要添加，表结构已是最新。")
    else:
        logger.info(f"\n请重启应用服务使新字段生效。")


if __name__ == "__main__":
    main()
