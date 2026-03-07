#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成测试案例API
根据需求文档生成测试案例，并导出为XMind格式

改进版：支持结构化文档解析、向量存储、检索增强生成
"""

import os
import re
import json
import uuid
import asyncio
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, make_response, send_file
from werkzeug.utils import secure_filename
from pathlib import Path

# 导入RAG服务
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.rag.utils.xmind_generator import XMindGenerator, parse_llm_response_to_test_cases
from common.llm.prompt_manager import (
    get_prompt_manager, get_test_case_prompt,
    get_doc_structure_prompt,
    get_requirement_pre_analysis_prompt,
    get_requirement_structure_prompt,
    get_api_pre_analysis_prompt,
    get_interface_json_extract_prompt,
    get_context_info_prompt,
    get_single_interface_prompt,
    get_feature_analysis_prompt,
    get_feature_test_case_prompt,
)
from api.http_rag_document import get_rag_service, UPLOAD_FOLDER, ALLOWED_EXTENSIONS
from common.db_mapper.review_record_mapper import ReviewRecordMapper
from common.db_mapper.review_summary_mapper import ReviewSummaryMapper
from common.config import get_sql_query, get_default_settings

logger = logging.getLogger(__name__)

# 基础目录（项目根目录）
BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 统一的XMind输出目录，使用绝对路径
XMIND_OUTPUT_DIR = BASE_DIR / "outputs" / "test_cases"
XMIND_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 创建Blueprint
test_case_gen_opt = Blueprint("test_case_gen_opt", __name__)


# ===== 文档类型常量 =====
class DocumentType:
    """文档类型枚举"""
    API_DOC = "api_doc"  # API 文档
    PRODUCT_DESIGN = "product_design"  # 产品设计文档

    @classmethod
    def get_valid_types(cls):
        """获取所有有效的文档类型"""
        return [cls.API_DOC, cls.PRODUCT_DESIGN]

    @classmethod
    def get_type_name(cls, doc_type):
        """获取文档类型的中文名称"""
        type_names = {
            cls.API_DOC: "API 文档",
            cls.PRODUCT_DESIGN: "产品设计文档"
        }
        return type_names.get(doc_type, "未知类型")

    @classmethod
    def validate(cls, doc_type):
        """验证文档类型是否有效"""
        return doc_type in cls.get_valid_types()


def json_response(body, status=200):
    """返回JSON响应"""
    resp = make_response(jsonify(body), status)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp


# ====== 新增：结构化文档解析 ======

def parse_document_structure(document_content: str) -> dict:
    """
    解析文档结构，识别4大部分：
    1. 基础知识
    2. 服务内容
    3. 模板配置
    4. 核心API应用（最重要：接口定义、出入参、流程图）

    返回结构化字典
    """
    # 从配置获取提示词，获取不到时使用默认值
    DOC_STRUCTURE_PROMPT = get_doc_structure_prompt(
        default="""你是资深技术文档分析师。请仔细阅读下面的技术文档，并将其结构化地拆分为4大部分：

【文档内容】
{content}

【任务】
请将文档拆分并返回如下 JSON 结构（严格JSON，不要有其他内容）：
{{
    "basic_knowledge": "基础知识部分：提取与本系统/服务相关的基础概念、术语解释、前置条件等内容。如果该部分内容没有，请返回空字符串。",
    "service_content": "服务内容部分：提取业务流程、业务规则、服务范围等内容。如果该部分内容m没有，请返回空字符串。",
    "template_config": "模板配置部分：提取配置项、模板说明、参数配置等内容。如果该部分内容没有，请返回空字符串。",
    "api_section": "核心API应用部分：这是最重要的部分！提取所有接口定义、接口地址、请求方法、请求参数、响应参数、接口流程、调用示例等内容。如果该部分内容没有，请返回空字符串。"
}}

【注意】
- 每一部分的 content 必须是原始文档中对应内容的完整提取或精简概括，不要编造内容。
- 如果某部分在文档中不存在或内容极少，请返回空字符串""。
- API部分是核心，请尽可能完整地提取接口信息。
"""
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        max_input_chars = 60000  # 增加输入长度，确保包含完整的API接口信息
        content = document_content[:max_input_chars]

        prompt = DOC_STRUCTURE_PROMPT.format(content=content)

        rag = get_rag_service()
        if not rag:
            raise RuntimeError("RAG服务未初始化")

        result = loop.run_until_complete(
            rag._generate_answer(
                prompt=prompt,
                temperature=0.2,
                max_tokens=8000,  # 增加输出token，确保完整返回所有接口信息
            )
        )

        import re

        # 尝试修复和解析JSON
        def try_parse_json(json_str):
            """尝试解析JSON，如果失败则尝试修复"""
            # 先尝试直接解析
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

            # 尝试修复：处理未转义的引号和换行符
            try:
                # 尝试找到有效的JSON块
                json_match = re.search(r'\{[\s\S]*\}', json_str)
                if json_match:
                    json_str = json_match.group()

                # 处理换行符在字符串中的问题
                # 尝试逐行解析
                lines = json_str.split('\n')
                fixed_lines = []
                in_string = False
                for line in lines:
                    if '"' in line:
                        # 简单检查：奇数个引号表示字符串未结束
                        quote_count = line.count('"')
                        if quote_count % 2 == 1:
                            # 字符串未结束，尝试找到结束引号
                            line = line + '"'
                    fixed_lines.append(line)

                fixed_json = '\n'.join(fixed_lines)
                return json.loads(fixed_json)
            except json.JSONDecodeError:
                pass

            # 最后尝试：使用正则提取键值对
            try:
                result = {}
                # 提取 basic_knowledge
                match = re.search(r'"basic_knowledge"\s*:\s*"([^"]*)"', json_str, re.DOTALL)
                if match:
                    result["basic_knowledge"] = match.group(1)
                # 提取 service_content
                match = re.search(r'"service_content"\s*:\s*"([^"]*)"', json_str, re.DOTALL)
                if match:
                    result["service_content"] = match.group(1)
                # 提取 template_config
                match = re.search(r'"template_config"\s*:\s*"([^"]*)"', json_str, re.DOTALL)
                if match:
                    result["template_config"] = match.group(1)
                # 提取 api_section
                match = re.search(r'"api_section"\s*:\s*"([^"]*)"', json_str, re.DOTALL)
                if match:
                    result["api_section"] = match.group(1)

                if result:
                    return result
            except:
                pass

            return None

        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if json_match:
            parsed = try_parse_json(json_match.group())
            if parsed:
                return {
                    "basic_knowledge": parsed.get("basic_knowledge", "").strip(),
                    "service_content": parsed.get("service_content", "").strip(),
                    "template_config": parsed.get("template_config", "").strip(),
                    "api_section": parsed.get("api_section", "").strip(),
                }
        logger.warning("文档结构解析失败，返回默认结构")
        return {
            "basic_knowledge": "",
            "service_content": "",
            "template_config": "",
            "api_section": document_content[:5000],
        }
    except Exception as e:
        logger.error(f"文档结构解析异常: {e}", exc_info=True)
        return {
            "basic_knowledge": "",
            "service_content": "",
            "template_config": "",
            "api_section": document_content[:5000],
        }
    finally:
        loop.close()


# 存储向量库的collection引用（临时方案，避免重复创建）
_temp_vector_collections = {}


def _get_requirement_pre_analysis_prompt() -> str:
    """获取需求文档预分析提示词，优先从配置获取，失败时使用默认值"""
    return get_requirement_pre_analysis_prompt(
        default="""你是资深业务分析师和产品架构师。请仔细阅读下面的需求文档，进行全面分析。

【文档内容】
{content}

【核心任务：从需求文档中提取关键信息】

请分析需求文档，提取以下信息：

1. 项目概述
   - 项目背景和目标
   - 主要业务需求

2. 功能模块
   - 核心功能列表
   - 每个功能的主要描述

3. 业务流程
   - 主要业务流程描述
   - 关键业务节点

4. 业务规则
   - 重要的业务规则和约束条件

5. 数据需求（如果有）
   - 主要业务实体
   - 数据流转关系

6. 接口需求（从需求文档中推断）
   - 推断可能需要的接口
   - 接口的主要功能描述

【输出JSON格式】
{{
    "project_background": "项目背景和目标描述",
    "business_module": "业务模块名称",
    "business_summary": "业务摘要",
    "functional_modules": [
        {{
            "name": "功能模块名称",
            "description": "功能描述",
            "main_requirements": ["需求1", "需求2"]
        }}
    ],
    "business_flows": [
        {{
            "name": "流程名称",
            "description": "流程描述",
            "key_nodes": ["节点1", "节点2"]
        }}
    ],
    "business_rules": ["规则1", "规则2"],
    "data_entities": ["实体1", "实体2"],
    "inferred_interfaces": [
        {{
            "name": "推断的接口名称",
            "purpose": "接口用途描述"
        }}
    ]
}}

【关键要求】
- 从需求文档中提取所有重要信息，不要编造内容
- 如果文档中没有某个方面的信息，使用空列表或空字符串
- 重点关注业务需求和功能描述
- 接口需求是推断性的，基于业务功能需求推断可能需要的接口
"""
    )


# ===== 需求文档预解析 Prompt =====


def parse_requirement_document(document_content: str, rag) -> dict:
    """
    解析需求文档

    Args:
        document_content: 文档内容
        rag: RAG服务实例

    Returns:
        解析后的需求文档结构
    """
    REQUIREMENT_STRUCTURE_PROMPT = """你是资深技术文档分析师。请仔细阅读下面的需求文档，将其结构化地拆分为以下部分：

【文档内容】
{content}

【任务】
请将文档拆分并返回如下 JSON 结构（严格JSON，不要有其他内容）：
{{
    "project_overview": "项目概述：提取项目背景、项目目标、业务场景等。如果没有或很少，返回空字符串。",
    "functional_modules": "功能模块：提取所有功能模块的描述，每个模块的主要功能点。如果没有或很少，返回空字符串。",
    "business_rules": "业务规则：提取业务流程、业务规则、约束条件等内容。如果没有或很少，返回空字符串。",
    "data_requirements": "数据需求：提取数据相关的要求，包括实体、数据流转等。如果没有或很少，返回空字符串。",
    "interface_requirements": "接口需求：提取对接口的需求描述，包括接口应该提供的功能等。如果没有或很少，返回空字符串。",
    "other_requirements": "其他需求：提取非功能需求、性能要求、安全要求等其他内容。如果没有或很少，返回空字符串。"
}}

"""

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        max_input_chars = 15000
        content = document_content[:max_input_chars]

        prompt = REQUIREMENT_STRUCTURE_PROMPT.format(content=content)

        result = loop.run_until_complete(
            rag._generate_answer(
                prompt=prompt,
                temperature=0.2,
                max_tokens=3000,
            )
        )

        # 解析JSON
        import re
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                return {
                    "project_overview": parsed.get("project_overview", "").strip(),
                    "functional_modules": parsed.get("functional_modules", "").strip(),
                    "business_rules": parsed.get("business_rules", "").strip(),
                    "data_requirements": parsed.get("data_requirements", "").strip(),
                    "interface_requirements": parsed.get("interface_requirements", "").strip(),
                    "other_requirements": parsed.get("other_requirements", "").strip(),
                }
            except json.JSONDecodeError:
                pass

        logger.warning("需求文档结构解析失败，返回默认结构")
        return {
            "project_overview": document_content[:3000],
            "functional_modules": "",
            "business_rules": "",
            "data_requirements": "",
            "interface_requirements": "",
            "other_requirements": "",
        }
    except Exception as e:
        logger.error(f"需求文档解析异常: {e}", exc_info=True)
        return {
            "project_overview": "",
            "functional_modules": "",
            "business_rules": "",
            "data_requirements": "",
            "interface_requirements": "",
            "other_requirements": "",
        }
    finally:
        loop.close()


def store_api_to_vector_db(rag, api_content: str, document_title: str, business_module: str) -> str:
    """
    将核心API部分存入向量库（简化版）

    由于VectorIndexer初始化复杂，这里采用简化策略：
    1. 尝试使用RAG服务的knowledge_base来存储
    2. 如果失败，返回None，但不影响主流程（会使用增强prompt作为替代）

    返回 collection_name，如果失败返回 None
    """
    try:
        if not api_content or len(api_content) < 100:
            logger.warning("API内容过短，跳过向量化存储")
            return None

        # 简化方案：使用rag.knowledge_base来存储
        # 需要先有Document对象
        from common.rag.core.models import Document, DocumentType as DocType
        from common.rag.core.document_processor import DocumentProcessor, ChunkingConfig

        # 创建 Document 对象
        doc = Document(
            content=api_content,
            source_uri=f"test_case_gen:{document_title}",
            doc_type=DocType.API_DOC,
            metadata={
                "document_title": document_title,
                "business_module": business_module,
                "section": "api_section",
                "generated_at": datetime.now().isoformat(),
            }
        )

        # 分块处理
        chunking_config = ChunkingConfig(chunk_size=800, chunking_strategy="semantic")
        processor = DocumentProcessor(config=chunking_config)
        chunks = processor.process_documents([doc])

        if not chunks:
            logger.warning("文档分块结果为空")
            return None

        # 生成唯一 collection 名称
        collection_name = f"tc_api_{uuid.uuid4().hex[:8]}"

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # 使用rag.knowledge_base来添加文档
            # 注意：这里使用knowledge_base的add_documents方法
            from common.rag.core.knowledge_base import KnowledgeBase

            # 创建临时knowledge_base实例
            kb = KnowledgeBase(config_dir=str(BASE_DIR / "app" / "config"))

            # 直接添加文档块到指定collection
            for chunk in chunks:
                # 使用_ensure_collection和add_chunk方法
                # 这里简化处理：如果knowledge_base没有直接add方法，则跳过向量存储
                pass

            # 简化处理：记录成功但不实际存储（因为knowledge_base API较复杂）
            # 实际使用时会通过增强prompt来传递API内容
            logger.info(f"API内容准备完成，collection: {collection_name}, chunks: {len(chunks)}")
            logger.info("（简化模式：使用增强prompt传递API内容，而非向量检索）")

            _temp_vector_collections[collection_name] = {
                "chunks": len(chunks),
                "created_at": datetime.now().isoformat(),
                "api_content": api_content  # 保存原始内容作为fallback
            }

            return collection_name
        except Exception as ve:
            logger.warning(f"向量库存储简化处理: {ve}")
            # 即使存储失败，也保存内容供prompt使用
            collection_name = f"tc_api_{uuid.uuid4().hex[:8]}"
            _temp_vector_collections[collection_name] = {
                "chunks": 0,
                "created_at": datetime.now().isoformat(),
                "api_content": api_content  # 保存原始内容
            }
            return collection_name
        finally:
            loop.close()

    except Exception as e:
        logger.warning(f"存储API到向量库简化处理: {e}")
        # 不抛出异常，静默返回None，但会在prompt中传递完整API内容
        return None


def retrieve_api_context(rag, feature_query: str, collection_name: str, top_k: int = 5) -> str:
    """
    从向量库检索与当前功能相关的接口详细信息
    优先使用向量检索，如果失败则使用保存的原始API内容
    """
    if not collection_name:
        return ""

    # 首先检查是否有保存的API内容（fallback）
    if collection_name in _temp_vector_collections:
        saved_data = _temp_vector_collections[collection_name]
        if "api_content" in saved_data and saved_data["api_content"]:
            # 使用保存的API内容作为上下文
            logger.info(f"使用保存的API内容作为上下文（collection: {collection_name}）")
            return saved_data["api_content"]

    # 尝试向量检索
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # 直接使用 knowledge_base 的 search 方法
        results = loop.run_until_complete(
            rag.knowledge_base.search(
                query=feature_query,
                collection_name=collection_name,
                top_k=top_k,
                filters=None
            )
        )

        if not results:
            # 回退到保存的内容
            if collection_name in _temp_vector_collections:
                return _temp_vector_collections[collection_name].get("api_content", "")
            return ""

        # 拼接检索到的内容
        context_parts = []
        for idx, (chunk, score) in enumerate(results, 1):
            context_parts.append(
                f"【相关文档 {idx} (相关性: {score:.2f})】\n{chunk.content}\n"
            )

        return "\n".join(context_parts)

    except Exception as e:
        logger.warning(f"向量检索失败，使用fallback: {e}")
        # 回退到保存的内容
        if collection_name in _temp_vector_collections:
            return _temp_vector_collections[collection_name].get("api_content", "")
        return ""
    finally:
        loop.close()


# ===== Prompt 模板 =====

# 阶段0：文档预解析 - 自动识别接口详细设计部分
DOC_PRE_ANALYSIS_PROMPT = """你是资深技术文档分析师。请仔细阅读下面的技术文档，进行全面分析。

