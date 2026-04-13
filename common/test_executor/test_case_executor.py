"""
测试用例执行器 - 从 DB 读取用例并准备执行

核心职责：
1. 从 crosstest_test_case 读取用例
2. 从 crosstest_api_config 读取接口配置
3. 从 crosstest_environment_config 读取环境配置
4. 将 expected_results 解析为断言格式
5. 生成可被 pytest 执行器使用的标准化数据
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from common.test_executor.expected_results import ExpectedResultsParser
from common.db_mapper.test_case_mapper import TestCaseMapper
from common.db_mapper.api_config_mapper import ApiConfigMapper
from common.db_mapper.environment_config_mapper import EnvironmentConfigMapper
from common.test_executor.db_check_parser import DbCheckConfigParser

logger = logging.getLogger(__name__)


@dataclass
class TestCaseExecutionData:
    """
    单个测试用例的执行数据。

    从 DB 读取并经过标准化处理，
    可直接传递给 pytest 测试函数或 APITestRunner。
    """
    case_id: str          # 业务用例编号
    db_id: int            # 数据库主键
    name: str
    module: str
    priority: str
    method: str            # HTTP 方法
    path: str              # API 路径
    headers: Dict[str, str] = field(default_factory=dict)
    query_params: Dict[str, Any] = field(default_factory=dict)
    request_body: Any = None

    # 断言相关
    assertions: List[Dict[str, Any]] = field(default_factory=list)

    # 数据库断言配置（方案B：SQL查询 + 字段断言分离）
    post_script: List[Dict[str, Any]] = field(default_factory=list)  # 后置脚本：执行SQL，存入变量
    db_checks: List[Dict[str, Any]] = field(default_factory=list)    # 数据库断言：引用变量，执行字段断言

    # 执行配置
    timeout: int = 30
    max_retry_times: int = 0
    tags: List[str] = field(default_factory=list)

    # 元数据
    case_status: str = "enabled"
    description: str = ""

    # 变量配置（从 preconditions JSON 中解析）
    preconditions: str = ""                        # 原始 preconditions JSON 字符串
    case_variables: Dict[str, Any] = field(default_factory=dict)  # 从 preconditions 解析出的变量字典

    # 响应字段提取配置（从接口响应中提取字段，供后续用例引用）
    extract_fields: List[Dict[str, Any]] = field(default_factory=list)
    # extract_fields 格式：
    # [
    #     {
    #         "name": "变量名",           # 提取后的变量名，用于后续用例引用
    #         "path": "$.data.orderId",   # JSONPath 路径
    #         "description": "订单ID"     # 描述（可选）
    #     }
    # ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "db_id": self.db_id,
            "name": self.name,
            "module": self.module,
            "priority": self.priority,
            "method": self.method,
            "path": self.path,
            "headers": self.headers,
            "query_params": self.query_params,
            "request_body": self.request_body,
            "assertions": self.assertions,
            "post_script": self.post_script,
            "db_checks": self.db_checks,
            "timeout": self.timeout,
            "max_retry_times": self.max_retry_times,
            "tags": self.tags,
            "case_status": self.case_status,
            "description": self.description,
            "preconditions": self.preconditions,
            "case_variables": self.case_variables,
            "extract_fields": self.extract_fields,
        }


class TestCaseExecutor:
    """
    测试用例执行器。

    从数据库读取用例，组装执行所需的所有数据。
    """

    def __init__(self):
        self.test_case_mapper = TestCaseMapper()
        self.api_config_mapper = ApiConfigMapper()
        self.env_config_mapper = EnvironmentConfigMapper()
        self.assertion_parser = ExpectedResultsParser()
        self.db_check_parser = DbCheckConfigParser()

    def load_cases(
        self,
        case_ids: List[int],
        env_id: Optional[int] = None
    ) -> List[TestCaseExecutionData]:
        """
        加载测试用例执行数据。

        Args:
            case_ids: 用例数据库 ID 列表
            env_id: 环境配置 ID（可选，不传则从用例关联的 api_config 获取默认环境）

        Returns:
            List[TestCaseExecutionData]: 用例执行数据列表
        """
        logger.info("【TestCaseExecutor】加载 %d 个测试用例", len(case_ids))

        # 1. 读取用例
        raw_cases = []
        for cid in case_ids:
            case = self.test_case_mapper.get_by_id(cid)
            if case is None:
                logger.warning("【TestCaseExecutor】用例不存在: id=%d", cid)
                continue
            raw_cases.append(case)

        if not raw_cases:
            logger.warning("【TestCaseExecutor】未找到任何有效用例")
            return []

        # 2. 读取环境配置
        env_config = None
        if env_id:
            env_config = self.env_config_mapper.get_by_id(env_id)

        # 3. 批量读取 API 配置
        api_config_ids = [c.api_config_id for c in raw_cases if c.api_config_id]
        api_configs = {}
        for acid in api_config_ids:
            cfg = self.api_config_mapper.get_by_id(acid)
            if cfg:
                api_configs[acid] = cfg

        # 4. 组装执行数据
        execution_cases = []
        for case in raw_cases:
            try:
                exec_data = self._build_execution_data(case, api_configs, env_config)
                execution_cases.append(exec_data)
            except Exception as e:
                logger.error("【TestCaseExecutor】构建用例 %s 执行数据失败: %s",
                            case.case_id or case.id, e)

        logger.info("【TestCaseExecutor】成功加载 %d 个用例", len(execution_cases))
        return execution_cases

    def _build_execution_data(
        self,
        case,
        api_configs: Dict,
        env_config
    ) -> TestCaseExecutionData:
        """构建单个用例的执行数据"""
        # API 配置
        api_cfg = api_configs.get(case.api_config_id) if case.api_config_id else None
        logger.info("【_build_execution_data】case_id=%s, api_config_id=%s, api_cfg=%s",
                    getattr(case, 'case_id', None) or case.id, case.api_config_id,
                    f"ApiConfig(id={api_cfg.id}, name={getattr(api_cfg, 'name', 'N/A')}, "
                    f"method={getattr(api_cfg, 'method', 'N/A')}, "
                    f"path={getattr(api_cfg, 'api_path', 'N/A')})"
                    if api_cfg else "None")

        # 解析 preconditions JSON，提取变量配置
        preconditions_str = getattr(case, 'preconditions', '') or ''
        case_variables = self._parse_preconditions(preconditions_str)
        logger.info("【_build_execution_data】解析 preconditions: 原始=%s, 提取变量=%s",
                    preconditions_str[:200] if preconditions_str else '(空)',
                    case_variables)

        # 解析断言（包括 HTTP 断言和 db_check 引用）
        assertions = self._parse_assertions(case.expected_results)

        # 解析数据库断言配置（post_script 和 db_checks）
        post_script, db_checks = self._parse_db_checks(case.expected_results)

        # 解析响应字段提取配置（优先从 expected_results 解析，否则 fallback 到 extract_fields 列）
        extract_fields = self._parse_extract_fields(case.expected_results)
        if not extract_fields:
            extract_fields = getattr(case, 'extract_fields', []) or []
            if extract_fields:
                logger.info("【_build_execution_data】从 extract_fields 列读取到 %d 个提取配置: %s",
                           len(extract_fields), [f.get('name') for f in extract_fields])

        # 请求参数（优先用 test_data；若为空则 fallback 到 test_steps）
        headers = self._merge_headers(env_config, api_cfg)
        query_params, request_body = self._parse_request_params(case.test_data, api_cfg, getattr(case, "test_steps", None))

        # 优先级字段可能为枚举值
        priority = str(case.priority) if case.priority else "P2"

        method = self._get_method(api_cfg)
        path = self._get_path(api_cfg)
        logger.info("【_build_execution_data】最终 method=%s, path=%s, headers=%s, query=%s, body=%s",
                    method, path,
                    json.dumps(headers, ensure_ascii=False) if headers else "{}",
                    json.dumps(query_params, ensure_ascii=False) if query_params else "{}",
                    json.dumps(request_body, ensure_ascii=False) if request_body is not None else "None")
        logger.info("【_build_execution_data】数据库断言配置: post_script=%d个, db_checks=%d个",
                    len(post_script), len(db_checks))

        return TestCaseExecutionData(
            case_id=case.case_id or f"DB_{case.id}",
            db_id=case.id,
            name=case.name,
            module=case.module,
            priority=priority,
            method=method,
            path=path,
            headers=headers,
            query_params=query_params,
            request_body=request_body,
            assertions=assertions,
            post_script=post_script,
            db_checks=db_checks,
            timeout=case.timeout or 30,
            max_retry_times=case.max_retry_times or 0,
            tags=case.tags or [],
            case_status=str(case.case_status) if case.case_status else "enabled",
            description=case.description or "",
            preconditions=preconditions_str,
            case_variables=case_variables,
            extract_fields=extract_fields,
        )

    def _parse_assertions(self, expected_results) -> List[Dict[str, Any]]:
        """解析 expected_results 为断言列表"""
        return self.assertion_parser.parse(expected_results)

    def _parse_preconditions(self, preconditions_str: str) -> Dict[str, Any]:
        """
        解析 preconditions JSON 字符串，提取变量配置。

        preconditions JSON 格式示例：
        {
            "variables": {
                "payeeMno": "ALIPAY",
                "requestId": "REQ123456789",
                "outTradeNo": "OT987654321"
            }
        }

        或者直接是变量键值对：
        {
            "payeeMno": "ALIPAY",
            "requestId": "REQ123456789"
        }

        Returns:
            Dict[str, Any]: 变量名字典 {变量名: 变量值}
        """
        if not preconditions_str:
            return {}

        try:
            # 尝试解析 JSON
            preconditions = json.loads(preconditions_str)
            if not isinstance(preconditions, dict):
                logger.warning("【_parse_preconditions】preconditions 不是 JSON 对象: %s", type(preconditions))
                return {}

            # 方式1：variables 字段包装
            if "variables" in preconditions and isinstance(preconditions["variables"], dict):
                variables = preconditions["variables"]
                logger.info("【_parse_preconditions】从 variables 字段提取 %d 个变量", len(variables))
                return variables

            # 方式2：直接在顶层键值对中查找变量
            # 过滤掉非变量字段
            non_variable_keys = {"description", "desc", "note", "type", "name", "enabled", "active"}
            variables = {}
            for key, value in preconditions.items():
                if key.lower() not in non_variable_keys and isinstance(value, (str, int, float, bool)):
                    variables[key] = value

            if variables:
                logger.info("【_parse_preconditions】从 preconditions 顶层提取 %d 个变量: %s",
                           len(variables), list(variables.keys()))
            else:
                logger.info("【_parse_preconditions】preconditions 中未发现变量配置")

            return variables

        except json.JSONDecodeError as e:
            logger.warning("【_parse_preconditions】JSON 解析失败: %s, 原始内容: %s", e, preconditions_str[:200])
            return {}
        except Exception as e:
            logger.warning("【_parse_preconditions】解析 preconditions 异常: %s", e)
            return {}

    def _parse_db_checks(self, expected_results) -> tuple:
        """解析数据库断言配置（post_script 和 db_checks）"""
        return self.db_check_parser.parse(expected_results)

    def _parse_extract_fields(self, expected_results) -> List[Dict[str, Any]]:
        """
        解析响应字段提取配置。

        支持以下两种配置格式：

        格式一（独立顶层字段）：
        {
            "extract_fields": [
                {"name": "orderId", "path": "$.data.orderId", "description": "订单ID"},
                {"name": "userId", "path": "$.data.userId"}
            ]
        }

        格式二（嵌套在 extract 下）：
        {
            "extract": [
                {"name": "orderId", "path": "$.data.orderId"},
                {"name": "userId", "path": "$.data.userId"}
            ]
        }

        Returns:
            List[Dict[str, Any]]: 提取配置列表
        """
        if not expected_results:
            return []

        if isinstance(expected_results, str):
            try:
                expected_results = json.loads(expected_results)
            except json.JSONDecodeError:
                logger.warning("【_parse_extract_fields】expected_results JSON 解析失败")
                return []

        if not isinstance(expected_results, dict):
            return []

        # 格式一：直接取 extract_fields
        extract_list = expected_results.get("extract_fields", [])

        # 格式二：取 extract 字段
        if not extract_list:
            extract_list = expected_results.get("extract", [])

        if not isinstance(extract_list, list):
            logger.warning("【_parse_extract_fields】extract_fields/extract 必须是数组")
            return []

        result = []
        for item in extract_list:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            path = item.get("path")
            if not name or not path:
                logger.warning("【_parse_extract_fields】缺少 name 或 path: %s", item)
                continue
            result.append({
                "name": name,
                "path": path,
                "description": item.get("description", ""),
            })

        if result:
            logger.info("【_parse_extract_fields】解析出 %d 个提取配置: %s",
                       len(result), [r["name"] for r in result])
        return result

    def _merge_headers(self, env_config, api_cfg) -> Dict[str, str]:
        """
        获取请求头。

        优先级规则：API配置 headers 有值时使用（覆盖模式），为空时生成器使用默认 Content-Type。

        支持存储多个请求头，数据库 JSON 格式示例：
        {
            "Content-Type": "application/json",
            "Authorization": "Bearer xxx",
            "X-User-Id": "12345",
            "X-Request-Type": "test"
        }
        """
        headers: Dict[str, str] = {}

        # API 配置的 headers 优先，有值就用配置的（覆盖模式，支持多个 key-value）
        if api_cfg and hasattr(api_cfg, "headers") and api_cfg.headers:
            if isinstance(api_cfg.headers, dict):
                headers.update(api_cfg.headers)

        # 不再合并 env_config.headers，保持 API 配置独立
        # 如果 API headers 为空，生成器会用 {"Content-Type": "application/json"} 作为默认值

        return headers

    def _parse_request_params(self, test_data, api_cfg, test_steps=None) -> tuple:
        """
        解析请求参数，分离 query 和 body。

        优先级：test_data > test_steps（作为 body fallback）。

        Args:
            test_data: 案例的测试数据字段（dict 或其他）
            api_cfg: API 配置对象
            test_steps: 案例的 test_steps 字段（list），用于 body fallback
        """
        query: Dict[str, Any] = {}
        body: Any = None

        if test_data:
            if isinstance(test_data, dict):
                query = test_data.get("params", test_data.get("query", {}))
                body = test_data.get("body", test_data.get("json", {}))
                if not body:
                    # 如果没有显式 body，整个 test_data 作为 body
                    body = {k: v for k, v in test_data.items()
                           if k not in ("params", "query")}
            else:
                body = test_data

        # 直接使用 test_steps 作为 body（不包裹 test_steps key）
        if body in (None, {}) and test_steps:
            logger.info("【_parse_request_params】使用 test_steps 作为 body")
            body = test_steps

        # API 默认参数
        if api_cfg and hasattr(api_cfg, "default_params") and api_cfg.default_params:
            default_params = api_cfg.default_params
            if isinstance(default_params, dict):
                for k, v in default_params.items():
                    if k not in query:
                        query[k] = v

        return query, body or {}

    def _get_method(self, api_cfg) -> str:
        if api_cfg and hasattr(api_cfg, "method"):
            val = api_cfg.method
            logger.info("【_get_method】api_cfg.method 原始值: %s, 类型: %s", val, type(val).__name__)
            if hasattr(val, "value"):
                result = val.value.upper()
            else:
                result = str(val or "GET").upper()
            logger.info("【_get_method】返回 method: %s", result)
            return result
        logger.info("【_get_method】无 api_cfg 或无 method 属性，返回默认 GET")
        return "GET"

    def _get_path(self, api_cfg) -> str:
        if api_cfg and hasattr(api_cfg, "api_path"):
            path = api_cfg.api_path or ""
            logger.info("【_get_path】api_cfg.api_path: %s", path)
            return path
        logger.info("【_get_path】无 api_cfg 或无 api_path 属性，返回空字符串")
        return ""

    def save_execution_result(
        self,
        case_id: int,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """
        保存执行结果回写数据库。

        更新 crosstest_test_case.last_execution_status 和 last_execution_time。
        """
        from datetime import datetime
        try:
            self.test_case_mapper.update_with_version_check(
                id=case_id,
                update_data={
                    "last_execution_status": status,
                    "last_execution_time": datetime.now(),
                }
            )
            logger.info("【TestCaseExecutor】用例 %d 执行结果已回写: %s", case_id, status)
        except Exception as e:
            logger.warning("【TestCaseExecutor】回写执行结果失败: %s", e)
