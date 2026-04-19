#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档类型分类器
自动识别文档类型并推荐最佳处理策略
"""

import re
import logging
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """文档类型枚举"""
    API_DOC = "api_doc"              # API接口文档
    TECHNICAL_SPEC = "technical_spec"  # 技术规格文档
    PRODUCT_DESIGN = "product_design"   # 产品设计文档
    USER_GUIDE = "user_guide"          # 用户使用指南
    TEST_CASE = "test_case"            # 测试用例文档
    REQUIREMENT = "requirement"         # 需求文档
    UNKNOWN = "unknown"                # 未知类型


@dataclass
class DocumentClassifier:
    """文档类型分类器"""
    
    # API文档特征
    api_keywords: List[str] = field(default_factory=lambda: [
        "api", "接口", "endpoint", "endpoint", "请求方法", "http方法",
        "get", "post", "put", "delete", "path", "url", "参数",
        "request", "response", "状态码", "header", "body", "query"
    ])
    
    # 技术文档特征
    tech_keywords: List[str] = field(default_factory=lambda: [
        # 架构设计
        "架构", "architecture", "技术栈", "技术方案", "实现原理", "系统架构", "模块设计",
        "系统结构", "系统模块", "模块划分", "层次结构", "分层架构",
        # 技术特性
        "数据结构", "算法", "数据库", "schema", "表结构", "字段", "存储",
        "安全", "认证", "授权", "加密", "日志", "监控", "性能",
        "SCA", "PSD2", "OTP", "Challenge", "authentication",
        # 设计模式
        "接口", "服务", "流程", "时序", "序列图", "流程图",
        "设计方案", "详细设计", "概要设计", "技术设计"
    ])
    
    # 产品文档特征
    product_keywords: List[str] = field(default_factory=lambda: [
        "产品", "功能", "需求", "业务流程", "用户故事", "用例",
        "界面", "交互", "体验", "原型", "PRD", "MRD"
    ])
    
    # 测试文档特征
    test_keywords: List[str] = field(default_factory=lambda: [
        "测试", "test", "用例", "测试点", "测试步骤", "预期结果",
        "断言", "验证", "冒烟", "回归", "性能", "压测"
    ])
    
    # 用户指南特征
    guide_keywords: List[str] = field(default_factory=lambda: [
        "使用说明", "用户指南", "操作手册", "教程", "tutorial",
        "快速开始", "getting started", "安装", "配置", "步骤"
    ])
    
    def __post_init__(self):
        """初始化分类器"""
        # 编译正则表达式以提高性能
        self._compile_patterns()
    
    def _compile_patterns(self):
        """编译常用正则表达式"""
        # API端点模式
        self.endpoint_pattern = re.compile(
            r'(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s+(/[\w\-/{}]+)',
            re.IGNORECASE
        )
        
        # OpenAPI/Swagger模式
        self.openapi_pattern = re.compile(
            r'(openapi|swagger|api-doc|api documentation)',
            re.IGNORECASE
        )
        
        # 参数表格模式
        self.param_table_pattern = re.compile(
            r'(参数|parameter|field|property).*?(类型|type|required)',
            re.IGNORECASE
        )
        
        # 响应码模式
        self.status_code_pattern = re.compile(
            r'(200|201|400|401|403|404|500|502|503)\s+(OK|Error|Success|Created)',
            re.IGNORECASE
        )
    
    def classify(self, content: str, filename: str = "", metadata: Dict = None) -> Tuple[DocumentType, float, Dict]:
        """
        分类文档类型
        
        Args:
            content: 文档内容
            filename: 文件名（用于辅助判断）
            metadata: 已有元数据
            
        Returns:
            (文档类型, 置信度, 详细评分)
        """
        # 合并文本用于分析
        full_text = content
        if filename:
            full_text = f"{filename}\n{content}"
        
        # 1. 计算各类别的特征得分
        scores = self._calculate_scores(full_text)
        
        # 2. 检查特殊模式（API文档的特征模式）
        scores = self._check_special_patterns(full_text, scores)
        
        # 3. 文件名辅助判断
        if filename:
            scores = self._check_filename(filename, scores)
        
        # 4. 元数据辅助判断
        if metadata:
            scores = self._check_metadata(metadata, scores)
        
        # 5. 选择得分最高的类型
        best_type = max(scores.keys(), key=lambda x: scores[x]['total'])
        confidence = scores[best_type]['total']
        
        logger.info(f"文档分类结果: {best_type.value}, 置信度: {confidence:.2f}")
        
        return best_type, confidence, scores
    
    def _calculate_scores(self, text: str) -> Dict[DocumentType, Dict]:
        """计算各类别的特征得分"""
        text_lower = text.lower()
        
        scores = {}
        
        # API文档得分
        api_score = sum(1 for kw in self.api_keywords if kw.lower() in text_lower)
        scores[DocumentType.API_DOC] = {
            'keyword': api_score,
            'pattern': 0,
            'filename': 0,
            'total': api_score
        }
        
        # 技术文档得分
        tech_score = sum(1 for kw in self.tech_keywords if kw.lower() in text_lower)
        scores[DocumentType.TECHNICAL_SPEC] = {
            'keyword': tech_score,
            'pattern': 0,
            'filename': 0,
            'total': tech_score
        }
        
        # 产品文档得分
        product_score = sum(1 for kw in self.product_keywords if kw.lower() in text_lower)
        scores[DocumentType.PRODUCT_DESIGN] = {
            'keyword': product_score,
            'pattern': 0,
            'filename': 0,
            'total': product_score
        }
        
        # 测试文档得分
        test_score = sum(1 for kw in self.test_keywords if kw.lower() in text_lower)
        scores[DocumentType.TEST_CASE] = {
            'keyword': test_score,
            'pattern': 0,
            'filename': 0,
            'total': test_score
        }
        
        # 用户指南得分
        guide_score = sum(1 for kw in self.guide_keywords if kw.lower() in text_lower)
        scores[DocumentType.USER_GUIDE] = {
            'keyword': guide_score,
            'pattern': 0,
            'filename': 0,
            'total': guide_score
        }
        
        # 需求文档得分（与产品文档类似，但权重不同）
        scores[DocumentType.REQUIREMENT] = {
            'keyword': product_score * 0.8,
            'pattern': 0,
            'filename': 0,
            'total': product_score * 0.8
        }
        
        scores[DocumentType.UNKNOWN] = {
            'keyword': 0,
            'pattern': 0,
            'filename': 0,
            'total': 0
        }
        
        return scores
    
    def _check_special_patterns(self, text: str, scores: Dict) -> Dict:
        """检查特殊模式"""
        # 检查API端点模式
        endpoints = self.endpoint_pattern.findall(text)
        if endpoints:
            scores[DocumentType.API_DOC]['pattern'] = len(endpoints) * 2
            scores[DocumentType.API_DOC]['total'] += scores[DocumentType.API_DOC]['pattern']
        
        # 检查OpenAPI/Swagger模式
        if self.openapi_pattern.search(text):
            scores[DocumentType.API_DOC]['pattern'] += 5
            scores[DocumentType.API_DOC]['total'] += 5
        
        # 检查参数表格模式
        if self.param_table_pattern.search(text):
            scores[DocumentType.API_DOC]['pattern'] += 3
            scores[DocumentType.API_DOC]['total'] += 3
        
        # 检查响应码模式
        status_codes = self.status_code_pattern.findall(text)
        if status_codes:
            scores[DocumentType.API_DOC]['pattern'] += len(status_codes)
            scores[DocumentType.API_DOC]['total'] += len(status_codes)
        
        # ============ 增加技术文档模式 ============
        # 检查时序图/流程图标记
        sequence_diagram_patterns = [
            r'sequence', r'sequence diagram', r'sequencechart',
            r'时序图', r'流程图', r'流程', r'mermaid', r'flowchart'
        ]
        tech_pattern_count = sum(1 for p in sequence_diagram_patterns if re.search(p, text, re.IGNORECASE))
        if tech_pattern_count:
            scores[DocumentType.TECHNICAL_SPEC]['pattern'] += tech_pattern_count * 2
            scores[DocumentType.TECHNICAL_SPEC]['total'] += tech_pattern_count * 2
        
        # 检查章节结构模式（第一章、第二章、1.1、1.2）
        chapter_patterns = [
            r'^\d+\.\s+\w+',           # 1. xxx 格式
            r'^\d+\.\d+\s+\w+',       # 1.1 xxx 格式
            r'第[一二三四五六七八九十]+章',  # 第一章
            r'第[一二三四五六七八九十]+节',  # 第一节
        ]
        chapter_count = sum(1 for p in chapter_patterns if re.search(p, text, re.MULTILINE))
        if chapter_count > 3:  # 多个章节
            scores[DocumentType.TECHNICAL_SPEC]['pattern'] += 5
            scores[DocumentType.TECHNICAL_SPEC]['total'] += 5
        
        # 检查系统模块相关模式
        module_patterns = [
            r'模块', r'系统模块', r'子系统', r'component',
            r'服务', r'service', r'processor', r'handler'
        ]
        module_count = sum(1 for p in module_patterns if p.lower() in text.lower())
        if module_count >= 3:
            scores[DocumentType.TECHNICAL_SPEC]['pattern'] += module_count
            scores[DocumentType.TECHNICAL_SPEC]['total'] += module_count
        
        return scores
    
    def _check_filename(self, filename: str, scores: Dict) -> Dict:
        """检查文件名特征"""
        fn_lower = filename.lower()
        
        # API文档文件名特征
        if any(kw in fn_lower for kw in ['api', '接口', 'endpoint', 'swagger', 'openapi']):
            scores[DocumentType.API_DOC]['filename'] += 3
            scores[DocumentType.API_DOC]['total'] += 3
        
        # 技术文档文件名特征
        if any(kw in fn_lower for kw in ['tech', '技术', '架构', 'design', 'spec']):
            scores[DocumentType.TECHNICAL_SPEC]['filename'] += 3
            scores[DocumentType.TECHNICAL_SPEC]['total'] += 3
        
        # 产品文档文件名特征
        if any(kw in fn_lower for kw in ['product', '产品', 'prd', 'mrd', '需求']):
            scores[DocumentType.PRODUCT_DESIGN]['filename'] += 3
            scores[DocumentType.PRODUCT_DESIGN]['total'] += 3
        
        # 测试文档文件名特征
        if any(kw in fn_lower for kw in ['test', '测试', 'case', '用例']):
            scores[DocumentType.TEST_CASE]['filename'] += 3
            scores[DocumentType.TEST_CASE]['total'] += 3
        
        # 用户指南文件名特征
        if any(kw in fn_lower for kw in ['guide', '指南', 'manual', '手册', 'doc']):
            scores[DocumentType.USER_GUIDE]['filename'] += 3
            scores[DocumentType.USER_GUIDE]['total'] += 3
        
        return scores
    
    def _check_metadata(self, metadata: Dict, scores: Dict) -> Dict:
        """检查元数据"""
        # 如果元数据中已指定类型，大幅提升该类型得分
        if 'doc_type' in metadata:
            doc_type_str = metadata['doc_type'].lower()
            for dt in DocumentType:
                if dt.value.lower() in doc_type_str:
                    scores[dt]['filename'] += 5
                    scores[dt]['total'] += 5
                    break
        
        return scores
    
    def recommend_strategy(self, doc_type: DocumentType) -> str:
        """根据文档类型推荐最佳切片策略"""
        strategies = {
            DocumentType.API_DOC: "hierarchical",
            DocumentType.TECHNICAL_SPEC: "recursive",
            DocumentType.PRODUCT_DESIGN: "hybrid",
            DocumentType.REQUIREMENT: "semantic",
            DocumentType.TEST_CASE: "semantic",
            DocumentType.USER_GUIDE: "hierarchical",
            DocumentType.UNKNOWN: "semantic"
        }
        
        return strategies.get(doc_type, "semantic")


@dataclass
class ClassificationResult:
    """分类结果"""
    doc_type: DocumentType
    confidence: float
    scores: Dict
    recommended_strategy: str


def classify_document(content: str, filename: str = "", metadata: Dict = None) -> Tuple[DocumentType, float, Dict]:
    """
    文档分类的便捷函数
    
    Args:
        content: 文档内容
        filename: 文件名
        metadata: 元数据
        
    Returns:
        (文档类型, 置信度, 评分详情)
    """
    classifier = DocumentClassifier()
    return classifier.classify(content, filename, metadata)


if __name__ == "__main__":
    # 测试分类器
    test_content = """
    # 用户创建API
    
    ## 接口描述
    创建新用户接口，用于在系统中创建新用户。
    
    ## 请求方法
    POST /api/v1/users
    
    ## 请求参数
    | 参数名 | 类型 | 必填 | 说明 |
    |--------|------|------|------|
    | username | string | 是 | 用户名 |
    | email | string | 是 | 邮箱 |
    | password | string | 是 | 密码 |
    
    ## 响应
    200 OK
    {
        "id": 12345,
        "username": "test_user",
        "email": "test@example.com"
    }
    """
    
    doc_type, confidence, scores = classify_document(test_content, "user_api.md")
    print(f"文档类型: {doc_type.value}")
    print(f"置信度: {confidence:.2f}")
    print(f"各类型得分: {scores}")
