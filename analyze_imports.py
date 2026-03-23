# -*- coding: utf-8 -*-
"""分析模块导入依赖关系"""
import os
import re
import sys

# 统计各模块被导入的情况
modules_to_check = {
    'common.db_enitiy': 'common/db_enitiy',
    'common.db_mapper': 'common/db_mapper',
    'common.llm': 'common/llm',
    'common.rag': 'common/rag',
    'common.test_executor': 'common/test_executor',
}

def find_imports(module_prefix, search_dirs):
    """查找导入指定模块的所有文件"""
    results = {}
    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for root, dirs, files in os.walk(search_dir):
            for f in files:
                if f.endswith('.py'):
                    filepath = os.path.join(root, f)
                    try:
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as file:
                            content = file.read()
                            # 检查是否导入了指定模块
                            if re.search(rf'from\s+{module_prefix}\.|import\s+{module_prefix}\.', content):
                                rel_path = os.path.relpath(filepath, '.')
                                results[rel_path] = True
                    except:
                        pass
    return list(results.keys())

print('=== Import Dependency Analysis ===')
print('')

# 搜索目录
search_dirs = ['api', 'common', 'app', 'platform_service', 'workers', 'tools']

for module, path in modules_to_check.items():
    files = find_imports(module, search_dirs)
    print(f'{module}:')
    print(f'  Used by {len(files)} files:')
    for f in files[:10]:
        print(f'    - {f}')
    if len(files) > 10:
        print(f'    ... and {len(files) - 10} more')
    print('')

print('=' * 60)
print('')
print('Summary: Files that need to be updated during migration')
print('')

# 统计总共有多少文件需要更新
all_affected = set()
for module, path in modules_to_check.items():
    files = find_imports(module, search_dirs)
    all_affected.update(files)

print(f'Total files with imports to update: {len(all_affected)}')
for f in sorted(all_affected):
    print(f'  - {f}')
