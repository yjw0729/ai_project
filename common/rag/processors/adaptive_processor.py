#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
差异化文档处理器
根据文档类型采用不同的处理策略，提升向量化效果
"""

import re
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from common.rag.core.models import Document, DocumentChunk
from common.rag.processors.document_classifier import (
    DocumentClassifier, 
    DocumentType, 
    ClassificationResult
)

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """处理结果"""
    chunks: List[DocumentChunk]
    doc_type: DocumentType
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ClassificationResult:
    """分类结果"""
    doc_type: DocumentType
    confidence: float
    features: Dict[str, Any] = field(default_factory=dict)


class AdaptiveDocumentProcessor:
    """
    自适应文档处理器
    
    根据文档类型自动选择最佳处理策略：
    - API文档: 保留参数表格和端点信息
    - 技术文档: 保持代码块完整性
    - 产品文档: 保留结构和功能描述
    - 需求文档: 保持逻辑关联
    """
    
    def __init__(self):
        self.classifier = DocumentClassifier()
        logger.info("自适应文档处理器初始化完成")
    
    def process(
        self, 
        document: Document,
        content: str = None,
        auto_classify: bool = True
    ) -> ProcessingResult:
        """
        处理文档
        
        Args:
            document: 文档对象
            content: 文档内容（可选，默认从document获取）
            auto_classify: 是否自动分类
            
        Returns:
            ProcessingResult: 处理结果
        """
        # 获取内容
        text_content = content or document.content
        
        if not text_content:
            return ProcessingResult(
                chunks=[],
                doc_type=DocumentType.UNKNOWN,
                confidence=0.0,
                warnings=["文档内容为空"]
            )
        
        # 自动分类
        classification = None
        if auto_classify:
            classification = self.classifier.classify(
                content=text_content,
                file_path=document.source_uri,
                metadata=document.metadata
            )
            doc_type = classification.doc_type
            confidence = classification.confidence
            logger.info(f"文档分类结果: {doc_type.value}, 置信度: {confidence:.2f}")
        else:
            # 使用文档元数据中的类型
            meta_type = document.metadata.get("doc_type")
            if meta_type:
                try:
                    doc_type = DocumentType(meta_type)
                except:
                    doc_type = DocumentType.UNKNOWN
            else:
                doc_type = DocumentType.UNKNOWN
            confidence = 0.0
            classification = ClassificationResult(
                doc_type=doc_type,
                confidence=confidence
            )
        
        # 根据类型选择处理器
        processor = self._get_processor(doc_type)
        
        # 处理文档
        chunks = processor.process(text_content, document, classification)
        
        # 构建结果
        result_metadata = {
            "doc_type": doc_type.value,
            "confidence": confidence,
            "chunk_count": len(chunks),
        }
        if classification.features:
            result_metadata["features"] = classification.features
        
        return ProcessingResult(
            chunks=chunks,
            doc_type=doc_type,
            confidence=confidence,
            metadata=result_metadata
        )
    
    def _get_processor(self, doc_type: DocumentType) -> 'BaseTypeProcessor':
        """根据文档类型获取处理器"""
        processors = {
            DocumentType.API_DOC: APIDocProcessor(),
            DocumentType.TECHNICAL: TechnicalDocProcessor(),
            DocumentType.PRODUCT: ProductDocProcessor(),
            DocumentType.REQUIREMENT: RequirementDocProcessor(),
            DocumentType.USER_GUIDE: UserGuideProcessor(),
            DocumentType.UNKNOWN: GenericDocProcessor(),
        }
        return processors.get(doc_type, GenericDocProcessor())


class BaseTypeProcessor:
    """文档处理器基类"""
    
    def process(
        self, 
        content: str, 
        document: Document,
        classification: ClassificationResult
    ) -> List[DocumentChunk]:
        """处理文档，返回块列表"""
        raise NotImplementedError
    
    def _create_chunk(
        self,
        content: str,
        document: Document,
        chunk_index: int,
        classification: ClassificationResult = None,
        metadata: Dict = None
    ) -> DocumentChunk:
        """创建文档块"""
        doc_type_value = classification.doc_type.value if classification and classification.doc_type else "unknown"
        chunk_metadata = {
            "doc_type": doc_type_value,
            "chunk_index": chunk_index,
            "chunk_size": len(content),
            "token_count": len(content) // 4,  # 粗略估算
        }
        if metadata:
            chunk_metadata.update(metadata)
        
        return DocumentChunk(
            content=content,
            source_type=document.source_type,
            source_uri=document.source_uri,
            doc_type=document.doc_type,
            metadata=chunk_metadata,
            parent_doc_id=document.id,
            chunk_index=chunk_index
        )


class APIDocProcessor(BaseTypeProcessor):
    """
    API文档处理器
    
    特点：
    - 保留参数表格结构
    - 提取API端点信息
    - 保持请求/响应示例完整
    """
    
    def process(
        self, 
        content: str, 
        document: Document,
        classification: ClassificationResult
    ) -> List[DocumentChunk]:
        """处理API文档"""
        chunks = []
        
        # 1. 提取并保留API端点
        endpoints = self._extract_endpoints(content)
        
        # 2. 提取并保留参数表格
        tables = self._extract_tables(content)
        
        # 3. 按章节分割（API文档通常有明确的章节结构）
        sections = self._split_by_sections(content)
        
        for i, section in enumerate(sections):
            # 为每个section添加上下文
            enriched_content = self._enrich_api_content(
                section["content"], 
                endpoints,
                tables,
                section.get("title", "")
            )
            
            chunk = self._create_chunk(
                enriched_content,
                document,
                i,
                classification,
                {
                    "section_title": section.get("title", ""),
                    "section_level": section.get("level", 0),
                    "contains_endpoint": any(ep in enriched_content for ep in endpoints),
                    "contains_table": len([t for t in tables if t in enriched_content]) > 0
                }
            )
            chunks.append(chunk)
        
        return chunks
    
    def _extract_endpoints(self, content: str) -> List[str]:
        """提取API端点"""
        patterns = [
            r'(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s+(/[\w/{}.-]+)',
            r'`(GET|POST|PUT|DELETE|PATCH)\s+/[\w/{}]+`',
        ]
        endpoints = []
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            endpoints.extend([f"{m[0]} {m[1]}" for m in matches])
        return list(set(endpoints))
    
    def _extract_tables(self, content: str) -> List[str]:
        """提取表格"""
        # Markdown表格
        tables = re.findall(r'(\|[\s\S]*?\|\n\|[\s\S]*?\|\n(?:\|[\s\S]*?\|[\s\S]*?)*)', content)
        return tables
    
    def _split_by_sections(self, content: str) -> List[Dict]:
        """按章节分割"""
        sections = []
        lines = content.split('\n')
        current_section = {"title": "", "content": [], "level": 0}
        
        for line in lines:
            # 检测标题
            heading = self._is_heading(line)
            if heading:
                # 保存之前的section
                if current_section["content"]:
                    current_section["content"] = '\n'.join(current_section["content"])
                    sections.append(current_section)
                
                # 新建section
                current_section = {
                    "title": heading["title"],
                    "content": [],
                    "level": heading["level"]
                }
            else:
                current_section["content"].append(line)
        
        # 添加最后一个section
        if current_section["content"]:
            current_section["content"] = '\n'.join(current_section["content"])
            sections.append(current_section)
        
        # 如果没有识别到章节，使用默认分块
        if not sections:
            sections = [{"title": "全文", "content": content, "level": 0}]
        
        return sections
    
    def _is_heading(self, line: str) -> Optional[Dict]:
        """检测标题"""
        line = line.strip()
        
        # Markdown标题
        md_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if md_match:
            return {
                "title": md_match.group(2),
                "level": len(md_match.group(1))
            }
        
        # 数字编号标题
        num_match = re.match(r'^(\d+\.?\d*)\s+(.+)$', line)
        if num_match:
            return {
                "title": num_match.group(2),
                "level": 2
            }
        
        return None
    
    def _enrich_api_content(
        self, 
        content: str, 
        endpoints: List[str],
        tables: List[str],
        section_title: str
    ) -> str:
        """为API内容添加额外信息"""
        enriched = content
        
        # 如果section没有端点，尝试从全局端点列表中找到相关的
        if endpoints and section_title:
            relevant_endpoints = [
                ep for ep in endpoints 
                if section_title.lower() in ep.lower() or ep.lower() in section_title.lower()
            ]
            if relevant_endpoints:
                enriched = f"API端点: {', '.join(relevant_endpoints)}\n\n{enriched}"
        
        return enriched


class TechnicalDocProcessor(BaseTypeProcessor):
    """
    技术文档处理器
    
    特点：
    - 保持代码块完整性
    - 保留代码注释
    - 提取关键类和函数
    """
    
    def process(
        self, 
        content: str, 
        document: Document,
        classification: ClassificationResult
    ) -> List[DocumentChunk]:
        """处理技术文档"""
        chunks = []
        
        # 1. 提取代码块（保持完整性）
        code_blocks = self._extract_code_blocks(content)
        
        # 2. 提取技术术语和关键概念
        tech_terms = self._extract_tech_terms(content)
        
        # 3. 按语义段落分割（非代码部分）
        prose_sections = self._split_prose_sections(content)
        
        # 4. 合并代码块和文本
        # 策略：先处理文本段落，再插入相关的代码块
        chunk_index = 0
        
        for section in prose_sections:
            # 为文本段落添加上下文
            enriched = self._enrich_technical_content(
                section["content"],
                code_blocks,
                tech_terms
            )
            
            # 如果内容太长，进一步分割
            if len(enriched) > 2000:
                sub_chunks = self._split_large_content(enriched, code_blocks)
                for sub in sub_chunks:
                    chunk = self._create_chunk(
                        sub,
                        document,
                        chunk_index,
                        {"section_type": "prose"}
                    )
                    chunks.append(chunk)
                    chunk_index += 1
            else:
                chunk = self._create_chunk(
                    enriched,
                    document,
                    chunk_index,
                    {"section_type": "prose"}
                )
                chunks.append(chunk)
                chunk_index += 1
        
        # 添加独立的代码块作为单独chunk（重要的代码示例）
        for i, code in enumerate(code_blocks[:5]):  # 最多添加5个代码块
            chunk = self._create_chunk(
                code,
                document,
                chunk_index,
                {"section_type": "code_example", "code_index": i}
            )
            chunks.append(chunk)
            chunk_index += 1
        
        return chunks
    
    def _extract_code_blocks(self, content: str) -> List[str]:
        """提取代码块"""
        # Markdown代码块
        md_blocks = re.findall(r'```[\s\S]*?```', content)
        
        # 缩进代码块
        indent_blocks = re.findall(r'^\s{4,}.+$', content, re.MULTILINE)
        
        return md_blocks + indent_blocks
    
    def _extract_tech_terms(self, content: str) -> List[str]:
        """提取技术术语"""
        terms = []
        
        # 提取函数定义
        func_patterns = [
            r'def\s+(\w+)',
            r'function\s+(\w+)',
            r'class\s+(\w+)',
            r'interface\s+(\w+)',
            r'fn\s+(\w+)',
        ]
        for pattern in func_patterns:
            matches = re.findall(pattern, content)
            terms.extend(matches)
        
        return list(set(terms))
    
    def _split_prose_sections(self, content: str) -> List[Dict]:
        """分割非代码的文本部分"""
        # 移除代码块后的内容
        content_no_code = re.sub(r'```[\s\S]*?```', '\n[代码块]\n', content)
        content_no_code = re.sub(r'^\s{4,}.+$', '\n[代码块]\n', content_no_code, flags=re.MULTILINE)
        
        # 按段落分割
        paragraphs = re.split(r'\n\s*\n', content_no_code)
        
        sections = []
        for para in paragraphs:
            para = para.strip()
            if para and para != "[代码块]":
                sections.append({"content": para})
        
        return sections if sections else [{"content": content}]
    
    def _enrich_technical_content(
        self, 
        content: str, 
        code_blocks: List[str],
        tech_terms: List[str]
    ) -> str:
        """为技术内容添加上下文"""
        enriched = content
        
        # 添加关键词标签
        if tech_terms:
            terms_str = ", ".join(tech_terms[:10])
            enriched = f"[技术术语: {terms_str}]\n\n{enriched}"
        
        return enriched
    
    def _split_large_content(
        self, 
        content: str, 
        code_blocks: List[str]
    ) -> List[str]:
        """分割大块内容"""
        # 按句子分割
        sentences = re.split(r'(?<=[。！？])\s*', content)
        
        sub_chunks = []
        current = ""
        
        for sentence in sentences:
            if len(current) + len(sentence) > 1500:
                if current:
                    sub_chunks.append(current)
                current = sentence
            else:
                current += sentence
        
        if current:
            sub_chunks.append(current)
        
        return sub_chunks if sub_chunks else [content]


class ProductDocProcessor(BaseTypeProcessor):
    """
    产品文档处理器
    
    特点：
    - 保留功能描述的完整性
    - 识别产品特性
    - 保持用户场景关联
    """
    
    def process(
        self, 
        content: str, 
        document: Document,
        classification: ClassificationResult
    ) -> List[DocumentChunk]:
        """处理产品文档"""
        chunks = []
        
        # 1. 识别产品功能模块
        features = self._extract_features(content)
        
        # 2. 按功能模块分割
        sections = self._split_by_features(content)
        
        for i, section in enumerate(sections):
            enriched = self._enrich_product_content(
                section["content"],
                features
            )
            
            chunk = self._create_chunk(
                enriched,
                document,
                i,
                {
                    "feature_name": section.get("feature", ""),
                    "section_type": "feature"
                }
            )
            chunks.append(chunk)
        
        return chunks
    
    def _extract_features(self, content: str) -> List[str]:
        """提取产品功能"""
        features = []
        
        # 匹配功能描述模式
        patterns = [
            r'功能[：:]\s*(.+)',
            r'功能特性[：:]\s*(.+)',
            r'支持(.+)',
            r'具备(.+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            features.extend(matches)
        
        return features[:20]  # 最多20个
    
    def _split_by_features(self, content: str) -> List[Dict]:
        """按功能特征分割"""
        sections = []
        
        # 按标题分割
        lines = content.split('\n')
        current_section = {"feature": "", "content": []}
        
        for line in lines:
            # 检测功能/特性标题
            feature_match = re.match(r'^#{1,3}\s+(.+?)(功能|特性|模块).*$', line)
            if feature_match:
                # 保存之前的
                if current_section["content"]:
                    current_section["content"] = '\n'.join(current_section["content"])
                    sections.append(current_section)
                
                current_section = {
                    "feature": feature_match.group(1),
                    "content": [line]
                }
            else:
                current_section["content"].append(line)
        
        # 添加最后一个
        if current_section["content"]:
            current_section["content"] = '\n'.join(current_section["content"])
            sections.append(current_section)
        
        # 如果没有识别到特征，按段落分割
        if len(sections) <= 1:
            paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
            sections = [{"feature": "", "content": p} for p in paragraphs]
        
        return sections
    
    def _enrich_product_content(
        self, 
        content: str, 
        features: List[str]
    ) -> str:
        """为产品内容添加上下文"""
        # 提取与当前内容相关的功能
        relevant = [f for f in features if f in content]
        
        if relevant:
            return f"[相关功能: {', '.join(relevant[:5])}]\n\n{content}"
        
        return content


class RequirementDocProcessor(BaseTypeProcessor):
    """
    需求文档处理器
    
    特点：
    - 保持需求条目完整性
    - 保留验收标准
    - 关联优先级信息
    """
    
    def process(
        self, 
        content: str, 
        document: Document,
        classification: ClassificationResult
    ) -> List[DocumentChunk]:
        """处理需求文档"""
        chunks = []
        
        # 1. 提取需求条目
        requirements = self._extract_requirements(content)
        
        # 2. 按需求分割
        for i, req in enumerate(requirements):
            enriched = self._enrich_requirement_content(req)
            
            chunk = self._create_chunk(
                enriched,
                document,
                i,
                {
                    "requirement_id": req.get("id", ""),
                    "priority": req.get("priority", ""),
                    "has_acceptance": bool(req.get("acceptance_criteria"))
                }
            )
            chunks.append(chunk)
        
        # 如果没有识别到需求条目，使用默认分块
        if not chunks:
            sections = self._split_by_headings(content)
            for i, section in enumerate(sections):
                chunk = self._create_chunk(
                    section["content"],
                    document,
                    i,
                    {"section_title": section.get("title", "")}
                )
                chunks.append(chunk)
        
        return chunks
    
    def _extract_requirements(self, content: str) -> List[Dict]:
        """提取需求条目"""
        requirements = []
        
        # 按需求ID或编号分割
        req_patterns = [
            r'(需求[ID:id]?\s*[:：]?\s*)(\w+)',
            r'(REQ[-_]?)(\d+)',
            r'^\[(\d+)\]\s+(.+)$',
        ]
        
        current_req = None
        
        for line in content.split('\n'):
            matched = False
            for pattern in req_patterns:
                match = re.match(pattern, line)
                if match:
                    # 保存之前的
                    if current_req:
                        requirements.append(current_req)
                    
                    current_req = {
                        "id": match.group(2),
                        "content": [line],
                        "priority": self._extract_priority(line),
                        "acceptance_criteria": ""
                    }
                    matched = True
                    break
            
            if not matched and current_req:
                # 检查是否是验收标准
                if '验收' in line or 'AC' in line:
                    current_req["acceptance_criteria"] += line + "\n"
                else:
                    current_req["content"].append(line)
        
        # 添加最后一个
        if current_req:
            requirements.append(current_req)
        
        # 转换content为字符串
        for req in requirements:
            req["content"] = '\n'.join(req["content"])
        
        return requirements
    
    def _extract_priority(self, text: str) -> str:
        """提取优先级"""
        priority_match = re.search(r'[Pp]([0-3])', text)
        if priority_match:
            return f"P{priority_match.group(1)}"
        
        high_priority = ['高', '紧急', '重要', 'critical', 'high']
        if any(p in text.lower() for p in high_priority):
            return "P0"
        
        return "P2"  # 默认
    
    def _split_by_headings(self, content: str) -> List[Dict]:
        """按标题分割"""
        sections = []
        lines = content.split('\n')
        current = {"title": "", "content": []}
        
        for line in lines:
            if re.match(r'^#{1,6}\s+', line):
                if current["content"]:
                    current["content"] = '\n'.join(current["content"])
                    sections.append(current)
                current = {"title": line.strip("# ").strip(), "content": [line]}
            else:
                current["content"].append(line)
        
        if current["content"]:
            current["content"] = '\n'.join(current["content"])
            sections.append(current)
        
        return sections if sections else [{"title": "", "content": content}]
    
    def _enrich_requirement_content(self, req: Dict) -> str:
        """为需求内容添加元信息"""
        parts = []
        
        if req.get("id"):
            parts.append(f"[需求ID: {req['id']}]")
        
        if req.get("priority"):
            parts.append(f"[优先级: {req['priority']}]")
        
        content = '\n'.join(req.get("content", []))
        
        if parts:
            return '\n'.join(parts) + '\n\n' + content
        
        return content


class UserGuideProcessor(BaseTypeProcessor):
    """
    用户指南处理器
    
    特点：
    - 保持操作步骤连贯性
    - 识别步骤顺序
    - 提取操作要点
    """
    
    def process(
        self, 
        content: str, 
        document: Document,
        classification: ClassificationResult
    ) -> List[DocumentChunk]:
        """处理用户指南"""
        chunks = []
        
        # 1. 提取操作步骤
        steps = self._extract_steps(content)
        
        # 2. 按步骤组分割（每3-5个步骤为一组）
        step_groups = self._group_steps(steps)
        
        for i, group in enumerate(step_groups):
            enriched = self._enrich_guide_content(group)
            
            chunk = self._create_chunk(
                enriched,
                document,
                i,
                {
                    "step_group": i + 1,
                    "step_count": len(group)
                }
            )
            chunks.append(chunk)
        
        # 如果没有识别到步骤，使用默认分块
        if not chunks:
            sections = self._split_by_headings(content)
            for i, section in enumerate(sections):
                chunk = self._create_chunk(
                    section["content"],
                    document,
                    i,
                    {"section_title": section.get("title", "")}
                )
                chunks.append(chunk)
        
        return chunks
    
    def _extract_steps(self, content: str) -> List[Dict]:
        """提取操作步骤"""
        steps = []
        
        # 匹配步骤模式
        step_patterns = [
            r'^步骤\s*(\d+)[：:]\s*(.+)',
            r'^\[?(\d+)\]?\.\s+(.+)',
            r'^第[一二三四五六七八九十\d]+[步部分][：:]\s*(.+)',
            r'^(\d+)[.)]\s+(.+)',
        ]
        
        for line in content.split('\n'):
            for pattern in step_patterns:
                match = re.match(pattern, line)
                if match:
                    step_num = match.group(1)
                    step_content = match.group(2)
                    
                    # 提取关键操作
                    action = self._extract_action(step_content)
                    
                    steps.append({
                        "number": int(step_num) if step_num.isdigit() else 0,
                        "content": step_content,
                        "action": action
                    })
                    break
        
        return steps
    
    def _extract_action(self, text: str) -> str:
        """提取关键操作"""
        actions = ["点击", "输入", "选择", "打开", "保存", "提交", "删除", "修改", "查看", "执行"]
        
        for action in actions:
            if action in text:
                return action
        
        return "操作"
    
    def _group_steps(self, steps: List[Dict]) -> List[List[Dict]]:
        """将步骤分组"""
        if not steps:
            return []
        
        # 每组最多5个步骤
        group_size = 5
        groups = []
        
        for i in range(0, len(steps), group_size):
            groups.append(steps[i:i + group_size])
        
        return groups
    
    def _enrich_guide_content(self, steps: List[Dict]) -> str:
        """为指南内容添加结构"""
        lines = ["[操作步骤]"]
        
        for step in steps:
            step_num = step.get("number", "?")
            content = step.get("content", "")
            action = step.get("action", "操作")
            
            lines.append(f"步骤{step_num}: {content}")
        
        return '\n'.join(lines)
    
    def _split_by_headings(self, content: str) -> List[Dict]:
        """按标题分割"""
        sections = []
        lines = content.split('\n')
        current = {"title": "", "content": []}
        
        for line in lines:
            if re.match(r'^#{1,6}\s+', line):
                if current["content"]:
                    current["content"] = '\n'.join(current["content"])
                    sections.append(current)
                current = {"title": line.strip("# ").strip(), "content": [line]}
            else:
                current["content"].append(line)
        
        if current["content"]:
            current["content"] = '\n'.join(current["content"])
            sections.append(current)
        
        return sections if sections else [{"title": "", "content": content}]


class GenericDocProcessor(BaseTypeProcessor):
    """
    通用文档处理器
    
    使用默认的分块策略处理未知类型文档
    """
    
    def process(
        self, 
        content: str, 
        document: Document,
        classification: ClassificationResult
    ) -> List[DocumentChunk]:
        """处理通用文档"""
        chunks = []
        
        # 使用默认的递归分块策略
        # 按段落分割
        paragraphs = re.split(r'\n\s*\n', content)
        
        current_chunk = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # 如果加上当前段落会超过限制，先保存当前块
            if len(current_chunk) + len(para) > 1500:
                if current_chunk:
                    chunk = self._create_chunk(
                        current_chunk,
                        document,
                        len(chunks)
                    )
                    chunks.append(chunk)
                    current_chunk = para
                else:
                    # 单个段落就超过限制，需要进一步分割
                    sub_chunks = self._split_paragraph(para)
                    for sub in sub_chunks:
                        chunk = self._create_chunk(
                            sub,
                            document,
                            len(chunks)
                        )
                        chunks.append(chunk)
            else:
                current_chunk += "\n\n" + para if current_chunk else para
        
        # 处理最后一个chunk
        if current_chunk:
            chunk = self._create_chunk(
                current_chunk,
                document,
                len(chunks)
            )
            chunks.append(chunk)
        
        return chunks
    
    def _split_paragraph(self, para: str) -> List[str]:
        """分割段落"""
        # 按句子分割
        sentences = re.split(r'(?<=[。！？.!?])\s*', para)
        
        chunks = []
        current = ""
        
        for sent in sentences:
            if len(current) + len(sent) > 1000:
                if current:
                    chunks.append(current)
                current = sent
            else:
                current += sent
        
        if current:
            chunks.append(current)
        
        return chunks if chunks else [para]


# 便捷函数
def process_adaptive(
    document: Document,
    content: str = None
) -> ProcessingResult:
    """自适应处理文档"""
    processor = AdaptiveDocumentProcessor()
    return processor.process(document, content)


if __name__ == "__main__":
    # 测试
    from common.rag.core.models import Document
    
    # 测试API文档
    api_content = """
# 用户管理API

## 获取用户列表
GET /api/v1/users

### 请求参数
| 名称 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码 |
| size | int | 否 | 每页数量 |

### 响应示例
```json
{
  "code": 0,
  "data": []
}
```

## 创建用户
POST /api/v1/users

### 请求参数
| 名称 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 用户名 |
| email | string | 是 | 邮箱 |
"""
    
    doc = Document(
        id="test_api",
        content=api_content,
        source_type="file",
        source_uri="test_api.md"
    )
    
    processor = AdaptiveDocumentProcessor()
    result = processor.process(doc)
    
    print(f"文档类型: {result.doc_type.value}")
    print(f"置信度: {result.confidence:.2f}")
    print(f"分块数量: {len(result.chunks)}")
    
    for i, chunk in enumerate(result.chunks):
        print(f"\n--- Chunk {i} ---")
        print(chunk.content[:200])

