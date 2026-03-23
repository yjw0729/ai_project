# shared/llm-sdk/llm_client.py
"""
LLM客户端SDK - 跨服务共享的LLM调用客户端。

本模块封装了通义千问等LLM API的调用，提供：
- HTTP请求封装
- 重试机制
- 错误分类和友好提示
- 同步/异步调用

注意：本模块从 common.llm.llm_client 重新导出核心组件，
      供其他服务（如 workers/）独立使用。
"""

from common.llm.llm_client import (
    LLMClient,
    MockLLMClient,
    OpenAILLMClient,
    chat,
    chat_with_prompt,
    get_client,
    DASHSCOPE_API_URL,
    DEFAULT_MODEL,
)

__version__ = "1.0.0"

__all__ = [
    "LLMClient",
    "MockLLMClient",
    "OpenAILLMClient",
    "chat",
    "chat_with_prompt",
    "get_client",
    "DASHSCOPE_API_URL",
    "DEFAULT_MODEL",
]
