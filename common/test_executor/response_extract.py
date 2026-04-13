"""
响应字段提取夹具

提供统一的响应字段提取能力，支持从接口响应中提取指定字段并存储到上下文中，
供后续接口或断言使用。

使用方式：
    1. 通过 pytest fixture 获取 response_context
    2. 用例执行完成后，调用 extract_from_response() 提取字段
    3. 后续用例通过 response_context.get("变量名") 获取提取的值

字段引用格式（变量替换时使用）：
    ${RESPONSE.变量名}  或  ${response.变量名}

线程安全：response_context 是函数级 scope，每次执行独立，
        多个用例并行执行时不会互相干扰。
"""

import json
import logging
import threading
from typing import Any, Dict, Optional

import pytest
import jsonpath_ng

logger = logging.getLogger(__name__)

# session 级共享变量池（threading.Local 隔离线程）
_session_store = threading.local()


def _get_session_context() -> Dict[str, Any]:
    """
    获取当前线程的 session 级上下文。

    用于在同一次测试会话中，跨用例共享提取的响应变量。
    threading.local() 确保多线程并行执行时互不干扰。
    """
    if not hasattr(_session_store, "context"):
        _session_store.context = {}
    return _session_store.context


def _get_or_create_context(request_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    获取共享上下文。

    优先使用 request_context（pytest fixture 传入的函数级上下文），
    若为空则降级到 session 级上下文。
    """
    if request_context is not None:
        return request_context
    return _get_session_context()


def extract_from_response(
    resp,
    extract_fields: list,
    context: Optional[Dict[str, Any]] = None,
    case_id: str = "unknown",
) -> Dict[str, Any]:
    """
    从响应对象中提取指定字段。

    Args:
        resp: requests.Response 对象
        extract_fields: 提取配置列表，格式：
            [
                {"name": "变量名", "path": "$.data.orderId", "description": "描述"},
                ...
            ]
        context: 共享上下文字典，提取的变量会存入此字典
        case_id: 用例编号（仅用于日志）

    Returns:
        Dict[str, Any]: 提取结果 {"变量名": 值, ...}

    Raises:
        不抛异常，提取失败时记录日志并跳过该字段。
    """
    shared = _get_or_create_context(context)

    if not extract_fields:
        logger.debug("【extract_from_response】用例 %s 无提取配置", case_id)
        return {}

    if not hasattr(resp, "json"):
        logger.warning("【extract_from_response】用例 %s: resp 不支持 json()，跳过提取", case_id)
        return {}

    try:
        body = resp.json()
    except Exception as e:
        logger.warning("【extract_from_response】用例 %s: 响应体解析失败: %s", case_id, e)
        body = {}

    extracted = {}

    for field_cfg in extract_fields:
        name = field_cfg.get("name", "")
        path = field_cfg.get("path", "")
        description = field_cfg.get("description", "")

        if not name or not path:
            logger.warning("【extract_from_response】用例 %s: 配置缺少 name 或 path: %s", case_id, field_cfg)
            continue

        try:
            expr = jsonpath_ng.parse(path)
            matches = [m.value for m in expr.find(body)]

            if matches:
                value = matches[0]
                extracted[name] = value
                shared[name] = value
                logger.info(
                    "【extract_from_response】用例 %s 提取成功: %s (%s) = %s",
                    case_id, name, path,
                    json.dumps(value, ensure_ascii=False)[:200]
                )
            else:
                logger.warning(
                    "【extract_from_response】用例 %s: 路径 %s 无匹配结果，跳过字段 %s",
                    case_id, path, name
                )
        except Exception as e:
            logger.warning(
                "【extract_from_response】用例 %s: 提取字段 %s (path=%s) 失败: %s",
                case_id, name, path, e
            )

    # 日志汇总
    if extracted:
        logger.info(
            "【extract_from_response】用例 %s 提取完成: 共 %d/%d 个字段成功, 变量名: %s",
            case_id, len(extracted), len(extract_fields), list(extracted.keys())
        )
    else:
        if extract_fields:
            logger.warning(
                "【extract_from_response】用例 %s: 无任何字段提取成功，检查配置或响应结构",
                case_id
            )

    return extracted


def get_extracted_value(
    name: str,
    context: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    从共享上下文获取已提取的变量值。

    Args:
        name: 变量名
        context: 优先使用的上下文字典

    Returns:
        变量值，若不存在返回 None
    """
    shared = _get_or_create_context(context)
    value = shared.get(name)
    if value is not None:
        logger.debug("【get_extracted_value】获取变量 %s = %s", name,
                    json.dumps(value, ensure_ascii=False)[:200])
    else:
        logger.debug("【get_extracted_value】变量 %s 不存在", name)
    return value


def list_all_extracted(context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """获取当前所有已提取的变量（快照）"""
    shared = _get_or_create_context(context)
    logger.debug("【list_all_extracted】当前已提取变量: %s", list(shared.keys()))
    return dict(shared)


def clear_extracted(context: Optional[Dict[str, Any]] = None) -> None:
    """
    清空共享上下文中的所有提取变量。

    通常在 session 级 fixture teardown 时调用，或在需要重置时调用。
    """
    shared = _get_or_create_context(context)
    count = len(shared)
    shared.clear()
    logger.info("【clear_extracted】已清空 %d 个提取变量", count)


# =============================================================================
# pytest fixtures
# =============================================================================

@pytest.fixture(scope="function")
def response_context():
    """
    函数级 fixture，提供响应提取上下文。

    同一个测试函数内的所有步骤共享同一个 context 字典。
    函数执行结束后自动清空（teardown）。

    使用示例：
        def test_order_flow(response_context):
            # 调用提取函数
            extract_from_response(resp, extract_fields, context=response_context)
            # 获取已提取的变量
            order_id = response_context.get("orderId")
    """
    context: Dict[str, Any] = {}
    yield context
    logger.debug("【response_context fixture】teardown，清空 context: %s", list(context.keys()))
    context.clear()


@pytest.fixture(scope="session", autouse=False)
def response_context_session():
    """
    Session 级 fixture，提供响应提取上下文（会话内共享）。

    适用于同一执行批次内的多用例按顺序执行时，共享提取变量。
    默认不自动启用（autouse=False），需要显式在测试文件中引入。

    使用示例：
        # 在生成的测试文件顶部添加：
        from common.test_executor.response_extract import response_context_session

        # 或通过 conftest.py 引入
    """
    context = _get_session_context()
    logger.info("【response_context_session fixture】session 开始，已提取变量: %s", list(context.keys()))
    yield context
    logger.info("【response_context_session fixture】session 结束，已提取变量: %s", list(context.keys()))
    context.clear()
