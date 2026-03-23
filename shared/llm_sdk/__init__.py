# shared/llm_sdk/__init__.py
"""
LLM SDK 共享包。

本包提供跨服务共享的 LLM 客户端封装。
核心实现位于 common.llm，本包提供统一的导入接口。
"""

from common.llm.llm_client import LLMClient, MockLLMClient, chat, chat_with_prompt, get_client

__all__ = [
    "LLMClient",
    "MockLLMClient",
    "chat",
    "chat_with_prompt",
    "get_client",
]
