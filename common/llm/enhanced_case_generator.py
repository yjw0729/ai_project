"""
增强的用例生成器

核心设计：
1. 先清洗后使用 - 业务上下文会经过 LLM 清洗
2. RAG 存储干净内容 - 存入 RAG 的都是清洗后的数据
3. 查询直接使用 - 从 RAG 查询的内容已经干净，无需再次清洗
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from common.llm.llm_client import OpenAILLMClient
from common.business_context.context_manager import (
    BusinessContextManager,
    ContextSource,
    CleanedContext,
)

logger = logging.getLogger(__name__)


@dataclass
class GenerationConfig:
    """生成配置"""
    api_name: str = ""
    api_path: str = ""
    api_method: str = "GET"
    api_desc: str = ""
    params_example: Dict[str, Any] = field(default_factory=dict)
    constraints: str = ""

    # 业务上下文 - 支持多种格式
    # 1. 字符串文本
    # 2. 向量数据库查询 (collection_name + query)
    # 3. 已上传的 context_id
    business_context: Optional[Union[str, Dict, int]] = None
    context_name: str = "业务文档"

    # 生成控制
    max_interface_cases: int = 10
    max_scenario_cases: int = 5
    max_context_chars: int = 8000

    # 输出控制
    include_interface_cases: bool = True
    include_scenario_cases: bool = True


@dataclass
class GeneratedCase:
    """生成的单个用例"""
    case_type: str  # "interface" 或 "scenario"
    title: str
    description: str
    priority: str = "P2"
    tags: List[str] = field(default_factory=list)

    # 接口信息（interface 类型）
    method: str = ""
    path: str = ""
    request: Dict[str, Any] = field(default_factory=dict)

    # 场景信息（scenario 类型）
    scenario_name: str = ""
    scenario_description: str = ""
    preconditions: str = ""
    test_steps: List[Dict[str, Any]] = field(default_factory=list)

    # 断言
    expected_results: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_type": self.case_type,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "tags": self.tags,
            "method": self.method,
            "path": self.path,
            "request": self.request,
            "test_steps": self.test_steps,
            "expected_results": self.expected_results,
            "scenario_name": self.scenario_name,
            "scenario_description": self.scenario_description,
            "preconditions": self.preconditions,
        }


@dataclass
class GenerationResult:
    """生成结果"""
    success: bool
    interface_cases: List[GeneratedCase] = field(default_factory=list)
    scenario_cases: List[GeneratedCase] = field(default_factory=list)
    raw_output: str = ""
    context_summary: str = ""
    cleaned_context: CleanedContext = None  # 清洗后的上下文
    errors: List[str] = field(default_factory=list)

    @property
    def all_cases(self) -> List[GeneratedCase]:
        return self.interface_cases + self.scenario_cases

    @property
    def total_count(self) -> int:
        return len(self.interface_cases) + len(self.scenario_cases)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "interface_case_count": len(self.interface_cases),
            "scenario_case_count": len(self.scenario_cases),
            "total_count": self.total_count,
            "interface_cases": [c.to_dict() for c in self.interface_cases],
            "scenario_cases": [c.to_dict() for c in self.scenario_cases],
            "raw_output": self.raw_output,
            "context_summary": self.context_summary,
            "cleaned_content_preview": self.cleaned_context.cleaned_content[:500] if self.cleaned_context else "",
            "structured_knowledge": self.cleaned_context.structured_knowledge if self.cleaned_context else {},
            "errors": self.errors,
        }


class EnhancedCaseGenerator:
    """
    增强的用例生成器

    核心特点：
    1. 自动清洗业务上下文（修正OCR错误、补全缺失内容）
    2. 提取结构化业务知识（实体、流程、规则）
    3. 基于清洗后的干净内容生成用例

    业务上下文来源：
    1. 直接传入文本字符串（会清洗后存入 RAG）
    2. 从 RAG 查询（假设 RAG 中存的是干净内容）
    3. 从文件提取并清洗（PDF/Word/图片）
    4. 复用已有的 context_id

    使用示例:
        generator = EnhancedCaseGenerator(llm_client)

        # 方式1: 文本直接传入（会自动清洗并存入 RAG）
        result = generator.generate({
            "api_name": "创建订单",
            "api_path": "/api/v1/order",
            "api_method": "POST",
            "business_context": "订单流程：用户选择商品 -> 创建订单 -> 支付"
        })

        # 方式2: 从 RAG 查询（直接获取干净内容）
        result = generator.generate({
            "api_name": "创建订单",
            "api_path": "/api/v1/order",
            "api_method": "POST",
            "business_context": {
                "type": "vector_db",
                "collection_name": "documents",
                "query": "订单流程 业务规则"
            }
        })

        # 方式3: 从文件提取并清洗
        result = generator.generate({
            "api_name": "创建订单",
            "api_path": "/api/v1/order",
            "api_method": "POST",
            "business_context": {
                "type": "file",
                "path": "./业务文档.pdf"
            }
        })
    """

    # 接口用例 Prompt
    INTERFACE_CASE_PROMPT = """你是一个专业的 API 测试工程师。请根据以下接口信息和业务上下文生成测试用例。

