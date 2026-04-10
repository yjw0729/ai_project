"""
数据库断言编排器

负责编排 post_script（SQL查询）和 db_checks（数据库断言）的执行流程：

执行流程：
1. 解析 post_script 配置，执行 SQL 查询
2. 将查询结果存入 variables 变量池
3. 解析 db_checks 配置，执行 SQL 查询
4. 对查询结果进行字段断言验证
5. 汇总所有断言结果

设计方案：SQL 与断言分离
- post_script: 定义 SQL 查询，设置变量
- db_checks: 引用 db_checks.id，执行断言验证
"""
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from common.test_executor.db_query_executor import DbQueryExecutor, QueryResult, get_db_query_executor
from common.test_executor.db_field_validator import DbFieldValidator, FieldValidationResult, get_db_field_validator

logger = logging.getLogger(__name__)


@dataclass
class DbCheckResult:
    """单个 db_check 的执行结果"""
    id: str                           # db_check 配置的 id
    sql: str                         # 实际执行的 SQL
    params: List[Any]               # SQL 参数
    query_result: Optional[QueryResult]  # 查询结果
    field_results: List[FieldValidationResult]  # 字段验证结果
    passed: bool                    # 是否全部通过
    duration_ms: float              # 总耗时（毫秒）
    error: Optional[str] = None     # 错误信息

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sql": self.sql,
            "params": self.params,
            "passed": self.passed,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "field_results": [r.to_dict() for r in self.field_results],
        }


@dataclass
class DbAssertionExecutionResult:
    """数据库断言执行结果（汇总）"""
    all_passed: bool                # 是否全部通过
    total_checks: int              # db_checks 总数
    passed_checks: int             # 通过的 db_checks 数量
    total_fields: int               # 字段断言总数
    passed_fields: int            # 通过的字段断言数量
    results: List[DbCheckResult]   # 每个 db_check 的结果
    variables: Dict[str, Any]      # 执行过程中设置的变量
    duration_ms: float             # 总耗时（毫秒）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "all_passed": self.all_passed,
            "summary": {
                "total_checks": self.total_checks,
                "passed_checks": self.passed_checks,
                "total_fields": self.total_fields,
                "passed_fields": self.passed_fields,
                "duration_ms": self.duration_ms,
            },
            "results": [r.to_dict() for r in self.results],
            "variables": self.variables,
        }