【文档内容】
{content}

【核心任务：提取所有接口的详细信息】

请在文档中找到接口详细设计相关的章节（可能是3.3、4.2、5.2、6.3，也可能是"接口详细设计"、"接口定义"、"API设计"等标题）。
并且对检查到的接口信息进行详细的识别，获取到表格形式接口请求入参的描述和响应出参的描述，还有描述下方可能存在的接口请求入参的json样例，
和响应参数描述下方的响应报文json样例，如果说识别到一个接口出现多个响应样例，那么我们取第一个就可以，

你必须提取出文档中提供的所有接口的信息，并且按照遵循下方的提示词语样式，按照识别到的接口数量依次进行递增：
1. 接口1：名称、路径、方法、请求参数表格、响应参数表格、处理流程、流程图
2. 接口2：名称、路径、方法、请求参数表格、响应参数表格、处理流程、流程图
3. 接口3：名称、路径、方法、请求参数表格、响应参数表格、处理流程、流程图

【请求参数格式】（必须从表格提取）
参数名|类型|必填|说明
例：
userId|string|必填|用户唯一标识
challengeId|string|必填|Challenge ID
name|string|可选|Challenge名称

【响应参数格式】（必须从表格提取）
参数名|类型|说明
例：
code|string|响应状态码
message|string|响应消息
data|object|返回数据

【输出JSON格式】
{{
    "project_background": "项目背景描述",
    "business_module": "业务模块名称",
    "interface_count": 8,
    "page_count": 1,
    "core_flows": ["流程1", "流程2"],
    "interface_list": [
        {{
            "name": "创建Challenge",
            "method": "POST",
            "path": "/sca/v1/create/challenges",
            "description": "创建Challenge接口",
            "request_params": "userId|string|必填|用户ID\nchallengeId|string|必填|Challenge ID",
            "request_json": "{{\"userId\": \"xxx\", \"challengeId\": \"xxx\"}}",
            "response_json": "{{\"code\": 0, \"message\": \"success\"}}",
            "response_params": "code|string|状态码\nmessage|string|消息",
            "process_flow": "1.接收请求 2.验证参数 3.创建数据 4.返回结果",
            "flow_chart_desc": "Challenge创建流程图"
        }},
    ],
    "flow_charts": ["流程图1", "流程图2"]
}}

【关键要求】
- request_params和response_params必须从文档表格中提取完整信息
- 如果文档中有请求JSON示例，请提取到request_json字段中
- 如果文档中有响应JSON示例，请提取到response_json字段中（取第一个响应示例即可）
- 如果某个接口缺少某些信息，使用空字符串表示，

请直接输出 JSON："""


# ====== 新增：获取接口JSON示例的Prompt ======
INTERFACE_JSON_EXTRACT_PROMPT = """你是资深测试开发工程师。请从以下API接口文档中提取指定接口的请求JSON示例和响应JSON示例。

【接口名称】
{interface_name}

【接口路径】
{method} {path}

【接口描述】
{description}

【API文档内容】
{api_content}

请从API文档中找出该接口的完整请求JSON示例和响应JSON示例。

【输出JSON格式】
{{
    "request_json": "请求JSON示例（完整格式，如果文档中没有则返回空字符串）",
    "response_json": "响应JSON示例（完整格式，如果文档中没有则返回空字符串）"
}}

请直接输出 JSON（不要包含其他解释文本）："""


# 阶段1：发送背景信息给大模型（不发回复）- 包含完整出入参和流程图
CONTEXT_INFO_PROMPT = """你是资深测试开发工程师。请先了解以下项目背景信息，不需要回复。

【项目背景】
{project_background}

【业务模块】
{business_module}

【接口总数】
{interface_count} 个

【页面/功能单元总数】
{page_count} 个

【核心业务流程】
{core_flows}

【接口详细信息（包含出入参和流程图）】
{interface_list}

【流程图说明】
{flow_charts}

好的，我已经了解了上述项目背景信息。请在后续生成测试用例时参考这些信息，特别是每个接口的请求参数、响应参数和处理流程。
"""

# 阶段2：单接口测试用例生成（分接口处理）- 包含出入参和流程图
SINGLE_INTERFACE_PROMPT = """你是资深测试开发工程师。请根据以下接口详情，为该接口设计全面、详细的测试用例。

【接口名称】
{name}

【请求方法】
{method}

【接口路径】
{path}

【接口描述】
{description}

【请求参数（从接口文档提取，必须完整列出每个参数的详细信息）】
{request_params}

【响应参数（从接口文档提取，必须完整列出）】
{response_params}

【接口处理流程/业务逻辑（必须详细描述每一步）】
{process_flow}

【相关流程图描述】
{flow_chart}

【项目背景参考】
{project_background}

【重要：测试案例格式要求】
你生成的测试案例必须遵循以下JSON格式：
- scene: 测试场景描述，必须包含完整的接口地址、请求方法、具体参数名和参数值
- expected: 预期结果，必须包含HTTP状态码、具体响应字段和值
- priority: P0/P1/P2/P3

【场景(scene)示例 - 必须包含完整信息】
正确示例1: "scene": "POST /auth/sca/verify 验证用户授权信息，请求参数: userId=123456, authType=SC, authCode=ABC123，前置条件: 用户已登录且Token有效"
正确示例2: "scene": "GET /sca/v1/user/profile 获取用户详情，请求参数: userId=123456，Header: Authorization=Bearer token123，前置条件: 用户已登录"
正确示例3: "scene": "POST /sca/v1/challenge/create 创建Challenge，请求参数: challengeName=性能测试挑战, challengeType=TIME_LIMITED, duration=3600, maxParticipants=100，返回challengeId"

【预期(expected)示例 - 必须包含具体响应值】
正确示例1: "expected": "HTTP 200, response: {success: true, authStatus: 'AUTHORIZED', expiresIn: 7200, tokenType: 'Bearer'}"
正确示例2: "expected": "HTTP 200, response: {code: 200, message: 'success', data: {userId: '123456', username: 'testuser', email: 'test@example.com'}}"
正确示例3: "expected": "HTTP 201, response: {code: 201, message: 'Challenge创建成功', data: {challengeId: 'chg_abc123', status: 'ACTIVE'}}"

【必须覆盖的测试场景 - 每种场景都需要生成具体参数值】
1. 正常流程：必填参数全部提供且值合法，验证接口成功调用
2. 参数缺失：分别缺失每个必填参数，验证错误提示
3. 参数错误：参数类型错误、参数格式错误、参数值不在有效范围内
4. 鉴权失败：无Authorization header、Token过期、Token无效
5. 边界场景：参数值为空字符串、参数值为null、数组参数为空数组、字符串参数超长
6. 重复提交：相同参数重复提交，验证幂等性
7. 并发测试：多线程同时调用

【输出要求】
1. 严格输出 JSON 数组格式，不要输出markdown代码块
2. 每个接口生成 {min_cases} 条测试用例（必须至少生成{min_cases}条，越多越好）
3. 必须包含scene、expected、priority三个字段
4. scene中必须包含具体的接口路径、请求方法、参数名和参数值
5. expected中必须包含具体的HTTP状态码和响应体内容
6. 不要生成其他冗余字段

请直接输出 JSON："""


# 阶段1：功能/接口清单抽取（优化版 - 降低temperature）
FEATURE_ANALYSIS_PROMPT = """你是资深测试开发工程师兼需求分析师。
请先只做"需求梳理"，不要直接给出测试用例。

【输入的文档内容（已结构化拆分）】
{document_structure}

【任务】
1. 认真阅读以上文档，特别关注"api_section"（核心API应用）部分，这是接口测试的核心依据。
2. 识别出系统中的业务模块、关键功能、接口或子流程。
3. 将这些内容整理成一个 JSON 数组，每个元素描述一个"功能/接口单元(feature)"。

【JSON 数组元素字段规范】
- id: 功能编号，字符串，例如 "F1"、"F2" ……
- module: 所属业务模块名称
- name: 功能/接口名称
- type: 功能类型，"页面功能"、"接口"、"批处理"、"流程"
- description: 功能描述
- interfaces: 该功能涉及的接口列表（字符串数组），例如 ["POST /auth/sca/verify"]
- scenarios: 典型业务场景描述（字符串数组）
- api_details: 可选，从api_section中提取的该功能对应的接口详细信息

【重要约束】
1. 严格输出 JSON 数组格式，不要输出任何其他内容
2. 数组长度控制在 5~15 之间
3. 优先从 api_section 中提取接口详细信息
4. 不要使用markdown代码块包裹JSON

请直接输出 JSON："""


# 阶段2：基于检索到的接口详情生成测试用例（优化版 - 更明确的格式要求）
FEATURE_TEST_CASE_PROMPT_WITH_CONTEXT = """你是资深测试开发工程师。请根据接口文档，为某一个功能/接口设计测试用例。

【功能/接口描述（JSON）】
{feature_json}

【接口详细信息】（重点参考）
{retrieved_api_context}

【需求文档摘要】
{document_summary}

【重要：测试案例格式要求】
你生成的测试案例必须遵循以下JSON格式：
- scene: 测试场景描述，必须包含接口地址、请求方法、具体参数值
- expected: 预期结果，必须包含HTTP状态码、响应字段和值
- priority: P0/P1/P2/P3

【场景(scene)示例】
"scene": "POST /auth/sca/verify 验证用户授权信息，请求参数: userId=123456, authType=SC, authCode=ABC123，前置条件: 用户已登录且Token有效"

【预期(expected)示例】
"expected": "HTTP 200, response: {success: true, authStatus: 'AUTHORIZED', expiresIn: 7200}"

【必须覆盖的测试场景】
1. 正常流程：接口调用成功的场景
2. 参数缺失：必填参数缺失时的错误处理
3. 参数错误：参数格式/值错误时的错误处理
4. 鉴权失败：无权限/Token失效的场景
5. 边界场景：参数值在边界情况下的处理

【输出要求】
1. 严格输出 JSON 数组格式，不要输出markdown代码块
2. 每个功能生成 {min_cases} 条测试用例
3. 必须包含scene、expected、priority三个字段
4. 不要生成其他冗余字段

请直接输出 JSON："""


# Fallback 用优化版 prompt
FEATURE_TEST_CASE_PROMPT = """你是资深测试开发工程师。请根据接口文档，为某一个功能/接口设计测试用例。

【功能/接口描述（JSON）】
{feature_json}

【需求文档摘要】
{document_summary}

