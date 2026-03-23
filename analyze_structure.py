# -*- coding: utf-8 -*-
"""分析项目目录结构"""
import os
import sys

print('=== Project Structure Analysis ===')
print('')

# 统计各目录文件数
dirs_to_check = [
    ('common/db_enitiy', 'Entity Layer'),
    ('common/db_mapper', 'Data Access Layer'),
    ('common/llm', 'LLM Layer'),
    ('common/rag', 'RAG Layer'),
    ('common/test_executor', 'Test Executor'),
    ('common/fixtures', 'Fixtures'),
    ('common/datacase_function', 'DB Functions'),
    ('common/csv_function', 'CSV Functions'),
    ('common/sql', 'SQL Scripts'),
    ('api', 'API Layer'),
    ('app', 'Application'),
    ('platform_service/service', 'Service Layer'),
    ('shared', 'Shared Package'),
]

print('Directory File Statistics:')
print('-' * 60)
for dir_path, desc in dirs_to_check:
    if os.path.isdir(dir_path):
        py_files = []
        for root, dirs, files in os.walk(dir_path):
            for f in files:
                if f.endswith('.py'):
                    rel_path = os.path.relpath(os.path.join(root, f), '.')
                    py_files.append(rel_path)
        print(f'{desc:20} | {dir_path:25} | {len(py_files)} files')
        for pf in py_files[:3]:
            print(f'                       - {pf}')
        if len(py_files) > 3:
            print(f'                       ... and {len(py_files) - 3} more')
    else:
        print(f'{desc:20} | {dir_path:25} | NOT EXISTS')

print('')
print('=' * 60)