class DbCheckRunner:
    """
    数据库断言编排器

    负责执行 post_script 和 db_checks 配置，执行数据库层面的断言验证。
    """

    def __init__(self, db_query_executor: Optional[DbQueryExecutor] = None,
                 db_field_validator: Optional[DbFieldValidator] = None):
        """
        Args:
            db_query_executor: 数据库查询执行器（可选，默认使用全局实例）
            db_field_validator: 字段验证器（可选，默认使用全局实例）
        """
        self.query_executor = db_query_executor or get_db_query_executor()
        self.field_validator = db_field_validator or get_db_field_validator()

    def execute(
        self,
        post_script: Optional[List[Dict[str, Any]]] = None,
        db_checks: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> DbAssertionExecutionResult:
        """
        执行数据库断言

        Args:
            post_script: 后置脚本配置列表
                [
                    {
                        "id": "query_order",
                        "type": "db_query",
                        "db_key": "default",
                        "sql": "SELECT * FROM orders WHERE id = ?",
                        "params": [123],
                        "set_variable": "order_record"  # 可选，存入变量
                    }
                ]
            db_checks: 数据库断言配置列表
                [
                    {
                        "id": "order_status_check",
                        "db_key": "default",
                        "sql": "SELECT status FROM orders WHERE id = ?",
                        "params": ["${variables.order_record.id}"],
                        "assertions": [
                            {"field": "status", "operator": "equals", "expected": "CREATED"},
                            {"field": "amount", "operator": "greater_than", "expected": 0}
                        ]
                    }
                ]
            context: 执行上下文（包含 response、request、variables 等）

        Returns:
            DbAssertionExecutionResult: 执行结果
        """
        import time
        start_time = time.time()

        # 初始化上下文
        if context is None:
            context = {}

        # 确保 variables 存在
        if "variables" not in context:
            context["variables"] = {}

        variables = context["variables"]

        logger.info("【DbCheckRunner】开始执行 post_script=%d, db_checks=%d",
                    len(post_script or []), len(db_checks or []))

        results: List[DbCheckResult] = []

        # ---- 1. 执行 post_script ----
        if post_script:
            for script in post_script:
                self._execute_post_script(script, context, variables)

        # ---- 2. 执行 db_checks ----
        if db_checks:
            for check in db_checks:
                result = self._execute_db_check(check, context)
                results.append(result)

        # ---- 3. 汇总结果 ----
        duration_ms = (time.time() - start_time) * 1000

        total_fields = sum(len(r.field_results) for r in results)
        passed_fields = sum(sum(1 for f in r.field_results if f.passed) for r in results)

        execution_result = DbAssertionExecutionResult(
            all_passed=all(r.passed for r in results) if results else True,
            total_checks=len(results),
            passed_checks=sum(1 for r in results if r.passed),
            total_fields=total_fields,
            passed_fields=passed_fields,
            results=results,
            variables=variables,
            duration_ms=duration_ms,
        )

        logger.info("【DbCheckRunner】执行完成: total_checks=%d, passed=%d, total_fields=%d, passed=%d, duration=%.2fms",
                    len(results), execution_result.passed_checks,
                    total_fields, passed_fields, duration_ms)

        return execution_result

    def _execute_post_script(
        self,
        script: Dict[str, Any],
        context: Dict[str, Any],
        variables: Dict[str, Any],
    ) -> None:
        """
        执行后置脚本

        Args:
            script: 脚本配置
            context: 执行上下文
            variables: 变量池
        """
        script_id = script.get("id", script.get("type", "unknown"))
        script_type = script.get("type", "db_query")
        db_key = script.get("db_key", "default")
        sql = script.get("sql", "")
        params = script.get("params", [])
        set_variable = script.get("set_variable")

        logger.info("【DbCheckRunner】执行 post_script: id=%s, type=%s, db_key=%s",
                    script_id, script_type, db_key)

        try:
            if script_type == "db_query":
                query_result = self.query_executor.execute(
                    sql=sql,
                    db_key=db_key,
                    params=params,
                    context=context,
                    timeout=script.get("timeout", 10),
                )

                if query_result.error:
                    logger.error("【DbCheckRunner】post_script [%s] 查询失败: %s",
                                script_id, query_result.error)
                    return

                # 设置变量
                if set_variable:
                    if query_result.row_count > 0:
                        # 如果是单条记录，取第一条
                        variables[set_variable] = query_result.rows[0]
                        logger.info("【DbCheckRunner】post_script [%s] 设置变量 [%s] = %s",
                                    script_id, set_variable,
                                    f"查询结果({query_result.row_count}行)")
                    else:
                        variables[set_variable] = None
                        logger.warning("【DbCheckRunner】post_script [%s] 查询结果为空，设置变量 [%s] = None",
                                        script_id, set_variable)

                logger.info("【DbCheckRunner】post_script [%s] 执行成功: %d行, 耗时%.2fms",
                            script_id, query_result.row_count, query_result.duration_ms)

        except Exception as e:
            logger.error("【DbCheckRunner】post_script [%s] 执行异常: %s", script_id, str(e))

    def _execute_db_check(
        self,
        check: Dict[str, Any],
        context: Dict[str, Any],
    ) -> DbCheckResult:
        """
        执行单个 db_check

        Args:
            check: db_check 配置
            context: 执行上下文

        Returns:
            DbCheckResult: 执行结果
        """
        import time
        start_time = time.time()

        check_id = check.get("id", "unknown")
        db_key = check.get("db_key", "default")
        sql = check.get("sql", "")
        params = check.get("params", [])
        assertions = check.get("assertions", [])

        logger.info("【DbCheckRunner】执行 db_check: id=%s, db_key=%s, sql=%s",
                    check_id, db_key, sql[:100] + "..." if len(sql) > 100 else sql)

        try:
            # 执行查询
            query_result = self.query_executor.execute(
                sql=sql,
                db_key=db_key,
                params=params,
                context=context,
                timeout=check.get("timeout", 10),
            )

            field_results: List[FieldValidationResult] = []

            # 执行字段断言
            if query_result.error:
                # 查询失败
                logger.error("【DbCheckRunner】db_check [%s] 查询失败: %s",
                            check_id, query_result.error)
                return DbCheckResult(
                    id=check_id,
                    sql=sql,
                    params=params,
                    query_result=query_result,
                    field_results=field_results,
                    passed=False,
                    duration_ms=(time.time() - start_time) * 1000,
                    error=query_result.error,
                )

            if query_result.row_count == 0:
                # 无查询结果
                logger.warning("【DbCheckRunner】db_check [%s] 查询结果为空", check_id)
                return DbCheckResult(
                    id=check_id,
                    sql=sql,
                    params=params,
                    query_result=query_result,
                    field_results=field_results,
                    passed=False,
                    duration_ms=(time.time() - start_time) * 1000,
                    error="查询结果为空",
                )

            # 对第一行结果进行字段断言
            row = query_result.rows[0]
            field_results = self.field_validator.validate_all(row, assertions)

            passed = all(f.passed for f in field_results)

            duration_ms = (time.time() - start_time) * 1000

            logger.info("【DbCheckRunner】db_check [%s] 完成: %d个字段, passed=%s, 耗时%.2fms",
                        check_id, len(field_results), passed, duration_ms)

            return DbCheckResult(
                id=check_id,
                sql=sql,
                params=params,
                query_result=query_result,
                field_results=field_results,
                passed=passed,
                duration_ms=duration_ms,
            )

        except Exception as e:
            logger.error("【DbCheckRunner】db_check [%s] 执行异常: %s", check_id, str(e))
            return DbCheckResult(
                id=check_id,
                sql=sql,
                params=params,
                query_result=None,
                field_results=[],
                passed=False,
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e),
            )


# 全局单例
_global_runner: Optional[DbCheckRunner] = None


def get_db_check_runner() -> DbCheckRunner:
    """获取全局数据库断言编排器实例"""
    global _global_runner
    if _global_runner is None:
        _global_runner = DbCheckRunner()
    return _global_runner
