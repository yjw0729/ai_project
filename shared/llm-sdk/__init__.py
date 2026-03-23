"""
llm-sdk/ LLM客户端共享包。

本包在服务拆分后独立发布为 pip 包。
"""

from shared.llm_sdk.llm_client import (
    LLMClient,
    MockLLMClient,
    OpenAILLMClient,
    chat,
    chat_with_prompt,
    get_client,
)

__version__ = "1.0.0"

__all__ = [
    "__version__",
    "LLMClient",
    "MockLLMClient",
    "OpenAILLMClient",
    "chat",
    "chat_with_prompt",
    "get_client",
]
