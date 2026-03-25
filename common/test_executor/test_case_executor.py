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

    # 执行配置
    timeout: int = 30
    max_retry_times: int = 0
    tags: List[str] = field(default_factory=list)

    # 元数据
    case_status: str = "enabled"
    description: str = ""

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
            "timeout": self.timeout,
            "max_retry_times": self.max_retry_times,
            "tags": self.tags,
            "case_status": self.case_status,
            "description": self.description,
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

        # 解析断言
        assertions = self._parse_assertions(case.expected_results)

        # 请求参数
        headers = self._merge_headers(env_config, api_cfg)
        query_params, request_body = self._parse_request_params(case.test_data, api_cfg)

        # 优先级字段可能为枚举值
        priority = str(case.priority) if case.priority else "P2"

        return TestCaseExecutionData(
            case_id=case.case_id or f"DB_{case.id}",
            db_id=case.id,
            name=case.name,
            module=case.module,
            priority=priority,
            method=self._get_method(api_cfg),
            path=self._get_path(api_cfg),
            headers=headers,
            query_params=query_params,
            request_body=request_body,
            assertions=assertions,
            timeout=case.timeout or 30,
            max_retry_times=case.max_retry_times or 0,
            tags=case.tags or [],
            case_status=str(case.case_status) if case.case_status else "enabled",
            description=case.description or "",
        )

    def _parse_assertions(self, expected_results) -> List[Dict[str, Any]]:
        """解析 expected_results 为断言列表"""
        return self.assertion_parser.parse(expected_results)

    def _merge_headers(self, env_config, api_cfg) -> Dict[str, str]:
        """合并请求头：环境配置 < API配置 < 用例配置（后续可扩展）"""
        headers: Dict[str, str] = {}

        # 环境默认 headers
        if env_config and hasattr(env_config, "headers") and env_config.headers:
            if isinstance(env_config.headers, dict):
                headers.update(env_config.headers)

        # API 配置 headers
        if api_cfg and hasattr(api_cfg, "headers") and api_cfg.headers:
            if isinstance(api_cfg.headers, dict):
                headers.update(api_cfg.headers)

        return headers

    def _parse_request_params(self, test_data, api_cfg) -> tuple:
        """解析请求参数，分离 query 和 body"""
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
            if hasattr(val, "value"):
                return val.value.upper()
            return str(val or "GET").upper()
        return "GET"

    def _get_path(self, api_cfg) -> str:
        if api_cfg and hasattr(api_cfg, "api_path"):
            return api_cfg.api_path or ""
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
