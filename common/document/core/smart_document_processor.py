#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能文档类型识别器
根据文档内容特征自动识别文档类型，并推荐最佳处理策略
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """文档类型枚举"""
    API_DOC = "api_doc"           # API接口文档
    PRD = "prd"                   # 产品需求文档
    TEST_CASE = "test_case"       # 测试用例文档
    USER_MANUAL = "user_manual"   # 用户手册
    TECHNICAL_SPEC = "technical_spec"  # 技术规格说明
    UNKNOWN = "unknown"           # 未知类型


@dataclass
class DocumentTypeProfile:
    """文档类型特征画像"""
    doc_type: DocumentType
    confidence: float  # 置信度 0-1
    detected_features: List[str] = field(default_factory=list)
    recommended_chunking_strategy: str = "semantic"
    recommended_chunk_size: int = 1500
    recommended_overlap: int = 200
    metadata_template: Dict[str, Any] = field(default_factory=dict)


class DocumentTypeDetector:
    """
    文档类型检测器
    
    通过多维度特征分析识别文档类型：
    - 标题特征
    - 关键词匹配
    - 结构模式识别
    - 内容语义分析
    """
    
    def __init__(self):
        # API文档特征
        self.api_doc_patterns = {
            "title_patterns": [
                r"api[_\s]?文档",
                r"接口[_\s]?文档", 
                r"rest[_\s]?api",
                r"接口[_\s]?说明",
                r"接口[_\s]?规范",
                r"/[a-z]+/[a-z]+",  # URL路径模式
            ],
            "keywords": [
                "请求方式", "请求方法", "http method",
                "请求参数", "response", "request body",
                "返回参数", "返回值", "状态码",
                "content-type", "authorization",
                "path", "query", "header",
            ],
            "structure_markers": [
                "GET", "POST", "PUT", "DELETE", "PATCH",
                "application/json",
                "200 OK", "400 Bad Request", "500 Error",
            ]
        }
        
        # PRD文档特征
        self.prd_patterns = {
            "title_patterns": [
                r"产品[_\s]?需求",
                r"prd",
                r"产品[_\s]?设计",
                r"需求[_\s]?文档",
                r"feature[_\s]?spec",
            ],
            "keywords": [
                "需求背景", "需求目的", "功能需求",
                "业务流程", "用户故事", "用例",
                "产品目标", "核心功能", "非功能需求",
                "性能要求", "兼容性", "安全要求",
            ],
            "structure_markers": [
                "功能列表", "模块划分", "角色",
                "前置条件", "后置条件", "约束条件",
            ]
        }
        
        # 测试用例文档特征
        self.test_case_patterns = {
            "title_patterns": [
                r"测试[_\s]?用例",
                r"test[_\s]?case",
                r"测试[_\s]?方案",
                r"测试[_\s]?计划",
            ],
            "keywords": [
                "测试步骤", "预期结果", "测试数据",
                "前置条件", "后置条件", "测试环境",
                "断言", "验证", "通过条件", "失败条件",
            ],
            "structure_markers": [
                "用例编号", "用例名称", "优先级",
                "P0", "P1", "P2", "P3",
                "功能测试", "集成测试", "回归测试",
            ]
        }
        
        # 技术规格文档特征
        self.technical_spec_patterns = {
            "title_patterns": [
                r"技术[_\s]?规格",
                r"技术[_\s]?方案",
                r"架构[_\s]?设计",
                r"technical[_\s]?spec",
            ],
            "keywords": [
                "架构", "组件", "模块", "服务",
                "数据库", "表结构", "字段",
                "部署", "集群", "缓存",
            ],
            "structure_markers": [
                "架构图", "流程图", "时序图",
                "数据库设计", "接口定义",
            ]
        }
        
        # 用户手册特征
        self.user_manual_patterns = {
            "title_patterns": [
                r"用户[_\s]?手册",
                r"使用[_\s]?指南",
                r"帮助[_\s]?文档",
                r"user[_\s]?manual",
            ],
            "keywords": [
                "如何使用", "快速开始", "安装",
                "配置", "步骤", "注意事项",
                "常见问题", "故障排除",
            ],
            "structure_markers": [
                "第一步", "第二步", "第三步",
                "截图", "示例图", "操作步骤",
            ]
        }
    
    def detect(self, content: str, filename: str = "", metadata: Dict = None) -> DocumentTypeProfile:
        """
        检测文档类型
        
        Args:
            content: 文档内容
            filename: 文件名（用于辅助判断）
            metadata: 现有元数据
            
        Returns:
            DocumentTypeProfile: 文档类型特征画像
        """
        # 1. 先检查文件名
        filename_type = self._detect_from_filename(filename)
        
        # 2. 检查内容特征
        content_type, content_features = self._detect_from_content(content)
        
        # 3. 综合判断
        scores = {
            DocumentType.API_DOC: 0.0,
            DocumentType.PRD: 0.0,
            DocumentType.TEST_CASE: 0.0,
            DocumentType.USER_MANUAL: 0.0,
            DocumentType.TECHNICAL_SPEC: 0.0,
        }
        
        # 文件名权重
        if filename_type != DocumentType.UNKNOWN:
            scores[filename_type] += 0.3
        
        # 内容特征权重
        for doc_type, features in content_features.items():
            scores[doc_type] += features * 0.7
        
        # 找出最高分
        max_score = max(scores.values())
        if max_score < 0.2:
            return self._create_unknown_profile()
        
        detected_type = max(scores, key=scores.get)
        confidence = min(max_score, 1.0)
        
        # 生成推荐配置
        return self._create_profile(detected_type, confidence, content_features)
    
    def _detect_from_filename(self, filename: str) -> DocumentType:
        """从文件名推断文档类型"""
        if not filename:
            return DocumentType.UNKNOWN
        
        filename_lower = filename.lower()
        
        if any(p in filename_lower for p in ["api", "接口", "_v", "rest"]):
            return DocumentType.API_DOC
        elif any(p in filename_lower for p in ["prd", "需求", "product"]):
            return DocumentType.PRD
        elif any(p in filename_lower for p in ["test", "测试", "case", "用例"]):
            return DocumentType.TEST_CASE
        elif any(p in filename_lower for p in ["技术", "spec", "架构", "technical"]):
            return DocumentType.TECHNICAL_SPEC
        elif any(p in filename_lower for p in ["manual", "guide", "手册", "指南"]):
            return DocumentType.USER_MANUAL
        
        return DocumentType.UNKNOWN
    
    def _detect_from_content(self, content: str) -> Tuple[DocumentType, Dict[DocumentType, float]]:
        """从内容特征检测文档类型"""
        if not content:
            return DocumentType.UNKNOWN, {}
        
        content_lower = content.lower()
        features = {}
        
        # 检测API文档特征
        api_score = self._calculate_type_score(
            content, content_lower, self.api_doc_patterns
        )
        features[DocumentType.API_DOC] = api_score
        
        # 检测PRD文档特征
        prd_score = self._calculate_type_score(
            content, content_lower, self.prd_patterns
        )
        features[DocumentType.PRD] = prd_score
        
        # 检测测试用例特征
        test_score = self._calculate_type_score(
            content, content_lower, self.test_case_patterns
        )
        features[DocumentType.TEST_CASE] = test_score
        
        # 检测技术规格特征
        tech_score = self._calculate_type_score(
            content, content_lower, self.technical_spec_patterns
        )
        features[DocumentType.TECHNICAL_SPEC] = tech_score
        
        # 检测用户手册特征
        manual_score = self._calculate_type_score(
            content, content_lower, self.user_manual_patterns
        )
        features[DocumentType.USER_MANUAL] = manual_score
        
        # 返回得分最高的类型
        max_type = max(features, key=features.get) if features else DocumentType.UNKNOWN
        return max_type, features
    
    def _calculate_type_score(
        self, 
        content: str, 
        content_lower: str, 
        patterns: Dict
    ) -> float:
        """计算某种类型的匹配得分"""
        score = 0.0
        
        # 标题匹配 (权重最高)
        title_matches = 0
        for pattern in patterns.get("title_patterns", []):
            if re.search(pattern, content_lower):
                title_matches += 1
        if title_matches > 0:
            score += 0.4 * min(title_matches / 2, 1.0)
        
        # 关键词匹配
        keyword_matches = sum(1 for kw in patterns.get("keywords", []) if kw in content_lower)
        if keyword_matches > 0:
            score += 0.3 * min(keyword_matches / 5, 1.0)
        
        # 结构标记匹配
        structure_matches = sum(1 for marker in patterns.get("structure_markers", []) if marker in content_lower)
        if structure_matches > 0:
            score += 0.3 * min(structure_matches / 5, 1.0)
        
        return score
    
    def _create_profile(
        self, 
        doc_type: DocumentType, 
        confidence: float,
        features: Dict[DocumentType, float]
    ) -> DocumentTypeProfile:
        """创建文档类型特征画像"""
        
        # 根据不同类型设置推荐配置
        type_configs = {
            DocumentType.API_DOC: {
                "strategy": "api_structured",
                "chunk_size": 800,
                "overlap": 100,
                "template": {
                    "api_endpoint": "",
                    "api_method": "",
                    "parameters": [],
                    "responses": []
                }
            },
            DocumentType.PRD: {
                "strategy": "hierarchical",
                "chunk_size": 1500,
                "overlap": 200,
                "template": {
                    "feature_name": "",
                    "user_stories": [],
                    "acceptance_criteria": []
                }
            },
            DocumentType.TEST_CASE: {
                "strategy": "test_case_oriented",
                "chunk_size": 1000,
                "overlap": 150,
                "template": {
                    "test_case_id": "",
                    "test_steps": [],
                    "expected_results": []
                }
            },
            DocumentType.TECHNICAL_SPEC: {
                "strategy": "hierarchical",
                "chunk_size": 1200,
                "overlap": 150,
                "template": {
                    "component": "",
                    "specifications": {}
                }
            },
            DocumentType.USER_MANUAL: {
                "strategy": "step_by_step",
                "chunk_size": 1000,
                "overlap": 150,
                "template": {
                    "section": "",
                    "steps": []
                }
            },
        }
        
        config = type_configs.get(doc_type, {
            "strategy": "semantic",
            "chunk_size": 1500,
            "overlap": 200,
            "template": {}
        })
        
        # 收集检测到的特征
        detected = [k.value for k, v in features.items() if v > 0.1]
        
        return DocumentTypeProfile(
            doc_type=doc_type,
            confidence=confidence,
            detected_features=detected,
            recommended_chunking_strategy=config["strategy"],
            recommended_chunk_size=config["chunk_size"],
            recommended_overlap=config["overlap"],
            metadata_template=config["template"]
        )
    
    def _create_unknown_profile(self) -> DocumentTypeProfile:
        """创建未知类型的默认画像"""
        return DocumentTypeProfile(
            doc_type=DocumentType.UNKNOWN,
            confidence=0.0,
            detected_features=[],
            recommended_chunking_strategy="recursive",
            recommended_chunk_size=1000,
            recommended_overlap=200,
            metadata_template={}
        )


def detect_document_type(
    content: str, 
    filename: str = "", 
    metadata: Dict = None
) -> Tuple[DocumentType, float, Dict]:
    """
    便捷函数：检测文档类型
    
    Returns:
        (文档类型, 置信度, 推荐配置)
    """
    detector = DocumentTypeDetector()
    profile = detector.detect(content, filename, metadata)
    
    return (
        profile.doc_type,
        profile.confidence,
        {
            "chunking_strategy": profile.recommended_chunking_strategy,
            "chunk_size": profile.recommended_chunk_size,
            "overlap": profile.recommended_overlap,
            "metadata_template": profile.metadata_template
        }
    )

