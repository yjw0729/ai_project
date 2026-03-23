"""
基于 Redis 的令牌桶限流器。
对重量级操作接口进行限流，保护后端资源。
"""

import time
import structlog
from functools import wraps
from flask import request, jsonify

logger = structlog.get_logger()


class RateLimiter:
    """
    Redis 令牌桶限流器。

    限流维度：
    - user: 每个用户单独计数
    - endpoint: 每个接口单独计数
    """

    def __init__(self, redis_client):
        self.redis = redis_client

    def consume(
        self,
        key: str,
        limit: int,
        window: int = 60,
    ) -> tuple[bool, int]:
        now = time.time()
        redis_key = f"rate_limit:{key}"

        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(redis_key, 0, now - window)
        pipe.zcard(redis_key)
        pipe.zadd(redis_key, {str(now): now})
        pipe.expire(redis_key, window + 1)
        results = pipe.execute()

        current_count = results[1]

        if current_count >= limit:
            self.redis.zrem(redis_key, str(now))
            remaining = 0
            logger.warning("限流触发", key=key, limit=limit, window=window)
            return False, 0

        remaining = max(0, limit - current_count - 1)
        return True, remaining

    def get_remaining(self, key: str, limit: int, window: int = 60) -> int:
        now = time.time()
        redis_key = f"rate_limit:{key}"
        self.redis.zremrangebyscore(redis_key, 0, now - window)
        current = self.redis.zcard(redis_key)
        return max(0, limit - current)


RATE_LIMIT_CONFIG = {
    "execute_async": {"limit": 10, "window": 60, "message": "执行过于频繁，请60秒后再试"},
    "generate_async": {"limit": 10, "window": 60, "message": "生成过于频繁，请60秒后再试"},
    "execute": {"limit": 20, "window": 60, "message": "执行过于频繁，请60秒后再试"},
    "generate": {"limit": 20, "window": 60, "message": "生成过于频繁，请60秒后再试"},
    "default": {"limit": 100, "window": 60, "message": "请求过于频繁"},
}


def rate_limit(
    endpoint_key: str = "default",
    user_id_getter=None,
):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                import redis
                redis_client = redis.Redis(
                    host="localhost",
                    port=6379,
                    password="pytest_sxp_2026",
                    decode_responses=True,
                    socket_connect_timeout=2,
                )
                redis_client.ping()
            except Exception:
                return f(*args, **kwargs)

            config = RATE_LIMIT_CONFIG.get(endpoint_key, RATE_LIMIT_CONFIG["default"])
            user_id = (user_id_getter or (lambda: request.headers.get("X-User-ID", "anonymous")))()

            limiter = RateLimiter(redis_client)
            allowed, remaining = limiter.consume(
                f"user:{user_id}:{endpoint_key}",
                config["limit"],
                config["window"],
            )

            if not allowed:
                return jsonify({
                    "code": 429,
                    "message": config["message"],
                    "data": {
                        "retry_after": config["window"],
                        "limit": config["limit"],
                        "remaining": 0,
                    }
                }), 429

            response = f(*args, **kwargs)

            if hasattr(response, "headers"):
                response.headers["X-RateLimit-Limit"] = str(config["limit"])
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                response.headers["X-RateLimit-Window"] = str(config["window"])

            return response

        return decorated_function
    return decorator