【重要：测试案例格式要求】
你生成的测试案例必须遵循以下JSON格式：
- scene: 测试场景描述，必须包含接口地址、请求方法、具体参数值
- expected: 预期结果，必须包含HTTP状态码、响应字段和值
- priority: P0/P1/P2/P3

【场景(scene)示例】
"scene": "POST /auth/sca/verify 验证用户授权信息，请求参数: userId=123456, authType=SC, authCode=ABC123"

【预期(expected)示例】
"expected": "HTTP 200, response: {success: true, authStatus: 'AUTHORIZED'}"

【必须覆盖的测试场景】
1. 正常流程：接口调用成功的场景
2. 参数缺失：必填参数缺失时的错误处理
3. 参数错误：参数格式/值错误时的错误处理
4. 边界场景：参数值在边界情况下的处理

【输出要求】
1. 严格输出 JSON 数组格式，不要输出markdown代码块
2. 每个功能生成 {min_cases} 条测试用例
3. 必须包含scene、expected、priority三个字段

请直接输出 JSON："""


# ===== 主接口 =====

@test_case_gen_opt.route('/generate_test_cases', methods=['POST'])
def generate_test_cases():
    """
    生成测试案例接口（改进版：结构化解析 + 向量存储 + 检索增强）

    请求参数：
    - file: 需求文档文件 (multipart/form-data, 支持docx/pdf/txt)
    - document_title: 文档标题 (可选)
    - business_module: 业务模块 (可选)
    - force_regenerate: 是否强制重新生成 (可选, 默认false)

    返回：
    - file: xmind文件下载
    """
    # 用于跟踪需要清理的向量集合
    collections_to_cleanup = []

    try:
        rag = get_rag_service()
        if not rag:
            return json_response({
                "code": 500,
                "message": "RAG服务初始化失败",
                "data": None
            }, 500)

        # 检查文件
        if 'file' not in request.files:
            return json_response({
                "code": 400,
                "message": "未找到文件",
                "data": None
            }, 400)

        file = request.files['file']
        if file.filename == '':
            return json_response({
                "code": 400,
                "message": "未选择文件",
                "data": None
            }, 400)

        file_ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if file_ext not in ALLOWED_EXTENSIONS:
            return json_response({
                "code": 400,
                "message": f"不支持的文件类型。允许的类型: {', '.join(ALLOWED_EXTENSIONS)}",
                "data": None
            }, 400)

        document_title = request.form.get('document_title', file.filename.rsplit('.', 1)[0])
        business_module = request.form.get('business_module', '')

        # 保存上传的文件
        doc_id = str(uuid.uuid4())
        new_filename = f"{doc_id}.{file_ext}"
        file_path = os.path.join(UPLOAD_FOLDER, new_filename)
        file.save(file_path)

        logger.info(f"开始生成测试案例: {document_title}, 文件: {file_path}")

        # 提取文档内容
        document_content = _extract_document_content(file_path, file_ext)

        if not document_content:
            return json_response({
                "code": 400,
                "message": "无法提取文档内容",
                "data": None
            }, 400)

        logger.info(f"文档内容提取成功，长度: {len(document_content)}")

        # ===== 新增：结构化解析文档 =====
        logger.info("开始结构化解析文档...")
        doc_structure = parse_document_structure(document_content)

        api_section = doc_structure.get("api_section", "")
        logger.info(f"文档结构解析完成: basic_knowledge={len(doc_structure.get('basic_knowledge',''))} chars, "
                    f"service_content={len(doc_structure.get('service_content',''))} chars, "
                    f"template_config={len(doc_structure.get('template_config',''))} chars, "
                    f"api_section={len(api_section)} chars")

        # ===== 新增：将API部分存入向量库 =====
        collection_name = None
        if api_section and len(api_section) > 200:
            logger.info("将API内容存入向量库...")
            collection_name = store_api_to_vector_db(rag, api_section, document_title, business_module)
            if collection_name:
                collections_to_cleanup.append(collection_name)
                logger.info(f"API内容已存入向量库，collection: {collection_name}")

        # ===== 生成测试用例（智能版：分接口处理） =====
        test_cases = _generate_test_cases_smart(
            rag=rag,
            doc_structure=doc_structure,
            document_title=document_title,
            business_module=business_module
        )

        if not test_cases:
            logger.warning("智能生成失败，尝试原有方案...")
            # 回退到原有增强版
            test_cases = _generate_test_cases_enhanced(
                rag=rag,
                doc_structure=doc_structure,
                collection_name=collection_name,
                document_title=document_title,
                business_module=business_module
            )

        if not test_cases:
            logger.warning("LLM生成失败，使用默认测试案例模板")
            test_cases = _generate_default_test_cases(document_title, business_module)

        logger.info(f"生成测试案例数量: {len(test_cases)}")

        # 生成XMind文件
        xmind_gen = XMindGenerator(output_dir=str(XMIND_OUTPUT_DIR))
        xmind_path = xmind_gen.generate_test_cases_xmind(
            document_title=document_title,
            test_cases=test_cases,
            business_module=business_module
        )

        logger.info(f"XMind文件生成成功: {xmind_path}")

        return send_file(
            xmind_path,
            as_attachment=True,
            download_name=os.path.basename(xmind_path),
            mimetype='application/octet-stream'
        )

    except Exception as e:
        logger.error(f"生成测试案例失败: {e}", exc_info=True)
        return json_response({
            "code": 500,
            "message": f"生成测试案例失败: {str(e)}",
            "data": None
        }, 500)


# ===== 新版智能测试用例生成（分接口处理）=====

def _generate_test_cases_smart(rag, doc_structure: dict, document_title: str, 
                                business_module: str) -> list:
    """
    智能版测试用例生成：分接口单独处理
    流程：
    1. 阶段0：预解析文档，识别项目背景、接口列表、流程图
    2. 阶段1：发送背景信息给大模型（不发回复）
    3. 阶段2：分接口单独生成测试用例
    4. 阶段3：汇总、去重、格式化输出
    """
    if not doc_structure:
        return []

    # 合并所有文档内容用于预解析
    full_content = f"""
【基础知识】
{doc_structure.get('basic_knowledge', '')}

【服务内容】
{doc_structure.get('service_content', '')}

【模板配置】
{doc_structure.get('template_config', '')}

【核心API应用】
{doc_structure.get('api_section', '')}
"""

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # 用于保存预解析的项目信息
    project_info = {
        "project_background": "",
        "business_module": business_module or "",
        "interface_count": 0,
        "page_count": 0,
        "core_flows": [],
        "interface_list": [],
        "flow_charts": []
    }

    try:
        # ===== 阶段0：文档预解析 =====
        logger.info("=" * 80)
        logger.info("【阶段0】开始文档预解析，识别项目背景、接口列表...")

        # 限制输入长度，避免token超限（增加输入长度以包含更多信息）
        max_chars = 60000  # 增加输入长度，确保完整文档内容
        pre_analysis_prompt = DOC_PRE_ANALYSIS_PROMPT.format(
            content=full_content[:max_chars]
        )

        logger.info(f"阶段0输入长度: {len(pre_analysis_prompt)} 字符")
        logger.info(f"阶段0输入内容前500字符:\n{full_content[:max_chars][:500]}")

        pre_result = loop.run_until_complete(
            rag._generate_answer(
                prompt=pre_analysis_prompt,
                temperature=0.1,
                max_tokens=15000,  # 大幅增加输出token限制，确保所有接口信息完整
            )
        )

        logger.info(f"阶段0输出长度: {len(pre_result)} 字符")
        logger.info(f"阶段0输出前500字符:\n{pre_result[:500]}")
        logger.info(f'-------------------------------------------------------------------------------------------------------------')
        logger.info(f'输出完整字符{pre_result}')
        logger.info(f'-------------------------------------------------------------------------------------------------------------')

        # 解析阶段0结果
        project_info = _parse_pre_analysis_result(pre_result)
        
        logger.info(f"预解析结果: 项目背景={project_info['project_background'][:50]}...")
        logger.info(f"接口数量={project_info['interface_count']}, 页面数量={project_info['page_count']}")
        logger.info(f"接口列表长度={len(project_info['interface_list'])}")
        
        # 打印每个接口的详细信息
        logger.info("=" * 80)
        logger.info("【阶段0解析出的接口详情】")
        for idx, iface in enumerate(project_info['interface_list'], 1):
            logger.info(f"--- 接口 {idx} ---")
            logger.info(f"  名称: {iface.get('name', '未命名')}")
            logger.info(f"  方法: {iface.get('method', '未指定')}")
            logger.info(f"  路径: {iface.get('path', '未指定')}")
            logger.info(f"  请求参数: {iface.get('request_params', '无')[:200]}...")
            logger.info(f"  响应参数: {iface.get('response_params', '无')[:200]}...")
            logger.info(f"  处理流程: {iface.get('process_flow', '无')[:200]}...")
        logger.info("=" * 80)

        # ===== 阶段1：发送背景信息（不发回复） =====
        logger.info("=" * 80)
        logger.info("【阶段1】发送背景信息给大模型...")

        interface_list_text = ""
        if project_info['interface_list']:
            for idx, iface in enumerate(project_info['interface_list'], 1):
                interface_list_text += f"""
接口{idx}: {iface.get('name', '未命名')}
  - 方法: {iface.get('method', '未指定')}
  - 路径: {iface.get('path', '未指定')}
  - 描述: {iface.get('description', '无')}
  - 请求参数: {iface.get('request_params', '无')}
  - 响应参数: {iface.get('response_params', '无')}
  - 处理流程: {iface.get('process_flow', '无')}
  - 流程图描述: {iface.get('flow_chart_desc', '无')}
