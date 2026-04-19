"""
[DEPRECATED] 限流装饰器
rate_limiter.py 已删除，此模块提供最小桩以保持接口兼容。
实际限流功能由 MQ 层异步消费机制替代。
"""

from functools import wraps


def rate_limit(key: str):
    """
    限流装饰器（桩实现）。

    原本限制 API 调用频率，当前已由消息队列异步消费机制替代，
    故此装饰器仅透传，不做实际限流。

    用法（保持与原接口兼容）：
        @rate_limit("some_key")
        def my_endpoint():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator
