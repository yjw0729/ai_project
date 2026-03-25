"""
重试工具模块

提供测试级别的重试装饰器和管理器，支持：
- 通用重试装饰器（基于异常）
- 条件重试装饰器（基于返回值）
- 重试上下文管理器
"""

import time
import logging
from functools import wraps
from typing import Callable, Any, Optional, Tuple, Type

logger = logging.getLogger(__name__)


class RetryConfig:
    """重试配置"""

    def __init__(
        self,
        max_attempts: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
        on_retry: Optional[Callable] = None
    ):
        self.max_attempts = max_attempts
        self.delay = delay
        self.backoff = backoff
        self.exceptions = exceptions
        self.on_retry = on_retry


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 1.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    重试装饰器

    Args:
        max_attempts: 最大尝试次数
        delay: 初始延迟（秒）
        backoff: 延迟倍增因子
        exceptions: 需要重试的异常类型
        on_retry: 重试时的回调函数 (exception, attempt_number)

    Example:
        @retry(max_attempts=3, delay=1, exceptions=(ConnectionError,))
        def test_api_call():
            return requests.get("http://api.example.com")
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(
                            f"函数 {func.__name__} 在 {max_attempts} 次尝试后仍失败: {e}"
                        )
                        raise

                    logger.warning(
                        f"函数 {func.__name__} 第 {attempt} 次尝试失败: {e}, "
                        f"{current_delay:.1f}秒后重试..."
                    )

                    if on_retry:
                        on_retry(e, attempt)

                    time.sleep(current_delay)
                    current_delay *= backoff

            if last_exception:
                raise last_exception

        return wrapper
    return decorator


def retry_on_condition(
    condition: Callable[[Any], bool],
    max_attempts: int = 3,
    delay: float = 1.0,
    error_message: str = "条件不满足"
):
    """
    基于条件结果的重试装饰器

    Args:
        condition: 返回True表示需要重试（条件未满足）
        max_attempts: 最大尝试次数
        delay: 延迟（秒）
        error_message: 最终失败时的错误信息

    Example:
        @retry_on_condition(
            condition=lambda r: r.status_code != 200,
            max_attempts=3
        )
        def check_api():
            return requests.get("http://api.example.com")
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            for attempt in range(1, max_attempts + 1):
                result = func(*args, **kwargs)

                if not condition(result):
                    return result

                if attempt < max_attempts:
                    logger.info(
                        f"函数 {func.__name__} 第 {attempt} 次尝试条件未满足, "
                        f"{delay}秒后重试..."
                    )
                    time.sleep(delay)
                else:
                    raise AssertionError(
                        f"{error_message}: {func.__name__} 在 {max_attempts} 次尝试后仍未满足条件"
                    )

            return result

        return wrapper
    return decorator


class RetryContext:
    """上下文管理器，用于在代码块中执行重试"""

    def __init__(
        self,
        max_attempts: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        exceptions: Tuple[Type[Exception], ...] = (Exception,)
    ):
        self.max_attempts = max_attempts
        self.delay = delay
        self.backoff = backoff
        self.exceptions = exceptions
        self.current_delay = delay
        self.attempt = 0
        self.last_exception = None

    def __enter__(self):
        self.attempt += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return True

        if not issubclass(exc_type, self.exceptions):
            return False

        self.last_exception = exc_val

        if self.attempt >= self.max_attempts:
            logger.error(
                f"重试上下文在 {self.max_attempts} 次尝试后仍失败: {exc_val}"
            )
            return False

        logger.warning(
            f"重试上下文第 {self.attempt} 次失败: {exc_val}, "
            f"{self.current_delay:.1f}秒后重试..."
        )
        time.sleep(self.current_delay)
        self.current_delay *= self.backoff
        return True


def pytest_configure(config):
    """注册 no_retry marker"""
    config.addinivalue_line(
        "markers",
        "no_retry: 不对此测试执行失败重试"
    )