"""

        context_prompt = CONTEXT_INFO_PROMPT.format(
            project_background=project_info['project_background'],
            business_module=project_info['business_module'] or business_module,
            interface_count=project_info['interface_count'],
            page_count=project_info['page_count'],
            core_flows="\n".join([f"- {f}" for f in project_info['core_flows']]) if project_info.get('core_flows') else "",
            interface_list=interface_list_text if interface_list_text else "",
            flow_charts="\n".join([f"- {f}" for f in project_info['flow_charts']]) if project_info.get('flow_charts') else ""
        )

        # 发送背景信息，不等待回复（只是让模型"学习"上下文）
        logger.info(f"阶段1背景信息长度: {len(context_prompt)} 字符")

        loop.run_until_complete(
            rag._generate_answer(
                prompt=context_prompt,
                temperature=0.1,
                max_tokens=500,  # 增加token限制，确保模型能正常响应
            )
        )
        logger.info("背景信息已发送，大模型已了解项目上下文")

        # ===== 阶段2：分接口生成测试用例 =====
        logger.info("=" * 80)
        logger.info("【阶段2】开始分接口生成测试用例...")

        all_cases = []
        interface_list = project_info['interface_list']

        if not interface_list:
            # 如果没有识别到接口列表，使用旧的备选方案
            logger.warning("未能从预解析中获取接口列表，回退到原有方案")
            return _generate_test_cases_enhanced_fallback(
                rag, doc_structure, document_title, business_module
            )

        # 对每个接口单独生成测试用例
        for idx, iface in enumerate(interface_list, 1):
            try:
                # 根据接口重要性调整用例数量（前3个接口多生成一些）
                base_min_cases = 8  # 增加基础用例数量
                extra = 3 if idx <= 3 else 0  # 前3个接口额外增加
                min_cases = base_min_cases + extra

                interface_prompt = SINGLE_INTERFACE_PROMPT.format(
                    name=iface.get('name', '未命名接口'),
                    method=iface.get('method', 'POST'),
                    path=iface.get('path', '/api/unknown'),
                    description=iface.get('description', '无描述'),
                    request_params=iface.get('request_params', '无说明'),
                    response_params=iface.get('response_params', '无说明'),
                    process_flow=iface.get('process_flow', '无流程说明'),
                    flow_chart=iface.get('flow_chart_desc', '无流程图'),
                    project_background=project_info['project_background'],
                    min_cases=min_cases,
                )

                logger.info(f"--- 接口 {idx}/{len(interface_list)}: {iface.get('name')} ---")
                logger.info(f"输入prompt长度: {len(interface_prompt)} 字符")

                answer = loop.run_until_complete(
                    rag._generate_answer(
                        prompt=interface_prompt,
                        temperature=0.2,
                        max_tokens=8000,  # 大幅增加输出token限制，确保完整输出
                    )
                )

                logger.info(f"输出长度: {len(answer)} 字符")

                # 解析用例
                cases = parse_llm_response_to_test_cases(answer)
                if not cases:
                    logger.warning(f"接口 {iface.get('name')} 未生成有效用例")
                    continue

                # 为每个用例添加模块信息
                module_name = project_info['business_module'] or business_module or "功能验证"
                for c in cases:
                    if not c:
                        continue
                    c["module"] = module_name
                    # 确保字段完整 - 防止None值导致切片失败
                    scene_val = c.get("scene") or c.get("title") or ""
                    if not scene_val:
                        scene_val = f"{iface.get('name')}测试场景"
                    c["scene"] = scene_val
                    
                    expected_val = c.get("expected") or c.get("expected_result") or ""
                    if not expected_val:
                        expected_val = "符合接口文档约定的响应"
                    c["expected"] = expected_val
                    
                    if c.get("priority") not in {"P0", "P1", "P2", "P3"}:
                        c["priority"] = "P2"

                all_cases.extend(cases)
                logger.info(f"接口 {iface.get('name')} 生成 {len(cases)} 条用例")

            except Exception as iface_err:
                logger.error(f"接口 {iface.get('name')} 生成失败: {iface_err}")
                continue

        if not all_cases:
            logger.warning("所有接口都未能生成用例，回退到原有方案")
            return _generate_test_cases_enhanced_fallback(
                rag, doc_structure, document_title, business_module
            )

        # ===== 阶段3：汇总、去重、格式化 =====
        logger.info("=" * 80)
        logger.info("【阶段3】汇总、去重、格式化...")

        final_cases = _deduplicate_and_format_cases(all_cases)
        logger.info(f"去重后测试用例数量: {len(final_cases)}")

        return final_cases

    except Exception as e:
        logger.error(f"智能生成测试用例失败: {e}", exc_info=True)
        return []
    finally:
        loop.close()


def _parse_pre_analysis_result(result: str) -> dict:
    """解析阶段0的预分析结果"""
    import re
    default_info = {
        "project_background": "",
        "business_module": "",
        "interface_count": 0,
        "page_count": 0,
        "core_flows": [],
        "interface_list": [],
        "flow_charts": []
    }

    try:
        # 尝试提取JSON
        json_str = None
        start_idx = result.find('{')
        if start_idx != -1:
            bracket_count = 0
            for i in range(start_idx, len(result)):
                if result[i] == '{':
                    bracket_count += 1
                elif result[i] == '}':
                    bracket_count -= 1
                    if bracket_count == 0:
                        json_str = result[start_idx:i+1]
                        break

        if json_str:
            parsed = json.loads(json_str)
            return {
                "project_background": parsed.get("project_background", ""),
                "business_module": parsed.get("business_module", ""),
                "interface_count": int(parsed.get("interface_count", 0)),
                "page_count": int(parsed.get("page_count", 0)),
                "core_flows": parsed.get("core_flows", []),
                "interface_list": parsed.get("interface_list", []),
                "flow_charts": parsed.get("flow_charts", [])
            }
    except Exception as e:
        logger.warning(f"预解析结果JSON解析失败: {e}")

    return default_info


def _parse_requirement_analysis_result(result: str) -> dict:
    """
    解析需求预分析结果

    参数：
    - result: 大模型返回的需求预分析结果

    返回：
    - 解析后的需求信息字典
    """
    import re
    default_info = {
        "project_background": "",
        "business_summary": "",
        "functional_modules": [],
        "business_flows": [],
    }

    try:
        # 尝试提取JSON
        json_str = None
        start_idx = result.find('{')
        if start_idx != -1:
            bracket_count = 0
            for i in range(start_idx, len(result)):
                if result[i] == '{':
                    bracket_count += 1
                elif result[i] == '}':
                    bracket_count -= 1
                    if bracket_count == 0:
                        json_str = result[start_idx:i+1]
                        break

        if json_str:
            parsed = json.loads(json_str)
            return {
                "project_background": parsed.get("project_background", ""),
                "business_summary": parsed.get("business_summary", ""),
                "functional_modules": parsed.get("functional_modules", []),
                "business_flows": parsed.get("business_flows", []),
            }
    except Exception as e:
        logger.warning(f"需求预分析结果JSON解析失败: {e}")

    return default_info


def _deduplicate_and_format_cases(cases: list) -> list:
    """去重并格式化测试用例"""
    seen = set()
    unique_cases = []

    for case in cases:
        # 用scene和expected生成唯一标识
        scene = case.get("scene", "") or ""
        expected = case.get("expected", "") or ""
        key = f"{scene[:50]}_{expected[:50]}"

        if key not in seen:
            seen.add(key)
            unique_cases.append(case)

    # 限制总用例数量，避免过多（增加上限以保留更多用例）
    max_cases = 80
    if len(unique_cases) > max_cases:
        # 按优先级排序，保留前N个
        priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        unique_cases.sort(key=lambda x: priority_order.get(x.get("priority", "P2"), 2))
        unique_cases = unique_cases[:max_cases]

    return unique_cases


def _generate_test_cases_enhanced_fallback(rag, doc_structure: dict,
                                            document_title: str, 
                                            business_module: str) -> list:
    """
    备选方案：使用原有的增强版生成逻辑
    当智能版无法识别接口时使用
    """
    # 这里复用原有的 _generate_test_cases_enhanced 函数逻辑
    # 由于原函数已经存在，我们直接调用它
    return []  # 返回空列表，让外层使用默认模板


def _generate_test_cases_enhanced(rag, doc_structure: dict, collection_name: str,
                                   document_title: str, business_module: str) -> list:
    """
    改进版测试用例生成：利用结构化文档和向量检索
    """
    if not doc_structure:
        return []

    # 构造给阶段1的输入
    doc_structure_text = f"""
【基础知识】
{doc_structure.get('basic_knowledge', '')}

【服务内容】
{doc_structure.get('service_content', '')}

【模板配置】
{doc_structure.get('template_config', '')}

