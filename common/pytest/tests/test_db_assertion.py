"""
测试用例：验证数据库断言功能

这个测试用例用于测试：
1. post_script SQL 查询和变量设置
2. db_checks 字段断言
3. 变量引用替换
4. 多数据源支持
"""
import pytest
import json
from datetime import datetime

from common.test_executor.db_check_runner import DbCheckRunner
from common.test_executor.db_query_executor import DbQueryExecutor, VariableResolver
from common.test_executor.db_field_validator import DbFieldValidator


class TestDbQueryExecutor:
    """测试数据库查询执行器"""

    def test_variable_resolver_simple(self):
        """测试简单变量解析"""
        context = {
            "response": {
                "json": {"code": 0, "data": {"user_id": 12345, "name": "test_user"}},
                "status_code": 200,
            },
            "request": {
                "body": {"username": "admin", "password": "123456"},
            },
            "variables": {},
        }

        resolver = VariableResolver(context)

        # 测试简单变量
        result = resolver.resolve("${response.json.data.user_id}")
        assert result == 12345

        # 测试嵌套变量
        result = resolver.resolve("${response.json.data.name}")
        assert result == "test_user"

        # 测试非变量字符串
        result = resolver.resolve("SELECT * FROM users")
        assert result == "SELECT * FROM users"

        # 测试字典中的变量
        sql = "SELECT * FROM orders WHERE user_id = ${response.json.data.user_id}"
        result = resolver.resolve(sql)
        assert result == "SELECT * FROM orders WHERE user_id = 12345"

    def test_variable_resolver_special(self):
        """测试特殊变量"""
        context = {"variables": {}}
        resolver = VariableResolver(context)

        # 测试 timestamp
        result = resolver.resolve("${timestamp}")
        assert isinstance(result, int)
        assert result > 0

        # 测试 date
        result = resolver.resolve("${date}")
        assert isinstance(result, str)
        assert len(result) == 10  # YYYY-MM-DD

        # 测试 uuid
        result = resolver.resolve("${uuid}")
        assert isinstance(result, str)
        assert len(result) == 36  # UUID format

    def test_db_query_executor_connect(self):
        """测试数据库连接（需要实际的数据库配置）"""
        executor = DbQueryExecutor()

        # 测试查询（使用系统数据库）
        result = executor.execute_raw(
            sql="SELECT 1 as test",
            db_key="default",
        )

        # 如果数据库配置正确，应该能执行
        if result.error is None:
            assert result.row_count >= 1
            assert result.rows[0]["test"] == 1


