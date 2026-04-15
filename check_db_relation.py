"""
检查 api_config 和 test_case 表的关联状态
"""
import json
from sqlalchemy import create_engine, text

# 读取数据库配置
with open('app/db_config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

db_config = config.get('default', {})
conn_str = f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['db_name']}?charset=utf8mb4"

engine = create_engine(conn_str)

print("=" * 60)
print("1. crosstest_api_config 表数据")
print("=" * 60)
with engine.connect() as conn:
    result = conn.execute(text("SELECT id, name, api_path, method, module FROM crosstest_api_config LIMIT 20"))
    for row in result:
        print(f"ID: {row[0]}, 名称: {row[1]}, 路径: {row[2]}, 方法: {row[3]}, 模块: {row[4]}")
    print(f"\n总数: {result.rowcount}")

print("\n" + "=" * 60)
print("2. crosstest_test_case 表数据")
print("=" * 60)
with engine.connect() as conn:
    result = conn.execute(text("SELECT id, name, module, api_config_id, test_steps FROM crosstest_test_case LIMIT 20"))
    for row in result:
        print(f"ID: {row[0]}, 名称: {row[1][:30] if row[1] else 'None'}..., 模块: {row[2]}, api_config_id: {row[3]}")
    print(f"\n总数: {result.rowcount}")

print("\n" + "=" * 60)
print("3. 关联查询")
print("=" * 60)
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT tc.id, tc.name, tc.api_config_id, ac.api_path, ac.method
        FROM crosstest_test_case tc
        LEFT JOIN crosstest_api_config ac ON tc.api_config_id = ac.id
        WHERE tc.api_config_id IS NOT NULL
        LIMIT 20
    """))
    for row in result:
        print(f"用例ID: {row[0]}, api_config_id: {row[2]}, api_path: {row[3]}, method: {row[4]}")
    print(f"\n总数: {result.rowcount}")