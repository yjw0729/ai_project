import json
import os
from functools import lru_cache
from typing import Any, Dict


@lru_cache()
def load_ai_config() -> Dict[str, Any]:
    """
    读取 app/ai_config.json 配置。
    优先从环境变量覆盖敏感项（如 api_key）。
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # 项目根目录下的utils/../..
    config_path = os.path.join(base_dir, "app", "ai_config.json")
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}

    # 环境变量覆盖敏感信息
    api_key_env = os.environ.get("QWEN_API_KEY")
    if api_key_env:
        data["api_key"] = api_key_env
    base_url_env = os.environ.get("QWEN_BASE_URL")
    if base_url_env:
        data["base_url"] = base_url_env
    model_env = os.environ.get("QWEN_MODEL")
    if model_env:
        data["model"] = model_env

    return data