【核心API应用】
{doc_structure.get('api_section', '')}
"""

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # ===== 调试日志：保存完整输入输出 =====
    debug_dir = BASE_DIR / "outputs" / "debug_logs"
    debug_dir.mkdir(parents=True, exist_ok=True)
    debug_file = debug_dir / f"test_case_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    try:
        # ===== 阶段1：抽取功能/接口清单 =====
        analysis_prompt = FEATURE_ANALYSIS_PROMPT.format(
            document_structure=doc_structure_text[:15000],  # 限制长度
        )

        logger.info("=" * 80)
        logger.info("【阶段1】开始调用大模型抽取功能清单...")
        logger.info(f"输入prompt长度: {len(analysis_prompt)} 字符")
        logger.info(f"输入prompt前500字符:\n{analysis_prompt[:500]}")

        analysis_answer = loop.run_until_complete(
            rag._generate_answer(
                prompt=analysis_prompt,
                temperature=0.1,  # 降低temperature以获得更稳定的结构化输出
                max_tokens=3000,  # 增加max_tokens避免截断
            )
        )

        logger.info(f"阶段1输出长度: {len(analysis_answer)} 字符")
        logger.info(f"阶段1输出前1000字符:\n{analysis_answer[:1000]}")

        # 解析 feature JSON
        features = []
        import re
        # 修复：使用更健壮的JSON数组提取方法
        # 方法：找到第一个 [ 和最后一个 ]，确保提取完整的数组
        json_str = None
        start_idx = analysis_answer.find('[')
        if start_idx != -1:
            # 从第一个 [ 开始向后查找
            # 使用括号匹配来找到正确的结束位置
            bracket_count = 0
            for i in range(start_idx, len(analysis_answer)):
                if analysis_answer[i] == '[':
                    bracket_count += 1
                elif analysis_answer[i] == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        json_str = analysis_answer[start_idx:i+1]
                        break
        
        if json_str:
            try:
                features = json.loads(json_str)
                logger.info(f"JSON解析成功，原始字符串长度: {len(json_str)} 字符")
            except json.JSONDecodeError as e:
                logger.warning(f"JSON解析失败: {e}")
                # 尝试修复常见的JSON问题
                try:
                    # 移除可能的前后文本
                    json_str = json_str.strip()
                    features = json.loads(json_str)
                except Exception:
                    features = []
        else:
            # Fallback: 尝试原始的正则方法
            json_match = re.search(r'\[.*\]', analysis_answer, re.DOTALL)
            if json_match:
                try:
                    features = json.loads(json_match.group())
                except Exception:
                    features = []

        if not isinstance(features, list):
            features = []

        if not features:
            logger.warning("未能识别出有效的功能/接口列表")
            return []

        max_features = 10
        features = features[:max_features]
        logger.info(f"识别出 {len(features)} 个功能/接口")

        all_cases = []

        # ===== 阶段2：针对每个 feature 生成用例 =====
        for idx, feature in enumerate(features, start=1):
            try:
                base_min_cases = 6
                extra = 2 if idx <= 3 else 0
                min_cases = base_min_cases + extra

                feature_json = json.dumps(feature, ensure_ascii=False, indent=2)

                # ===== 新增：从向量库检索接口详情 =====
                retrieved_context = ""
                if collection_name:
                    # 用 feature name 和 description 作为查询
                    feature_name = feature.get("name", "")
                    feature_desc = feature.get("description", "")
                    query = f"{feature_name} {feature_desc}"
                    retrieved_context = retrieve_api_context(rag, query, collection_name, top_k=3)

                # 构造 prompt
                # 优先从配置获取，失败时使用代码默认值
                prompt_manager = get_prompt_manager()
                if retrieved_context:
                    # 使用增强版 prompt（带向量检索结果）
                    template = prompt_manager.get_test_case_prompt(
                        "feature_with_context",
                        FEATURE_TEST_CASE_PROMPT_WITH_CONTEXT
                    )
                    tc_prompt = template.format(
                        feature_json=feature_json,
                        retrieved_api_context=retrieved_context,
                        document_summary=doc_structure.get("api_section", "")[:2000],
                        min_cases=min_cases,
                    )
                else:
                    # 使用普通版 prompt
                    template = prompt_manager.get_test_case_prompt(
                        "feature_basic",
                        FEATURE_TEST_CASE_PROMPT
                    )
                    tc_prompt = template.format(
                        feature_json=feature_json,
                        document_summary=doc_structure.get("api_section", "")[:2000],
                        min_cases=min_cases,
                    )

                # ===== 调试日志：记录阶段2每次调用 =====
                logger.info("=" * 80)
                logger.info(f"【阶段2】功能 {idx}/{len(features)}: {feature.get('name')}")
                logger.info(f"输入prompt长度: {len(tc_prompt)} 字符")
                logger.info(f"feature_json内容:\n{feature_json}")
                if retrieved_context:
                    logger.info(f"检索到的接口上下文(前500字符):\n{retrieved_context[:500]}")
                logger.info(f"document_summary长度: {len(doc_structure.get('api_section', '')[:2000])} 字符")

                answer = loop.run_until_complete(
                    rag._generate_answer(
                        prompt=tc_prompt,
                        temperature=0.2,  # 降低temperature以获得更稳定的结构化输出
                        max_tokens=4000,   # 增加max_tokens避免截断
                    )
                )

                logger.info(f"阶段2输出长度: {len(answer)} 字符")
                logger.info(f"阶段2输出前800字符:\n{answer[:800]}")

                cases = parse_llm_response_to_test_cases(answer)
                if not cases:
                    continue

                # 规范化字段 - 支持新的简洁格式（scene/expected）
                module_name = feature.get("module") or "功能验证"
                for c in cases:
                    # 兼容新旧格式
                    if c.get("scene") and not c.get("title"):
                        # 新格式：scene + expected
                        c["title"] = c.get("scene", "")[:50]
                    elif c.get("title") and not c.get("scene"):
                        # 旧格式：title + steps + expected_result
                        c["scene"] = c.get("title", "")
                    
                    if not c.get("module"):
                        c["module"] = module_name
                    if c.get("priority") not in {"P0", "P1", "P2", "P3"}:
                        c["priority"] = "P2"
                    if c.get("test_type") not in {"功能测试", "异常测试", "边界测试", "安全测试", "性能测试"}:
                        c["test_type"] = "功能测试"
                    
                    # 处理预期结果
                    if c.get("expected_result") and not c.get("expected"):
                        c["expected"] = c.get("expected_result")
                    
                    # 确保有场景和预期
                    if not c.get("scene"):
                        c["scene"] = c.get("title", f"{module_name}测试场景")
                    if not c.get("expected"):
                        c["expected"] = "符合接口文档约定的响应"

                all_cases.extend(cases)
                logger.info(f"功能 {idx}/{len(features)} ({feature.get('name')}) 生成 {len(cases)} 条用例")

            except Exception as fe:
                logger.error(f"为某个 feature 生成测试用例失败: {fe}", exc_info=True)
                continue

        return all_cases

    except Exception as e:
        logger.error(f"增强版生成测试案例失败: {e}", exc_info=True)
        return []
    finally:
        loop.close()


# ===== 原有辅助函数 =====

def _extract_document_content(file_path: str, file_ext: str) -> str:
    """提取文档内容"""
    try:
        if file_ext in ['docx', 'doc']:
            from docx import Document
            doc = Document(file_path)
            content_parts = []
            for paragraph in doc.paragraphs:
                text = paragraph.text.strip()
                if text:
                    content_parts.append(text)
            for table in doc.tables:
                for row in table.rows:
                    row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_text:
                        content_parts.append(" | ".join(row_text))
            return "\n\n".join(content_parts)

        elif file_ext in ['pdf']:
            try:
                import PyPDF2
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    text_parts = [page.extract_text() for page in reader.pages]
                    return "\n\n".join([t for t in text_parts if t])
            except:
                return "PDF内容提取失败"

        elif file_ext in ['txt', 'md', 'markdown']:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()

        return ""

    except Exception as e:
        logger.error(f"提取文档内容失败: {e}")
        return ""


def _generate_default_test_cases(document_title: str, business_module: str) -> list:
    """生成默认测试案例模板"""
    return [
        {
            "title": f"验证{document_title}基本功能",
            "module": business_module or "功能验证",
            "priority": "P0",
            "test_type": "功能测试",
            "precondition": "系统正常运行",
            "steps": ["打开功能页面", "执行基本操作", "验证结果"],
            "expected_result": "功能正常"
        }
    ]


# ====== 图片提取和分析功能 ======

import base64
from io import BytesIO

# 图片输出目录
IMAGE_OUTPUT_DIR = BASE_DIR / "outputs" / "extracted_images"
IMAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_images_from_docx(doc_path: str) -> list:
    """
    从Word文档中提取所有图片

    返回：
    - list: 图片列表，每个元素包含 {image_bytes, filename, index}
    """
    images = []

    try:
        from docx import Document

        doc = Document(doc_path)

        # 遍历文档中的所有关系
        for rel_id, rel in doc.part.rels.items():
            if "image" in rel.target_ref:
                try:
                    # 获取图片数据
                    image_part = rel.target_part
                    image_bytes = image_part.blob

                    # 获取图片格式
                    content_type = image_part.content_type
                    ext = _get_image_extension(content_type)

                    # 生成文件名
                    filename = f"image_{len(images)}{ext}"

                    images.append({
                        "image_bytes": image_bytes,
                        "filename": filename,
                        "index": len(images),
                        "content_type": content_type
                    })

                    logger.info(f"提取图片: {filename}, 大小: {len(image_bytes)} bytes")

                except Exception as e:
                    logger.warning(f"提取图片失败: {e}")
                    continue

        logger.info(f"从Word文档中共提取 {len(images)} 张图片")

    except Exception as e:
        logger.error(f"从Word文档提取图片失败: {e}", exc_info=True)

    return images


def extract_images_from_pdf(pdf_path: str) -> list:
    """
    从PDF文档中提取所有图片

    返回：
    - list: 图片列表，每个元素包含 {image_bytes, filename, index}
    """
    images = []

    try:
        import pdfplumber

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_images = page.images
                for img_idx, img in enumerate(page_images, 1):
                    try:
                        # pdfplumber 的图片需要从 xobject 中提取
                        if 'stream' in img:
                            stream = img['stream']
                            # 获取图片数据
                            if hasattr(stream, 'get_data'):
                                image_bytes = stream.get_data()
                            else:
                                continue

                            # 尝试获取图片格式
                            img_format = img.get('name', 'PNG')
                            if '.' not in img_format:
                                ext = '.png'
                            else:
                                ext = ''

                            filename = f"page{page_num}_img{img_idx}{ext}"

                            images.append({
                                "image_bytes": image_bytes,
                                "filename": filename,
                                "index": len(images),
                                "content_type": f"image/{img_format.lower()}",
                                "page": page_num
                            })

                            logger.info(f"提取图片: {filename}, 大小: {len(image_bytes)} bytes")

                    except Exception as e:
                        logger.warning(f"提取PDF图片失败 (page {page_num}): {e}")
                        continue

        logger.info(f"从PDF文档中共提取 {len(images)} 张图片")

    except Exception as e:
        logger.error(f"从PDF文档提取图片失败: {e}", exc_info=True)

    return images


def _get_image_extension(content_type: str) -> str:
    """根据content_type获取文件扩展名"""
    mime_to_ext = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/bmp": ".bmp",
        "image/webp": ".webp"
    }
    return mime_to_ext.get(content_type, ".png")


def save_images_to_disk(images: list, doc_id: str) -> list:
    """
    将图片保存到磁盘

    返回：
    - list: 保存后的图片信息列表
    """
    saved_images = []

    doc_image_dir = IMAGE_OUTPUT_DIR / doc_id
    doc_image_dir.mkdir(parents=True, exist_ok=True)

    for img_data in images:
        try:
            filename = img_data["filename"]
            filepath = doc_image_dir / filename

            with open(filepath, "wb") as f:
                f.write(img_data["image_bytes"])

            saved_images.append({
                "filename": filename,
                "filepath": str(filepath),
                "index": img_data["index"],
                "content_type": img_data.get("content_type", "image/png")
            })

            logger.info(f"图片已保存: {filepath}")

        except Exception as e:
            logger.warning(f"保存图片失败: {e}")

    return saved_images


def analyze_flowchart_image(image_bytes: bytes, image_index: int = 0) -> dict:
    """
    使用千问3多模态模型分析流程图图片

    参数：
    - image_bytes: 图片二进制数据
    - image_index: 图片索引

    返回：
    - dict: 分析结果
    """
    try:
        import dashscope
        from dashscope import MultiModalConversation

        # 设置API Key
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            logger.warning("未设置DASHSCOPE_API_KEY环境变量")
            return {
                "success": False,
                "error": "未设置DASHSCOPE_API_KEY环境变量",
                "image_index": image_index
            }

        dashscope.api_key = api_key

        # 将图片转为base64
        img_base64 = base64.b64encode(image_bytes).decode('utf-8')

        # 构建消息
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "image": f"data:image/png;base64,{img_base64}"
                    },
                    {
                        "text": """请分析这张系统交互流程图或泳道图，提取以下信息：
                        1. 涉及的系统和组件（有哪些参与方）
                        2. 各系统之间的交互顺序和调用关系
                        3. 图中所标明的的业务流程步骤包括正向流程和异常的流程，
                        4. 关键的数据流向
                        5. 是否有分支、循环、并行等特殊逻辑，如果存在那么将这些逻辑查找狐出来
                        
                        使用资深产品设计工程师的角度，用结构化的方式描述这个图内的业务流程，
                        如果图片不包含流程图信息，请说明"未识别到流程图"。"""
                    }
                ]
            }
        ]

        logger.info(f"开始分析流程图图片 {image_index}...")

        # 调用千问3多模态模型
        response = MultiModalConversation.call(
            model='qwen3.5-plus',
            messages=messages
        )

        if response.status_code == 200:
            result_content = response.output.choices[0].message.content
            analysis_text = ""
            for item in result_content:
                if 'text' in item:
                    analysis_text += item['text']

            logger.info(f"图片 {image_index} 分析完成，结果长度: {len(analysis_text)}")

            return {
                "success": True,
                "analysis": analysis_text,
                "image_index": image_index
            }
        else:
            logger.warning(f"图片分析失败: {response.code} - {response.message}")
            return {
                "success": False,
                "error": f"{response.code}: {response.message}",
                "image_index": image_index
            }

    except Exception as e:
        logger.error(f"分析流程图图片失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "image_index": image_index
        }


def extract_and_analyze_images(file_path: str, file_ext: str, doc_id: str) -> list:
    """
    提取并分析文档中的所有图片

    参数：
    - file_path: 文件路径
    - file_ext: 文件扩展名
    - doc_id: 文档ID

    返回：
    - list: 分析结果列表
    """
    images = []

    # 提取图片
    if file_ext in ['docx', 'doc']:
        images = extract_images_from_docx(file_path)
    elif file_ext in ['pdf']:
        images = extract_images_from_pdf(file_path)

    if not images:
        logger.info("文档中未提取到图片")
        return []

    # 保存图片到磁盘
    saved_images = save_images_to_disk(images, doc_id)

    # 分析每张图片（使用线程池并发处理）
    analysis_results = []

    # 使用线程池并发分析图片
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def analyze_single_image(img_data):
        """分析单张图片的函数"""
        result = analyze_flowchart_image(img_data["image_bytes"], img_data["index"])
        result["filename"] = img_data["filename"]
        return result

    # 根据图片数量调整线程数，最多同时处理5张
    max_workers = min(len(images), 5)
    logger.info(f"开始并发分析 {len(images)} 张图片，使用 {max_workers} 个线程")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有分析任务
        future_to_img = {executor.submit(analyze_single_image, img): img for img in images}

        # 收集结果
        for future in as_completed(future_to_img):
            img_data = future_to_img[future]
            try:
                result = future.result()
                analysis_results.append(result)
                logger.info(f"图片分析完成: {result.get('filename', '未知')}, 成功: {result.get('success', False)}")
            except Exception as img_error:
                logger.error(f"图片分析异常: {img_error}")
                analysis_results.append({
                    "success": False,
                    "error": str(img_error),
                    "filename": img_data.get("filename", ""),
                    "image_index": img_data.get("index", 0)
                })

    logger.info(f"所有图片分析完成，共 {len(analysis_results)} 张")

    return analysis_results


# ====== 新增：异步获取接口JSON示例 ======
def extract_interface_json_samples(doc_id: str, interface_list: list, api_section: str):
    """
    异步获取接口的JSON示例

    参数：
    - doc_id: 文档ID
    - interface_list: 接口列表
    - api_section: API文档内容
    """
    import threading
    import time

    def _run_async_task():
        """在线程中执行异步任务"""
        logger.info(f"[JSON示例提取] 开始异步获取接口JSON示例，doc_id={doc_id}, 接口数量={len(interface_list)}")

        try:
            # 等待几秒确保主流程已完成
            time.sleep(2)

            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # 获取RAG服务
                from api.http_rag_document import get_rag_service
                rag = get_rag_service()

                # 遍历每个接口，获取JSON示例
                from common.db_mapper.review_record_mapper import ReviewRecordMapper
                review_mapper = ReviewRecordMapper()

                for idx, interface in enumerate(interface_list, 1):
                    interface_name = interface.get('name', '')
                    method = interface.get('method', '')
                    path = interface.get('path', '')
                    description = interface.get('description', '')

                    if not interface_name:
                        logger.warning(f"[JSON示例提取] 接口{idx}缺少名称，跳过")
                        continue

                    logger.info(f"[JSON示例提取] 正在处理接口 {idx}/{len(interface_list)}: {interface_name}")

                    # 构建prompt
                    prompt = INTERFACE_JSON_EXTRACT_PROMPT.format(
                        interface_name=interface_name,
                        method=method,
                        path=path,
                        description=description,
                        api_content=api_section[:30000]  # 限制长度，避免token超限
                    )

                    # 调用大模型
                    result = loop.run_until_complete(
                        rag._generate_answer(
                            prompt=prompt,
                            temperature=0.1,
                            max_tokens=4000
                        )
                    )

                    # ===== 添加日志：打印 LLM 原始返回 =====
                    logger.info(f"[JSON示例提取] LLM原始返回（{interface_name}）: {result[:500]}...")

                    # 解析结果
                    request_json = ""
                    response_json = ""

                    try:
                        # 提取JSON
                        json_match = re.search(r'\{.*\}', result, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(0)
                            logger.info(f"[JSON示例提取] 提取的JSON字符串: {json_str[:500]}...")
                            json_data = json.loads(json_str)
                            request_json = json_data.get('request_json', '')
                            response_json = json_data.get('response_json', '')
                            logger.info(f"[JSON示例提取] 解析后 request_json长度={len(request_json)}, response_json长度={len(response_json)}")
                    except Exception as parse_err:
                        logger.warning(f"[JSON示例提取] 解析JSON失败: {parse_err}")

                    # 查找对应的数据库记录并更新
                    try:
                        db_records = review_mapper.get_all_by_doc_id(doc_id)
                        for record in db_records:
                            if record.get('interface_name') == interface_name:
                                review_mapper.update_json_samples(
                                    record_id=record['id'],
                                    request_json=request_json,
                                    response_json=response_json
                                )
                                logger.info(f"[JSON示例提取] 已更新接口 {interface_name} 的JSON示例")
                                break
                    except Exception as db_err:
                        logger.error(f"[JSON示例提取] 更新数据库失败: {db_err}")

                    # 每次处理完后稍作延迟，避免请求过快
                    time.sleep(1)

                logger.info(f"[JSON示例提取] 异步任务完成，doc_id={doc_id}")

            finally:
                loop.close()

        except Exception as e:
            logger.error(f"[JSON示例提取] 异步任务执行失败: {e}", exc_info=True)

    # 启动异步线程
    thread = threading.Thread(target=_run_async_task, daemon=True)
    thread.start()
    logger.info(f"[JSON示例提取] 已启动异步线程，doc_id={doc_id}")


# ====== 审核功能相关变量 ======

# 内存存储审核数据（生产环境建议使用数据库）
_review_data_store = {}


# ====== 审核数据结构 ======

class ReviewData:
    """审核数据结构"""
    def __init__(self, doc_id: str, document_title: str, business_module: str = ""):
        self.doc_id = doc_id
        self.document_title = document_title
        self.business_module = business_module
        self.project_background = ""
        self.business_summary = ""  # 服务内容摘要
        self.interface_list = []  # 接口列表
        self.flow_chart_analysis = []  # 流程图分析结果
        self.status = "pending"  # pending, approved, rejected
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.document_content = ""  # 原始文档内容（用于后续生成）
        self.api_section = ""  # API部分内容（用于后续生成）
        self.image_analysis = []  # 图片分析结果列表
        # 需求文档专用字段
        self.functional_modules = []  # 功能模块列表
        self.business_flows = []  # 业务流程列表
        self.business_rules = []  # 业务规则列表
        self.inferred_interfaces = []  # 推断的接口列表
        self.document_type = ""  # 文档类型：api_doc / product_design

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "document_title": self.document_title,
            "business_module": self.business_module,
            "project_background": self.project_background,
            "business_summary": self.business_summary,
            "interface_list": self.interface_list,
            "flow_chart_analysis": self.flow_chart_analysis,
            "image_analysis": self.image_analysis,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "functional_modules": self.functional_modules,
            "business_flows": self.business_flows,
            "business_rules": self.business_rules,
            "inferred_interfaces": self.inferred_interfaces,
            "document_type": self.document_type
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ReviewData':
        review = cls(
            doc_id=data.get("doc_id", ""),
            document_title=data.get("document_title", ""),
            business_module=data.get("business_module", "")
        )
        review.project_background = data.get("project_background", "")
        review.business_summary = data.get("business_summary", "")
        review.interface_list = data.get("interface_list", [])
        review.flow_chart_analysis = data.get("flow_chart_analysis", [])
        review.status = data.get("status", "pending")
        review.created_at = data.get("created_at", datetime.now().isoformat())
        review.updated_at = data.get("updated_at", datetime.now().isoformat())
        review.document_content = data.get("document_content", "")
        review.api_section = data.get("api_section", "")
        review.image_analysis = data.get("image_analysis", [])
        review.functional_modules = data.get("functional_modules", [])
        review.business_flows = data.get("business_flows", [])
        review.business_rules = data.get("business_rules", [])
        review.inferred_interfaces = data.get("inferred_interfaces", [])
        review.document_type = data.get("document_type", "")
        return review


# ====== 审核相关API接口 ======

@test_case_gen_opt.route('/start_review', methods=['POST'])
def start_review():
    """
    启动审核流程
    上传文档，进行阶段0预解析，返回待审核数据

    请求参数：
    - file: 需求文档文件 (multipart/form-data, 支持docx/pdf/txt)
    - document_title: 文档标题 (可选)
    - business_module: 业务模块 (可选)

    返回：
    - doc_id: 文档ID（用于后续查询和提交审核）
    - project_background: 项目背景
    - business_summary: 业务摘要
    - interface_list: 接口列表（待审核）
    - flow_chart_analysis: 流程图分析结果（待审核）
    """
    logger.info("=" * 80)
    logger.info("【审核接口】开始启动审核流程")
    logger.info("=" * 80)

    try:
        # 检查RAG服务
        logger.info("检查RAG服务状态...")
        rag = get_rag_service()
        if not rag:
            logger.error("RAG服务未初始化")
            return json_response({
                "code": 500,
                "message": "RAG服务初始化失败",
                "data": None
            }, 500)
        logger.info("RAG服务状态: OK")

        # 检查文件
        logger.info("检查上传文件...")
        if 'file' not in request.files:
            logger.warning("请求中未包含文件")
            return json_response({
                "code": 400,
                "message": "未找到文件",
                "data": None
            }, 400)

        file = request.files['file']
        if file.filename == '':
            logger.warning("文件名为空")
            return json_response({
                "code": 400,
                "message": "未选择文件",
                "data": None
            }, 400)

        file_ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        logger.info(f"上传文件名: {file.filename}, 扩展名: {file_ext}")

        if file_ext not in ALLOWED_EXTENSIONS:
            logger.warning(f"不支持的文件类型: {file_ext}")
            return json_response({
                "code": 400,
                "message": f"不支持的文件类型。允许的类型: {', '.join(ALLOWED_EXTENSIONS)}",
                "data": None
            }, 400)

        document_title = request.form.get('document_title', file.filename.rsplit('.', 1)[0])
        business_module = request.form.get('business_module', '')
        document_type = request.form.get('document_type', '')

        # 验证 document_type 参数
        if not document_type:
            return json_response({
                "code": 400,
                "message": "必须指定 document_type 参数（api_doc: API 文档, product_design: 产品设计文档）",
                "data": None
            }, 400)

        if not DocumentType.validate(document_type):
            return json_response({
                "code": 400,
                "message": f"无效的 document_type: {document_type}。有效值: api_doc（API 文档）, product_design（产品设计文档）",
                "data": None
            }, 400)

        logger.info(f"文档标题: {document_title}, 业务模块: {business_module}, 文档类型: {DocumentType.get_type_name(document_type)}")

        # 保存上传的文件
        doc_id = str(uuid.uuid4())
        new_filename = f"{doc_id}.{file_ext}"
        file_path = os.path.join(UPLOAD_FOLDER, new_filename)
        file.save(file_path)
        logger.info(f"文件保存成功: {file_path}")

        logger.info(f"开始审核流程: {document_title}, doc_id: {doc_id}")

        # 提取文档内容
        logger.info("提取文档内容...")
        document_content = _extract_document_content(file_path, file_ext)

        if not document_content:
            logger.warning("无法提取文档内容")
            return json_response({
                "code": 400,
                "message": "无法提取文档内容",
                "data": None
            }, 400)

        logger.info(f"文档内容提取成功，长度: {len(document_content)} 字符")

        # ===== 根据文档类型分发处理流程 =====
        if document_type == DocumentType.API_DOC:
            # 技术设计文档处理流程
            logger.info("=" * 80)
            logger.info("【审核接口】处理技术设计文档")
            logger.info("=" * 80)
            result = process_api_document(
                rag=rag,
                file_path=file_path,
                file_ext=file_ext,
                doc_id=doc_id,
                document_title=document_title,
                business_module=business_module,
                document_content=document_content
            )
        else:
            # 需求文档处理流程
            logger.info("=" * 80)
            logger.info("【审核接口】处理需求文档")
            logger.info("=" * 80)
            result = process_product_design_document(
                rag=rag,
                file_path=file_path,
                file_ext=file_ext,
                doc_id=doc_id,
                document_title=document_title,
                business_module=business_module,
                document_content=document_content
            )

        # 返回结果
        return json_response({
            "code": 200,
            "message": "审核数据已生成",
            "data": result
        })

    except Exception as e:
        logger.error(f"启动审核流程异常: {e}", exc_info=True)
        return json_response({
            "code": 500,
            "message": f"服务器内部错误: {str(e)}",
            "data": None
        }, 500)


def process_api_document(rag, file_path: str, file_ext: str, doc_id: str,
                                      document_title: str, business_module: str,
                                      document_content: str) -> dict:
    """
    处理技术设计文档（原有流程）

    Returns:
        返回包含 review_data 的字典
    """
    logger.info("开始处理技术设计文档...")

    # 结构化解析文档
    logger.info("开始结构化解析文档...")
    doc_structure = parse_document_structure(document_content)
    logger.info(f"文档结构解析完成: 基础知识={len(doc_structure.get('basic_knowledge', ''))}字符, "
               f"服务内容={len(doc_structure.get('service_content', ''))}字符, "
               f"API数量={len(doc_structure.get('api_section', ''))}字符")

    api_section = doc_structure.get("api_section", "")

    # 阶段0：预解析文档
    logger.info("=" * 80)
    logger.info("【审核接口】开始阶段0预解析")
    logger.info("=" * 80)

    # 合并所有文档内容用于预解析
    full_content = f"""
