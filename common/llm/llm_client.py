"""
轻量版大模型客户端。

功能目标：
- 调用通义千问 DashScope 的兼容 OpenAI 接口生成内容。
- 记录请求/响应日志，便于排查问题。
- 提供字符串 prompt 和 messages 两种调用方式，方便现有/后续代码复用。
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


DASHSCOPE_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
DEFAULT_MODEL = "qwen-plus"

# 各模型 max_tokens 上限（超出此值的请求会被自动裁剪到上限）
# 同时记录各模型的上下文窗口大小（tokens）
MODEL_CONTEXT_LIMITS = {
    # VLM 多模态模型
    "qwen-vl-plus":           {"context": 32_000,   "max_output": 8_000},
    "qwen-vl-max":           {"context": 32_000,   "max_output": 8_000},
    "qwen-vl-max-2025-01-15":  {"context": 32_000, "max_output": 8_000},
    "qwen-vl-plus-2025-01-15": {"context": 32_000,"max_output": 8_000},
    # 3.5-plus 高性能模型（128K 上下文窗口）
    "qwen-plus":              {"context": 128_000,  "max_output": 32_000},
    "qwen-plus-2025-01-25":  {"context": 128_000,  "max_output": 32_000},
    "qwen-plus-latest":      {"context": 128_000,  "max_output": 32_000},
    "qwen3.5-plus":          {"context": 128_000,  "max_output": 32_000},
    # turbo 快速模型
    "qwen-turbo":            {"context": 131_072,  "max_output": 8_000},
    "qwen-turbo-latest":     {"context": 131_072,  "max_output": 8_000},
    # max 旗舰模型
    "qwen-max":              {"context": 32_000,   "max_output": 8_000},
    "qwen-max-long":         {"context": 1_048_576,"max_output": 8_000},
}


def _cap_max_tokens(model: str, max_tokens: int) -> int:
    """根据模型限制裁剪 max_tokens，不破坏默认行为。"""
    limits = MODEL_CONTEXT_LIMITS.get(model.lower(), {})
    limit = limits.get("max_output", max_tokens)
    return min(max_tokens, limit)


def get_model_context_limit(model: str) -> int:
    """获取模型的上下文窗口上限（单位: tokens）。"""
    return MODEL_CONTEXT_LIMITS.get(model.lower(), {}).get("context", 32_000)


def estimate_tokens(text: str) -> int:
    """估算文本的 token 数量（按中文4字符≈1 token，英文1单词≈1.3 token 计算）。"""
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    non_chinese = len(text) - chinese_chars
    return int(chinese_chars / 4 + non_chinese / 1.3)


def _normalize_api_url(api_url: str) -> str:
    """确保 url 指向 /chat/completions 终端，兼容未带尾路径的配置。"""
    if not api_url:
        return DASHSCOPE_API_URL
    url = api_url.strip()
    if url.endswith("/chat/completions"):
        return url
    # 处理末尾是否有斜杠
    if url.endswith("/"):
        return url + "chat/completions"
    return url + "/chat/completions"


class LLMClient:
    """封装对大模型的简单调用逻辑。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.2,
        max_tokens: int = 16_384,
        timeout: int = 1200,
        api_url: str = DASHSCOPE_API_URL,
    ) -> None:
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY") or os.getenv("DASH_SCOPE_API_KEY")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.api_url = _normalize_api_url(api_url or DASHSCOPE_API_URL)

        if not self.api_key:
            logger.warning("DASHSCOPE_API_KEY 未配置，调用大模型将会失败。")

    # --- 公共调用入口 ---
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **extra: Any,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        以 messages 形式调用聊天接口。
        返回 (content, raw_response)。
        """
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": _cap_max_tokens(model or self.model, max_tokens or self.max_tokens),
        }
        if extra:
            payload.update(extra)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        logger.info(
            "【大模型请求】url=%s, model=%s, temperature=%s, max_tokens=%s",
            self.api_url,
            payload["model"],
            payload["temperature"],
            payload["max_tokens"],
        )

        resp = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )

        if resp.status_code != 200:
            # 先记录完整错误，再尝试给出可读提示
            logger.error("【大模型响应错误】status_code=%s, body=%s", resp.status_code, resp.text)

            friendly_msg = None
            try:
                err_body = resp.json()
                err_info = (err_body or {}).get("error") or {}
                err_code = (err_info.get("code") or "").lower()
                err_message = err_info.get("message") or resp.text

                if err_code == "arrearage":
                    friendly_msg = (
                        "大模型调用失败：账户欠费或额度不足，请在阿里云控制台处理账单/恢复服务后重试。"
                    )
                elif err_code in {"invalid_authentication", "invalid_api_key"}:
                    friendly_msg = "大模型调用失败：API Key 无效或未授权，请检查配置。"
                elif err_code in {"insufficient_quota", "rate_limit_exceeded"}:
                    friendly_msg = "大模型调用失败：额度或频控限制，请稍后重试或提升配额。"
                elif err_message:
                    friendly_msg = f"大模型调用失败：{err_message}"
            except Exception:
                # 如果解析失败，保持默认行为
                friendly_msg = None

            if friendly_msg:
                raise requests.HTTPError(friendly_msg, response=resp)
            resp.raise_for_status()

        data = resp.json()
        content = self._extract_content(data)
        usage = data.get("usage", {})
        finish_reason = self._extract_finish_reason(data)

        logger.info(
            "【大模型响应】status_code=%s, choices=%s, finish_reason=%s, tokens(p/c/t)=%s/%s/%s, 响应长度=%s, 响应前500字符=%s",
            resp.status_code,
            len(data.get("choices", [])),
            finish_reason,
            usage.get("prompt_tokens", "-"),
            usage.get("completion_tokens", "-"),
            usage.get("total_tokens", "-"),
            len(content) if isinstance(content, str) else 0,
            (content or "")[:500],
        )

        if finish_reason == "length":
            logger.warning("【大模型响应】finish_reason=length，可能因max_tokens导致截断，建议调高max_tokens或精简prompt。")

        return content, data

    def _split_into_chunks(self, text: str, max_chars: int) -> List[str]:
        """
        将长文本按段落分割为多个块，每个块不超过 max_chars 字符。
        优先在段落边界（空行）和句号处分割，保证语义完整性。
        """
        if len(text) <= max_chars:
            return [text]

        chunks = []
        paragraphs = text.split('\n\n')
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            # 如果单个段落就超过 max_chars，再按句子分割
            if len(para) > max_chars:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                sentences = re.split(r'(?<=[。！？.!?])', para)
                for sent in sentences:
                    sent = sent.strip()
                    if not sent:
                        continue
                    if len(current_chunk) + len(sent) + 2 <= max_chars:
                        current_chunk += ("\n\n" if current_chunk else "") + sent
                    else:
                        if current_chunk.strip():
                            chunks.append(current_chunk.strip())
                        current_chunk = sent
                continue
            # 普通段落，检查加入后是否超限
            if len(current_chunk) + len(para) + 2 <= max_chars:
                current_chunk += ("\n\n" if current_chunk else "") + para
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = para

        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        return chunks

    def chat_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        parallel: bool = True,
    ) -> List[str]:
        """
        批量调用 LLM，支持并行和串行两种模式。

        Args:
            prompts: 待处理的所有 prompt 列表
            system_prompt: 统一的系统提示词
            max_tokens: 每个请求的最大输出 token 数
            temperature: 温度参数
            parallel: True=并行调用（并发），False=串行调用

        Returns:
            每个 prompt 对应的 LLM 响应列表
        """
        if not prompts:
            return []

        if parallel:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            # 并行调用，并发数限制为 5，避免触发 API 限流
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(
                        self.chat_with_prompt,
                        prompt,
                        system_prompt=system_prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    ): i
                    for i, prompt in enumerate(prompts)
                }
                results = ["" for _ in range(len(prompts))]
                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        content, _ = future.result()
                        results[idx] = content
                    except Exception as e:
                        logger.error("【并行LLM调用】第 %d 个请求失败: %s", idx, str(e))
                        results[idx] = ""
                return results
        else:
            # 串行调用
            results = []
            for i, prompt in enumerate(prompts):
                try:
                    content, _ = self.chat_with_prompt(
                        prompt,
                        system_prompt=system_prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    results.append(content)
                except Exception as e:
                    logger.error("【串行LLM调用】第 %d/%d 个请求失败: %s", i + 1, len(prompts), str(e))
                    results.append("")
            return results

    def chat_with_prompt(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        以单个 prompt 调用，自动组装成 messages。
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages=messages, **kwargs)

    # 兼容旧调用：直接传 prompt，返回 content
    def complete(self, prompt: str, **kwargs: Any) -> str:
        content, _ = self.chat_with_prompt(prompt=prompt, **kwargs)
        return content

    # --- 辅助方法 ---
    @staticmethod
    def _extract_content(resp_json: Dict[str, Any]) -> str:
        choices = resp_json.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        return message.get("content", "")

    @staticmethod
    def _extract_finish_reason(resp_json: Dict[str, Any]) -> str:
        choices = resp_json.get("choices") or []
        if not choices:
            return ""
        return choices[0].get("finish_reason", "")


# 便捷的模块级实例和函数，兼容旧用法
_default_client: Optional[LLMClient] = None


def get_client() -> LLMClient:
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client


def chat(messages: List[Dict[str, str]], **kwargs: Any) -> Tuple[str, Dict[str, Any]]:
    """
    便捷函数：直接传入 messages，返回 (content, raw_response)。
    """
    return get_client().chat(messages=messages, **kwargs)


def chat_with_prompt(prompt: str, system_prompt: Optional[str] = None, **kwargs: Any) -> Tuple[str, Dict[str, Any]]:
    """
    便捷函数：传入纯文本 prompt，自动组装 messages。
    """
    return get_client().chat_with_prompt(prompt=prompt, system_prompt=system_prompt, **kwargs)


class MockLLMClient:
    """
    轻量 mock，用于离线/测试场景，避免真实调用大模型。

    - 支持传入 mock_response 覆盖默认返回
    - 接口与真实 client 的 `complete`/`chat`/`chat_with_prompt` 基本兼容
    """

    def __init__(self, mock_response: Optional[str] = None) -> None:
        self.mock_response = mock_response

    def complete(self, prompt: str, **kwargs: Any) -> str:
        if self.mock_response is not None:
            return self.mock_response

        # 默认返回一个简单的用例列表，保持解析流程可运行
        return (
            '[{"id":"MOCK_TC_001","title":"Mock case","priority":"P1","tags":["mock"],'
            '"request":{"method":"POST","path":"/mock","headers":{},"query":{},"body":{}},'
            '"expect":"mock expect","status_code":200,"assertions":["status_code == 200"]}]'
        )

    def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> Tuple[str, Dict[str, Any]]:
        # 将 messages 拼接为 prompt，走 complete 逻辑
        prompt_parts = []
        for m in messages or []:
            role = m.get("role", "user")
            content = m.get("content", "")
            prompt_parts.append(f"[{role}] {content}")
        prompt = "\n".join(prompt_parts)
        content = self.complete(prompt, **kwargs)
        return content, {"choices": [{"message": {"content": content}}]}

    def chat_with_prompt(self, prompt: str, system_prompt: Optional[str] = None, **kwargs: Any) -> Tuple[str, Dict[str, Any]]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages=messages, **kwargs)


# 兼容旧代码的别名，OpenAI 兼容模式已在 LLMClient 内实现
class OpenAILLMClient(LLMClient):
    """
    保留历史名称的兼容包装，功能与 LLMClient 相同。
    """

    def __init__(self, base_url: Optional[str] = None, **kwargs: Any) -> None:
        # 历史代码使用 base_url 参数，这里兼容并映射到 api_url
        api_url = _normalize_api_url(base_url or kwargs.pop("api_url", None) or DASHSCOPE_API_URL)
        super().__init__(api_url=api_url, **kwargs)