## 接口信息
- 接口名称: {api_name}
- 接口路径: {api_path}
- HTTP 方法: {api_method}
- 接口描述: {api_desc}
- 参数示例: {params_example}
- 约束条件: {constraints}

## 业务上下文（已清洗的结构化信息）
{business_context}

## 生成要求
1. 生成 {max_cases} 个接口测试用例
2. 覆盖正常场景、边界值、异常情况
3. 每个用例包含: title, description, priority, tags, request, expected_results

## 返回格式（JSON数组）
```json
[
  {{
    "title": "正常场景-登录成功",
    "description": "使用正确的用户名密码登录",
    "priority": "P0",
    "tags": ["正常流程", "smoke"],
    "request": {{
      "method": "POST",
      "path": "/api/v1/login",
      "headers": {{"Content-Type": "application/json"}},
      "body": {{"username": "testuser", "password": "Test123456"}}
    }},
    "expected_results": [
      {{"type": "status_code", "expected": 200}},
      {{"type": "json_path", "path": "$.code", "expected": 0}}
    ]
  }}
]
```
请直接返回 JSON 数组，不要包含其他文字。"""

    # 场景用例 Prompt
    SCENARIO_CASE_PROMPT = """你是一个专业的测试工程师。请根据以下接口和业务上下文生成业务场景测试用例。

## 核心接口信息
- 接口名称: {api_name}
- 接口路径: {api_path}
- HTTP 方法: {api_method}
- 参数示例: {params_example}

## 业务上下文（已清洗的结构化信息）
{business_context}

## 场景生成要求
1. 生成 {max_cases} 个业务场景测试用例
2. 场景包含多个步骤，体现业务流程
3. 后置步骤可引用前置步骤的返回数据
4. 每个步骤使用 extract 字段提取数据供后续使用

## 场景用例格式
```json
[
  {{
    "scenario_name": "用户完整购物流程",
    "title": "正常购物流程-从浏览到支付",
    "description": "用户浏览商品 -> 加入购物车 -> 创建订单 -> 支付",
    "priority": "P0",
    "tags": ["核心流程", "smoke"],
    "preconditions": "用户已登录，购物车为空",
    "test_steps": [
      {{
        "step_number": 1,
        "description": "查询商品列表",
        "api": "GET /api/v1/products",
        "extract": {{"product_id": "$.data[0].id"}},
        "expected_results": [{{"type": "status_code", "expected": 200}}]
      }},
      {{
        "step_number": 2,
        "description": "将商品加入购物车",
        "api": "POST /api/v1/cart",
        "body": {{"product_id": "{{product_id}}", "quantity": 1}},
        "extract": {{"cart_id": "$.data.cart_id"}},
        "expected_results": []
      }},
      {{
        "step_number": 3,
        "description": "创建订单",
        "api": "POST /api/v1/orders",
        "body": {{"cart_id": "{{cart_id}}"}},
        "expected_results": [
          {{"type": "json_path", "path": "$.code", "expected": 0}}
        ]
      }}
    ],
    "expected_results": [{{"type": "contains", "expected": "订单创建成功"}}]
  }}
]
```
请直接返回 JSON 数组，不要包含其他文字。"""

    # 混合生成 Prompt
    MIXED_CASE_PROMPT = """你是一个专业的 API 测试工程师。请根据以下信息生成完整的测试用例集。

## 接口信息
- 接口名称: {api_name}
- 接口路径: {api_path}
- HTTP 方法: {api_method}
- 接口描述: {api_desc}
- 参数示例: {params_example}
- 约束条件: {constraints}

## 业务上下文（已清洗的结构化信息）
{business_context}

## 生成要求
1. 生成接口测试用例: {max_interface_cases} 个（参数验证、边界值、异常处理）
2. 生成业务场景测试用例: {max_scenario_cases} 个（多步骤流程测试）

