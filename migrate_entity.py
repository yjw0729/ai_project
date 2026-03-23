# -*- coding: utf-8 -*-
"""迁移脚本：common/db_enitiy → platform_service/models"""

import os
import shutil
import re

# 配置
SOURCE_DIR = 'common/db_enitiy'
TARGET_DIR = 'platform_service/models'
BACKUP_DIR = 'common/db_enitiy_backup'

def copy_entity_files():
    """复制实体文件到新目录"""
    print(f'Copying entity files from {SOURCE_DIR} to {TARGET_DIR}...')

    # 创建目标目录
    os.makedirs(TARGET_DIR, exist_ok=True)

    # 复制所有 .py 文件（除了 __init__.py）
    for filename in os.listdir(SOURCE_DIR):
        if filename.endswith('.py') and filename != '__init__.py':
            src = os.path.join(SOURCE_DIR, filename)
            dst = os.path.join(TARGET_DIR, filename)
            shutil.copy2(src, dst)
            print(f'  Copied: {filename}')

    print('Entity files copied successfully!')

def create_compat_layer():
    """创建兼容层：旧路径重定向到新路径"""
    print('Creating compatibility layer...')

    # 读取原始 __init__.py
    init_path = os.path.join(SOURCE_DIR, '__init__.py')
    with open(init_path, 'r', encoding='utf-8') as f:
        original_content = f.read()

    # 创建新的兼容 __init__.py
    compat_content = '''# -*- coding: utf-8 -*-
"""
common/db_enitiy/ - 实体层（兼容层）

⚠️  注意：实体层已迁移到 platform_service/models/
   此目录保留作为向后兼容，建议使用新路径。

迁移时间：2026-03-21
"""

# ==================== 向后兼容导入 ====================
# 兼容旧的导入路径，自动重定向到新位置

from platform_service.models import (
    TestCase,
    TestExecution,
    ApiConfig,
    EnvironmentConfig,
    DatabaseConfig,
    TestSuite,
    TestSuiteCase,
    TestPlan,
    GlobalVariable,
    ReviewRecord,
    ReviewSummary,
    TaskExecution,
)

# 重新导出，保持原有接口
__all__ = [
    "TestCase",
    "TestExecution",
    "ApiConfig",
    "EnvironmentConfig",
    "DatabaseConfig",
    "TestSuite",
    "TestSuiteCase",
    "TestPlan",
    "GlobalVariable",
    "ReviewRecord",
    "ReviewSummary",
    "TaskExecution",
]

# ==================== 兼容警告 ====================
import warnings as _warnings

class _DeprecationWrapper:
    """包装器，在首次访问时显示弃用警告"""

    def __init__(self, module_name):
        self.module_name = module_name
        self._warned = False

    def __getattr__(self, name):
        if not self._warned:
            _warnings.warn(
                f"导入路径 'common.db_enitiy.{name}' 已弃用，请使用 'platform_service.models.{name}'",
                DeprecationWarning,
                stacklevel=2
            )
            self._warned = True
        # 从新模块获取属性
        import platform_service.models as new_module
        return getattr(new_module, name)

# 使用延迟导入
def __getattr__(name):
    """延迟导入，触发弃用警告"""
    _warnings.warn(
        f"导入路径 'common.db_enitiy.{name}' 已弃用，请使用 'platform_service.models.{name}'",
        DeprecationWarning,
        stacklevel=2
    )
    import platform_service.models as new_module
    if hasattr(new_module, name):
        return getattr(new_module, name)
    raise AttributeError(f"module 'common.db_enitiy' has no attribute '{name}'")

print('[MIGRATION] common/db_enitiy -> platform_service/models')
print('[MIGRATION] Old import path still works (backward compatible)')
'''

    with open(init_path, 'w', encoding='utf-8') as f:
        f.write(compat_content)

    print('Compatibility layer created!')

def create_new_init():
    """创建新的 __init__.py"""
    new_init_path = os.path.join(TARGET_DIR, '__init__.py')

    new_content = '''# -*- coding: utf-8 -*-
"""
platform_service/models/ - 实体层

包含数据表映射实体类，定义数据库表的结构。

实体列表：
- TestCase: 测试用例
- TestExecution: 测试执行记录
- ApiConfig: 接口配置
- EnvironmentConfig: 环境配置
- DatabaseConfig: 数据库配置
- TestSuite: 测试套件
- TestSuiteCase: 测试套件-用例关联
- TestPlan: 测试计划
- GlobalVariable: 全局变量
- ReviewRecord: 评审记录
- ReviewSummary: 评审汇总
- TaskExecution: 任务执行记录
"""

from platform_service.models.test_case import TestCase
from platform_service.models.test_execution import TestExecution
from platform_service.models.api_config import ApiConfig
from platform_service.models.environment_config import EnvironmentConfig
from platform_service.models.database_config import DatabaseConfig
from platform_service.models.test_suite import TestSuite
from platform_service.models.test_suite_case import TestSuiteCase
from platform_service.models.test_plan import TestPlan
from platform_service.models.global_variable import GlobalVariable
from platform_service.models.review_record import ReviewRecord
from platform_service.models.review_summary import ReviewSummary
from platform_service.models.task_execution import TaskExecution

__all__ = [
    "TestCase",
    "TestExecution",
    "ApiConfig",
    "EnvironmentConfig",
    "DatabaseConfig",
    "TestSuite",
    "TestSuiteCase",
    "TestPlan",
    "GlobalVariable",
    "ReviewRecord",
    "ReviewSummary",
    "TaskExecution",
]
'''

    with open(new_init_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print('New __init__.py created in platform_service/models/')

if __name__ == '__main__':
    print('=' * 60)
    print('Entity Layer Migration: common/db_enitiy -> platform_service/models')
    print('=' * 60)
    print('')

    # 1. 复制实体文件
    copy_entity_files()
    print('')

    # 2. 创建新的 __init__.py
    create_new_init()
    print('')

    # 3. 创建兼容层
    create_compat_layer()
    print('')

    print('=' * 60)
    print('Migration Step 1 Complete!')
    print('')
    print('Now you can import from both:')
    print('  - OLD: from common.db_enitiy import TestCase')
    print('  - NEW: from platform_service.models import TestCase')
    print('=' * 60)
