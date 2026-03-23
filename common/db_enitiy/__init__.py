# -*- coding: utf-8 -*-
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
