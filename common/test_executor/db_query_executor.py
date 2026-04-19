"""
数据库查询执行器

支持：
1. 多数据源配置 - 每个 SQL 可指定不同的 db_key
2. 变量替换 - 支持 ${response.xxx}、${request.body.xxx} 等变量
3. 参数化查询 - SQL 参数与变量替换分离
4. 结果缓存 - 避免重复查询
"""
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field

from common.db.datacase.contect_db import db_session

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """查询结果"""
    sql: str                          # 实际执行的 SQL
    params: List[Any]                # 实际使用的参数
    rows: List[Dict[str, Any]]       # 查询结果行列表
    row_count: int                   # 结果行数
    duration_ms: float               # 查询耗时（毫秒）
    db_key: str                      # 使用的数据源
    error: Optional[str] = None      # 错误信息

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sql": self.sql,
            "params": self.params,
            "rows": self.rows,
            "row_count": self.row_count,
            "duration_ms": self.duration_ms,
            "db_key": self.db_key,
            "error": self.error,
        }


class VariableResolver:
    """
    变量解析器

    支持的变量格式：
    - ${response.json.xxx} - HTTP 响应 JSON 字段
    - ${response.status_code} - HTTP 状态码
    - ${response.headers.xxx} - HTTP 响应头
    - ${request.body.xxx} - 请求体字段
    - ${request.query.xxx} - Query 参数
    - ${request.headers.xxx} - 请求头
    - ${request.path.xxx} - 路径参数
    - ${env.XXX} - 环境变量
    - ${variables.xxx} - 自定义变量（后置脚本设置的变量）
    - ${timestamp} - 当前时间戳（秒）
    - ${date} - 当前日期（YYYY-MM-DD）
    - ${datetime} - 当前日期时间（YYYY-MM-DD HH:MM:SS）
    - ${uuid} - UUID
    """

    VAR_PATTERN = re.compile(r'\$\{([^}]+)\}')

    def __init__(self, context: Dict[str, Any]):
        """
        Args:
            context: 执行上下文，包含 response、request、variables 等
        """
        self.context = context

    def resolve(self, value: Any) -> Any:
        """解析变量引用"""
        if value is None:
            return None

        if isinstance(value, str):
            return self._resolve_string(value)

        if isinstance(value, list):
            return [self.resolve(item) for item in value]

        if isinstance(value, dict):
            return {k: self.resolve(v) for k, v in value.items()}

        return value

    def _resolve_string(self, text: str) -> Any:
        """解析字符串中的变量引用"""
        if not isinstance(text, str):
            return text

        matches = self.VAR_PATTERN.findall(text)

        if not matches:
            return text

        # 如果只有一个匹配且是完整字符串，尝试返回对应类型的值
        if len(matches) == 1 and text == f"${{{matches[0]}}}":
            return self._get_variable_value(matches[0])

        # 否则进行字符串替换
        result = text
        for match in matches:
            resolved_value = self._get_variable_value(match)
            if resolved_value is not None:
                result = result.replace(f"${{{match}}}", str(resolved_value))

        return result

    def _get_variable_value(self, path: str) -> Any:
        """
        获取变量值

        Args:
            path: 变量路径，如 "response.json.data.user_id"

        Returns:
            变量的值，如果不存在返回 None
        """
        parts = path.split('.')
        if not parts:
            return None

        # 获取顶层变量
        var_type = parts[0].lower()

        if var_type == 'timestamp':
            return int(datetime.now().timestamp())

        if var_type == 'date':
            return datetime.now().strftime('%Y-%m-%d')

        if var_type == 'datetime':
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if var_type == 'uuid':
            import uuid as uuid_module
            return str(uuid_module.uuid4())

        if var_type == 'variables':
            # 从上下文变量中获取
            variables = self.context.get('variables', {})
            return self._get_nested_value(variables, parts[1:])

        if var_type == 'env':
            # 环境变量
            import os
            return os.environ.get('.'.join(parts[1:]))

        if var_type in ('response', 'request'):
            return self._get_nested_value(self.context.get(var_type, {}), parts[1:])

        # 尝试从上下文中直接获取
        return self.context.get(path)

    def _get_nested_value(self, data: Any, path: List[str]) -> Any:
        """获取嵌套字典中的值"""
        if not path:
            return data

        current = data
        for key in path:
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list):
                try:
                    index = int(key)
                    current = current[index]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current