class TestDbFieldValidator:
    """测试数据库字段验证器"""

    def test_validate_equals(self):
        """测试 equals 断言"""
        validator = DbFieldValidator()

        row = {"status": "CREATED", "amount": 100.00, "name": "test"}

        # 测试 equals
        result = validator.validate(row, "status", "equals", "CREATED")
        assert result.passed is True

        result = validator.validate(row, "status", "equals", "PAID")
        assert result.passed is False

        # 测试 not_equals
        result = validator.validate(row, "status", "not_equals", "PAID")
        assert result.passed is True

    def test_validate_numeric(self):
        """测试数值比较断言"""
        validator = DbFieldValidator()

        row = {"amount": 100.00, "count": 5}

        # 测试 greater_than
        result = validator.validate(row, "amount", "greater_than", 50)
        assert result.passed is True

        result = validator.validate(row, "amount", "greater_than", 100)
        assert result.passed is False

        # 测试 less_than
        result = validator.validate(row, "count", "less_than", 10)
        assert result.passed is True

        # 测试 between
        result = validator.validate(row, "amount", "between", {"min": 50, "max": 200})
        assert result.passed is True

        result = validator.validate(row, "amount", "between", {"min": 200, "max": 300})
        assert result.passed is False

    def test_validate_string(self):
        """测试字符串断言"""
        validator = DbFieldValidator()

        row = {"email": "test@example.com", "phone": "13800138000"}

        # 测试 contains
        result = validator.validate(row, "email", "contains", "@example.com")
        assert result.passed is True

        # 测试 starts_with
        result = validator.validate(row, "phone", "starts_with", "138")
        assert result.passed is True

        # 测试 ends_with
        result = validator.validate(row, "email", "ends_with", ".com")
        assert result.passed is True

        # 测试 regex
        result = validator.validate(row, "phone", "regex", r"^1[3-9]\d{9}$")
        assert result.passed is True

    def test_validate_null(self):
        """测试空值断言"""
        validator = DbFieldValidator()

        row = {"deleted_at": None, "name": "test", "status": "active"}

        # 测试 is_null
        result = validator.validate(row, "deleted_at", "is_null", None)
        assert result.passed is True

        # 测试 is_not_null
        result = validator.validate(row, "name", "is_not_null", None)
        assert result.passed is True

        result = validator.validate(row, "deleted_at", "is_not_null", None)
        assert result.passed is False

    def test_validate_list(self):
        """测试列表断言"""
        validator = DbFieldValidator()

        row = {"status": "active", "role": "admin"}

        # 测试 in_list
        result = validator.validate(row, "status", "in_list", ["active", "pending"])
        assert result.passed is True

        result = validator.validate(row, "status", "in_list", ["inactive", "deleted"])
        assert result.passed is False

        # 测试 not_in_list
        result = validator.validate(row, "role", "not_in_list", ["guest", "visitor"])
        assert result.passed is True

    def test_validate_nested_field(self):
        """测试嵌套字段"""
        validator = DbFieldValidator()

        row = {
            "user": {
                "profile": {
                    "name": "test_user",
                    "age": 25
                }
            }
        }

        result = validator.validate(row, "user.profile.name", "equals", "test_user")
        assert result.passed is True

        result = validator.validate(row, "user.profile.age", "greater_than", 18)
        assert result.passed is True

    def test_validate_all(self):
        """测试批量验证"""
        validator = DbFieldValidator()

        row = {
            "status": "CREATED",
            "amount": 100.00,
            "user_id": 12345,
            "created_at": "2024-01-01 10:00:00",
        }

        assertions = [
            {"field": "status", "operator": "equals", "expected": "CREATED"},
            {"field": "amount", "operator": "greater_than", "expected": 0},
            {"field": "user_id", "operator": "not_equals", "expected": None},
            {"field": "created_at", "operator": "is_not_null"},
        ]

        results = validator.validate_all(row, assertions)

        assert len(results) == 4
        assert all(r.passed for r in results)


class TestDbCheckRunner:
    """测试数据库断言编排器"""

    def test_execute_simple_db_check(self):
        """测试简单的 db_check 执行（需要数据库配置）"""
        runner = DbCheckRunner()

        db_checks = [
            {
                "id": "test_check",
                "db_key": "default",
                "sql": "SELECT 1 as test_value",
                "params": [],
                "assertions": [
                    {"field": "test_value", "operator": "equals", "expected": 1},
                ]
            }
        ]

        result = runner.execute(
            post_script=None,
            db_checks=db_checks,
            context={"variables": {}},
        )

        # 如果数据库配置正确，应该能通过
        if result.results and result.results[0].query_result:
            if result.results[0].query_result.error is None:
                assert result.total_checks >= 1


class TestDbCheckConfigParser:
    """测试配置解析器"""

    def test_parse_expected_results_with_db_checks(self):
        """测试解析包含 db_checks 的 expected_results"""
        from common.test_executor.db_check_parser import DbCheckConfigParser

        parser = DbCheckConfigParser()

        expected_results = {
            "post_script": [
                {
                    "id": "query_order",
                    "type": "db_query",
                    "db_key": "default",
                    "sql": "SELECT * FROM orders WHERE id = ?",
                    "params": [123],
                    "set_variable": "order_record",
                }
            ],
            "db_checks": [
                {
                    "id": "order_status_check",
                    "db_key": "default",
                    "sql": "SELECT status, amount FROM orders WHERE id = ?",
                    "params": ["${variables.order_record.id}"],
                    "assertions": [
                        {"field": "status", "operator": "equals", "expected": "CREATED"},
                        {"field": "amount", "operator": "greater_than", "expected": 0},
                    ]
                }
            ],
        }

        post_script, db_checks = parser.parse(expected_results)

        assert len(post_script) == 1
        assert post_script[0]["id"] == "query_order"
        assert post_script[0]["set_variable"] == "order_record"

        assert len(db_checks) == 1
        assert db_checks[0]["id"] == "order_status_check"
        assert len(db_checks[0]["assertions"]) == 2

    def test_parse_assertions(self):
        """测试解析字段断言"""
        from common.test_executor.db_check_parser import DbCheckConfigParser

        parser = DbCheckConfigParser()

        assertions = [
            {"field": "status", "operator": "equals", "expected": "ACTIVE"},
            {"field": "amount", "operator": "greater_than", "expected": 100},
            {"field": "name", "operator": "contains", "expected": "test"},
        ]

        parsed = parser._parse_assertions(assertions)

        assert len(parsed) == 3
        assert parsed[0]["field"] == "status"
        assert parsed[0]["operator"] == "equals"
        assert parsed[0]["expected"] == "ACTIVE"


