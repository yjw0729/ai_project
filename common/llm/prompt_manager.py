# -*- coding: utf-8 -*-
"""
提示词管理器
统一管理系统中所有大模型调用的提示词模板，支持从配置文件加载和回退机制
"""

import os
import logging
from typing import Dict, Optional, Any
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# 默认配置文件路径
DEFAULT_PROMPTS_FILE = "app/prompts.yaml"


class PromptManager:
    """
    提示词管理器
    
    特性：
    1. 从YAML配置文件加载提示词模板
    2. 支持回退机制：如果配置文件不存在或加载失败，使用代码中的默认值
    3. 支持动态参数格式化
    """
    
    _instance: Optional['PromptManager'] = None
    
    def __new__(cls, config_path: Optional[str] = None):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_path: Optional[str] = None):
        if self._initialized:
            return
        
        self._initialized = True
        self._config_path = config_path or self._find_config_file()
        self._prompts: Dict[str, Any] = {}
        self._load_config()
    
    def _find_config_file(self) -> str:
        """查找配置文件"""
        # 首先检查环境变量
        env_path = os.environ.get('PROMPTS_CONFIG_PATH')
        if env_path and os.path.exists(env_path):
            return env_path
        
        # 尝试多个可能的路径
        possible_paths = [
            DEFAULT_PROMPTS_FILE,
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), DEFAULT_PROMPTS_FILE),
            os.path.join(os.getcwd(), DEFAULT_PROMPTS_FILE),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"找到提示词配置文件: {path}")
                return path
        
        # 使用默认路径（即使不存在，也会回退到代码默认值）
        logger.warning(f"未找到提示词配置文件，将使用代码默认值: {possible_paths[0]}")
        return possible_paths[0]
    
    def _load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self._config_path):
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    self._prompts = yaml.safe_load(f) or {}
                logger.info(f"成功加载提示词配置文件: {self._config_path}, 共 {len(self._prompts)} 个顶级配置")
            else:
                logger.warning(f"提示词配置文件不存在: {self._config_path}，将使用代码默认值")
                self._prompts = {}
        except yaml.YAMLError as e:
            logger.error(f"解析提示词配置文件失败: {e}，将使用代码默认值")
            self._prompts = {}
        except Exception as e:
            logger.error(f"加载提示词配置文件失败: {e}，将使用代码默认值")
            self._prompts = {}
    
    def reload(self):
        """重新加载配置"""
        self._prompts = {}
        self._load_config()
    
    def get_prompt(self, category: str, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        获取指定类别的prompt
        
        Args:
            category: 顶级分类（如 test_case_generation, iteration, document, qa）
            key: 子键（如 feature_with_context, new_feature, prd, default）
            default: 如果不存在，返回的默认值
            
        Returns:
            提示词模板字符串，如果都不存在返回default
        """
        # 尝试从配置文件获取
        if category in self._prompts:
            category_prompts = self._prompts[category]
            if isinstance(category_prompts, dict) and key in category_prompts:
                return category_prompts[key]
        
        # 返回默认值
        if default:
            return default
        
        logger.warning(f"未找到提示词: {category}.{key}，请检查配置文件")
        return None
    
    def get_test_case_prompt(self, prompt_type: str = "feature_with_context", 
                              default: Optional[str] = None) -> str:
        """获取测试用例生成的prompt"""
        return self.get_prompt("test_case_generation", prompt_type, default) or ""
    
    def get_iteration_prompt(self, iteration_type: str = "new_feature",
                             default: Optional[str] = None) -> str:
        """获取版本迭代场景的prompt"""
        return self.get_prompt("iteration", iteration_type, default) or ""
    
    def get_document_prompt(self, doc_type: str = "both",
                           default: Optional[str] = None) -> str:
        """获取文档类型prompt"""
        return self.get_prompt("document", doc_type, default) or ""
    
    def get_qa_prompt(self, default: Optional[str] = None) -> str:
        """获取智能问答prompt"""
        return self.get_prompt("qa", "default", default) or ""
    
    def get_api_case_prompt(self, default: Optional[str] = None) -> str:
        """获取API用例生成默认prompt"""
        return self.get_prompt("api_case", "default", default) or ""
    
    def get_llm_config(self) -> Dict[str, Any]:
        """获取LLM默认配置"""
        return self._prompts.get("llm_defaults", {
            "temperature": 0.7,
            "max_tokens": 4000
        })

    # ============================================================
    # 文档解析相关提示词
    # ============================================================

    def get_doc_structure_prompt(self, default: Optional[str] = None) -> str:
        """获取技术文档结构拆分提示词"""
        return self.get_prompt("document", "doc_structure", default) or ""

    def get_requirement_pre_analysis_prompt(self, default: Optional[str] = None) -> str:
        """获取需求文档预分析提示词"""
        return self.get_prompt("document", "requirement_pre_analysis", default) or ""

    def get_requirement_structure_prompt(self, default: Optional[str] = None) -> str:
        """获取需求文档结构拆分提示词"""
        return self.get_prompt("document", "requirement_structure", default) or ""

    # ============================================================
    # API文档处理相关提示词
    # ============================================================

    def get_api_pre_analysis_prompt(self, default: Optional[str] = None) -> str:
        """获取API文档预分析提示词"""
        return self.get_prompt("api_document", "pre_analysis", default) or ""

    def get_interface_json_extract_prompt(self, default: Optional[str] = None) -> str:
        """获取接口JSON示例提取提示词"""
        return self.get_prompt("api_document", "json_extract", default) or ""

    # ============================================================
    # 测试用例生成相关提示词
    # ============================================================

    def get_context_info_prompt(self, default: Optional[str] = None) -> str:
        """获取背景信息提示词"""
        return self.get_prompt("test_case", "context_info", default) or ""

    def get_test_case_format_prompt(self, default: Optional[str] = None) -> str:
        """获取测试用例格式规范提示词"""
        return self.get_prompt("test_case", "test_case_format", default) or ""

    def get_single_interface_prompt(self, default: Optional[str] = None) -> str:
        """获取单接口测试用例生成提示词"""
        return self.get_prompt("test_case", "single_interface", default) or ""

    # ============================================================
    # 增强模式测试用例生成相关提示词
    # ============================================================

    def get_feature_analysis_prompt(self, default: Optional[str] = None) -> str:
        """获取功能分析提示词"""
        return self.get_prompt("enhanced_test_case", "feature_analysis", default) or ""

    def get_feature_test_case_prompt(self, with_context: bool = True,
                                      default: Optional[str] = None) -> str:
        """获取功能测试用例生成提示词"""
        key = "test_case_with_context" if with_context else "test_case_fallback"
        return self.get_prompt("enhanced_test_case", key, default) or ""

    # ============================================================
    # 场景配置
    # ============================================================

    def get_scene_config(self, scene: str) -> Dict[str, Any]:
        """获取场景配置"""
        llm_config = self.get_llm_config()
        return llm_config.get("scene_config", {}).get(scene, {
            "temperature": llm_config.get("temperature", 0.2),
            "max_tokens": llm_config.get("max_tokens", 4000)
        })
    
    def format_prompt(self, template: str, **kwargs) -> str:
        """
        格式化prompt模板
        
        Args:
            template: 提示词模板
            **kwargs: 格式化参数
            
        Returns:
            格式化后的提示词
        """
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"格式化prompt时缺少参数: {e}，将使用原模板")
            return template


# 全局单例
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager(config_path: Optional[str] = None) -> PromptManager:
    """获取提示词管理器单例"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager(config_path)
    return _prompt_manager


# 便捷函数
def get_test_case_prompt(prompt_type: str = "feature_with_context", 
                         default: Optional[str] = None) -> str:
    """获取测试用例生成的prompt（便捷函数）"""
    return get_prompt_manager().get_test_case_prompt(prompt_type, default)


def get_iteration_prompt(iteration_type: str = "new_feature",
                        default: Optional[str] = None) -> str:
    """获取版本迭代场景的prompt（便捷函数）"""
    return get_prompt_manager().get_iteration_prompt(iteration_type, default)


def get_document_prompt(doc_type: str = "both",
                        default: Optional[str] = None) -> str:
    """获取文档类型prompt（便捷函数）"""
    return get_prompt_manager().get_document_prompt(doc_type, default)


def get_qa_prompt(default: Optional[str] = None) -> str:
    """获取智能问答prompt（便捷函数）"""
    return get_prompt_manager().get_qa_prompt(default)


def get_api_case_prompt(default: Optional[str] = None) -> str:
    """获取API用例生成默认prompt（便捷函数）"""
    return get_prompt_manager().get_api_case_prompt(default)


def format_prompt(template: str, **kwargs) -> str:
    """格式化prompt（便捷函数）"""
    return get_prompt_manager().format_prompt(template, **kwargs)


# ============================================================
# 文档解析相关便捷函数
# ============================================================

def get_doc_structure_prompt(default: Optional[str] = None) -> str:
    """获取技术文档结构拆分提示词"""
    return get_prompt_manager().get_doc_structure_prompt(default)


def get_requirement_pre_analysis_prompt(default: Optional[str] = None) -> str:
    """获取需求文档预分析提示词"""
    return get_prompt_manager().get_requirement_pre_analysis_prompt(default)


def get_requirement_structure_prompt(default: Optional[str] = None) -> str:
    """获取需求文档结构拆分提示词"""
    return get_prompt_manager().get_requirement_structure_prompt(default)


# ============================================================
# API文档处理相关便捷函数
# ============================================================

def get_api_pre_analysis_prompt(default: Optional[str] = None) -> str:
    """获取API文档预分析提示词"""
    return get_prompt_manager().get_api_pre_analysis_prompt(default)


def get_interface_json_extract_prompt(default: Optional[str] = None) -> str:
    """获取接口JSON示例提取提示词"""
    return get_prompt_manager().get_interface_json_extract_prompt(default)


# ============================================================
# 测试用例生成相关便捷函数
# ============================================================

def get_context_info_prompt(default: Optional[str] = None) -> str:
    """获取背景信息提示词"""
    return get_prompt_manager().get_context_info_prompt(default)


def get_test_case_format_prompt(default: Optional[str] = None) -> str:
    """获取测试用例格式规范提示词"""
    return get_prompt_manager().get_test_case_format_prompt(default)


def get_single_interface_prompt(default: Optional[str] = None) -> str:
    """获取单接口测试用例生成提示词"""
    return get_prompt_manager().get_single_interface_prompt(default)


# ============================================================
# 增强模式测试用例生成相关便捷函数
# ============================================================

def get_feature_analysis_prompt(default: Optional[str] = None) -> str:
    """获取功能分析提示词"""
    return get_prompt_manager().get_feature_analysis_prompt(default)


def get_feature_test_case_prompt(with_context: bool = True,
                                  default: Optional[str] = None) -> str:
    """获取功能测试用例生成提示词"""
    return get_prompt_manager().get_feature_test_case_prompt(with_context, default)


# ============================================================
# 场景配置便捷函数
# ============================================================

def get_scene_config(scene: str) -> Dict[str, Any]:
    """获取场景配置"""
    return get_prompt_manager().get_scene_config(scene)
