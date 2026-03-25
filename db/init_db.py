"""
初始化 SQLite 数据库
执行 db/schema.sql 创建所有表并插入种子数据
"""
import sqlite3
import pathlib


def init_database():
    project_root = pathlib.Path(__file__).parent.parent.resolve()
    db_dir = project_root / 'db'
    db_dir.mkdir(exist_ok=True)
    db_path = db_dir / 'task.db'
    schema_path = db_dir / 'schema.sql'

    if db_path.exists():
        db_path.unlink()
        print(f"已删除旧数据库: {db_path}")

    conn = sqlite3.connect(str(db_path))
    with open(schema_path, encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.commit()

    # 验证
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"已创建表: {tables}")

    for table in tables:
        cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"  {table}: {cur.fetchone()[0]} 条记录")

    # 验证异常码
    cur = conn.execute("SELECT module, COUNT(*) FROM exception_codes GROUP BY module")
    for row in cur.fetchall():
        print(f"  异常码模块 {row[0]}: {row[1]} 条")

    conn.close()
    print(f"\n数据库初始化成功: {db_path}")

if __name__ == '__main__':
    init_database()
