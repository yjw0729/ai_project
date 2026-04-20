"""
LLM层模块索引。

提供功能：
- llm_client: 通义千问 API 客户端（HTTP调用、重试、错误分类）
- ai_case_generator: 基于 LLM 生成测试用例
- api_doc_analyzer: API文档分析器（OpenAPI / Swagger / 流程图）
- api_test_prompts: 测试用例生成 Prompt 模板
- prompt_manager: Prompt 管理器
- doc_parser: 文档解析器
"""

from common.llm.llm_client import LLMClient, MockLLMClient, chat, chat_with_prompt, get_client
from common.llm.ai_case_generator import generate_api_test_cases
from common.llm.api_doc_analyzer import APIDocAnalyzer, FlowchartAnalyzer
from common.llm.enhanced_case_generator import EnhancedCaseGenerator, generate_test_cases

__all__ = [
    # 客户端
    "LLMClient",
    "MockLLMClient",
    "chat",
    "chat_with_prompt",
    "get_client",
    # 用例生成
    "generate_api_test_cases",
    "EnhancedCaseGenerator",
    "generate_test_cases",
    # 文档分析
    "APIDocAnalyzer",
    "FlowchartAnalyzer",
]
