import yaml
import os
from typing import Any, Dict

def read_yaml_file(file_path: str) -> Dict[str, Any]:
    """
    读取 YAML 配置文件
    
    Args:
        file_path: YAML 文件路径
        
    Returns:
        解析后的字典数据
    """
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
    """
    写入数据到 YAML 文件
    
    Args:
        file_path: YAML 文件路径
        data: 要写入的数据
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
    except Exception as e:
        raise Exception(f"Error writing YAML file: {e}")