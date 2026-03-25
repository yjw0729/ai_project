import os
import json
import logging
from typing import List
from flask import Blueprint, jsonify, request, make_response, current_app

from common.llm.enhanced_case_generator import (
    EnhancedCaseGenerator,
    GenerationConfig,
    GenerationResult,
    GeneratedCase,
)
from common.llm.llm_client import OpenAILLMClient
from common.db_mapper.business_context_mapper import BusinessContextMapper
from common.db_enitiy.business_context import BusinessContext
from common.db_mapper.test_case_mapper import TestCaseMapper
from common.db_enitiy.test_case import TestCase
from common.db_enitiy.api_config import ApiConfig
from common.datacase_function.contect_db import db_session
from utils.read_config_path.read_ai_config import load_ai_config

enhanced_generate_opt = Blueprint("enhanced_generate_opt", __name__)


def json_response(body, status=200):
    resp = make_response(jsonify(body), status)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


def _get_llm_client(logger) -> tuple:
    """获取 LLM 客户端，返回 (client, error_message)"""
    try:
        ai_conf = load_ai_config()
        api_key = ai_conf.get("api_key")
        if not api_key:
            return None, "未配置 API Key"
        base_url = (ai_conf.get("base_url") or "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
        model = ai_conf.get("model") or "qwen-plus"
        temperature = ai_conf.get("temperature", 0.2)
        max_tokens = ai_conf.get("max_tokens", 16000)
        timeout = ai_conf.get("timeout", 600)

        client = OpenAILLMClient(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        return client, None
    except Exception as e:
        return None, str(e)


def _case_to_entity(
    case: GeneratedCase,
    api_config_id: int = None,
    module: str = None,
    system: str = None,
    creator: str = "ai_generator"
) -> TestCase:
    """将 GeneratedCase 转换为 TestCase ORM 实体"""

    if case.case_type == "scenario":
        return TestCase(
            name=case.title,
            description=case.description or case.scenario_description,
            module=module or "default",
            system=system,
            priority=case.priority,
            tags=case.tags,
            preconditions=case.preconditions,
            test_steps=[{
                "step_number": step.get("step_number", i + 1),
                "description": step.get("description", ""),
                "api": step.get("api", ""),
                "data": {
                    "headers": step.get("headers", {}),
                    "query": step.get("query", {}),
                    "body": step.get("body", {}),
                },
                "extract": step.get("extract", {}),
                "expected_results": step.get("expected_results", [])
            } for i, step in enumerate(case.test_steps)],
            expected_results=case.expected_results,
            test_data={
                "case_type": "scenario",
                "scenario_name": case.scenario_name,
                "request": {}
            },
            status="draft",
            case_status="enabled",
            last_execution_status="not_run",
            version=1,
            creator=creator,
            reviewer=None,
            review_status="pending",
            api_config_id=api_config_id,
        )
    else:
        return TestCase(
            name=case.title,
            description=case.description,
            module=module or "default",
            system=system,
            priority=case.priority,
            tags=case.tags,
            preconditions="",
            test_steps=[{
                "step_number": 1,
                "description": f"调用接口 {case.method} {case.path}",
                "data": case.request,
            }],
            expected_results=case.expected_results,
            test_data={
                "case_type": "interface",
                "request": case.request
            },
            status="draft",
            case_status="enabled",
            last_execution_status="not_run",
            version=1,
            creator=creator,
            reviewer=None,
            review_status="pending",
            api_config_id=api_config_id,
        )


def _save_context_to_db(
    context_data: dict,
    logger,
    db_key: str = "default"
) -> int:
    """保存业务上下文到数据库"""
    try:
        mapper = BusinessContextMapper(db_key=db_key)
        context = BusinessContext(
            name=context_data.get("name", "未命名上下文"),
            description=context_data.get("description", ""),
            source_type=context_data.get("source_type", "text"),
            source_name=context_data.get("source_name", ""),
            source_size=context_data.get("source_size", 0),
            content=context_data.get("content", ""),
            content_hash=context_data.get("content_hash", ""),
            total_chars=context_data.get("total_chars", 0),
            chunk_count=context_data.get("chunk_count", 0),
            chunk_size=context_data.get("chunk_size", 3000),
            module=context_data.get("module", ""),
            creator=context_data.get("creator", "system")
        )
        return mapper.create(context)
    except Exception as e:
        logger.error(f"保存业务上下文失败: {e}", exc_info=True)
        return None


def _save_cases_to_db(
    cases: List[GeneratedCase],
    logger,
    db_key: str = "default",
    api_config_id: int = None,
    module: str = None,
    system: str = None,
    creator: str = "ai_generator"
) -> List[int]:
    """保存用例到数据库"""
    mapper = TestCaseMapper(db_key=db_key)
    saved_ids = []

    for case in cases:
        try:
            entity = _case_to_entity(
                case,
                api_config_id=api_config_id,
                module=module,
                system=system,
                creator=creator
            )
            case_id = mapper.create(entity)
            saved_ids.append(case_id)
            logger.info(f"用例写入成功: id={case_id}, name={case.title}")
        except Exception as e:
            logger.error(f"用例写入失败: name={case.title}, error={e}", exc_info=True)

    return saved_ids


@enhanced_generate_opt.route("/ai/generate_with_context", methods=["POST"])
def generate_with_context():
    """
    增强的用例生成接口 - 支持业务上下文

    请求体示例:

    方式1: 直接传入文本
    {
        "api_name": "创建订单",
        "api_path": "/api/v1/order",
        "api_method": "POST",
        "params_example": {"product_id": 1, "quantity": 1},
        "business_context": "订单流程：用户选择商品 -> 加入购物车 -> 创建订单 -> 支付"
    }

    方式2: 从向量数据库查询（复用已有 RAG 文档）
    {
        "api_name": "创建订单",
        "api_path": "/api/v1/order",
        "api_method": "POST",
        "params_example": {"product_id": 1, "quantity": 1},
        "business_context": {
            "type": "vector_db",
            "collection_name": "documents",
            "query": "订单流程 业务规则",
            "top_k": 5
        }
    }

    方式3: 复用已上传的上下文 ID
    {
        "api_name": "创建订单",
        "api_path": "/api/v1/order",
        "api_method": "POST",
        "business_context": {
            "type": "context_id",
            "id": 123
        }
    }
    """
    logger = current_app.logger or logging.getLogger(__name__)

    try:
        payload = request.get_json(force=True, silent=False) or {}

        # 必填字段检查
        required_fields = ["api_name", "api_path", "api_method"]
        missing = [f for f in required_fields if not payload.get(f)]
        if missing:
            return json_response(
                {"code": 400, "msg": f"缺少必填字段: {','.join(missing)}", "data": None},
                status=400
            )

        # 获取 LLM 客户端
        llm_client, error = _get_llm_client(logger)
        if error:
            return json_response(
                {"code": 500, "msg": f"LLM 客户端初始化失败: {error}", "data": None},
                status=500
            )

        # 构建生成配置（直接传递 business_context，生成器会自动处理）
        config = GenerationConfig(
            api_name=payload.get("api_name"),
            api_path=payload.get("api_path"),
            api_method=payload.get("api_method", "GET"),
            api_desc=payload.get("api_desc", ""),
            params_example=payload.get("params_example", {}),
            constraints=payload.get("constraints", ""),
            business_context=payload.get("business_context"),  # 支持多种格式
            max_interface_cases=payload.get("max_interface_cases", 10),
            max_scenario_cases=payload.get("max_scenario_cases", 5),
            include_interface_cases=payload.get("include_interface_cases", True),
            include_scenario_cases=payload.get("include_scenario_cases", True),
        )

        # 生成用例
        logger.info("开始生成用例...")
        generator = EnhancedCaseGenerator(llm_client)
        result = generator.generate(config)

        if not result.success:
            return json_response(
                {
                    "code": 500,
                    "msg": f"用例生成失败: {', '.join(result.errors)}",
                    "data": {
                        "context_summary": result.context_summary,
                        "errors": result.errors
                    }
                },
                status=500
            )

        # 保存到数据库
        saved_case_ids = []
        context_id = None
        if payload.get("persist", False):
            api_config_id = None
            with db_session() as session:
                existing = session.query(ApiConfig).filter(
                    ApiConfig.api_path == config.api_path,
                    ApiConfig.method == config.api_method.upper(),
                    ApiConfig.is_deprecated == False
                ).first()
                if existing:
                    api_config_id = existing.id

            creator = payload.get("creator", "ai_generator")
            module = payload.get("module", config.api_name)

            # 保存用例
            saved_case_ids = _save_cases_to_db(
                result.all_cases,
                logger,
                api_config_id=api_config_id,
                module=module,
                creator=creator
            )

        # 返回结果
        return json_response({
            "code": 200,
            "msg": "生成成功",
            "data": {
                "success": True,
                "interface_case_count": len(result.interface_cases),
                "scenario_case_count": len(result.scenario_cases),
                "total_count": result.total_count,
                "interface_cases": [
                    {
                        "title": c.title,
                        "description": c.description,
                        "priority": c.priority,
                        "tags": c.tags,
                        "method": c.method,
                        "path": c.path,
                        "request": c.request,
                        "expected_results": c.expected_results
                    }
                    for c in result.interface_cases
                ],
                "scenario_cases": [
                    {
                        "scenario_name": c.scenario_name,
                        "title": c.title,
                        "description": c.description,
                        "priority": c.priority,
                        "tags": c.tags,
                        "preconditions": c.preconditions,
                        "test_steps": c.test_steps,
                        "expected_results": c.expected_results
                    }
                    for c in result.scenario_cases
                ],
                "context_summary": result.context_summary,
                "saved_case_ids": saved_case_ids,
                "context_id": context_id
            }
        })

    except Exception as e:
        logger.error(f"用例生成异常: {e}", exc_info=True)
        return json_response(
            {"code": 500, "msg": f"服务端异常: {str(e)}", "data": None},
            status=500
        )


@enhanced_generate_opt.route("/ai/context/<int:context_id>", methods=["GET"])
def get_context(context_id):
    """获取业务上下文详情"""
    logger = current_app.logger or logging.getLogger(__name__)

    try:
        mapper = BusinessContextMapper()
        context = mapper.get_by_id(context_id)

        if not context:
            return json_response({"code": 404, "msg": "上下文不存在", "data": None}, status=404)

        return json_response({
            "code": 200,
            "msg": "success",
            "data": context.to_dict()
        })

    except Exception as e:
        logger.error(f"获取业务上下文失败: {e}", exc_info=True)
        return json_response(
            {"code": 500, "msg": f"服务端异常: {str(e)}", "data": None},
            status=500
        )


@enhanced_generate_opt.route("/ai/context/list", methods=["GET"])
def list_contexts():
    """列出业务上下文"""
    logger = current_app.logger or logging.getLogger(__name__)

    try:
        skip = int(request.args.get("skip", 0))
        limit = int(request.args.get("limit", 20))
        module = request.args.get("module")

        mapper = BusinessContextMapper()
        contexts = mapper.list_all(skip=skip, limit=limit, module=module)

        return json_response({
            "code": 200,
            "msg": "success",
            "data": {
                "total": len(contexts),
                "items": [c.to_dict() for c in contexts]
            }
        })

    except Exception as e:
        logger.error(f"列出业务上下文失败: {e}", exc_info=True)
        return json_response(
            {"code": 500, "msg": f"服务端异常: {str(e)}", "data": None},
            status=500
        )
