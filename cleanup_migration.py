# -*- coding: utf-8 -*-
"""清理迁移临时文件"""
import os

files_to_remove = [
    'analyze_structure.py',
    'analyze_imports.py',
    'test_entity_import.py',
    'test_mapper_import.py',
    'test_flask_after_migration.py',
    'migrate_entity.py',
    'migrate_mapper.py',
]

for f in files_to_remove:
    if os.path.exists(f):
        os.remove(f)
        print(f'Removed: {f}')
    else:
        print(f'Not found: {f}')

print('')
print('Migration cleanup complete!')