class DbQueryExecutor:
    """
    数据库查询执行器

    特点：
    1. 每个查询可指定不同的数据源（db_key）
    2. 自动解析 SQL 中的变量引用
    3. 支持参数化查询
    4. 可选结果缓存
    """

    def __init__(self):
        # 查询结果缓存：{cache_key: QueryResult}
        self._cache: Dict[str, QueryResult] = {}

    def execute(
        self,
        sql: str,
        db_key: str = "default",
        params: Optional[List[Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        timeout: int = 10,
        use_cache: bool = False,
        cache_key: Optional[str] = None,
    ) -> QueryResult:
        """
        执行 SQL 查询

        Args:
            sql: SQL 语句（支持变量替换）
            db_key: 数据源标识（对应 db_config.json 中的 key）
            params: SQL 参数列表（支持变量替换）
            context: 执行上下文（包含 response、request、variables 等）
            timeout: 查询超时时间（秒）
            use_cache: 是否使用缓存
            cache_key: 缓存键（如果不指定则自动生成）

        Returns:
            QueryResult: 查询结果
        """
        import time
        start_time = time.time()

        # 默认上下文
        if context is None:
            context = {}

        # 解析变量
        resolver = VariableResolver(context)

        # 解析 SQL
        resolved_sql = resolver.resolve(sql)

        # 解析参数
        resolved_params = []
        if params:
            for p in params:
                resolved_params.append(resolver.resolve(p))

        # 生成缓存键
        if use_cache and not cache_key:
            cache_key = f"{db_key}:{resolved_sql}:{json.dumps(resolved_params, sort_keys=True)}"

        # 检查缓存
        if use_cache and cache_key and cache_key in self._cache:
            logger.info("【DbQueryExecutor】使用缓存: %s", cache_key)
            return self._cache[cache_key]

        # 执行查询
        try:
            logger.info("【DbQueryExecutor】执行 SQL [%s]: %s, params: %s", db_key, resolved_sql, resolved_params)

            with db_session(db_key) as session:
                # 使用 text() 包装原始 SQL
                from sqlalchemy import text
                stmt = text(resolved_sql)

                if resolved_params:
                    result = session.execute(stmt, resolved_params)
                else:
                    result = session.execute(stmt)

                rows = [dict(row._mapping) for row in result]
                row_count = len(rows)

            duration_ms = (time.time() - start_time) * 1000

            query_result = QueryResult(
                sql=resolved_sql,
                params=resolved_params,
                rows=rows,
                row_count=row_count,
                duration_ms=duration_ms,
                db_key=db_key,
            )

            logger.info("【DbQueryExecutor】查询成功: %d 行, 耗时: %.2fms", row_count, duration_ms)

            # 缓存结果
            if use_cache and cache_key:
                self._cache[cache_key] = query_result

            return query_result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = f"SQL执行失败: {str(e)}"
            logger.error("【DbQueryExecutor】%s [%s]: %s, params: %s", error_msg, db_key, resolved_sql, resolved_params)

            return QueryResult(
                sql=resolved_sql,
                params=resolved_params,
                rows=[],
                row_count=0,
                duration_ms=duration_ms,
                db_key=db_key,
                error=error_msg,
            )

    def execute_raw(
        self,
        sql: str,
        db_key: str = "default",
        params: Optional[List[Any]] = None,
    ) -> QueryResult:
        """
        执行原始 SQL（不进行变量替换）

        Args:
            sql: SQL 语句
            db_key: 数据源标识
            params: SQL 参数

        Returns:
            QueryResult: 查询结果
        """
        return self.execute(
            sql=sql,
            db_key=db_key,
            params=params,
            context={},
        )

    def clear_cache(self) -> None:
        """清空查询缓存"""
        self._cache.clear()
        logger.info("【DbQueryExecutor】缓存已清空")

    def get_cached_result(self, cache_key: str) -> Optional[QueryResult]:
        """获取缓存的查询结果"""
        return self._cache.get(cache_key)


# 全局单例
_global_executor: Optional[DbQueryExecutor] = None


def get_db_query_executor() -> DbQueryExecutor:
    """获取全局数据库查询执行器实例"""
    global _global_executor
    if _global_executor is None:
        _global_executor = DbQueryExecutor()
    return _global_executor
