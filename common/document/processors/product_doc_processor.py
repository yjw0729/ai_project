#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
产品文档专用处理器
针对产品设计文档的智能处理：功能点提取、业务流程、需求识别
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ProductFeature:
    """产品功能点"""
    name: str
    description: str
    priority: str = "P2"
    category: str = ""
    acceptance_criteria: List[str] = field(default_factory=list)


@dataclass
class BusinessFlow:
    """业务流程"""
    name: str
    steps: List[Dict] = field(default_factory=list)
    actors: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class UserRequirement:
    """用户需求"""
    id: str
    description: str
    type: str
    priority: str
    source: str = ""


class ProductDocumentProcessor:
    """产品文档专用处理器"""
    
    def __init__(self):
        self.feature_keywords = ['功能', 'feature', '功能点', '功能模块', '核心功能', '主要功能']
        self.flow_keywords = ['流程', 'process', '业务流程', '操作流程', '步骤', 'steps']
        self.requirement_keywords = ['需求', 'requirement', '功能需求', '业务需求', '用户需求']
        self.priority_keywords = {
            'P0': ['P0', '优先级0', '最高优先级', '必须', 'critical'],
            'P1': ['P1', '优先级1', '高优先级', '重要'],
            'P2': ['P2', '优先级2', '中优先级'],
            'P3': ['P3', '优先级3', '低优先级', '可选'],
        }
        self.actor_keywords = ['用户', 'user', '管理员', 'admin', '运营', '客户', '商户']
    
    def process(self, content: str, metadata: Dict = None) -> Tuple[List, Dict]:
        """处理产品文档内容"""
        features = self._extract_features(content)
        flows = self._extract_business_flows(content)
        requirements = self._extract_requirements(content)
        actors = self._extract_user_actors(content)
        
        enhanced_content = self._build_enhanced_content(content, features, flows, requirements, actors)
        
        extracted_metadata = {
            'product_features': [f.__dict__ for f in features],
            'business_flows': [f.__dict__ for f in flows],
            'requirements': [r.__dict__ for r in requirements],
            'user_actors': actors,
            'doc_type': 'product_design',
        }
        
        if metadata:
            extracted_metadata.update(metadata)
        
        chunks = self._chunk_product_document(enhanced_content, extracted_metadata, features, flows)
        
        logger.info(f"产品文档处理完成: {len(features)}个功能点, {len(flows)}个流程, {len(requirements)}个需求")
        
        return chunks, extracted_metadata
    
    def _extract_features(self, content: str) -> List[ProductFeature]:
        """提取产品功能点"""
        features = []
        lines = content.split('\n')
        
        current_feature = None
        current_description = []
        
        for line in lines:
            line = line.strip()
            is_feature_title = self._is_feature_title(line)
            
            if is_feature_title:
                if current_feature:
                    current_feature.description = '\n'.join(current_description).strip()
                    features.append(current_feature)
                
                feature_name = self._extract_title_text(line)
                priority = self._extract_priority(line)
                
                current_feature = ProductFeature(name=feature_name, priority=priority)
                current_description = []
            elif current_feature and line and not line.startswith('#'):
                current_description.append(line)
        
        if current_feature:
            current_feature.description = '\n'.join(current_description).strip()
            features.append(current_feature)
        
        return features
    
    def _is_feature_title(self, line: str) -> bool:
        """判断是否是功能标题"""
        if line.startswith('##') and any(kw in line.lower() for kw in self.feature_keywords):
            return True
        if re.match(r'^\d+[\.、]\s*[\u4e00-\u9fa5\w]+', line):
            if any(kw in line for kw in self.feature_keywords):
                return True
        return False
    
    def _extract_title_text(self, line: str) -> str:
        """提取标题文本"""
        text = re.sub(r'^#+\s*', '', line)
        text = re.sub(r'^\d+[\.、]\s*', '', text)
        return text.strip()
    
    def _extract_priority(self, line: str) -> str:
        """提取优先级"""
        line_lower = line.lower()
        for priority, keywords in self.priority_keywords.items():
            if any(kw in line_lower for kw in keywords):
                return priority
        return "P2"
    
    def _extract_business_flows(self, content: str) -> List[BusinessFlow]:
        """提取业务流程"""
        flows = []
        flow_sections = self._find_flow_sections(content)
        
        for section in flow_sections:
            flow = self._parse_flow_section(section)
            if flow:
                flows.append(flow)
        
        return flows
    
    def _find_flow_sections(self, content: str) -> List[str]:
        """查找流程相关章节"""
        sections = []
        lines = content.split('\n')
        
        in_flow_section = False
        current_section = []
        
        for line in lines:
            if any(kw in line.lower() for kw in self.flow_keywords):
                if not in_flow_section and len(line) < 50:
                    in_flow_section = True
                    current_section = [line]
                    continue
            
            if in_flow_section:
                if (line.strip().startswith('#') and len(current_section) > 3) or (not line.strip() and len(current_section) > 10):
                    sections.append('\n'.join(current_section))
                    in_flow_section = False
                    current_section = []
                else:
                    current_section.append(line)
        
        if current_section:
            sections.append('\n'.join(current_section))
        
        return sections
    
    def _parse_flow_section(self, section: str) -> Optional[BusinessFlow]:
        """解析流程章节"""
        lines = section.split('\n')
        if not lines:
            return None
        
        flow_name = lines[0].strip()
        flow_name = re.sub(r'^#+\s*', '', flow_name)
        
        actors = self._extract_flow_actors(section)
        steps = self._extract_flow_steps(section)
        
        return BusinessFlow(name=flow_name, steps=steps, actors=actors, description=section[:200])
    
    def _extract_flow_actors(self, section: str) -> List[str]:
        """提取流程参与者"""
        actors = []
        for keyword in self.actor_keywords:
            if keyword in section.lower():
                actor_pattern = rf'([\u4e00-\u9fa5\w]+)\s*{keyword}'
                matches = re.findall(actor_pattern, section)
                actors.extend(matches)
        return list(set(actors))
    
    def _extract_flow_steps(self, section: str) -> List[Dict]:
        """提取流程步骤"""
        steps = []
        lines = section.split('\n')
        
        step_patterns = [
            r'^(\d+)[\.、]\s*(.+)',
            r'^step\s*(\d+)[\s:：]*(.+)',
        ]
        
        for line in lines:
            line = line.strip()
            for pattern in step_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    steps.append({'step': match.group(1), 'description': match.group(2).strip()})
                    break
        
        return steps
    
    def _extract_requirements(self, content: str) -> List[UserRequirement]:
        """提取用户需求"""
        requirements = []
        req_sections = self._find_requirement_sections(content)
        
        for section in req_sections:
            req = self._parse_requirement_section(section)
            if req:
                requirements.append(req)
        
        return requirements
    
    def _find_requirement_sections(self, content: str) -> List[str]:
        """查找需求相关章节"""
        sections = []
        lines = content.split('\n')
        
        in_req_section = False
        current_section = []
        
        for line in lines:
            if any(kw in line.lower() for kw in self.requirement_keywords):
                if not in_req_section and len(line) < 50:
                    in_req_section = True
                    current_section = [line]
                    continue
            
            if in_req_section:
                if (line.strip().startswith('#') and len(current_section) > 3):
                    sections.append('\n'.join(current_section))
                    in_req_section = False
                    current_section = []
                else:
                    current_section.append(line)
        
        if current_section:
            sections.append('\n'.join(current_section))
        
        return sections
    
    def _parse_requirement_section(self, section: str) -> Optional[UserRequirement]:
        """解析需求章节"""
        lines = section.split('\n')
        if not lines:
            return None
        
        first_line = lines[0].strip()
        req_id_match = re.search(r'(REQ[-\s]?\d+)', first_line, re.IGNORECASE)
        req_id = req_id_match.group(1) if req_id_match else f"REQ-{hash(first_line) % 10000}"
        
        description = re.sub(r'^#+\s*', '', first_line)
        description = re.sub(r'^(REQ[-\s]?\d+)[\s:：]*', '', description, flags=re.IGNORECASE)
        
        priority = "P2"
        for prio, keywords in self.priority_keywords.items():
            if any(kw in description.lower() for kw in keywords):
                priority = prio
                break
        
        req_type = "functional"
        if any(kw in section.lower() for kw in ['性能', '安全', '非功能']):
            req_type = "non-functional"
        
        return UserRequirement(id=req_id, description=description, type=req_type, priority=priority)
    
    def _extract_user_actors(self, content: str) -> List[str]:
        """提取用户角色"""
        actors = []
        for keyword in self.actor_keywords:
            if keyword in content.lower():
                actor_pattern = rf'([\u4e00-\u9fa5\w]+)\s*{keyword}'
                matches = re.findall(actor_pattern, content)
                actors.extend(matches)
        return list(set(actors))
    
    def _build_enhanced_content(self, content: str, features, flows, requirements, actors) -> str:
        """构建增强的文档内容"""
        enhanced_parts = [content]
        
        if features:
            feature_summary = "\n\n## 功能点摘要\n"
            for f in features:
                feature_summary += f"- **{f.name}** [{f.priority}]: {f.description[:100]}...\n"
            enhanced_parts.append(feature_summary)
        
        if flows:
            flow_summary = "\n\n## 业务流程摘要\n"
            for flow in flows:
                flow_summary += f"- **{flow.name}**: {len(flow.steps)}个步骤\n"
            enhanced_parts.append(flow_summary)
        
        return '\n'.join(enhanced_parts)
    
    def _chunk_product_document(self, content: str, metadata: Dict, features, flows) -> List[Dict]:
        """对产品文档进行分块"""
        chunks = []
        
        for i, feature in enumerate(features):
            feature_content = f"# {feature.name}\n\n{feature.description}"
            chunks.append({
                'content': feature_content,
                'metadata': {**metadata, 'chunk_index': f"feature_{i}", 'chunk_type': 'product_feature', 'feature_name': feature.name}
            })
        
        for i, flow in enumerate(flows):
            flow_content = f"# {flow.name}\n\n{flow.description}\n\n## 步骤\n"
            for step in flow.steps:
                flow_content += f"{step['step']}. {step['description']}\n"
            chunks.append({
                'content': flow_content,
                'metadata': {**metadata, 'chunk_index': f"flow_{i}", 'chunk_type': 'business_flow', 'flow_name': flow.name}
            })
        
        return chunks if chunks else [{'content': content, 'metadata': metadata}]


def process_product_document(content: str, metadata: Dict = None) -> Tuple[List[Dict], Dict]:
    """处理产品文档的便捷函数"""
    processor = ProductDocumentProcessor()
    return processor.process(content, metadata)





