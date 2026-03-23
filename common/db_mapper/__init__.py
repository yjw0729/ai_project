# -*- coding: utf-8 -*-
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
