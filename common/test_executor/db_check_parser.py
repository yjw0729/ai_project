"""
数据库断言配置解析器

负责从 expected_results 中解析 post_script 和 db_checks 配置。
支持两种配置方式：

方式1: 直接在 expected_results 中配置
{
    "post_script": [...],
    "db_checks": [...],
    "assertions": [
        {"type": "db_check", "ref": "order_check"}
    ]
}

方式2: 简化的 db_checks 配置（与断言一起）
{
    "assertions": [
        {"type": "db_check", "ref": "order_check"}
    ],
    "db_checks": [
        {
            "id": "order_check",
            "db_key": "default",
            "sql": "SELECT status, amount FROM orders WHERE id = ?",
            "params": ["${response.json.data.order_id}"],
            "assertions": [
                {"field": "status", "operator": "equals", "expected": "CREATED"},
                {"field": "amount", "operator": "greater_than", "expected": 0}
            ]
        }
    ]
}
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DbCheckConfigParser:
    """
    数据库断言配置解析器

    从 expected_results 中解析 post_script 和 db_checks 配置。
    """

    def parse(
        self,
        expected_results: Any,
    ) -> tuple:
        """
        解析 expected_results，提取 post_script 和 db_checks

        Args:
            expected_results: expected_results 字段值

        Returns:
            tuple: (post_script: List, db_checks: List)
        """
        if expected_results is None:
            return [], []

        if isinstance(expected_results, dict):
            return self._parse_dict(expected_results)

        if isinstance(expected_results, list):
            return self._parse_list(expected_results)

        logger.warning("【DbCheckConfigParser】未知的 expected_results 格式: %s", type(expected_results))
        return [], []

    def _parse_dict(self, data: Dict[str, Any]) -> tuple:
        """解析字典格式的 expected_results"""
        post_script = []
        db_checks = []

        # 解析 post_script
        post_script_raw = data.get("post_script")
        if post_script_raw:
            post_script = self._parse_post_script_list(post_script_raw)

        # 解析 db_checks
        db_checks_raw = data.get("db_checks")
        if db_checks_raw:
            db_checks = self._parse_db_checks_list(db_checks_raw)

        return post_script, db_checks

    def _parse_list(self, data: List) -> tuple:
        """解析列表格式的 expected_results"""
        post_script = []
        db_checks = []

        for item in data:
            if not isinstance(item, dict):
                continue

            item_type = item.get("type")

            if item_type == "db_check":
                # 独立 db_check 配置（包含 sql 和 assertions）
                check_config = self._parse_single_db_check(item)
                if check_config:
                    db_checks.append(check_config)

            elif item_type == "post_script":
                script_config = self._parse_single_post_script(item)
                if script_config:
                    post_script.append(script_config)

        return post_script, db_checks

    def _parse_post_script_list(self, data: Any) -> List[Dict[str, Any]]:
        """解析 post_script 列表"""
        if not data:
            return []

        if isinstance(data, list):
            result = []
            for item in data:
                parsed = self._parse_single_post_script(item)
                if parsed:
                    result.append(parsed)
            return result

        logger.warning("【DbCheckConfigParser】post_script 应为列表格式")
        return []

    def _parse_db_checks_list(self, data: Any) -> List[Dict[str, Any]]:
        """解析 db_checks 列表"""
        if not data:
            return []

        if isinstance(data, list):
            result = []
            for item in data:
                parsed = self._parse_single_db_check(item)
                if parsed:
                    result.append(parsed)
            return result

        logger.warning("【DbCheckConfigParser】db_checks 应为列表格式")
        return []

    def _parse_single_post_script(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """解析单个 post_script 配置"""
        if not isinstance(item, dict):
            return None

        # 基本配置
        script = {
            "id": item.get("id", item.get("name", "unnamed")),
            "type": item.get("type", "db_query"),
            "db_key": item.get("db_key", "default"),
            "sql": item.get("sql", item.get("query", "")),
            "params": item.get("params", []),
            "timeout": item.get("timeout", 10),
            "set_variable": item.get("set_variable", item.get("variable")),
        }

        # 验证必填字段
        if not script["sql"]:
            logger.warning("【DbCheckConfigParser】post_script [%s] 缺少 sql 配置", script["id"])
            return None

        return script

    def _parse_single_db_check(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """解析单个 db_check 配置"""
        if not isinstance(item, dict):
            return None

        # 基本配置
        check = {
            "id": item.get("id", item.get("name", "unnamed")),
            "db_key": item.get("db_key", "default"),
            "sql": item.get("sql", item.get("query", "")),
            "params": item.get("params", []),
            "timeout": item.get("timeout", 10),
            "description": item.get("description", ""),
            "assertions": self._parse_assertions(item.get("assertions", [])),
            "skip_on_http_fail": item.get("skip_on_http_fail", True),
        }

        # 验证必填字段
        if not check["sql"]:
            logger.warning("【DbCheckConfigParser】db_check [%s] 缺少 sql 配置", check["id"])
            return None

        if not check["assertions"]:
            logger.warning("【DbCheckConfigParser】db_check [%s] 缺少 assertions 配置", check["id"])

        return check

    def _parse_assertions(self, assertions: Any) -> List[Dict[str, Any]]:
        """解析字段断言配置列表"""
        if not assertions:
            return []

        if isinstance(assertions, list):
            result = []
            for item in assertions:
                if isinstance(item, dict):
                    parsed = {
                        "field": item.get("field", item.get("column", "")),
                        "operator": item.get("operator", "equals"),
                        "expected": item.get("expected", item.get("value")),
                        "message": item.get("message", item.get("msg")),
                    }
                    result.append(parsed)
            return result

        return []


# 全局实例
_parser = DbCheckConfigParser()


def parse_db_check_config(expected_results: Any) -> tuple:
    """
    便捷函数：从 expected_results 解析 post_script 和 db_checks

    Returns:
        tuple: (post_script: List, db_checks: List)
    """
    return _parser.parse(expected_results)
