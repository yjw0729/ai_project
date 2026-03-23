# -*- coding: utf-8 -*-
"""验证数据访问层迁移"""

print('=== Testing Data Access Layer Import ===')
print('')

# 测试新路径导入
try:
    from platform_service.db import TestCaseMapper
    print('[OK] NEW: from platform_service.db import TestCaseMapper')
except Exception as e:
    print(f'[FAIL] NEW: {e}')

try:
    from platform_service.db import TaskExecutionMapper
    print('[OK] NEW: from platform_service.db import TaskExecutionMapper')
except Exception as e:
    print(f'[FAIL] NEW: {e}')

try:
    from platform_service.db import OptimisticLockError
    print('[OK] NEW: from platform_service.db import OptimisticLockError')
except Exception as e:
    print(f'[FAIL] NEW: {e}')

# 测试旧路径导入（兼容层）
try:
    from common.db_mapper import TestCaseMapper
    print('[OK] OLD: from common.db_mapper import TestCaseMapper')
except Exception as e:
    print(f'[FAIL] OLD: {e}')

try:
    from common.db_mapper import TaskExecutionMapper
    print('[OK] OLD: from common.db_mapper import TaskExecutionMapper')
except Exception as e:
    print(f'[FAIL] OLD: {e}')

print('')
print('Data Access Layer Migration Verified!')
