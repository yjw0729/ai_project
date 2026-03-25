"""
数据库初始化脚本

创建 crosstest_business_context 表（如果不存在）
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.datacase_function.contect_db import get_engine
from sqlalchemy import inspect, text

# 获取数据库引擎
engine = get_engine("default")

# 获取 inspector
inspector = inspect(engine)

# 获取所有现有表
existing_tables = inspector.get_table_names()
print(f"现有表: {existing_tables}")

# 定义要创建的表
target_table = "crosstest_business_context"

if target_table in existing_tables:
    print(f"\n表 '{target_table}' 已存在")
else:
    print(f"\n创建表 '{target_table}'...")

    create_sql = text(f"""
    CREATE TABLE IF NOT EXISTS {target_table} (
        id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
        name VARCHAR(255) NOT NULL COMMENT '上下文名称',
        description TEXT COMMENT '上下文描述',
        source_type VARCHAR(50) COMMENT '来源类型: text/pdf/docx/image/markdown/vector_db',
        source_name VARCHAR(255) COMMENT '原始文件名',
        source_size BIGINT COMMENT '原始文件大小(字节)',
        content TEXT COMMENT '提取的文本内容',
        content_hash VARCHAR(64) COMMENT '内容MD5哈希',
        total_chars INT DEFAULT 0 COMMENT '总字符数',
        api_config_id INT COMMENT '关联的API配置ID',
        module VARCHAR(100) COMMENT '所属模块',
        is_active TINYINT(1) DEFAULT 1 COMMENT '是否启用',
        is_deprecated TINYINT(1) DEFAULT 0 COMMENT '是否废弃',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
        creator VARCHAR(100) COMMENT '创建人',
        INDEX idx_api_config_id (api_config_id),
        INDEX idx_module (module),
        INDEX idx_is_deprecated (is_deprecated)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='业务上下文表'
    """)

    with engine.connect() as conn:
        conn.execute(create_sql)
        conn.commit()

    print(f"表 '{target_table}' 创建成功！")

print("\n检查完成。")
