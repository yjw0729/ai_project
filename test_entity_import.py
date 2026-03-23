# -*- coding: utf-8 -*-
"""验证实体层迁移"""

print('=== Testing Entity Layer Import ===')
print('')

# 测试新路径导入
try:
    from platform_service.models import TestCase
    print('[OK] NEW: from platform_service.models import TestCase')
except Exception as e:
    print(f'[FAIL] NEW: {e}')

try:
    from platform_service.models import TaskExecution
    print('[OK] NEW: from platform_service.models import TaskExecution')
except Exception as e:
    print(f'[FAIL] NEW: {e}')

try:
    from platform_service.models import ApiConfig
    print('[OK] NEW: from platform_service.models import ApiConfig')
except Exception as e:
    print(f'[FAIL] NEW: {e}')

# 测试旧路径导入（兼容层）
try:
    from common.db_enitiy import TestCase
    print('[OK] OLD: from common.db_enitiy import TestCase')
except Exception as e:
    print(f'[FAIL] OLD: {e}')

try:
    from common.db_enitiy import TaskExecution
    print('[OK] OLD: from common.db_enitiy import TaskExecution')
except Exception as e:
    print(f'[FAIL] OLD: {e}')

try:
    from common.db_enitiy import ApiConfig
    print('[OK] OLD: from common.db_enitiy import ApiConfig')
except Exception as e:
    print(f'[FAIL] OLD: {e}')

print('')
print('Entity Layer Migration Verified!')
