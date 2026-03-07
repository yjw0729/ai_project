# common/config/__init__.py
"""配置文件加载模块"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

_config_cache: Dict[str, Any] = {}


def get_config_path(config_name: str) -> Path:
    """获取配置文件路径"""
    base_dir = Path(__file__).parent.parent.parent
    return base_dir / "common" / "config" / config_name


def load_config(config_name: str, use_cache: bool = True) -> Dict[str, Any]:
    """
    加载配置文件
    
    Args:
        config_name: 配置文件名 (如 sql_config.json)
        use_cache: 是否使用缓存，默认 True
    
    Returns:
        配置字典
    """
    global _config_cache
    
    if use_cache and config_name in _config_cache:
        return _config_cache[config_name]
    
    config_path = get_config_path(config_name)
    
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    if use_cache:
        _config_cache[config_name] = config
    
    return config


def get_sql_config() -> Dict[str, Any]:
    """获取SQL配置文件"""
    return load_config("sql_config.json")


def reload_config(config_name: str) -> Dict[str, Any]:
    """重新加载配置文件（清除缓存）"""
    global _config_cache
    _config_cache.pop(config_name, None)
    return load_config(config_name, use_cache=False)


def get_sql_query(query_key: str) -> Optional[str]:
    """
    获取SQL查询语句
    
    Args:
        query_key: 查询键名 (如 get_summary_by_doc_id)
    
    Returns:
        SQL语句，如果不存在返回 None
    """
    sql_config = get_sql_config()
    queries = sql_config.get("review_queries", {})
    return queries.get(query_key)


def get_default_settings() -> Dict[str, Any]:
    """获取默认设置"""
    sql_config = get_sql_config()
    return sql_config.get("default_settings", {})
