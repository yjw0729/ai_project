"""
API自动化测试 - 参数替换器
支持变量插值：{{var_name}} 和 ${PREV.field}
"""

import re
import json
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class ParameterResolver:
    """参数替换器，支持全局变量和前置接口变量"""

    def __init__(self, global_variables: Optional[Dict[str, Any]] = None):
        self.global_variables: Dict[str, Any] = global_variables or {}
        self.prev_response: Optional[Dict[str, Any]] = None

    def set_global_variables(self, variables: Dict[str, Any]) -> None:
        """设置全局变量"""
        self.global_variables.update(variables)

    def set_prev_response(self, response_data: Dict[str, Any]) -> None:
        """设置前置接口响应数据"""
        self.prev_response = response_data

    def resolve(self, data: Any) -> Any:
        """
        递归解析数据中的所有变量。
        支持：
        - {{var_name}}: 全局变量
        - ${PREV.field}: 前置接口响应字段
        - ${RANDOM}: 随机数
        - ${TIMESTAMP}: 时间戳
        - ${UUID}: UUID
        """
        if isinstance(data, dict):
            return {k: self.resolve(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.resolve(item) for item in data]
        elif isinstance(data, str):
            return self._resolve_string(data)
        else:
            return data

    def _resolve_string(self, value: str) -> str:
        """解析字符串中的变量"""
        if not isinstance(value, str):
            return value

        original = value

        # 替换全局变量 {{var_name}}
        var_pattern = re.compile(r'\{\{(\w+)\}\}')
        for match in var_pattern.finditer(value):
            var_name = match.group(1)
            if var_name in self.global_variables:
                var_value = str(self.global_variables[var_name])
                value = value.replace(match.group(0), var_value)
                logger.debug("【参数替换】变量 %s -> %s", match.group(0), var_value)

        # 替换前置接口变量 ${PREV.field.subfield}
        prev_pattern = re.compile(r'\$\{PREV\.([^}]+)\}')
        if self.prev_response is not None:
            for match in prev_pattern.finditer(value):
                field_path = match.group(1)
                field_value = self._get_nested_field(self.prev_response, field_path)
                if field_value is not None:
                    value = value.replace(match.group(0), str(field_value))
                    logger.debug("【参数替换】前置变量 %s -> %s", match.group(0), field_value)

        # 替换特殊变量
        import random
        import time
        import uuid

        value = value.replace("${RANDOM}", str(random.randint(100000, 999999)))
        value = value.replace("${TIMESTAMP}", str(int(time.time())))
        value = value.replace("${UUID}", str(uuid.uuid4()))

        if value != original:
            logger.debug("【参数替换】最终值: %s", value)

        return value

    def _get_nested_field(self, data: Dict[str, Any], field_path: str) -> Optional[Any]:
        """获取嵌套字段值"""
        keys = field_path.split('.')
        current = data

        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list) and key.isdigit():
                idx = int(key)
                current = current[idx] if idx < len(current) else None
            else:
                return None

            if current is None:
                return None

        return current

    def extract_variables_from_response(
        self,
        response_data: Dict[str, Any],
        variable_mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        从响应中提取变量。
        variable_mapping: {"全局变量名": "响应字段路径"}
        """
        extracted = {}
        for var_name, field_path in variable_mapping.items():
            value = self._get_nested_field(response_data, field_path)
            if value is not None:
                extracted[var_name] = value
                self.global_variables[var_name] = value
                logger.info("【参数提取】%s = %s (from %s)", var_name, value, field_path)
        return extracted
