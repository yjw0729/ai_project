"""
数据库初始化模块

提供数据库初始化、连接管理等基础功能。
"""

import sqlite3
import os
from pathlib import Path
from typing import Optional


def get_db_path(db_name: str = 'task.db') -> str:
    """
    获取数据库文件路径

    Args:
        db_name: 数据库文件名

    Returns:
        完整的数据库文件路径
    """
    db_dir = Path(__file__).parent
    return str(db_dir / db_name)


def init_db(db_path: Optional[str] = None, schema_path: Optional[str] = None) -> str:
    """
    初始化数据库

    如果数据库文件不存在，则根据schema.sql创建表结构。

    Args:
        db_path: 数据库文件路径（可选，默认使用项目db目录下的task.db）
        schema_path: schema.sql文件路径（可选，默认使用项目db目录下的schema.sql）

    Returns:
        数据库文件路径
    """
    if db_path is None:
        db_path = get_db_path()

    if schema_path is None:
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')

    # 确保数据库目录存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # 如果schema文件不存在，报错
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema文件不存在: {schema_path}")

    # 连接数据库（如果文件不存在会自动创建）
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            cursor.executescript(f.read())

        conn.commit()
        print(f"[OK] 数据库初始化完成: {db_path}")

    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"数据库初始化失败: {e}") from e

    finally:
        conn.close()


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    获取数据库连接

    Args:
        db_path: 数据库文件路径（可选，默认使用默认路径）

    Returns:
        sqlite3.Connection对象
    """
    if db_path is None:
        db_path = get_db_path()

    # 如果数据库不存在，先初始化
    if not os.path.exists(db_path):
        init_db(db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # 支持字典式访问
    return conn


def close_connection(conn: sqlite3.Connection):
    """关闭数据库连接"""
    if conn:
        conn.close()


class DatabaseManager:
    """数据库管理器（上下文管理器）"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_db_path()
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> sqlite3.Connection:
        self.conn = get_connection(self.db_path)
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()


if __name__ == '__main__':
    # 演示数据库初始化
    print("开始初始化数据库...")
    db_path = init_db()
    print(f"数据库路径: {db_path}")

    # 验证数据库内容
    with DatabaseManager(db_path) as conn:
        cursor = conn.cursor()

        # 检查各表是否存在
        tables = ['tasks', 'documents', 'interfaces', 'assertion_configs',
                  'test_data_configs', 'exception_codes']

        for table in tables:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            )
            exists = cursor.fetchone() is not None
            status = "[OK]" if exists else "[FAIL]"
            print(f"  {status} 表 {table} {'存在' if exists else '不存在'}")

        # 统计异常码数量
        cursor.execute("SELECT COUNT(*) FROM exception_codes")
        count = cursor.fetchone()[0]
        print(f"\n异常码表记录数: {count}")

    print("\n数据库验证完成。")
