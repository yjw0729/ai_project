"""
API自动化测试 - 参数替换器
支持变量插值：{{var_name}} 和 ${PREV.field}
"""

import re
import json
import logging
import random
import time
import uuid
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


# ========== 动态值生成器 ==========

def generate_request_id():
    """生成请求ID（格式：REQ + 时间戳 + 6位随机数）"""
    return f"REQ{int(time.time() * 1000)}{random.randint(100000, 999999)}"


def generate_business_order_no():
    """生成商户订单号"""
    return f"BN{random.randint(100000, 999999)}{int(time.time())}"


def generate_business_sub_order_no():
    """生成商户子订单号"""
    return f"BS{random.randint(100000, 999999)}{int(time.time())}"


def generate_business_trade_order_no():
    """生成商户交易订单号"""
    return f"BT{random.randint(100000, 999999)}{int(time.time())}"


def generate_payee_bank_ac_name():
    """生成收款人银行卡姓名"""
    names = ["张三", "李四", "王五", "赵六", "钱七"]
    return names[random.randint(0, len(names) - 1)]


def generate_payee_bank_ac_no():
    """生成收款人银行卡号（模拟）"""
    return f"{random.randint(6200000000000000, 6299999999999999)}"


def generate_out_trade_no():
    """生成商户订单号（outTradeNo）"""
    return f"OT{int(time.time() * 1000)}{random.randint(100000, 999999)}"


def generate_payee_mno():
    """生成收款方通道编码"""
    mnos = ["ALIPAY", "WECHAT", "UNIONPAY", "BAIDU", "JDPAY"]
    return mnos[random.randint(0, len(mnos) - 1)]


def generate_random_string(length=8):
    """生成随机字符串"""
    import string
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def generate_random_int(min_val=100000, max_val=999999):
    """生成随机整数"""
    return random.randint(min_val, max_val)


# 预定义变量生成器映射（按变量名自动匹配）
_VARIABLE_GENERATORS = {
    "requestId": generate_request_id,
    "businessOrderNo": generate_business_order_no,
    "businessSubOrderNo": generate_business_sub_order_no,
    "businessTradeOrderNo": generate_business_trade_order_no,
    "payeeBankAcName": generate_payee_bank_ac_name,
    "payeeBankAcNo": generate_payee_bank_ac_no,
    "outTradeNo": generate_out_trade_no,
    "payeeMno": generate_payee_mno,
}


def _get_auto_value(var_name: str) -> str:
    """根据变量名自动生成合适的值"""
    generator = _VARIABLE_GENERATORS.get(var_name)
    if generator:
        return generator()

    # 默认生成通用随机值
    return f"auto_{var_name}_{generate_random_string(8)}"


class ParameterResolver:
    """参数替换器，支持全局变量和前置接口变量"""

    def __init__(self, global_variables: Optional[Dict[str, Any]] = None):
        self.global_variables: Dict[str, Any] = global_variables or {}
        self.prev_response: Optional[Dict[str, Any]] = None
        # 记录替换日志（用于调试）
        self._replaced_vars: List[Dict[str, str]] = []
        self._auto_generated_vars: List[Dict[str, str]] = []

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
        - {{var_name}}: 全局变量（优先），找不到则自动生成
        - ${PREV.field}: 前置接口响应字段
        - ${RANDOM}: 随机数
        - ${TIMESTAMP}: 时间戳
        - ${UUID}: UUID
        """
        # 重置日志
        self._replaced_vars = []
        self._auto_generated_vars = []

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

        # 为内置系统变量生成固定值（同一字段只生成一次）
        _random_cache = str(random.randint(100000, 999999))
        _timestamp_cache = str(int(time.time()))
        _uuid_cache = str(uuid.uuid4())

        # 替换全局变量 {{var_name}}
        var_pattern = re.compile(r'\{\{(\w+)\}\}')
        for match in var_pattern.finditer(value):
            var_name = match.group(1)
            placeholder = match.group(0)

            if var_name in self.global_variables:
                # 找到全局变量，进行替换
                var_value = str(self.global_variables[var_name])
                value = value.replace(placeholder, var_value)
                self._replaced_vars.append({
                    "placeholder": placeholder,
                    "var_name": var_name,
                    "value": var_value,
                    "source": "global"
                })
                logger.debug("【参数替换】变量 %s -> %s (来源: 全局变量)", placeholder, var_value)
            else:
                # 找不到全局变量，自动生成动态值
                auto_value = _get_auto_value(var_name)
                value = value.replace(placeholder, auto_value)
                self._auto_generated_vars.append({
                    "placeholder": placeholder,
                    "var_name": var_name,
                    "value": auto_value,
                    "source": "auto_generate"
                })
                logger.warning(
                    "【参数替换-自动生成】变量 %s 在全局变量中未找到，自动生成: %s",
                    placeholder, auto_value
                )

        # 替换前置接口变量 ${PREV.field.subfield}
        prev_pattern = re.compile(r'\$\{PREV\.([^}]+)\}')
        if self.prev_response is not None:
            for match in prev_pattern.finditer(value):
                field_path = match.group(1)
                placeholder = match.group(0)
                field_value = self._get_nested_field(self.prev_response, field_path)
                if field_value is not None:
                    value = value.replace(placeholder, str(field_value))
                    self._replaced_vars.append({
                        "placeholder": placeholder,
                        "field_path": field_path,
                        "value": str(field_value),
                        "source": "prev_response"
                    })
                    logger.debug("【参数替换】前置变量 %s -> %s", placeholder, field_value)

        # 替换响应提取变量 ${RESPONSE.varName}
        # 注意：这些变量在生成阶段无法解析（运行时才提取），保留占位符供生成代码中的运行时替换使用
        response_pattern = re.compile(r'\$\{RESPONSE\.([^}]+)\}')
        for match in response_pattern.finditer(value):
            var_name = match.group(1)
            placeholder = match.group(0)
            # 占位符格式: ${RESPONSE.orderId} -> 保留，生成代码时替换为 _get_session_context().get("orderId")
            self._replaced_vars.append({
                "placeholder": placeholder,
                "var_name": var_name,
                "value": f"${{RESPONSE.{var_name}}}",  # 保留占位符，运行时替换
                "source": "response_extract"
            })
            logger.debug("【参数替换】响应提取变量 %s (将在运行时解析)", placeholder)

        # 替换特殊变量（使用缓存值，同一替换中相同占位符生成相同值）
        value = value.replace("${RANDOM}", _random_cache)
        value = value.replace("${TIMESTAMP}", _timestamp_cache)
        value = value.replace("${UUID}", _uuid_cache)

        # 记录替换日志（用于日志输出）
        if original != value:
            self._replaced_vars.append({
                "placeholder": original,
                "value": value,
                "source": "builtin"
            })

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

    def get_replaced_vars(self) -> List[Dict[str, str]]:
        """获取被替换的变量列表"""
        return self._replaced_vars.copy()

    def get_auto_generated_vars(self) -> List[Dict[str, str]]:
        """获取自动生成的变量列表"""
        return self._auto_generated_vars.copy()
