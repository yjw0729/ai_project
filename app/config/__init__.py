"""
应用配置包
统一管理所有应用配置文件

注意：此包主要用于存放JSON配置文件，
实际的配置逻辑在 common.connectors 包中。
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径，确保可以导入common.connectors
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 延迟导入，避免循环依赖
def _import_config():
    try:
        from common.rag.config_vector_db import (
            VectorDBConfig, VectorDBType, VectorDBConfigManager,
            get_vector_db_config, create_default_vector_db_config
        )
        from common.rag.config_rag import (
            RAGConfig, RAGConfigManager,
            get_rag_config, create_default_rag_config
        )
        from common.rag.config_unified import (
            UnifiedConfig, get_unified_config
        )
        return {
            'VectorDBConfig': VectorDBConfig,
            'VectorDBType': VectorDBType,
            'VectorDBConfigManager': VectorDBConfigManager,
            'get_vector_db_config': get_vector_db_config,
            'create_default_vector_db_config': create_default_vector_db_config,
            'RAGConfig': RAGConfig,
            'RAGConfigManager': RAGConfigManager,
            'get_rag_config': get_rag_config,
            'create_default_rag_config': create_default_rag_config,
            'UnifiedConfig': UnifiedConfig,
            'get_unified_config': get_unified_config
        }
    except ImportError as e:
        raise ImportError(f"无法导入配置模块: {e}. 请确保common.rag包可用。")

# 延迟初始化的配置函数
_config_cache = None

def _get_config():
    global _config_cache
    if _config_cache is None:
        _config_cache = _import_config()
    return _config_cache

# 立即初始化配置，获取所有类和函数
_config_items = _get_config()

# 导出函数
get_vector_db_config = _config_items['get_vector_db_config']
get_rag_config = _config_items['get_rag_config']
get_unified_config = _config_items['get_unified_config']
create_default_vector_db_config = _config_items['create_default_vector_db_config']
create_default_rag_config = _config_items['create_default_rag_config']

# 导出类和枚举
VectorDBConfig = _config_items['VectorDBConfig']
VectorDBType = _config_items['VectorDBType']
VectorDBConfigManager = _config_items['VectorDBConfigManager']
RAGConfig = _config_items['RAGConfig']
RAGConfigManager = _config_items['RAGConfigManager']
UnifiedConfig = _config_items['UnifiedConfig']

__version__ = "1.0.0"

__all__ = [
    # 配置获取函数
    'get_vector_db_config', 'get_rag_config', 'get_unified_config',
    'create_default_vector_db_config', 'create_default_rag_config',

    # 配置类
    'VectorDBConfig', 'VectorDBType', 'VectorDBConfigManager',
    'RAGConfig', 'RAGConfigManager', 'UnifiedConfig'
]