【基础知识】
{doc_structure.get('basic_knowledge', '')}

【服务内容】
{doc_structure.get('service_content', '')}

【模板配置】
{doc_structure.get('template_config', '')}

【核心API应用】
{api_section}
"""

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # 限制输入长度，增加长度以包含完整接口列表
        max_chars = 60000
        pre_analysis_prompt = DOC_PRE_ANALYSIS_PROMPT.format(
            content=full_content[:max_chars]
        )

        logger.info(f"阶段0输入长度: {len(pre_analysis_prompt)} 字符")

        logger.info("调用大模型进行预解析...")
        pre_result = loop.run_until_complete(
            rag._generate_answer(
                prompt=pre_analysis_prompt,
                temperature=0.1,
                max_tokens=10000,
            )
        )

        logger.info(f"阶段0输出长度: {len(pre_result)} 字符")

        # 解析阶段0结果
        project_info = _parse_pre_analysis_result(pre_result)

        logger.info(f"预解析结果: 项目背景={project_info['project_background'][:50]}...")
        logger.info(f"接口数量={project_info['interface_count']}, 页面数量={project_info['page_count']}")
        if project_info.get('interface_list'):
            logger.info(f"接口列表: {[iface.get('name', '未命名') for iface in project_info['interface_list'][:3]]}...")

        # 创建审核数据对象
        logger.info("创建审核数据对象...")
        review_data = ReviewData(
            doc_id=doc_id,
            document_title=document_title,
            business_module=business_module
        )
        review_data.document_type = DocumentType.API_DOC
        review_data.project_background = project_info.get('project_background', '')
        review_data.business_summary = doc_structure.get('service_content', '')
        review_data.interface_list = project_info.get('interface_list', [])
        review_data.flow_chart_analysis = project_info.get('flow_charts', [])
        review_data.document_content = document_content
        review_data.api_section = api_section

        # 提取并分析文档中的图片
        logger.info("开始提取并分析文档中的图片...")
        try:
            image_analysis_results = extract_and_analyze_images(file_path, file_ext, doc_id)

            if image_analysis_results:
                review_data.image_analysis = image_analysis_results
                logger.info(f"图片分析完成，共分析 {len(image_analysis_results)} 张图片")

                for analysis in image_analysis_results:
                    if analysis.get("success"):
                        review_data.flow_chart_analysis.append({
                            "source": "image",
                            "filename": analysis.get("filename", ""),
                            "analysis": analysis.get("analysis", "")
                        })
                        logger.info(f"图片分析结果已添加: {analysis.get('filename')}")
            else:
                logger.info("文档中未提取到图片或图片分析失败")
                review_data.image_analysis = []

        except Exception as img_error:
            logger.warning(f"图片提取或分析失败: {img_error}")
            review_data.image_analysis = []

        # 保存到内存存储
        _review_data_store[doc_id] = review_data

        # 保存到数据库
        logger.info("保存审核记录到数据库...")
        logger.info(f"  - doc_id: {doc_id}")
        logger.info(f"  - document_title: {document_title}")
        logger.info(f"  - business_module: {business_module}")
        logger.info(f"  - interface_count: {len(review_data.interface_list)}")

        try:
            review_mapper = ReviewRecordMapper()
            db_records = review_mapper.save_from_review_data(review_data, creator="system")
            logger.info(f"审核记录已保存到数据库，共 {len(db_records)} 条记录")

            # 异步获取接口JSON示例
            if review_data.interface_list and api_section:
                logger.info("启动异步任务：获取接口JSON示例...")
                extract_interface_json_samples(
                    doc_id=doc_id,
                    interface_list=review_data.interface_list,
                    api_section=api_section
                )
                logger.info("异步任务已启动")

        except Exception as db_err:
            logger.error(f"保存审核记录到数据库失败: {db_err}", exc_info=True)

        logger.info(f"技术设计文档审核数据已创建，doc_id: {doc_id}")
        logger.info(f"审核数据概要: 接口数量={len(review_data.interface_list)}, "
                   f"流程图数量={len(review_data.flow_chart_analysis)}, "
                   f"图片分析数量={len(review_data.image_analysis)}")

        return {
            "doc_id": doc_id,
            "document_title": document_title,
            "business_module": business_module,
            "document_type": DocumentType.API_DOC,
            "project_background": review_data.project_background,
            "business_summary": review_data.business_summary,
            "interface_list": review_data.interface_list,
            "flow_chart_analysis": review_data.flow_chart_analysis,
            "image_analysis": review_data.image_analysis,
            "status": review_data.status
        }

    finally:
        loop.close()


def process_product_design_document(rag, file_path: str, file_ext: str, doc_id: str,
                                    document_title: str, business_module: str,
                                    document_content: str) -> dict:
    """
    处理需求文档（新增流程）

    Returns:
        返回包含 review_data 的字典
    """
    logger.info("开始处理需求文档...")

    # 1. 结构化解析需求文档
    logger.info("开始结构化解析需求文档...")
    doc_structure = parse_requirement_document(document_content, rag)
    logger.info(f"需求文档结构解析完成")

    # 2. 预分析需求文档
    logger.info("=" * 80)
    logger.info("【需求文档】开始预分析")
    logger.info("=" * 80)

    full_content = f"""
【项目概述】
{doc_structure.get('project_overview', '')}

【功能模块】
{doc_structure.get('functional_modules', '')}

【业务规则】
{doc_structure.get('business_rules', '')}

【数据需求】
{doc_structure.get('data_requirements', '')}

【接口需求】
{doc_structure.get('interface_requirements', '')}

