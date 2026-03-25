"""
parametrize 包

提供数据驱动测试功能。
"""

from parametrize.driver import (
    DataLoader,
    VariableReplacer,
    get_builtin_functions,
    load_data,
    parametrize_data,
)

__all__ = [
    'parametrize_data',
    'load_data',
    'DataLoader',
    'VariableReplacer',
    'get_builtin_functions',
]
