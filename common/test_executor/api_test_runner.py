"""
API自动化测试 - 核心测试运行器
"""

import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from threading import Lock

import requests

from common.test_executor.parameter_resolver import ParameterResolver
from common.test_executor.assertion_engine import AssertionEngine, AssertionResult

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """单个测试用例执行结果"""
    case_id: Union[int, str]
    case_name: str
    status: str  # passed, failed, skipped, error
    duration_ms: float
    response_time_ms: int
    assertions: List[Dict[str, Any]] = field(default_factory=list)
    response_body: Any = None
    response_headers: Dict[str, str] = field(default_factory=dict)
    status_code: Optional[int] = None
    error: Optional[str] = None
    stack_trace: Optional[str] = None
    steps: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["assertions"] = self.assertions
        return result


class APITestRunner:
    """
    API测试运行器。

    核心功能：
    - 单用例执行和批量执行（串行/并发）
    - 参数变量替换（全局变量、前置接口变量、特殊变量）
    - 断言执行（多种断言类型）
    - 变量提取（从响应中提取供后续用例使用）
    - 前置/后置脚本支持
    - 执行结果收集与报告
    """

    def __init__(
        self,
        env_config: Optional[Dict[str, Any]] = None,
        concurrency: int = 5,
        default_timeout: int = 30,
        max_retry: int = 2,
    ):
        self.env_config: Dict[str, Any] = env_config or {}
        self.concurrency: int = concurrency
        self.default_timeout: int = default_timeout
        self.max_retry: int = max_retry

        self.session: requests.Session = requests.Session()
        self.resolver: ParameterResolver = ParameterResolver()
        self.assertion_engine: AssertionEngine = AssertionEngine()

        self.results: List[TestResult] = []
        self._results_lock: Lock = Lock()

        self._apply_env_headers()

    def _apply_env_headers(self) -> None:
        """应用环境配置的默认headers"""
        headers = self.env_config.get("headers", {})
        if headers:
            self.session.headers.update(headers)

    # ==================== 核心执行方法 ====================

    def execute_single(self, test_case: Dict[str, Any]) -> TestResult:
        """执行单个测试用例"""
        start_time = time.time()
        case_id = test_case.get("id") or test_case.get("case_id") or str(uuid.uuid4())[:8]
        case_name = test_case.get("name") or test_case.get("title", f"Case_{case_id}")

        logger.info("【Runner】开始执行用例: %s (%s)", case_name, case_id)

        try:
            # 1. 替换变量
            resolved = self.resolver.resolve(test_case)

            # 2. 执行前置脚本
            self._run_setup_scripts(resolved)

            # 3. 发送请求
            response, resp_time_ms = self._send_request(resolved)

            # 4. 设置前置响应供后续用例使用
            resp_body = self._try_parse_json(response)
            self.resolver.set_prev_response(resp_body or {})

            # 5. 执行断言
            assertions_raw = resolved.get("assertions") or resolved.get("expected_results") or []
            assertion_results: List[AssertionResult] = self.assertion_engine.assert_all(
                response, assertions_raw
            )
            assertion_dicts = [r.to_dict() for r in assertion_results]
            all_passed = all(r.passed for r in assertion_results)

            # 6. 提取变量
            variable_mapping = resolved.get("variable_mapping") or resolved.get("extract_variables") or {}
            if variable_mapping:
                self.resolver.extract_variables_from_response(resp_body or {}, variable_mapping)

            # 7. 执行后置脚本
            self._run_teardown_scripts(resolved)

            duration_ms = (time.time() - start_time) * 1000
            status = "passed" if all_passed else "failed"

            result = TestResult(
                case_id=case_id,
                case_name=case_name,
                status=status,
                duration_ms=duration_ms,
                response_time_ms=resp_time_ms,
                assertions=assertion_dicts,
                response_body=self._safe_serialize(resp_body),
                response_headers=dict(response.headers) if hasattr(response, "headers") else {},
                status_code=response.status_code if hasattr(response, "status_code") else None,
            )

            logger.info("【Runner】用例 %s 执行完成: status=%s, duration=%.1fms",
                        case_id, status, duration_ms)
            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error("【Runner】用例 %s 执行异常: %s", case_id, str(e), exc_info=True)
            return TestResult(
                case_id=case_id,
                case_name=case_name,
                status="error",
                duration_ms=duration_ms,
                response_time_ms=0,
                error=str(e),
                stack_trace=self._get_traceback(),
            )

    def execute_batch(
        self,
        test_cases: List[Dict[str, Any]],
        mode: str = "parallel"
    ) -> List[TestResult]:
        """
        批量执行测试用例。
        mode: "parallel" 并发执行, "serial" 串行执行
        """
        logger.info("【Runner】批量执行开始: 总数=%d, 模式=%s", len(test_cases), mode)
        self.results = []

        if mode == "parallel":
            with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
                futures = {
                    executor.submit(self.execute_single, tc): tc
                    for tc in test_cases
                }
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        with self._results_lock:
                            self.results.append(result)
                    except Exception as e:
                        tc = futures[future]
                        logger.error("【Runner】Future执行异常: %s", str(e))
                        self.results.append(TestResult(
                            case_id=tc.get("id", "unknown"),
                            case_name=tc.get("name", "unknown"),
                            status="error",
                            duration_ms=0,
                            response_time_ms=0,
                            error=str(e),
                        ))
        else:
            for tc in test_cases:
                result = self.execute_single(tc)
                self.results.append(result)

        passed = sum(1 for r in self.results if r.status == "passed")
        failed = sum(1 for r in self.results if r.status == "failed")
        errors = sum(1 for r in self.results if r.status == "error")
        total_duration = sum(r.duration_ms for r in self.results)

        logger.info("【Runner】批量执行完成: 总数=%d, 通过=%d, 失败=%d, 异常=%d, 总耗时=%.1fms",
                    len(self.results), passed, failed, errors, total_duration)

        return self.results

    def execute_chain(
        self,
        test_chain: List[Dict[str, Any]],
        mode: str = "serial"
    ) -> List[TestResult]:
        """
        按依赖链顺序执行测试用例。
        前置用例的响应变量会自动传递给后续用例。
        """
        logger.info("【Runner】链式执行开始: 步骤数=%d", len(test_chain))
        self.results = []

        for step in test_chain:
            logger.info("【Runner】执行步骤: %s", step.get("name", "unnamed"))
            result = self.execute_single(step)
            self.results.append(result)

            # 如果当前步骤失败，可以选择停止链式执行
            if result.status == "failed" or result.status == "error":
                logger.warning("【Runner】步骤 %s 失败，链式执行可能中断",
                               step.get("name", "unnamed"))
                if mode == "fail_fast":
                    break

        return self.results

    # ==================== HTTP请求 ====================

    def _send_request(self, test_case: Dict[str, Any]) -> tuple:
        """发送HTTP请求，返回(response, response_time_ms)"""
        request_config = test_case.get("request") or test_case.get("test_data", {}).get("request", {})

        method = (request_config.get("method") or "GET").upper()
        path = request_config.get("path", "")
        headers = request_config.get("headers", {})
        query = request_config.get("query", {})
        body = request_config.get("body", {})
        timeout = request_config.get("timeout") or self.default_timeout

        url = self._join_url(self.env_config.get("base_url", ""), path)

        logger.debug("【Runner】发送请求: %s %s", method, url)
        logger.debug("【Runner】请求头: %s", json.dumps(headers, ensure_ascii=False))
        logger.debug("【Runner】请求参数: %s", json.dumps(query, ensure_ascii=False))
        logger.debug("【Runner】请求体: %s", json.dumps(body, ensure_ascii=False)[:500])

        start = time.time()
        try:
            resp = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=query,
                json=body if body else None,
                timeout=timeout,
            )
            resp_time_ms = int((time.time() - start) * 1000)
            logger.debug("【Runner】响应: status=%d, time=%dms, body=%s",
                         resp.status_code, resp_time_ms, str(resp.text)[:200])
            return resp, resp_time_ms
        except requests.Timeout:
            logger.error("【Runner】请求超时: %s %s (timeout=%ds)", method, url, timeout)
            raise
        except requests.RequestException as e:
            logger.error("【Runner】请求失败: %s %s - %s", method, url, str(e))
            raise

    @staticmethod
    def _join_url(base_url: str, path: str) -> str:
        """拼接URL"""
        if not base_url:
            return path
        base = base_url.rstrip("/")
        p = path.lstrip("/")
        return f"{base}/{p}"

    # ==================== 前置/后置脚本 ====================

    def _run_setup_scripts(self, test_case: Dict[str, Any]) -> None:
        """执行前置脚本"""
        setup_scripts = test_case.get("setup_scripts") or []
        for script in setup_scripts:
            try:
                self._execute_script(script, "setup")
            except Exception as e:
                logger.warning("【Runner】前置脚本执行失败: %s", str(e))

    def _run_teardown_scripts(self, test_case: Dict[str, Any]) -> None:
        """执行后置脚本"""
        teardown_scripts = test_case.get("teardown_scripts") or []
        for script in teardown_scripts:
            try:
                self._execute_script(script, "teardown")
            except Exception as e:
                logger.warning("【Runner】后置脚本执行失败: %s", str(e))

    def _execute_script(self, script: Union[str, Dict], script_type: str) -> Any:
        """执行脚本（支持Python代码片段或预定义函数）"""
        if isinstance(script, str):
            # 直接执行Python代码片段
            local_vars = {"resolver": self.resolver, "session": self.session}
            try:
                exec(script, {}, local_vars)
                logger.debug("【Runner】%s脚本执行成功: %s", script_type, script[:100])
            except Exception as e:
                logger.warning("【Runner】%s脚本执行异常: %s - %s", script_type, script[:100], str(e))
        elif isinstance(script, dict):
            script_name = script.get("name") or script.get("type", "unknown")
            logger.debug("【Runner】执行预定义脚本: %s", script_name)

    # ==================== 工具方法 ====================

    def _try_parse_json(self, response: Any) -> Optional[Dict[str, Any]]:
        """尝试解析响应为JSON"""
        if hasattr(response, "json"):
            try:
                return response.json()
            except Exception:
                pass
        return None

    def _safe_serialize(self, data: Any, max_len: int = 2000) -> Any:
        """安全序列化数据（避免超长）"""
        if data is None:
            return None
        if isinstance(data, (str, int, float, bool)):
            return data
        if isinstance(data, (list, dict)):
            try:
                s = json.dumps(data, ensure_ascii=False)
                if len(s) > max_len:
                    return {"_truncated": True, "_preview": s[:max_len]}
                return json.loads(s)
            except Exception:
                return str(data)
        return str(data)

    def _get_traceback(self) -> str:
        """获取当前堆栈跟踪"""
        import traceback
        return traceback.format_exc()

    # ==================== 报告生成 ====================

    def get_summary(self) -> Dict[str, Any]:
        """生成执行摘要"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == "passed")
        failed = sum(1 for r in self.results if r.status == "failed")
        errors = sum(1 for r in self.results if r.status == "error")
        skipped = sum(1 for r in self.results if r.status == "skipped")
        total_duration = sum(r.duration_ms for r in self.results)
        avg_duration = total_duration / total if total > 0 else 0

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "error": errors,
            "skipped": skipped,
            "success_rate": round(passed / total * 100, 2) if total > 0 else 0,
            "total_duration_ms": round(total_duration, 1),
            "avg_duration_ms": round(avg_duration, 1),
        }

    def set_global_variable(self, key: str, value: Any) -> None:
        """设置全局变量"""
        self.resolver.set_global_variable(key, value)

    def set_prev_response(self, response_data: Dict[str, Any]) -> None:
        """设置前置接口响应"""
        self.resolver.set_prev_response(response_data)

    def cleanup(self) -> None:
        """清理资源"""
        if hasattr(self.session, "close"):
            self.session.close()
