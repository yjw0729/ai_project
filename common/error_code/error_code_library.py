"""
异常码库加载器

提供异常码的加载、查询、断言生成功能
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ErrorCode:
    """异常码定义"""
    code: int
    http_status: int
    message: str
    description: str
    category: str = ""
    module: str = ""
    name: str = ""
    assertion_tip: str = ""


class ErrorCodeLibrary:
    """
    异常码库

    功能：
    1. 加载异常码配置
    2. 根据 code 查询异常信息
    3. 根据异常类型生成断言规则
    4. 支持变量替换的断言生成
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._config: Dict[str, Any] = {}
        self._error_codes: Dict[int, ErrorCode] = {}
        self._assertion_templates: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self):
        """加载异常码配置"""
        config_path = os.path.join(
            os.path.dirname(__file__),
            "error_code_library.yaml"
        )

        if not os.path.exists(config_path):
            logger.warning(f"异常码配置文件不存在: {config_path}")
            return

        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}

            # 加载断言模板
            self._assertion_templates = self._config.get("assertion_templates", {})

            # 构建异常码索引
            self._build_code_index()

            logger.info(f"异常码库加载成功，共 {len(self._error_codes)} 个异常码")

        except Exception as e:
            logger.error(f"加载异常码配置失败: {e}")

    def _build_code_index(self):
        """构建异常码索引"""
        # 通用异常码
        common_errors = self._config.get("common_errors", {})
        for name, info in common_errors.items():
            self._error_codes[info["code"]] = ErrorCode(
                code=info["code"],
                http_status=info.get("http_status", 200),
                message=info.get("message", ""),
                description=info.get("description", ""),
                category="COMMON",
                name=name
            )

        # 业务异常码
        business_errors = self._config.get("business_errors", {})
        for module, errors in business_errors.items():
            for name, info in errors.items():
                self._error_codes[info["code"]] = ErrorCode(
                    code=info["code"],
                    http_status=info.get("http_status", 200),
                    message=info.get("message", ""),
                    description=info.get("description", ""),
                    category="BUSINESS",
                    module=module,
                    name=name,
                    assertion_tip=info.get("assertion_tip", "")
                )

    def get_by_code(self, code: int) -> Optional[ErrorCode]:
        """根据异常码获取异常信息"""
        return self._error_codes.get(code)

    def get_by_name(self, category: str, name: str) -> Optional[ErrorCode]:
        """根据分类和名称获取异常信息"""
        common_errors = self._config.get("common_errors", {})
        if name in common_errors:
            info = common_errors[name]
            return ErrorCode(
                code=info["code"],
                http_status=info.get("http_status", 200),
                message=info.get("message", ""),
                description=info.get("description", ""),
                category="COMMON",
                name=name
            )

        business_errors = self._config.get("business_errors", {})
        if category in business_errors and name in business_errors[category]:
            info = business_errors[category][name]
            return ErrorCode(
                code=info["code"],
                http_status=info.get("http_status", 200),
                message=info.get("message", ""),
                description=info.get("description", ""),
                category="BUSINESS",
                module=category,
                name=name,
                assertion_tip=info.get("assertion_tip", "")
            )

        return None

    def get_by_category(self, category: str) -> List[ErrorCode]:
        """获取指定分类的所有异常码"""
        if category == "COMMON":
            common_errors = self._config.get("common_errors", {})
            return [
                ErrorCode(
                    code=info["code"],
                    http_status=info.get("http_status", 200),
                    message=info.get("message", ""),
                    description=info.get("description", ""),
                    category="COMMON",
                    name=name
                )
                for name, info in common_errors.items()
            ]

        business_errors = self._config.get("business_errors", {})
        if category in business_errors:
            return [
                ErrorCode(
                    code=info["code"],
                    http_status=info.get("http_status", 200),
                    message=info.get("message", ""),
                    description=info.get("description", ""),
                    category="BUSINESS",
                    module=category,
                    name=name,
                    assertion_tip=info.get("assertion_tip", "")
                )
                for name, info in business_errors[category].items()
            ]

        return []

    def get_all_codes(self) -> List[int]:
        """获取所有异常码列表"""
        return list(self._error_codes.keys())

    def generate_assertion(
        self,
        code: int,
        variables: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        生成断言规则

        Args:
            code: 异常码
            variables: 变量替换字典

        Returns:
            断言规则字典
        """
        error_info = self.get_by_code(code)
        if not error_info:
            return {"error": f"未知异常码: {code}"}

        variables = variables or {}

        # 构建断言
        assertions = [
            {
                "field": "code",
                "operator": "==",
                "value": code,
                "message": f"响应码应为 {code}"
            }
        ]

        # 添加 HTTP 状态断言
        if error_info.http_status != 200:
            assertions.append({
                "field": "http_status",
                "operator": "==",
                "value": error_info.http_status,
                "message": f"HTTP状态码应为 {error_info.http_status}"
            })

        # 格式化消息
        message = error_info.message
        for key, value in variables.items():
            message = message.replace(f"{{{key}}}", str(value))

        assertions.append({
            "field": "message",
            "operator": "contains",
            "value": message,
            "message": f"错误消息应包含: {message}"
        })

        # 添加 assertion_tip
        result = {
            "assertions": assertions,
            "error_info": {
                "code": error_info.code,
                "message": error_info.message,
                "description": error_info.description,
                "category": error_info.category,
                "module": error_info.module
            }
        }

        if error_info.assertion_tip:
            result["assertion_tip"] = error_info.assertion_tip

        return result

    def generate_success_assertion(self) -> Dict[str, Any]:
        """生成成功断言"""
        return {
            "assertions": [
                {"field": "code", "operator": "==", "value": 0, "message": "操作应成功"},
                {"field": "message", "operator": "==", "value": "success", "message": "消息应为 success"}
            ],
            "error_info": {
                "code": 0,
                "message": "success",
                "description": "操作成功"
            }
        }

    def generate_error_assertion(
        self,
        code: int,
        message_contains: str = None,
        variables: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        生成错误断言

        Args:
            code: 异常码
            message_contains: 期望错误消息包含的内容
            variables: 变量替换
        """
        error_info = self.get_by_code(code)
        if not error_info:
            return {"error": f"未知异常码: {code}"}

        assertions = [
            {"field": "code", "operator": "==", "value": code, "message": f"错误码应为 {code}"}
        ]

        # HTTP 状态码
        if error_info.http_status != 200:
            assertions.append({
                "field": "http_status",
                "operator": "==",
                "value": error_info.http_status,
                "message": f"HTTP状态码应为 {error_info.http_status}"
            })

        # 消息内容
        if message_contains:
            assertions.append({
                "field": "message",
                "operator": "contains",
                "value": message_contains,
                "message": f"消息应包含: {message_contains}"
            })

        return {
            "assertions": assertions,
            "error_info": {
                "code": error_info.code,
                "message": error_info.message,
                "description": error_info.description
            }
        }


# 全局单例
error_code_library = ErrorCodeLibrary()


def get_error_by_code(code: int) -> Optional[ErrorCode]:
    """获取异常码信息"""
    return error_code_library.get_by_code(code)


def get_assertion(code: int, **variables) -> Dict[str, Any]:
    """生成断言规则"""
    return error_code_library.generate_assertion(code, variables)


def get_success_assertion() -> Dict[str, Any]:
    """生成成功断言"""
    return error_code_library.generate_success_assertion()


def get_error_assertion(code: int, message_contains: str = None, **variables) -> Dict[str, Any]:
    """生成错误断言"""
    return error_code_library.generate_error_assertion(code, message_contains, variables)
