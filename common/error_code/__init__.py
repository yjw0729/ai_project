"""
异常码库。

提供异常码的加载、查询、断言生成功能。
"""
from common.error_code.error_code_library import (
    ErrorCode,
    ErrorCodeLibrary,
    error_code_library,
    get_error_by_code,
    get_assertion,
    get_success_assertion,
    get_error_assertion,
)

__all__ = [
    "ErrorCode",
    "ErrorCodeLibrary",
    "error_code_library",
    "get_error_by_code",
    "get_assertion",
    "get_success_assertion",
    "get_error_assertion",
]
