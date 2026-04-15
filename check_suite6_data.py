# 查询测试套件 ID=6 的用例数据
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

# 数据库连接配置
db_config = {
    "type": "mysql+pymysql",
    "host": "22.50.6.73",
    "port": 3306,
    "db_name": "quantumqa",
    "user": "qa",
    "password": "qa_tester"
}

conn_str = f"{db_config['type']}://{db_config['user']}:{quote_plus(db_config['password'])}@{db_config['host']}:{db_config['port']}/{db_config['db_name']}"
engine = create_engine(conn_str)

print("=" * 80)
print("查询测试套件 ID=6 的详细数据")
print("=" * 80)

with engine.connect() as conn:
    # 1. 查询测试套件基本信息
    print("\n【1. 测试套件基本信息】")
    result = conn.execute(text("""
        SELECT id, name, description, status, case_default_config
        FROM crosstest_test_suite
        WHERE id = 6
    """))
    suite = result.fetchone()
    if suite:
        print(f"  套件ID: {suite[0]}")
        print(f"  名称: {suite[1]}")
        print(f"  描述: {suite[2]}")
        print(f"  状态: {suite[3]}")
        print(f"  默认配置: {suite[4]}")
    else:
        print("  未找到该测试套件!")

    # 2. 查询所有关联的用例（包括未启用的）
    print("\n【2. 测试套件关联用例（全部）】")
    result = conn.execute(text("""
        SELECT
            sc.id,
            sc.suite_id,
            sc.case_id,
            sc.name,
            sc.execution_order,
            sc.enabled,
            sc.config,
            tc.name as test_case_name,
            tc.status as test_case_status
        FROM crosstest_test_suite_case sc
        LEFT JOIN crosstest_test_case tc ON sc.case_id = tc.id
        WHERE sc.suite_id = 6
        ORDER BY sc.execution_order
    """))
    cases = result.fetchall()
    print(f"  总记录数: {len(cases)}")
    print()
    for case in cases:
        print(f"  ---")
        print(f"  关联ID: {case[0]}")
        print(f"  套件ID: {case[1]}")
        print(f"  用例ID: {case[2]}")
        print(f"  用例名称: {case[3] or case[6]}")
        print(f"  执行顺序: {case[4]}")
        print(f"  enabled字段: {case[5]}")
        print(f"  config字段: {case[6]}")
        print(f"  test_case_name: {case[7]}")
        print(f"  test_case.status: {case[8]}")

    # 3. 分析 enabled 状态
    print("\n【3. enabled 状态分析】")
    enabled_count = sum(1 for c in cases if c[5] is True)
    disabled_count = sum(1 for c in cases if c[5] is False or c[5] is None)
    print(f"  enabled=True: {enabled_count}")
    print(f"  enabled=False/None: {disabled_count}")

    # 4. 分析 config 字段
    print("\n【4. config 字段分析】")
    config_stats = {"null": 0, "empty_dict": 0, "has_enabled_true": 0, "has_enabled_false": 0, "other": 0}
    for case in cases:
        cfg = case[6]
        if cfg is None:
            config_stats["null"] += 1
        elif cfg == "null" or cfg == "{}":
            config_stats["empty_dict"] += 1
        elif isinstance(cfg, dict):
            if cfg.get("enabled") is True:
                config_stats["has_enabled_true"] += 1
            elif cfg.get("enabled") is False:
                config_stats["has_enabled_false"] += 1
            else:
                config_stats["other"] += 1
        else:
            config_stats["other"] += 1

    for k, v in config_stats.items():
        print(f"  {k}: {v}")

    # 5. 模拟 SQL 查询逻辑（enabled_only=True）- 旧逻辑
    print("\n【5. 旧SQL查询逻辑结果（有问题）】")
    result = conn.execute(text("""
        SELECT id, case_id, enabled, config
        FROM crosstest_test_suite_case
        WHERE suite_id = 6
          AND (
              config IS NULL
              OR config = 'null'
              OR JSON_EXTRACT(config, '$.enabled') = TRUE
          )
        ORDER BY execution_order
    """))
    old_enabled_cases = result.fetchall()
    print(f"  旧逻辑筛选出的记录数: {len(old_enabled_cases)}")

    # 5b. 模拟 SQL 查询逻辑（enabled_only=True）- 新逻辑
    print("\n【5b. 新SQL查询逻辑结果（已修复）】")
    # 新逻辑：enabled 字段为 True 或 NULL 时视为启用
    # 同时 config 中 enabled=true 也视为启用
    result = conn.execute(text("""
        SELECT id, case_id, enabled, config
        FROM crosstest_test_suite_case
        WHERE suite_id = 6
          AND (
              enabled = 1
              OR enabled IS NULL
              OR JSON_EXTRACT(config, '$.enabled') = TRUE
              OR config IS NULL
          )
        ORDER BY execution_order
    """))
    new_enabled_cases = result.fetchall()
    print(f"  新逻辑筛选出的记录数: {len(new_enabled_cases)}")
    if new_enabled_cases:
        for case in new_enabled_cases:
            print(f"    ID={case[0]}, case_id={case[1]}, enabled={case[2]}, config={case[3]}")
    else:
        print("  没有记录符合启用条件！")

    # 6. 检查 test_case 表中用例的状态
    print("\n【6. 检查关联的 test_case 表数据】")
    if cases:
        case_ids = [c[2] for c in cases if c[2]]
        if case_ids:
            placeholders = ",".join([str(cid) for cid in case_ids])
            result = conn.execute(text(f"""
                SELECT id, name, status, module
                FROM crosstest_test_case
                WHERE id IN ({placeholders})
            """))
            test_cases = result.fetchall()
            print(f"  找到 {len(test_cases)} 条关联的用例记录")
            for tc in test_cases:
                print(f"    ID={tc[0]}, name={tc[1]}, status={tc[2]}, module={tc[3]}")

print("\n" + "=" * 80)