## 返回格式
```json
{{
  "interface_cases": [
    {{
      "case_type": "interface",
      "title": "正常场景-登录成功",
      "description": "使用正确的用户名密码登录",
      "priority": "P0",
      "tags": ["正常流程"],
      "method": "POST",
      "path": "/api/v1/login",
      "request": {{
        "headers": {{"Content-Type": "application/json"}},
        "body": {{"username": "testuser", "password": "Test123456"}}
      }},
      "expected_results": [
        {{"type": "status_code", "expected": 200}}
      ]
    }}
  ],
  "scenario_cases": [
    {{
      "case_type": "scenario",
      "scenario_name": "用户登录后下单",
      "title": "登录-选择商品-下单",
      "description": "用户登录后选择商品并下单",
      "priority": "P0",
      "tags": ["核心流程"],
      "preconditions": "测试商品存在",
      "test_steps": [
        {{
          "step_number": 1,
          "description": "用户登录",
          "api": "POST /api/v1/login",
          "extract": {{"token": "$.data.token"}},
          "expected_results": []
        }},
        {{
          "step_number": 2,
          "description": "查询商品",
          "api": "GET /api/v1/products",
          "headers": {{"Authorization": "Bearer {{token}}"}},
          "extract": {{"product_id": "$.data[0].id"}},
          "expected_results": []
        }},
        {{
          "step_number": 3,
          "description": "创建订单",
          "api": "POST /api/v1/orders",
          "headers": {{"Authorization": "Bearer {{token}}"}},
          "body": {{"product_id": "{{product_id}}"}},
          "expected_results": [
            {{"type": "json_path", "path": "$.code", "expected": 0}}
          ]
        }}
      ],
      "expected_results": [{{"type": "contains", "expected": "订单创建成功"}}]
    }}
  ]
}}
```
请直接返回 JSON 对象，不要包含其他文字。"""

    def __init__(self, llm_client: Optional[OpenAILLMClient] = None, ai_type: Optional[str] = None):
        import logging as _logging
        _logger = _logging.getLogger(__name__)
        if llm_client is not None and ai_type is not None:
            _logger.warning(
                "【EnhancedCaseGenerator】同时传入了 llm_client 和 ai_type，"
                "ai_type 将被忽略，以 llm_client 为准。"
            )
        if ai_type:
            from common.llm.llm_client import LLMClient
            self.llm_client = LLMClient.from_model(ai_type)
        else:
            self.llm_client = llm_client
        self.context_manager = BusinessContextManager(self.llm_client)

    def _prepare_context_source(self, config: GenerationConfig) -> Optional[ContextSource]:
        """准备业务上下文来源"""
        if not config.business_context:
            return None

        # 1. 字符串直接返回
        if isinstance(config.business_context, str):
            return ContextSource(
                source_type="text",
                content=config.business_context
            )

        # 2. 字典格式
        if isinstance(config.business_context, dict):
            ctx_type = config.business_context.get("type", "text")

            if ctx_type == "vector_db":
                return ContextSource(
                    source_type="vector_db",
                    vector_query=config.business_context.get("query", f"{config.api_name} 业务规则 流程"),
                    collection_name=config.business_context.get("collection_name", "documents"),
                    top_k=config.business_context.get("top_k", 5)
                )

            elif ctx_type == "context_id":
                return ContextSource(
                    source_type="context_id",
                    context_id=config.business_context.get("id")
                )

            elif ctx_type == "file":
                return ContextSource(
                    source_type="file",
                    file_path=config.business_context.get("path", "")
                )

            elif ctx_type == "image":
                return ContextSource(
                    source_type="image",
                    file_path=config.business_context.get("path") or config.business_context.get("data", "")
                )

            elif ctx_type == "text":
                return ContextSource(
                    source_type="text",
                    content=config.business_context.get("content", "")
                )

        # 3. 整数 ID
        if isinstance(config.business_context, int):
            return ContextSource(
                source_type="context_id",
                context_id=config.business_context
            )

        return None

    def _build_context_text(self, cleaned: CleanedContext, max_chars: int = 8000) -> str:
        """构建业务上下文文本（用于生成 Prompt）"""
        if not cleaned:
            return "无业务上下文"

        # 优先使用结构化知识
        if cleaned.structured_knowledge:
            parts = [cleaned.cleaned_content]

            # 添加结构化知识
            sk = cleaned.structured_knowledge

            if sk.get("entities"):
                parts.append(f"\n\n【业务实体】\n" + "\n".join(f"- {e}" for e in sk["entities"]))

            if sk.get("processes"):
                parts.append("\n\n【业务流程】")
                for proc in sk["processes"]:
                    parts.append(f"\n流程: {proc.get('name', '未命名')}")
                    parts.append(f"描述: {proc.get('description', '')}")
                    steps = proc.get("steps", [])
                    for i, step in enumerate(steps, 1):
                        parts.append(f"  {i}. {step}")

            if sk.get("rules"):
                parts.append("\n\n【业务规则】")
                for rule in sk["rules"]:
                    parts.append(f"- {rule}")

            if sk.get("constraints"):
                parts.append("\n\n【约束条件】")
                for c in sk["constraints"]:
                    parts.append(f"- {c}")

            if sk.get("error_cases"):
                parts.append("\n\n【异常情况】")
                for err in sk["error_cases"]:
                    parts.append(f"- {err}")

            text = "\n".join(parts)
        else:
            text = cleaned.cleaned_content or cleaned.original_content

        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n... (内容过长，已截断，总计 {len(text)} 字符)"

        return text

    def _parse_json_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """解析 JSON 响应"""
        try:
            text = response_text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            try:
                cleaned = text.replace(r'[\x00-\x1f\x7f-\x9f]', '')
                return json.loads(cleaned)
            except:
                return None

    def _convert_to_case(self, case_data: Dict[str, Any], default_path: str = "", default_method: str = "") -> GeneratedCase:
        """将字典转换为 GeneratedCase"""
        case_type = case_data.get("case_type", "")
        if not case_type:
            if case_data.get("test_steps") and len(case_data.get("test_steps", [])) > 1:
                case_type = "scenario"
            else:
                case_type = "interface"

        if case_type == "scenario":
            steps = case_data.get("test_steps", [])
            first_step = steps[0] if steps else {}
            first_api = first_step.get("api", "")

            return GeneratedCase(
                case_type="scenario",
                title=case_data.get("title", case_data.get("scenario_name", "未命名场景")),
                description=case_data.get("description", ""),
                priority=case_data.get("priority", "P2"),
                tags=case_data.get("tags", []),
                scenario_name=case_data.get("scenario_name", ""),
                scenario_description=case_data.get("description", ""),
                preconditions=case_data.get("preconditions", ""),
                test_steps=steps,
                expected_results=case_data.get("expected_results", []),
                method=first_api.split()[0] if first_api else default_method,
                path=first_api.split()[1] if len(first_api.split()) > 1 else default_path,
            )
        else:
            request = case_data.get("request", {})
            if isinstance(request, dict):
                method = request.get("method", default_method)
                path = request.get("path", default_path)
            else:
                method = default_method
                path = default_path

            return GeneratedCase(
                case_type="interface",
                title=case_data.get("title", "未命名用例"),
                description=case_data.get("description", ""),
                priority=case_data.get("priority", "P2"),
                tags=case_data.get("tags", []),
                method=method,
                path=path,
                request=request if isinstance(request, dict) else {},
                expected_results=case_data.get("expected_results", []),
            )

    def generate(self, config: Union[GenerationConfig, Dict[str, Any]]) -> GenerationResult:
        """
        生成测试用例

        Args:
            config: 生成配置

        Returns:
            GenerationResult: 生成结果
        """
        if isinstance(config, dict):
            config = GenerationConfig(**config)

        result = GenerationResult(success=False)

        # 1. 准备业务上下文来源
        logger.info("开始处理业务上下文...")
        source = self._prepare_context_source(config)
        cleaned_context = None

        if source:
            try:
                if source.source_type == "vector_db":
                    # 从 RAG 查询 - RAG 中存的是干净内容，直接获取
                    logger.info(f"从 RAG 查询: {source.collection_name}")
                    cleaned_context = self.context_manager.get_from_rag(
                        query=source.vector_query,
                        collection_name=source.collection_name,
                        top_k=source.top_k
                    )
                else:
                    # 其他来源：文本/文件/图片 - 需要清洗并存储
                    logger.info(f"清洗业务上下文: {source.source_type}")
                    cleaned_context = self.context_manager.clean_context(
                        source=source,
                        save_to_rag=True,  # 清洗后存入 RAG
                        business_module=config.context_name
                    )

                result.cleaned_context = cleaned_context
                result.context_summary = cleaned_context.summary or f"获取到 {len(cleaned_context.cleaned_content)} 字符"

                if cleaned_context.errors:
                    result.errors.extend(cleaned_context.errors)

                logger.info(f"业务上下文处理完成: {result.context_summary}")

            except Exception as e:
                logger.error(f"处理业务上下文失败: {e}")
                result.errors.append(f"处理业务上下文失败: {str(e)}")

        if not self.llm_client:
            result.errors.append("LLM 客户端未配置")
            return result

        # 2. 构建 Prompt
        context_text = self._build_context_text(cleaned_context, config.max_context_chars)

        # 3. 确定生成模式
        use_mixed = config.include_interface_cases and config.include_scenario_cases and context_text != "无业务上下文"

        try:
            if use_mixed:
                # 混合生成模式
                logger.info("使用混合生成模式...")
                prompt = self.MIXED_CASE_PROMPT.format(
                    api_name=config.api_name,
                    api_path=config.api_path,
                    api_method=config.api_method,
                    api_desc=config.api_desc,
                    params_example=json.dumps(config.params_example, ensure_ascii=False),
                    constraints=config.constraints or "无",
                    business_context=context_text,
                    max_interface_cases=config.max_interface_cases,
                    max_scenario_cases=config.max_scenario_cases,
                )

                response = self.llm_client.chat(prompt)
                response_text = self._extract_text(response)
                result.raw_output = response_text

                parsed = self._parse_json_response(response_text)
                if parsed:
                    for item in parsed.get("interface_cases", []):
                        item["case_type"] = "interface"
                        result.interface_cases.append(
                            self._convert_to_case(item, config.api_path, config.api_method)
                        )
                    for item in parsed.get("scenario_cases", []):
                        item["case_type"] = "scenario"
                        result.scenario_cases.append(
                            self._convert_to_case(item, config.api_path, config.api_method)
                        )
                    result.success = True
                else:
                    result.errors.append("解析 LLM 响应失败")

            elif config.include_scenario_cases and context_text != "无业务上下文":
                # 仅场景用例
                logger.info("使用场景生成模式...")
                prompt = self.SCENARIO_CASE_PROMPT.format(
                    api_name=config.api_name,
                    api_path=config.api_path,
                    api_method=config.api_method,
                    params_example=json.dumps(config.params_example, ensure_ascii=False),
                    business_context=context_text,
                    max_cases=config.max_scenario_cases,
                )

                response = self.llm_client.chat(prompt)
                response_text = self._extract_text(response)
                result.raw_output = response_text

                parsed = self._parse_json_response(response_text)
                if parsed and isinstance(parsed, list):
                    for item in parsed:
                        item["case_type"] = "scenario"
                        result.scenario_cases.append(
                            self._convert_to_case(item, config.api_path, config.api_method)
                        )
                    result.success = True
                else:
                    result.errors.append("解析 LLM 响应失败")

            elif config.include_interface_cases:
                # 仅接口用例
                logger.info("使用接口生成模式...")
                prompt = self.INTERFACE_CASE_PROMPT.format(
                    api_name=config.api_name,
                    api_path=config.api_path,
                    api_method=config.api_method,
                    api_desc=config.api_desc,
                    params_example=json.dumps(config.params_example, ensure_ascii=False),
                    constraints=config.constraints or "无",
                    business_context=context_text,
                    max_cases=config.max_interface_cases,
                )

                response = self.llm_client.chat(prompt)
                response_text = self._extract_text(response)
                result.raw_output = response_text

                parsed = self._parse_json_response(response_text)
                if parsed and isinstance(parsed, list):
                    for item in parsed:
                        item["case_type"] = "interface"
                        result.interface_cases.append(
                            self._convert_to_case(item, config.api_path, config.api_method)
                        )
                    result.success = True
                else:
                    result.errors.append("解析 LLM 响应失败")

        except Exception as e:
            logger.error(f"用例生成失败: {e}", exc_info=True)
            result.errors.append(f"生成异常: {str(e)}")

        return result

    def _extract_text(self, response: Any) -> str:
        """从 LLM 响应中提取文本"""
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            content = response.get("content", [])
            if isinstance(content, list) and content:
                return content[0].get("text", "")
            return response.get("text", "")
        return str(response)


def generate_test_cases(
    api_name: str,
    api_path: str,
    api_method: str = "GET",
    params_example: Dict[str, Any] = None,
    business_context: Union[str, Dict, int] = None,
    llm_client: OpenAILLMClient = None,
    ai_type: Optional[str] = None,
    max_interface_cases: int = 10,
    max_scenario_cases: int = 5,
    **kwargs
) -> GenerationResult:
    """
    便捷的用例生成函数

    Args:
        ai_type: 模型名称，对应 ai_config.json 中 models 下的 key。
                 传入时会优先于 llm_client 创建新客户端。
    """
    config = GenerationConfig(
        api_name=api_name,
        api_path=api_path,
        api_method=api_method,
        params_example=params_example or {},
        business_context=business_context,
        max_interface_cases=max_interface_cases,
        max_scenario_cases=max_scenario_cases,
        **kwargs
    )

    generator = EnhancedCaseGenerator(llm_client, ai_type=ai_type)
    return generator.generate(config)
