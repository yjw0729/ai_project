#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试用例文档专用分块器
针对测试用例和测试规范文档的结构化分块策略
"""

import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TestCase:
    """测试用例信息"""
    case_id: str
    title: str
    priority: str = "P2"
    preconditions: List[str] = field(default_factory=list)
    test_steps: List[Dict] = field(default_factory=list)
    expected_results: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


class TestDocChunker:
    """
    测试文档分块器
    
    专门处理测试用例文档，保持用例的完整性：
    - 用例ID和标题
    - 前置条件
    - 测试步骤
    - 预期结果
    
    分块策略：
    1. 识别文档中的测试用例
    2. 为每个用例创建完整的上下文块
    3. 保持步骤和结果的关联
    """
    
    def __init__(self, chunk_size: int = 1000, overlap: int = 150):
        """
        初始化测试文档分块器
        
        Args:
            chunk_size: 目标块大小
            overlap: 块之间的重叠大小
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        
        # 用例ID模式
        self.case_id_patterns = [
            r'TC[-\s]?(\d+)',
            r'用例[_\s]?编号[：:]?\s*(\w+)',
            r'case[_\s]?id[：:]?\s*(\w+)',
            r'TEST[-\s]?(\d+)',
        ]
        
        # 优先级模式
        self.priority_patterns = {
            "P0": [r'P0', r'优先级[：:]\s*0', r'最高', r'关键'],
            "P1": [r'P1', r'优先级[：:]\s*1', r'高'],
            "P2": [r'P2', r'优先级[：:]\s*2', r'中'],
            "P3": [r'P3', r'优先级[：:]\s*3', r'低'],
        }
        
        # 步骤关键词
        self.step_keywords = ["测试步骤", "操作步骤", "步骤", "step", "操作"]
        
        # 预期结果关键词
        self.result_keywords = ["预期结果", "期望结果", "验证点", "expected", "assertion"]
        
        # 前置条件关键词
        self.precondition_keywords = ["前置条件", "准备条件", "precondition", "前提"]
        
        logger.info(f"测试文档分块器初始化: chunk_size={chunk_size}, overlap={overlap}")
    
    def chunk(self, content: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        对测试文档进行分块
        
        Args:
            content: 文档内容
            metadata: 元数据
            
        Returns:
            分块结果列表
        """
        if not content:
            return []
        
        metadata = metadata or {}
        
        # 1. 提取测试用例
        test_cases = self._extract_test_cases(content)
        
        if test_cases:
            # 使用用例导向分块
            return self._chunk_by_test_cases(test_cases, metadata)
        else:
            # 回退到语义分块
            return self._fallback_chunking(content, metadata)
    
    def _extract_test_cases(self, content: str) -> List[TestCase]:
        """提取文档中的测试用例"""
        cases = []
        lines = content.split('\n')
        
        current_case = None
        current_section = "title"  # title, precondition, step, result
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检测新的测试用例
            case_id = self._detect_case_id(line)
            if case_id:
                # 保存之前的用例
                if current_case:
                    cases.append(current_case)
                
                # 创建新用例
                priority = self._detect_priority(line)
                current_case = TestCase(
                    case_id=case_id,
                    title=line,
                    priority=priority
                )
                current_section = "title"
                continue
            
            # 检测当前所在的区域
            section = self._detect_section(line)
            if section:
                current_section = section
                continue
            
            # 收集用例信息
            if current_case:
                self._parse_case_line(current_case, line, current_section)
        
        # 保存最后一个用例
        if current_case:
            cases.append(current_case)
        
        logger.info(f"提取到 {len(cases)} 个测试用例")
        return cases
    
    def _detect_case_id(self, line: str) -> Optional[str]:
        """检测用例ID"""
        for pattern in self.case_id_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                return match.group(1) if match.lastindex else match.group(0)
        
        # 如果没有匹配到ID模式，但行很短且没有标点，可能是标题行
        if len(line) < 80 and not line.endswith(('.', '。', '!', '！')):
            # 检查是否是数字编号
            if re.match(r'^\d+[\.\)]\s+', line):
                return None  # 这可能是步骤编号，不是新用例
        
        return None
    
    def _detect_priority(self, line: str) -> str:
        """检测优先级"""
        line_lower = line.lower()
        
        for priority, patterns in self.priority_patterns.items():
            for pattern in patterns:
                if re.search(pattern, line_lower):
                    return priority
        
        return "P2"  # 默认优先级
    
    def _detect_section(self, line: str) -> Optional[str]:
        """检测当前所在的区域"""
        line_lower = line.lower()
        
        # 前置条件区域
        for keyword in self.precondition_keywords:
            if keyword in line_lower:
                return "precondition"
        
        # 测试步骤区域
        for keyword in self.step_keywords:
            if keyword in line_lower:
                return "step"
        
        # 预期结果区域
        for keyword in self.result_keywords:
            if keyword in line_lower:
                return "result"
        
        return None
    
    def _parse_case_line(self, case: TestCase, line: str, section: str):
        """解析用例行"""
        line = line.strip()
        if not line:
            return
        
        # 标题区域 - 直接添加到标题
        if section == "title":
            if case.title and case.title != line:
                case.title += " " + line
        
        # 前置条件区域
        elif section == "precondition":
            # 检查是否是列表项
            if re.match(r'^[\-\*\•\d]+\s+', line):
                precondition = re.sub(r'^[\-\*\•\d]+\s+', '', line)
                case.preconditions.append(precondition)
            elif len(line) > 5:
                case.preconditions.append(line)
        
        # 测试步骤区域
        elif section == "step":
            # 解析步骤编号和内容
            match = re.match(r'^(\d+)[\.\)]\s*(.*)', line)
            if match:
                case.test_steps.append({
                    "step_number": match.group(1),
                    "description": match.group(2)
                })
            elif re.match(r'^[\-\*\•]\s*', line):
                step_content = re.sub(r'^[\-\*\•]\s*', '', line)
                if case.test_steps:
                    # 追加到上一步骤
                    case.test_steps[-1]["description"] += " " + step_content
                else:
                    case.test_steps.append({
                        "step_number": len(case.test_steps) + 1,
                        "description": step_content
                    })
        
        # 预期结果区域
        elif section == "result":
            if re.match(r'^[\-\*\•\d]+\s+', line):
                result = re.sub(r'^[\-\*\•\d]+\s+', '', line)
                case.expected_results.append(result)
            elif len(line) > 5:
                case.expected_results.append(line)
    
    def _chunk_by_test_cases(
        self, 
        test_cases: List[TestCase], 
        metadata: Dict
    ) -> List[Dict[str, Any]]:
        """基于测试用例进行分块"""
        chunks = []
        
        for i, test_case in enumerate(test_cases):
            # 构建用例上下文
            chunk_content = self._build_test_case_context(test_case)
            
            # 检查是否需要分割
            if len(chunk_content) > self.chunk_size * 1.3:
                sub_chunks = self._split_large_test_case(test_case, i, metadata)
                chunks.extend(sub_chunks)
            else:
                chunks.append({
                    "content": chunk_content,
                    "metadata": {
                        **metadata,
                        "doc_type": "test_case",
                        "chunk_type": "test_case",
                        "case_id": test_case.case_id,
                        "case_title": test_case.title[:50],
                        "priority": test_case.priority,
                        "case_index": i,
                        "total_cases": len(test_cases)
                    }
                })
        
        return chunks
    
    def _build_test_case_context(self, test_case: TestCase) -> str:
        """构建测试用例的完整上下文"""
        parts = []
        
        # 标题
        parts.append(f"## 测试用例: {test_case.case_id} - {test_case.title}")
        parts.append(f"优先级: {test_case.priority}")
        
        # 标签
        if test_case.tags:
            parts.append(f"标签: {', '.join(test_case.tags)}")
        
        # 前置条件
        if test_case.preconditions:
            parts.append("\n### 前置条件")
            for precondition in test_case.preconditions:
                parts.append(f"- {precondition}")
        
        # 测试步骤
        if test_case.test_steps:
            parts.append("\n### 测试步骤")
            for step in test_case.test_steps:
                parts.append(f"{step['step_number']}. {step['description']}")
        
        # 预期结果
        if test_case.expected_results:
            parts.append("\n### 预期结果")
            for result in test_case.expected_results:
                parts.append(f"- {result}")
        
        return "\n".join(parts)
    
    def _split_large_test_case(
        self, 
        test_case: TestCase, 
        index: int,
        metadata: Dict
    ) -> List[Dict[str, Any]]:
        """分割过大的测试用例块"""
        chunks = []
        
        # 基础信息块
        base_content = f"## 测试用例: {test_case.case_id} - {test_case.title}\n"
        base_content += f"优先级: {test_case.priority}\n"
        if test_case.tags:
            base_content += f"标签: {', '.join(test_case.tags)}\n"
        
        chunks.append({
            "content": base_content.strip(),
            "metadata": {
                **metadata,
                "doc_type": "test_case",
                "chunk_type": "test_case_base",
                "case_id": test_case.case_id,
                "priority": test_case.priority,
                "case_index": index
            }
        })
        
        # 前置条件块
        if test_case.preconditions:
            pre_content = f"### 测试用例 {test_case.case_id} - 前置条件\n\n"
            for precondition in test_case.preconditions:
                pre_content += f"- {precondition}\n"
            
            chunks.append({
                "content": pre_content.strip(),
                "metadata": {
                    **metadata,
                    "doc_type": "test_case",
                    "chunk_type": "test_case_precondition",
                    "case_id": test_case.case_id,
                    "case_index": index
                }
            })
        
        # 测试步骤块
        if test_case.test_steps:
            steps_content = f"### 测试用例 {test_case.case_id} - 测试步骤\n\n"
            for step in test_case.test_steps:
                steps_content += f"{step['step_number']}. {step['description']}\n"
            
            chunks.append({
                "content": steps_content.strip(),
                "metadata": {
                    **metadata,
                    "doc_type": "test_case",
                    "chunk_type": "test_case_steps",
                    "case_id": test_case.case_id,
                    "case_index": index
                }
            })
        
        # 预期结果块
        if test_case.expected_results:
            result_content = f"### 测试用例 {test_case.case_id} - 预期结果\n\n"
            for result in test_case.expected_results:
                result_content += f"- {result}\n"
            
            chunks.append({
                "content": result_content.strip(),
                "metadata": {
                    **metadata,
                    "doc_type": "test_case",
                    "chunk_type": "test_case_results",
                    "case_id": test_case.case_id,
                    "case_index": index
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
                        "doc_type": "test_case",
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
                    "doc_type": "test_case",
                    "chunk_type": "paragraph"
                }
            })
        
        return chunks


def chunk_test_document(
    content: str, 
    chunk_size: int = 1000, 
    overlap: int = 150,
    metadata: Dict = None
) -> List[Dict[str, Any]]:
    """
    便捷函数：对测试文档进行分块
    """
    chunker = TestDocChunker(chunk_size=chunk_size, overlap=overlap)
    return chunker.chunk(content, metadata)

