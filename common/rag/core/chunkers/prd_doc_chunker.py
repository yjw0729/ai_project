#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
产品需求文档(PRD)专用分块器
针对产品设计文档的结构化分块策略，保持功能模块的完整性
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PRDModule:
    """PRD功能模块信息"""
    title: str
    level: int  # 标题级别 (1-6)
    content: str = ""
    features: List[str] = field(default_factory=list)
    user_stories: List[str] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)


class PRDDocChunker:
    """
    产品需求文档分块器
    
    专门处理PRD文档，保持功能模块的完整性：
    - 功能模块
    - 用户故事
    - 验收标准
    - 业务流程
    
    分块策略：
    1. 识别文档的章节结构
    2. 按功能模块进行分块
    3. 保持用户故事和验收标准的关联
    """
    
    def __init__(self, chunk_size: int = 1500, overlap: int = 200):
        """
        初始化PRD文档分块器
        
        Args:
            chunk_size: 目标块大小
            overlap: 块之间的重叠大小
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        
        # PRD常见章节标题
        self.section_keywords = {
            1: ["产品概述", "产品背景", "产品目标", "产品愿景", "产品介绍"],
            2: ["核心功能", "功能列表", "功能模块", "主要功能"],
            3: ["业务流程", "功能详情", "详细设计", "功能描述", "用户场景"],
        }
        
        # 用户故事关键词
        self.user_story_keywords = ["用户故事", "用户场景", "作为", "我希望", "以便", "user story"]
        
        # 验收标准关键词
        self.acceptance_keywords = ["验收标准", "验收条件", "通过条件", "成功标准", "acceptance criteria"]
        
        logger.info(f"PRD文档分块器初始化: chunk_size={chunk_size}, overlap={overlap}")
    
    def chunk(self, content: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        对PRD文档进行分块
        
        Args:
            content: 文档内容
            metadata: 元数据
            
        Returns:
            分块结果列表
        """
        if not content:
            return []
        
        metadata = metadata or {}
        
        # 1. 识别文档结构
        modules = self._extract_modules(content)
        
        if modules:
            # 使用模块化分块
            return self._chunk_by_modules(modules, metadata)
        else:
            # 回退到语义分块
            return self._fallback_chunking(content, metadata)
    
    def _extract_modules(self, content: str) -> List[PRDModule]:
        """提取PRD文档的功能模块"""
        modules = []
        lines = content.split('\n')
        
        current_module = None
        current_section_type = "content"  # content, user_story, acceptance
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检测标题级别
            title_info = self._detect_title(line)
            if title_info:
                # 保存之前的模块
                if current_module:
                    modules.append(current_module)
                
                # 创建新模块
                current_module = PRDModule(
                    title=title_info["title"],
                    level=title_info["level"]
                )
                current_section_type = "content"
                continue
            
            # 检测特殊区域
            section_type = self._detect_special_section(line)
            if section_type:
                current_section_type = section_type
                continue
            
            # 收集内容
            if current_module:
                if current_section_type == "user_story":
                    if self._is_user_story(line):
                        current_module.user_stories.append(line)
                    else:
                        current_module.content += line + "\n"
                elif current_section_type == "acceptance":
                    if self._is_acceptance(line):
                        current_module.acceptance_criteria.append(line)
                    else:
                        current_module.content += line + "\n"
                else:
                    current_module.content += line + "\n"
        
        # 保存最后一个模块
        if current_module:
            modules.append(current_module)
        
        logger.info(f"提取到 {len(modules)} 个功能模块")
        return modules
    
    def _detect_title(self, line: str) -> Optional[Dict]:
        """检测标题"""
        # Markdown标题
        match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if match:
            return {
                "level": len(match.group(1)),
                "title": match.group(2).strip()
            }
        
        # 数字编号标题 (1. 2.3.)
        match = re.match(r'^(\d+(?:\.\d+)*)[.、]\s+(.+)$', line)
        if match:
            level = len(match.group(1).split('.'))
            return {
                "level": min(level, 6),
                "title": match.group(2).strip()
            }
        
        # 中文标题
        for level, keywords in self.section_keywords.items():
            for keyword in keywords:
                if keyword in line and len(line) < 50:
                    return {
                        "level": level,
                        "title": line.strip()
                    }
        
        return None
    
    def _detect_special_section(self, line: str) -> Optional[str]:
        """检测特殊区域"""
        line_lower = line.lower()
        
        # 用户故事区域
        for keyword in self.user_story_keywords:
            if keyword in line_lower:
                return "user_story"
        
        # 验收标准区域
        for keyword in self.acceptance_keywords:
            if keyword in line_lower:
                return "acceptance"
        
        return None
    
    def _is_user_story(self, line: str) -> bool:
        """判断是否是用户故事"""
        story_patterns = [
            r"作为.*希望.*以便",
            r"作为.*我想要.*为了",
            r"as a.*i want.*so that",
            r"用户角色.*功能.*价值"
        ]
        
        for pattern in story_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return True
        
        return False
    
    def _is_acceptance(self, line: str) -> bool:
        """判断是否是验收标准"""
        # 以数字、勾选框、 bullet point 开头
        if re.match(r'^[\d\-\*\•]\s+', line):
            return True
        
        # 包含验收相关关键词
        if any(kw in line.lower() for kw in ["当", "如果", "则", "应该", "必须", "可以"]):
            if len(line) > 10 and len(line) < 200:
                return True
        
        return False
    
    def _chunk_by_modules(
        self, 
        modules: List[PRDModule], 
        metadata: Dict
    ) -> List[Dict[str, Any]]:
        """基于功能模块进行分块"""
        chunks = []
        
        for i, module in enumerate(modules):
            # 构建模块上下文
            chunk_content = self._build_module_context(module)
            
            # 检查是否需要分割
            if len(chunk_content) > self.chunk_size * 1.3:
                sub_chunks = self._split_large_module(module, chunk_content, i, metadata)
                chunks.extend(sub_chunks)
            else:
                chunks.append({
                    "content": chunk_content,
                    "metadata": {
                        **metadata,
                        "doc_type": "prd",
                        "chunk_type": "prd_module",
                        "module_title": module.title,
                        "module_level": module.level,
                        "module_index": i,
                        "total_modules": len(modules)
                    }
                })
        
        return chunks
    
    def _build_module_context(self, module: PRDModule) -> str:
        """构建功能模块的完整上下文"""
        parts = []
        
        # 标题
        level_str = "#" * module.level
        parts.append(f"{level_str} {module.title}")
        
        # 主体内容
        if module.content.strip():
            parts.append(f"\n{module.content.strip()}")
        
        # 用户故事
        if module.user_stories:
            parts.append("\n### 用户故事")
            for story in module.user_stories:
                parts.append(f"- {story}")
        
        # 验收标准
        if module.acceptance_criteria:
            parts.append("\n### 验收标准")
            for criteria in module.acceptance_criteria:
                parts.append(f"- {criteria}")
        
        return "\n".join(parts)
    
    def _split_large_module(
        self, 
        module: PRDModule, 
        content: str, 
        index: int,
        metadata: Dict
    ) -> List[Dict[str, Any]]:
        """分割过大的模块块"""
        chunks = []
        
        # 基础内容块
        level_str = "#" * module.level
        base_content = f"{level_str} {module.title}\n\n"
        if module.content.strip():
            base_content += module.content.strip()
        
        chunks.append({
            "content": base_content.strip(),
            "metadata": {
                **metadata,
                "doc_type": "prd",
                "chunk_type": "prd_base",
                "module_title": module.title,
                "module_level": module.level,
                "module_index": index
            }
        })
        
        # 用户故事块
        if module.user_stories:
            story_content = f"{level_str} {module.title} - 用户故事\n\n"
            for story in module.user_stories:
                story_content += f"- {story}\n"
            
            chunks.append({
                "content": story_content.strip(),
                "metadata": {
                    **metadata,
                    "doc_type": "prd",
                    "chunk_type": "prd_user_stories",
                    "module_title": module.title,
                    "module_level": module.level,
                    "module_index": index
                }
            })
        
        # 验收标准块
        if module.acceptance_criteria:
            criteria_content = f"{level_str} {module.title} - 验收标准\n\n"
            for criteria in module.acceptance_criteria:
                criteria_content += f"- {criteria}\n"
            
            chunks.append({
                "content": criteria_content.strip(),
                "metadata": {
                    **metadata,
                    "doc_type": "prd",
                    "chunk_type": "prd_acceptance",
                    "module_title": module.title,
                    "module_level": module.level,
                    "module_index": index
                }
            })
        
        return chunks
    
    def _fallback_chunking(self, content: str, metadata: Dict) -> List[Dict[str, Any]]:
        """备用分块策略"""
        chunks = []
        
        # 按段落分割
        paragraphs = re.split(r'\n\s*\n', content)
        
        current_chunk = []
        current_size = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            para_size = len(para)
            
            if current_size + para_size > self.chunk_size and current_chunk:
                chunks.append({
                    "content": "\n\n".join(current_chunk),
                    "metadata": {
                        **metadata,
                        "doc_type": "prd",
                        "chunk_type": "paragraph"
                    }
                })
                current_chunk = []
                current_size = 0
            
            current_chunk.append(para)
            current_size += para_size + 2
        
        if current_chunk:
            chunks.append({
                "content": "\n\n".join(current_chunk),
                "metadata": {
                    **metadata,
                    "doc_type": "prd",
                    "chunk_type": "paragraph"
                }
            })
        
        return chunks


def chunk_prd_document(
    content: str, 
    chunk_size: int = 1500, 
    overlap: int = 200,
    metadata: Dict = None
) -> List[Dict[str, Any]]:
    """
    便捷函数：对PRD文档进行分块
    """
    chunker = PRDDocChunker(chunk_size=chunk_size, overlap=overlap)
    return chunker.chunk(content, metadata)

