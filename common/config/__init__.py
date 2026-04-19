# common/config/__init__.py
"""统一配置加载模块。

提供通用配置加载、AI 配置、XML 配置、YAML 配置等功能。
"""

import json
import os
import yaml
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

# xml 读取工具
try:
    import xml.etree.cElementTree as XMLTree
except ImportError:
    import xml.etree.ElementTree as XMLTree


# =========================================================================
# 通用配置加载（带缓存）
# =========================================================================

_config_cache: Dict[str, Any] = {}


def get_config_path(config_name: str) -> Path:
    """获取配置文件路径"""
    base_dir = Path(__file__).parent.parent.parent
    return base_dir / "common" / "config" / config_name


def load_config(config_name: str, use_cache: bool = True) -> Dict[str, Any]:
    """加载配置文件"""
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


def reload_config(config_name: str) -> Dict[str, Any]:
    """重新加载配置文件（清除缓存）"""
    global _config_cache
    _config_cache.pop(config_name, None)
    return load_config(config_name, use_cache=False)


def get_sql_config() -> Dict[str, Any]:
    """获取SQL配置文件"""
    return load_config("sql_config.json")


def get_sql_query(query_key: str) -> Optional[str]:
    """获取SQL查询语句"""
    sql_config = get_sql_config()
    queries = sql_config.get("review_queries", {})
    return queries.get(query_key)


def get_default_settings() -> Dict[str, Any]:
    """获取默认设置"""
    sql_config = get_sql_config()
    return sql_config.get("default_settings", {})


# =========================================================================
# AI 配置（app/ai_config.json）
# =========================================================================

@lru_cache()
def load_ai_config() -> Dict[str, Any]:
    """
    读取 app/ai_config.json 配置。
    优先从环境变量覆盖敏感项（如 api_key）。
    """
    return _load_ai_config_impl()


def load_ai_config_refresh() -> Dict[str, Any]:
    """强制重新读取配置，绕过 lru_cache"""
    load_ai_config.cache_clear()
    return _load_ai_config_impl()


def _load_ai_config_impl() -> Dict[str, Any]:
    base_dir = Path(__file__).parent.parent.parent
    config_path = base_dir / "app" / "ai_config.json"
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    if os.environ.get("QWEN_API_KEY"):
        data["api_key"] = os.environ["QWEN_API_KEY"]
    if os.environ.get("QWEN_BASE_URL"):
        data["base_url"] = os.environ["QWEN_BASE_URL"]
    if os.environ.get("QWEN_MODEL"):
        data["model"] = os.environ["QWEN_MODEL"]
    return data


# =========================================================================
# XML 配置（application.xml、eqlog.xml）
# =========================================================================

def get_xml_path(filename: Optional[str] = None) -> str:
    """
    获取 XML 配置文件路径。

    Args:
        filename: 配置文件名称（可选，默认自动查找 application.xml 或 eqlog.xml）

    Returns:
        配置文件绝对路径，不存在则返回空字符串
    """
    base_dir = Path(__file__).parent.parent.parent
    if filename is None:
        for name in ('application.xml', 'eqlog.xml'):
            xml_path = base_dir / "app" / name
            if xml_path.exists():
                return str(xml_path)
        return ''
    xml_path = base_dir / "app" / filename
    return str(xml_path) if xml_path.exists() else ''


def read_xml(xml_path: str, dir_type: str = 'mock_out_path') -> str:
    """
    解析 XML 配置文件，读取指定目录类型的路径。

    Args:
        xml_path: XML 配置文件路径
        dir_type: 配置节点路径，如 'file_path'、'mock_out_path'

    Returns:
        解析后的路径字符串（根据操作系统自动选择 win_path / linux_path）
    """
    result = ''
    if not xml_path:
        return result
    try:
        xml_tree = XMLTree.parse(xml_path)
        xml_root = xml_tree.getroot()
        system_name = os.name.lower()
        if system_name == 'nt':  # Windows
            result = xml_root.find(dir_type).find('win_path').text
        elif system_name == 'posix':  # Linux / macOS
            result = xml_root.find(dir_type).find('linux_path').text
        else:
            result = xml_root.find(dir_type).find('linux_path').text
    except Exception:
        pass
    return result or ''


# =========================================================================
# YAML 配置
# =========================================================================

def read_yaml_file(file_path: str) -> Dict[str, Any]:
    """读取 YAML 配置文件"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"YAML file not found: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return data or {}
    except yaml.YAMLError as e:
        raise ValueError(f"YAML parsing error: {e}")
    except Exception as e:
        raise Exception(f"Error reading YAML file: {e}")


def write_yaml_file(file_path: str, data: Dict[str, Any]) -> None:
    """写入数据到 YAML 文件"""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
    except Exception as e:
        raise Exception(f"Error writing YAML file: {e}")


# =========================================================================
# 日志目录初始化
# =========================================================================

def create_log_file() -> str:
    """
    确保日志目录存在，并返回默认的日志文件路径。

    Returns:
        日志文件的绝对路径（logs/app_flask.log）
    """
    base_dir = Path(__file__).parent.parent.parent
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / "app_flask.log"
    # 创建文件（若不存在），确保文件可写
    log_file.touch(exist_ok=True)
    return str(log_file)