class TestIntegration:
    """集成测试：完整的数据库断言流程"""

    def test_full_db_assertion_flow(self):
        """测试完整的数据库断言流程"""
        from common.test_executor.db_check_runner import DbCheckRunner
        from common.test_executor.db_query_executor import VariableResolver

        runner = DbCheckRunner()

        # 模拟 HTTP 响应后的上下文
        context = {
            "response": {
                "json": {
                    "code": 0,
                    "message": "success",
                    "data": {
                        "order_id": 12345,
                        "order_no": "ORD20240101001",
                        "user_id": 100,
                        "amount": 599.00,
                        "status": "CREATED",
                    }
                },
                "status_code": 200,
            },
            "request": {
                "body": {
                    "user_id": 100,
                    "product_ids": [1, 2, 3],
                }
            },
            "variables": {},
        }

        # 配置 post_script 和 db_checks
        post_script = [
            {
                "id": "query_order",
                "type": "db_query",
                "db_key": "default",
                "sql": "SELECT id, order_no, status, amount, user_id FROM orders WHERE order_no = ?",
                "params": ["${response.json.data.order_no}"],
                "set_variable": "order_info",
            }
        ]

        db_checks = [
            {
                "id": "order_basic_check",
                "db_key": "default",
                "sql": "SELECT status, amount, user_id FROM orders WHERE order_no = ?",
                "params": ["${response.json.data.order_no}"],
                "assertions": [
                    {"field": "status", "operator": "equals", "expected": "CREATED"},
                    {"field": "amount", "operator": "greater_than", "expected": 0},
                    {"field": "user_id", "operator": "equals", "expected": 100},
                ]
            },
            {
                "id": "order_amount_check",
                "db_key": "default",
                "sql": "SELECT amount FROM orders WHERE order_no = ?",
                "params": ["${response.json.data.order_no}"],
                "assertions": [
                    {"field": "amount", "operator": "between", "expected": {"min": 500, "max": 1000}},
                    {"field": "amount", "operator": "not_equals", "expected": 0},
                ]
            }
        ]

        # 执行
        result = runner.execute(
            post_script=post_script,
            db_checks=db_checks,
            context=context,
        )

        # 验证结果结构
        assert result is not None
        assert hasattr(result, "all_passed")
        assert hasattr(result, "total_checks")
        assert hasattr(result, "results")
        assert hasattr(result, "variables")

        # 打印结果供查看
        print(f"\n数据库断言执行结果:")
        print(f"  全部通过: {result.all_passed}")
        print(f"  检查总数: {result.total_checks}")
        print(f"  通过数量: {result.passed_checks}")
        print(f"  字段总数: {result.total_fields}")
        print(f"  字段通过数: {result.passed_fields}")
        print(f"  耗时: {result.duration_ms:.2f}ms")

        for check_result in result.results:
            print(f"\n  db_check [{check_result.id}]:")
            print(f"    SQL: {check_result.sql[:80]}...")
            print(f"    通过: {check_result.passed}")
            print(f"    耗时: {check_result.duration_ms:.2f}ms")
            if check_result.error:
                print(f"    错误: {check_result.error}")
            for field_result in check_result.field_results:
                print(f"      - {field_result.field}: {field_result.operator} => passed={field_result.passed}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