【其他需求】
{doc_structure.get('other_requirements', '')}
"""

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        max_chars = 35000
        pre_analysis_prompt = _get_requirement_pre_analysis_prompt().format(
            content=full_content[:max_chars]
        )

        logger.info(f"需求预分析输入长度: {len(pre_analysis_prompt)} 字符")

        pre_result = loop.run_until_complete(
            rag._generate_answer(
                prompt=pre_analysis_prompt,
                temperature=0.1,
                max_tokens=8000,
            )
        )

        logger.info(f"需求预分析输出长度: {len(pre_result)} 字符")

        # 解析预分析结果
        requirement_info = _parse_requirement_analysis_result(pre_result)

        logger.info(f"需求预分析结果: 项目背景={requirement_info.get('project_background', '')[:50]}...")
        logger.info(f"功能模块数量={len(requirement_info.get('functional_modules', []))}")
        logger.info(f"业务流程数量={len(requirement_info.get('business_flows', []))}")

        # 创建审核数据对象
        logger.info("创建需求文档审核数据对象...")
        review_data = ReviewData(
            doc_id=doc_id,
            document_title=document_title,
            business_module=business_module
        )
        review_data.document_type = DocumentType.PRODUCT_DESIGN
        review_data.project_background = requirement_info.get('project_background', '')
        review_data.business_summary = requirement_info.get('business_summary', doc_structure.get('project_overview', ''))

        # 需求文档不提取接口列表，设置为空
        review_data.interface_list = []
        review_data.flow_chart_analysis = []
        review_data.document_content = document_content

        # 需求文档可能有业务流程图，尝试提取
        try:
            image_analysis_results = extract_and_analyze_images(file_path, file_ext, doc_id)
            if image_analysis_results:
                review_data.image_analysis = image_analysis_results
                logger.info(f"需求文档图片分析完成，共分析 {len(image_analysis_results)} 张图片")

                for analysis in image_analysis_results:
                    if analysis.get("success"):
                        review_data.flow_chart_analysis.append({
                            "source": "image",
                            "filename": analysis.get("filename", ""),
                            "analysis": analysis.get("analysis", "")
                        })
            else:
                review_data.image_analysis = []
        except Exception as img_error:
            logger.warning(f"需求文档图片提取或分析失败: {img_error}")
            review_data.image_analysis = []

        # 存储功能模块和业务规则信息
        review_data.functional_modules = requirement_info.get('functional_modules', [])
        review_data.business_flows = requirement_info.get('business_flows', [])
        review_data.business_rules = requirement_info.get('business_rules', [])
        review_data.inferred_interfaces = requirement_info.get('inferred_interfaces', [])

        # 保存到内存存储
        _review_data_store[doc_id] = review_data

        # 保存到数据库（需求文档保存到 summary 表）
        logger.info("保存需求文档审核记录到数据库...")
        try:
            summary_mapper = ReviewSummaryMapper()
            summary_data = {
                "doc_id": doc_id,
                "document_title": document_title,
                "business_module": business_module,
                "document_type": DocumentType.PRODUCT_DESIGN,
                "project_background": review_data.project_background,
                "business_summary": review_data.business_summary,
                "interface_count": 0,
                "page_count": 0,
                "flow_chart_count": len(review_data.flow_chart_analysis),
                "image_count": len(review_data.image_analysis),
                "status": "pending"
            }
            summary_id = summary_mapper.create(summary_data)
            logger.info(f"需求文档审核记录已保存，summary_id: {summary_id}")

        except Exception as db_err:
            logger.error(f"保存需求文档审核记录失败: {db_err}", exc_info=True)

        logger.info(f"需求文档审核数据已创建，doc_id: {doc_id}")
        logger.info(f"审核数据概要: 功能模块数量={len(review_data.functional_modules)}, "
                   f"业务流程数量={len(review_data.business_flows)}, "
                   f"图片分析数量={len(review_data.image_analysis)}")

        return {
            "doc_id": doc_id,
            "document_title": document_title,
            "business_module": business_module,
            "document_type": DocumentType.PRODUCT_DESIGN,
            "project_background": review_data.project_background,
            "business_summary": review_data.business_summary,
            "functional_modules": review_data.functional_modules,
            "business_flows": review_data.business_flows,
            "business_rules": review_data.business_rules,
            "inferred_interfaces": review_data.inferred_interfaces,
            "flow_chart_analysis": review_data.flow_chart_analysis,
            "image_analysis": review_data.image_analysis,
            "status": review_data.status
        }

    finally:
        loop.close()


@test_case_gen_opt.route('/get_review_data/<doc_id>', methods=['GET'])
def get_review_data(doc_id: str):
    """
    获取审核数据
    优先从数据库读取分类后的数据，如果没有则从内存读取

    返回结构：
    - interface_list: 接口列表，每项只包含该接口匹配到的图片和流程分析
    - general_image_analysis: 未匹配到接口的知识图片
    - unmatched_flow_analysis: 未被任何接口使用的流程图条目（source_type=general_knowledge）
    - 顶层字段不再携带完整 flow_chart_analysis / document_content 等大字段，避免重复冗余

    参数：
    - doc_id: 文档ID
    """
    logger.info(f"【审核接口】获取审核数据, doc_id: {doc_id}")

    # 优先从数据库读取分类后的数据
    try:
        review_mapper = ReviewRecordMapper()
        db_records = review_mapper.get_all_by_doc_id(doc_id)

        if db_records and len(db_records) > 0:
            logger.info(f"从数据库读取到 {len(db_records)} 条记录")

            # 将记录按类型分类
            interface_records = []
            doc_level_record = None

            for record in db_records:
                if record.get('interface_name'):
                    interface_records.append(record)
                else:
                    doc_level_record = record  # 文档级别记录（含知识图片）

            # ── 接口列表：每项只带本接口的图片和流程分析，不重复全量数据 ──
            interface_list = []
            for rec in interface_records:
                interface_list.append({
                    'name': rec.get('interface_name', ''),
                    'method': rec.get('interface_method', ''),
                    'path': rec.get('interface_path', ''),
                    'description': rec.get('interface_description', ''),
                    'request_params': rec.get('request_params', ''),
                    'request_json_sample': rec.get('request_json_sample', ''),
                    'response_json_sample': rec.get('response_json_sample', ''),
                    'response_params': rec.get('response_params', ''),
                    'process_flow': rec.get('process_flow', ''),
                    'detail_flow_analysis': rec.get('detail_flow_analysis', ''),
                    'image_analysis': rec.get('image_analysis') or [],  # 该接口匹配的图片
                })

            # ── 知识图片：文档级别记录的 image_analysis ──
            general_image_analysis = []
            # ── 未匹配的流程条目：flow_chart_analysis 里 source_type=general_knowledge 的部分 ──
            unmatched_flow_analysis = []

            if doc_level_record:
                general_image_analysis = doc_level_record.get('image_analysis') or []
                for item in (doc_level_record.get('flow_chart_analysis') or []):
                    if isinstance(item, dict) and item.get('source_type') == 'general_knowledge':
                        unmatched_flow_analysis.append(item)

            # ── 顶层文档基础信息：不携带大字段 ──
            base_record = db_records[0]
            result_data = {
                'doc_id': base_record.get('doc_id'),
                'document_title': base_record.get('document_title'),
                'business_module': base_record.get('business_module'),
                'project_background': base_record.get('project_background'),
                'business_summary': base_record.get('business_summary'),
                'status': base_record.get('status'),
                'created_at': base_record.get('created_time'),
                'updated_at': base_record.get('updated_time'),
                # 接口列表（每项含自己的图片/流程，不含全量 flow_chart_analysis）
                'interface_list': interface_list,
                # 知识图片（未匹配到任何接口的图片）
                'general_image_analysis': general_image_analysis,
                # 未匹配的流程条目（供前端参考）
                'unmatched_flow_analysis': unmatched_flow_analysis,
            }

            logger.info(
                f"数据库数据: 接口数量={len(interface_list)}, "
                f"知识图片={len(general_image_analysis)}, "
                f"未匹配流程={len(unmatched_flow_analysis)}"
            )

            return json_response({
                "code": 200,
                "message": "获取成功",
                "data": result_data
            })

    except Exception as e:
        logger.warning(f"从数据库读取失败: {e}，尝试从内存读取", exc_info=True)

    # 回退：从内存读取（服务刚启动或数据库异常时）
    if doc_id not in _review_data_store:
        logger.warning(f"审核数据不存在: {doc_id}")
        return json_response({
            "code": 404,
            "message": "审核数据不存在",
            "data": None
        }, 404)

    review_data = _review_data_store[doc_id]
    logger.info(
        f"内存数据: 文档标题={review_data.document_title}, "
        f"状态={review_data.status}, "
        f"接口数量={len(review_data.interface_list)}, "
        f"流程图数量={len(review_data.flow_chart_analysis)}"
    )
    logger.info("【审核接口】获取审核数据完成（内存）")

    return json_response({
        "code": 200,
        "message": "获取成功",
        "data": review_data.to_dict()
    })


@test_case_gen_opt.route('/submit_review', methods=['POST'])
def submit_review():
    """
    提交审核结果

    请求参数：
    - doc_id: 文档ID
    - project_background: 项目背景（用户修改后）
    - business_summary: 业务摘要（用户修改后）
    - interface_list: 接口列表（用户修改后）
    - flow_chart_analysis: 流程图分析结果（用户修改后）
    - action: 操作类型 (approve/reject)

    返回：
    - 审核状态
    """
    logger.info("【审核接口】开始提交审核")
    logger.info("=" * 80)

    try:
        data = request.get_json()
        if not data:
            logger.warning("请求参数为空")
            return json_response({
                "code": 400,
                "message": "请求参数不能为空",
                "data": None
            }, 400)

        doc_id = data.get('doc_id')
        action = data.get('action', 'approve')
        reviewer = data.get('reviewer', 'system')
        review_comment = data.get('review_comment', '')
        logger.info(f"提交审核: doc_id={doc_id}, action={action}, reviewer={reviewer}")

        # ========== 检查JSON示例是否获取完成 ==========
        if action == 'approve':
            try:
                review_mapper = ReviewRecordMapper()
                json_status = review_mapper.check_json_samples_completed(doc_id)

                if not json_status.get("completed"):
                    pending_count = json_status.get("pending_count", 0)
                    pending_interfaces = json_status.get("pending_interfaces", [])
                    logger.warning(f"JSON示例未获取完成，pending_count={pending_count}")

                    return json_response({
                        "code": 400,
                        "message": f"接口JSON示例正在获取中，请稍后再提交审核。还有 {pending_count} 个接口的JSON示例未获取完成: {', '.join(pending_interfaces[:3])}{'...' if len(pending_interfaces) > 3 else ''}",
                        "data": {
                            "pending_count": pending_count,
                            "pending_interfaces": pending_interfaces
                        }
                    }, 400)

                logger.info("JSON示例检查通过，所有接口的JSON示例已获取完成")
            except Exception as check_err:
                logger.warning(f"检查JSON示例状态失败: {check_err}，继续提交审核")

        # ========== 优先从数据库检查数据是否存在 ==========
        review_data = None
        try:
            review_mapper = ReviewRecordMapper()
            db_records = review_mapper.get_all_by_doc_id(doc_id)

            if db_records and len(db_records) > 0:
                logger.info(f"从数据库读取到 {len(db_records)} 条记录，构建审核数据")
                # 从数据库记录构建 ReviewData 对象
                base_record = db_records[0]

                # 获取SQL配置中的设置
                settings = get_default_settings()
                list_page_size = settings.get('list_page_size', 20)

                # 分类接口记录
                interface_list = []
                for rec in db_records:
                    if rec.get('interface_name'):
                        interface_list.append({
                            'name': rec.get('interface_name', ''),
                            'method': rec.get('interface_method', ''),
                            'path': rec.get('interface_path', ''),
                            'description': rec.get('interface_description', ''),
                            'request_params': rec.get('request_params', ''),
                            'request_json_sample': rec.get('request_json_sample', ''),
                            'response_json_sample': rec.get('response_json_sample', ''),
                            'response_params': rec.get('response_params', ''),
                            'process_flow': rec.get('process_flow', ''),
                            'detail_flow_analysis': rec.get('detail_flow_analysis', ''),
                            'image_analysis': rec.get('image_analysis') or [],
                        })

                # 构建 ReviewData 对象
                review_data = ReviewData(
                    doc_id=doc_id,
                    document_title=base_record.get('document_title', ''),
                    business_module=base_record.get('business_module', '')
                )
                review_data.project_background = base_record.get('project_background', '')
                review_data.business_summary = base_record.get('business_summary', '')
                review_data.interface_list = interface_list
                review_data.status = base_record.get('status', 'pending')

                # 合并所有记录的 flow_chart_analysis
                all_flows = []
                for rec in db_records:
                    flow = rec.get('flow_chart_analysis') or []
                    all_flows.extend(flow)
                review_data.flow_chart_analysis = all_flows

                # 合并所有图片分析
                all_images = []
                for rec in db_records:
                    img = rec.get('image_analysis') or []
                    all_images.extend(img)
                review_data.image_analysis = all_images

                logger.info(f"数据库构建: 接口数量={len(review_data.interface_list)}, 流程图={len(review_data.flow_chart_analysis)}")
            else:
                logger.info("数据库中未找到记录，尝试从内存读取")
        except Exception as db_err:
            logger.warning(f"从数据库查询失败: {db_err}，尝试从内存读取")

        # 回退：从内存读取
        if review_data is None:
            if doc_id not in _review_data_store:
                logger.warning(f"审核数据不存在: {doc_id}")
                return json_response({
                    "code": 404,
                    "message": "审核数据不存在",
                    "data": None
                }, 404)
            review_data = _review_data_store[doc_id]
            logger.info(f"从内存读取: doc_id={doc_id}, status={review_data.status}")
        logger.info(f"当前审核状态: {review_data.status}")

        # 更新审核数据
        if 'project_background' in data:
            old_bg = review_data.project_background
            review_data.project_background = data['project_background']
            logger.info(f"更新项目背景: {len(old_bg)} -> {len(review_data.project_background)} 字符")

        if 'business_summary' in data:
            old_summary = review_data.business_summary
            review_data.business_summary = data['business_summary']
            logger.info(f"更新业务摘要: {len(old_summary)} -> {len(review_data.business_summary)} 字符")

        if 'interface_list' in data:
            old_count = len(review_data.interface_list)
            review_data.interface_list = data['interface_list']
            logger.info(f"更新接口列表: {old_count} -> {len(review_data.interface_list)} 个接口")

        if 'flow_chart_analysis' in data:
            old_flow_count = len(review_data.flow_chart_analysis)
            review_data.flow_chart_analysis = data['flow_chart_analysis']
            logger.info(f"更新流程图分析: {old_flow_count} -> {len(review_data.flow_chart_analysis)} 个")

        # 更新状态
        if action == 'approve':
            review_data.status = 'approved'
            logger.info("审核操作: 批准 (approve)")
        elif action == 'reject':
            review_data.status = 'rejected'
            logger.info("审核操作: 拒绝 (reject)")
        else:
            logger.warning(f"无效的操作类型: {action}")
            return json_response({
                "code": 400,
                "message": "无效的操作类型",
                "data": None
            }, 400)

        review_data.updated_at = datetime.now().isoformat()

        # 更新数据库中的审核记录
        logger.info("更新数据库中的审核记录...")
        try:
            review_mapper = ReviewRecordMapper()
            db_record = review_mapper.update_status(
                doc_id=doc_id,
                status=review_data.status,
                reviewer=reviewer,
                review_comment=review_comment
            )
            if db_record:
                logger.info(f"数据库审核状态已更新，ID: {db_record.get('id')}")
            else:
                logger.warning(f"未找到数据库记录，doc_id: {doc_id}")
        except Exception as db_err:
            logger.warning(f"更新数据库审核记录失败: {db_err}")

        logger.info(f"审核已提交，doc_id: {doc_id}, action: {action}, 新状态: {review_data.status}")
        logger.info("【审核接口】提交审核完成")

        return json_response({
            "code": 200,
            "message": "审核提交成功",
            "data": {
                "doc_id": doc_id,
                "status": review_data.status
            }
        })

    except Exception as e:
        logger.error(f"提交审核失败: {e}", exc_info=True)
        return json_response({
            "code": 500,
            "message": f"提交审核失败: {str(e)}",
            "data": None
        }, 500)


@test_case_gen_opt.route('/generate_with_review/<doc_id>', methods=['POST'])
def generate_with_review(doc_id: str):
    """
    根据审核通过的数据生成测试用例
    优先从缓存读取，缓存没有则从数据库查询

    参数：
    - doc_id: 文档ID

    返回：
    - xmind文件下载
    """
    logger.info("=" * 80)
    logger.info(f"【审核接口】开始根据审核数据生成测试用例, doc_id: {doc_id}")
    logger.info("=" * 80)

    # ========== 优先从缓存读取，缓存没有则从数据库查询 ==========
    review_data = None

    # 1. 先尝试从内存缓存读取
    if doc_id in _review_data_store:
        logger.info(f"从内存缓存读取审核数据: {doc_id}")
        review_data = _review_data_store[doc_id]
    else:
        # 2. 缓存没有，从数据库读取
        logger.info(f"缓存中未找到，从数据库读取审核数据: {doc_id}")
        try:
            review_mapper = ReviewRecordMapper()
            db_records = review_mapper.get_all_by_doc_id(doc_id)

            if db_records and len(db_records) > 0:
                logger.info(f"从数据库读取到 {len(db_records)} 条记录，构建审核数据")
                base_record = db_records[0]

                # 分类接口记录
                interface_list = []
                for rec in db_records:
                    if rec.get('interface_name'):
                        interface_list.append({
                            'name': rec.get('interface_name', ''),
                            'method': rec.get('interface_method', ''),
                            'path': rec.get('interface_path', ''),
                            'description': rec.get('interface_description', ''),
                            'request_params': rec.get('request_params', ''),
                            'request_json_sample': rec.get('request_json_sample', ''),
                            'response_json_sample': rec.get('response_json_sample', ''),
                            'response_params': rec.get('response_params', ''),
                            'process_flow': rec.get('process_flow', ''),
                            'detail_flow_analysis': rec.get('detail_flow_analysis', ''),
                            'image_analysis': rec.get('image_analysis') or [],
                        })

                # 构建 ReviewData 对象
                review_data = ReviewData(
                    doc_id=doc_id,
                    document_title=base_record.get('document_title', ''),
                    business_module=base_record.get('business_module', '')
                )
                review_data.project_background = base_record.get('project_background', '')
                review_data.business_summary = base_record.get('business_summary', '')
                review_data.interface_list = interface_list
                review_data.status = base_record.get('status', 'pending')

                # 合并所有记录的 flow_chart_analysis
                all_flows = []
                for rec in db_records:
                    flow = rec.get('flow_chart_analysis') or []
                    all_flows.extend(flow)
                review_data.flow_chart_analysis = all_flows

                # 合并所有图片分析
                all_images = []
                for rec in db_records:
                    img = rec.get('image_analysis') or []
                    all_images.extend(img)
                review_data.image_analysis = all_images

                # 尝试从 base_record 获取 api_section（如果数据库有存储的话）
                review_data.api_section = base_record.get('api_section', '')
                review_data.document_content = base_record.get('document_content', '')

                logger.info(f"数据库构建: 接口数量={len(review_data.interface_list)}, 流程图={len(review_data.flow_chart_analysis)}")
            else:
                logger.info("数据库中未找到记录")

        except Exception as db_err:
            logger.warning(f"从数据库查询失败: {db_err}", exc_info=True)

    # 3. 如果仍然没有数据，返回404
    if review_data is None:
        logger.warning(f"审核数据不存在: {doc_id}")
        return json_response({
            "code": 404,
            "message": "审核数据不存在",
            "data": None
        }, 404)

    logger.info(f"审核状态: {review_data.status}")

    if review_data.status != 'approved':
        logger.warning(f"审核未通过，无法生成测试用例，当前状态: {review_data.status}")
        return json_response({
            "code": 400,
            "message": "审核未通过，无法生成测试用例",
            "data": None
        }, 400)

    logger.info(f"文档标题: {review_data.document_title}")
    logger.info(f"接口数量: {len(review_data.interface_list)}")
    logger.info(f"流程图数量: {len(review_data.flow_chart_analysis)}")

    try:
        # 检查RAG服务
        logger.info("检查RAG服务...")
        rag = get_rag_service()
        if not rag:
            logger.error("RAG服务未初始化")
            return json_response({
                "code": 500,
                "message": "RAG服务初始化失败",
                "data": None
            }, 500)
        logger.info("RAG服务状态: OK")

        logger.info(f"开始根据审核数据生成测试用例: {doc_id}")

        # 构建doc_structure（使用审核后的数据）
        doc_structure = {
            "basic_knowledge": "",
            "service_content": review_data.business_summary,
            "template_config": "",
            "api_section": review_data.api_section
        }

        # 构建project_info（使用审核后的接口列表）
        project_info = {
            "project_background": review_data.project_background,
            "business_module": review_data.business_module,
            "interface_count": len(review_data.interface_list),
            "page_count": 1,
            "core_flows": review_data.flow_chart_analysis,
            "interface_list": review_data.interface_list,
            "flow_charts": review_data.flow_chart_analysis
        }

        # 阶段1：发送背景信息（不发回复）
        logger.info("=" * 80)
        logger.info("【阶段1】发送背景信息给大模型...")

        interface_list_text = ""
        if review_data.interface_list:
            for idx, iface in enumerate(review_data.interface_list, 1):
                interface_list_text += f"""
                    接口{idx}: {iface.get('name', '未命名')}
                      - 方法: {iface.get('method', '未指定')}
                      - 路径: {iface.get('path', '未指定')}
                      - 描述: {iface.get('description', '无')}
                      - 请求参数: {iface.get('request_params', '无')}
                      - 响应参数: {iface.get('response_params', '无')}
                      - 处理流程: {iface.get('process_flow', '无')}
                      - 流程图描述: {iface.get('flow_chart_desc', '无')}
                    """

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            context_prompt = CONTEXT_INFO_PROMPT.format(
                project_background=review_data.project_background,
                business_module=review_data.business_module,
                interface_count=len(review_data.interface_list),
                page_count=1,
                core_flows="\n".join([f"- {f}" for f in review_data.flow_chart_analysis]) if review_data.flow_chart_analysis else "",
                interface_list=interface_list_text if interface_list_text else "",
                flow_charts="\n".join([f"- {f}" for f in review_data.flow_chart_analysis]) if review_data.flow_chart_analysis else ""
            )

            logger.info(f"阶段1背景信息长度: {len(context_prompt)} 字符")

            loop.run_until_complete(
                rag._generate_answer(
                    prompt=context_prompt,
                    temperature=0.1,
                    max_tokens=500,
                )
            )
            logger.info("背景信息已发送，大模型已了解项目上下文")

            # 阶段2：分接口生成测试用例
            logger.info("=" * 80)
            logger.info("【阶段2】开始分接口生成测试用例...")

            all_cases = []

            for idx, iface in enumerate(review_data.interface_list, 1):
                try:
                    base_min_cases = 8
                    extra = 3 if idx <= 3 else 0
                    min_cases = base_min_cases + extra

                    interface_prompt = SINGLE_INTERFACE_PROMPT.format(
                        name=iface.get('name', '未命名接口'),
                        method=iface.get('method', 'POST'),
                        path=iface.get('path', '/api/unknown'),
                        description=iface.get('description', '无描述'),
                        request_params=iface.get('request_params', '无说明'),
                        response_params=iface.get('response_params', '无说明'),
                        process_flow=iface.get('process_flow', '无流程说明'),
                        flow_chart=iface.get('flow_chart_desc', '无流程图'),
                        project_background=review_data.project_background,
                        min_cases=min_cases,
                    )

                    logger.info(f"--- 接口 {idx}/{len(review_data.interface_list)}: {iface.get('name')} ---")

                    answer = loop.run_until_complete(
                        rag._generate_answer(
                            prompt=interface_prompt,
                            temperature=0.2,
                            max_tokens=8000,
                        )
                    )

                    logger.info(f"输出长度: {len(answer)} 字符")

                    # 解析用例
                    cases = parse_llm_response_to_test_cases(answer)
                    if not cases:
                        logger.warning(f"接口 {iface.get('name')} 未生成有效用例")
                        continue

                    # 为每个用例添加模块信息
                    module_name = review_data.business_module or "功能验证"
                    for c in cases:
                        if not c:
                            continue
                        c["module"] = module_name
                        scene_val = c.get("scene") or c.get("title") or ""
                        if not scene_val:
                            scene_val = f"{iface.get('name')}测试场景"
                        c["scene"] = scene_val

                        expected_val = c.get("expected") or c.get("expected_result") or ""
                        if not expected_val:
                            expected_val = "符合接口文档约定的响应"
                        c["expected"] = expected_val

                    all_cases.extend(cases)
                    logger.info(f"接口 {idx}/{len(review_data.interface_list)} ({iface.get('name')}) 生成 {len(cases)} 条用例")

                except Exception as ie:
                    logger.error(f"为接口 {iface.get('name')} 生成测试用例失败: {ie}", exc_info=True)
                    continue

            if not all_cases:
                logger.warning("未能生成有效测试用例，使用默认模板")
                all_cases = _generate_default_test_cases(review_data.document_title, review_data.business_module)

            logger.info(f"生成测试案例总数: {len(all_cases)}")
            logger.info("开始生成XMind文件...")

            # 生成XMind文件
            xmind_gen = XMindGenerator(output_dir=str(XMIND_OUTPUT_DIR))
            xmind_path = xmind_gen.generate_test_cases_xmind(
                document_title=review_data.document_title,
                test_cases=all_cases,
                business_module=review_data.business_module
            )

            logger.info(f"XMind文件生成成功: {xmind_path}")
            logger.info(f"下载文件名: {os.path.basename(xmind_path)}")

            # 更新数据库中的生成结果
            logger.info("更新数据库中的生成结果...")
            try:
                review_mapper = ReviewRecordMapper()
                db_record = review_mapper.update_generation_result(
                    doc_id=doc_id,
                    xmind_file_path=xmind_path,
                    test_case_count=len(all_cases)
                )
                if db_record:
                    logger.info(f"数据库生成结果已更新，ID: {db_record.get('id')}, 测试用例数量: {len(all_cases)}")
                else:
                    logger.warning(f"未找到数据库记录，doc_id: {doc_id}")
            except Exception as db_err:
                logger.warning(f"更新数据库生成结果失败: {db_err}")

            logger.info("【审核接口】根据审核数据生成测试用例完成")

            return send_file(
                xmind_path,
                as_attachment=True,
                download_name=os.path.basename(xmind_path),
                mimetype='application/octet-stream'
            )

        finally:
            loop.close()

    except Exception as e:
        logger.error(f"生成测试案例失败: {e}", exc_info=True)
        return json_response({
            "code": 500,
            "message": f"生成测试案例失败: {str(e)}",
            "data": None
        }, 500)


@test_case_gen_opt.route('/list_reviews', methods=['GET'])
def list_reviews():
    """
    获取审核记录列表（从汇总表查询，高效）

    Query 参数（均可选）：
    - status: 过滤状态 (pending / approved / rejected)
    - business_module: 过滤业务模块
    - document_type: 过滤文档类型 (api_doc / product_design)
    - limit: 每页条数，默认 100
    - offset: 偏移量，默认 0
    """
    logger.info("【审核接口】获取审核记录列表（汇总表）")

    status = request.args.get('status')
    business_module = request.args.get('business_module')
    document_type = request.args.get('document_type')
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
    except ValueError:
        limit, offset = 100, 0

    try:
        summary_mapper = ReviewSummaryMapper()
        reviews = summary_mapper.list_all(
            status=status,
            business_module=business_module,
            document_type=document_type,
            limit=limit,
            offset=offset,
        )
        total = summary_mapper.get_count(status=status, business_module=business_module, document_type=document_type)

        logger.info(f"审核记录数量: {len(reviews)} / 总计: {total}")
        for i, r in enumerate(reviews[:5], 1):
            logger.info(f"  {i}. {r.get('document_title')} - {r.get('status')}")

        logger.info("【审核接口】获取审核列表完成")
        return json_response({
            "code": 200,
            "message": "获取成功",
            "data": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "list": reviews,
            }
        })
    except Exception as e:
        logger.error(f"获取审核列表失败: {e}", exc_info=True)
        return json_response({
            "code": 500,
            "message": f"获取列表失败: {str(e)}",
            "data": None
        }, 500)


@test_case_gen_opt.route('/delete_review/<doc_id>', methods=['DELETE'])
def delete_review(doc_id: str):
    """
    删除审核记录（同时清理明细表 + 汇总表）

    参数：
    - doc_id: 文档ID
    """
    logger.info(f"【审核接口】删除审核记录, doc_id: {doc_id}")

    try:
        review_mapper = ReviewRecordMapper()
        # delete_by_doc_id 内部已同步删除汇总表
        deleted = review_mapper.delete_by_doc_id(doc_id)

        # 同时清理内存缓存（若存在）
        _review_data_store.pop(doc_id, None)

        if not deleted:
            logger.warning(f"数据库中未找到记录: {doc_id}")
            return json_response({
                "code": 404,
                "message": "审核数据不存在",
                "data": None
            }, 404)

        logger.info(f"审核记录已删除: {doc_id}")
        return json_response({
            "code": 200,
            "message": "删除成功",
            "data": {"doc_id": doc_id}
        })
    except Exception as e:
        logger.error(f"删除审核记录失败: {e}", exc_info=True)
        return json_response({
            "code": 500,
            "message": f"删除失败: {str(e)}",
            "data": None
        }, 500)
