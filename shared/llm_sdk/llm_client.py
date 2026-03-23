"""
LLM 共享客户端 SDK。

本文件是 shared/llm_sdk/ 的主入口模块，
完整实现在 common/llm/llm_client.py 中，此处通过相对路径引用。
本包在拆分时可独立发布为 pip 包。
"""

# 引用核心实现（保持单一数据源，避免代码重复）
from common.llm.llm_client import (
    LLMClient,
    MockLLMClient,
    OpenAILLMClient,
    chat,
    chat_with_prompt,
    get_client,
    DEFAULT_MODEL,
    DASHSCOPE_API_URL,
)

__all__ = [
    "LLMClient",
    "MockLLMClient",
    "OpenAILLMClient",
    "chat",
    "chat_with_prompt",
    "get_client",
    "DEFAULT_MODEL",
    "DASHSCOPE_API_URL",
]
