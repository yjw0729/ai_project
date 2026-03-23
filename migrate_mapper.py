# -*- coding: utf-8 -*-
"""迁移脚本：common/db_mapper → platform_service/db"""

import os
import shutil
import re

# 配置
SOURCE_DIR = 'common/db_mapper'
TARGET_DIR = 'platform_service/db'

def copy_mapper_files():
    """复制 Mapper 文件到新目录"""
    print(f'Copying mapper files from {SOURCE_DIR} to {TARGET_DIR}...')

    # 创建目标目录
    os.makedirs(TARGET_DIR, exist_ok=True)

    # 复制所有 .py 文件（除了 __init__.py）
    for filename in os.listdir(SOURCE_DIR):
        if filename.endswith('.py') and filename != '__init__.py':
            src = os.path.join(SOURCE_DIR, filename)
            dst = os.path.join(TARGET_DIR, filename)
            shutil.copy2(src, dst)
            print(f'  Copied: {filename}')

    print('Mapper files copied successfully!')

def update_mapper_imports():
    """更新 Mapper 文件中的导入路径"""
    print('Updating import paths in mapper files...')

    # 需要替换的导入映射
    import_replacements = [
        # 实体层导入：从 common.db_enitiy 改为 platform_service.models
        ('from common.db_enitiy', 'from platform_service.models'),
        ('import common.db_enitiy', 'import platform_service.models'),
    ]

    # 也要更新 db_enitiy 内部引用
    internal_replacements = [
        ('from common.db_enitiy.', 'from platform_service.models.'),
    ]

    for filename in os.listdir(TARGET_DIR):
        if filename.endswith('.py'):
            filepath = os.path.join(TARGET_DIR, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            original_content = content

            # 应用替换
            for old, new in import_replacements:
                content = content.replace(old, new)

            # 写回文件（仅当有更改时）
            if content != original_content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f'  Updated imports: {filename}')

    print('Import paths updated!')

def create_new_init():
    """创建新的 __init__.py"""
    new_init_path = os.path.join(TARGET_DIR, '__init__.py')

    new_content = '''# -*- coding: utf-8 -*-
"""
platform_service/db/ - 数据访问层

包含数据库 CRUD 操作类。

Mapper 列表：
- TestCaseMapper: 测试用例 CRUD
- TestExecutionMapper: 测试执行记录 CRUD
- ApiConfigMapper: 接口配置 CRUD
- EnvironmentConfigMapper: 环境配置 CRUD
- DatabaseConfigMapper: 数据库配置 CRUD
- TestSuiteMapper: 测试套件 CRUD
- TestSuiteCaseMapper: 测试套件-用例关联 CRUD
- TestPlanMapper: 测试计划 CRUD
- GlobalVariableMapper: 全局变量 CRUD
- ReviewRecordMapper: 评审记录 CRUD
- ReviewSummaryMapper: 评审汇总 CRUD
- TaskExecutionMapper: 任务执行记录 CRUD
"""

from platform_service.db.test_case_mapper import TestCaseMapper, OptimisticLockError
from platform_service.db.test_execution_mapper import TestExecutionMapper
from platform_service.db.api_config_mapper import ApiConfigMapper
from platform_service.db.environment_config_mapper import EnvironmentConfigMapper
from platform_service.db.database_config_mapper import DatabaseConfigMapper
from platform_service.db.test_suite_mapper import TestSuiteMapper
from platform_service.db.test_suite_case_mapper import TestSuiteCaseMapper
from platform_service.db.test_plan_mapper import TestPlanMapper
from platform_service.db.global_variable_mapper import GlobalVariableMapper
from platform_service.db.review_record_mapper import ReviewRecordMapper
from platform_service.db.review_summary_mapper import ReviewSummaryMapper
from platform_service.db.task_execution_mapper import TaskExecutionMapper

__all__ = [
    "TestCaseMapper",
    "OptimisticLockError",
    "TestExecutionMapper",
    "ApiConfigMapper",
    "EnvironmentConfigMapper",
    "DatabaseConfigMapper",
    "TestSuiteMapper",
    "TestSuiteCaseMapper",
    "TestPlanMapper",
    "GlobalVariableMapper",
    "ReviewRecordMapper",
    "ReviewSummaryMapper",
    "TaskExecutionMapper",
]
'''

    with open(new_init_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print('New __init__.py created in platform_service/db/')

def create_compat_layer():
    """创建兼容层"""
    print('Creating compatibility layer...')

    compat_content = '''# -*- coding: utf-8 -*-
"""
common/db_mapper/ - 数据访问层（兼容层）

⚠️  注意：数据访问层已迁移到 platform_service/db/
   此目录保留作为向后兼容，建议使用新路径。

迁移时间：2026-03-21
"""

# ==================== 向后兼容导入 ====================
# 兼容旧的导入路径，自动重定向到新位置

from platform_service.db import (
    TestCaseMapper,
    OptimisticLockError,
    TestExecutionMapper,
    ApiConfigMapper,
    EnvironmentConfigMapper,
    DatabaseConfigMapper,
    TestSuiteMapper,
    TestSuiteCaseMapper,
    TestPlanMapper,
    GlobalVariableMapper,
    ReviewRecordMapper,
    ReviewSummaryMapper,
    TaskExecutionMapper,
)

# 重新导出，保持原有接口
__all__ = [
    "TestCaseMapper",
    "OptimisticLockError",
    "TestExecutionMapper",
    "ApiConfigMapper",
    "EnvironmentConfigMapper",
    "DatabaseConfigMapper",
    "TestSuiteMapper",
    "TestSuiteCaseMapper",
    "TestPlanMapper",
    "GlobalVariableMapper",
    "ReviewRecordMapper",
    "ReviewSummaryMapper",
    "TaskExecutionMapper",
]

# ==================== 兼容警告 ====================
import warnings as _warnings

def __getattr__(name):
    """延迟导入，触发弃用警告"""
    _warnings.warn(
        f"导入路径 'common.db_mapper.{name}' 已弃用，请使用 'platform_service.db.{name}'",
        DeprecationWarning,
        stacklevel=2
    )
    import platform_service.db as new_module
    if hasattr(new_module, name):
        return getattr(new_module, name)
    raise AttributeError(f"module 'common.db_mapper' has no attribute '{name}'")

print('[MIGRATION] common/db_mapper -> platform_service/db')
print('[MIGRATION] Old import path still works (backward compatible)')
'''

    init_path = os.path.join(SOURCE_DIR, '__init__.py')
    with open(init_path, 'w', encoding='utf-8') as f:
        f.write(compat_content)

    print('Compatibility layer created!')

if __name__ == '__main__':
    print('=' * 60)
    print('Data Access Layer Migration: common/db_mapper -> platform_service/db')
    print('=' * 60)
    print('')

    # 1. 复制 Mapper 文件
    copy_mapper_files()
    print('')

    # 2. 更新导入路径
    update_mapper_imports()
    print('')

    # 3. 创建新的 __init__.py
    create_new_init()
    print('')

    # 4. 创建兼容层
    create_compat_layer()
    print('')

    print('=' * 60)
    print('Migration Step 2 Complete!')
    print('')
    print('Now you can import from both:')
    print('  - OLD: from common.db_mapper import TestCaseMapper')
    print('  - NEW: from platform_service.db import TestCaseMapper')
    print('=' * 60)
