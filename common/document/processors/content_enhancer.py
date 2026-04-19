#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容增强器
在向量化和检索时增强文本块的内容，提升检索质量
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class EnhancementType(Enum):
    """增强类型"""
    CONTEXT = "context"           # 上下文增强
    METADATA = "metadata"         # 元数据增强
    KEYWORD = "keyword"           # 关键词增强
    STRUCTURE = "structure"       # 结构增强
    SUMMARY = "summary"           # 摘要增强


@dataclass
class EnhancementConfig:
    """增强配置"""
    add_summary: bool = True           # 添加摘要
    add_keywords: bool = True           # 添加关键词
    add_context: bool = True            # 添加上下文
    add_structure: bool = True          # 添加结构信息
    max_summary_length: int = 200       # 摘要最大长度
    max_keywords: int = 10             # 关键词最大数量


@dataclass
class EnhancedChunk:
    """增强后的文本块"""
    original_content: str
    enhanced_content: str
    summary: str = ""
    keywords: List[str] = field(default_factory=list)
    structure: Dict[str, Any] = field(default_factory=dict)
    entities: List[Dict[str, str]] = field(default_factory=list)
    enhancements: List[str] = field(default_factory=list)


class ContentEnhancer:
    """
    内容增强器
    
    功能：
    - 自动生成摘要
    - 提取关键词
    - 识别实体
    - 补充上下文信息
    - 保留结构信息
    """
    
    def __init__(self, config: EnhancementConfig = None):
        self.config = config or EnhancementConfig()
        logger.info("内容增强器初始化完成")
    
    def enhance(
        self,
        content: str,
        metadata: Dict[str, Any] = None,
        doc_type: str = None
    ) -> EnhancedChunk:
        """
        增强内容
        
        Args:
            content: 原始内容
            metadata: 元数据
            doc_type: 文档类型
            
        Returns:
            EnhancedChunk: 增强后的内容
        """
        meta = metadata or {}
        
        # 1. 提取关键词
        keywords = []
        if self.config.add_keywords:
            keywords = self._extract_keywords(content)
        
        # 2. 生成摘要
        summary = ""
        if self.config.add_summary:
            summary = self._generate_summary(content)
        
        # 3. 识别实体
        entities = self._extract_entities(content, doc_type)
        
        # 4. 提取结构信息
        structure = {}
        if self.config.add_structure:
            structure = self._extract_structure(content)
        
        # 5. 构建增强内容
        enhanced_parts = []
        enhancements = []
        
        # 添加结构信息
        if structure and self.config.add_structure:
            structure_str = self._format_structure(structure)
            enhanced_parts.append(structure_str)
            enhancements.append("structure")
        
        # 添加关键词
        if keywords and self.config.add_keywords:
            keywords_str = f"[关键词: {', '.join(keywords[:self.config.max_keywords])}]"
            enhanced_parts.append(keywords_str)
            enhancements.append("keywords")
        
        # 添加摘要
        if summary and self.config.add_summary:
            enhanced_parts.append(f"[摘要: {summary}]")
            enhancements.append("summary")
        
        # 添加实体信息
        if entities:
            entities_str = self._format_entities(entities)
            enhanced_parts.append(entities_str)
            enhancements.append("entities")
        
        # 组合增强内容
        if enhanced_parts:
            enhanced_content = content + "\n\n" + "\n".join(enhanced_parts)
        else:
            enhanced_content = content
        
        return EnhancedChunk(
            original_content=content,
            enhanced_content=enhanced_content,
            summary=summary,
            keywords=keywords,
            structure=structure,
            entities=entities,
            enhancements=enhancements
        )
    
    def _extract_keywords(self, content: str) -> List[str]:
        """提取关键词"""
        keywords = []
        
        # 1. 提取标题中的关键词
        heading_keywords = re.findall(r'^#{1,6}\s+(.+)$', content, re.MULTILINE)
        keywords.extend(heading_keywords[:3])
        
        # 2. 提取加粗文本
        bold_keywords = re.findall(r'\*\*(.+?)\*\*', content)
        keywords.extend(bold_keywords[:3])
        
        # 3. 提取代码中的标识符
        code_keywords = []
        code_blocks = re.findall(r'```[\s\S]*?```', content)
        for block in code_blocks:
            # 提取函数名
            code_keywords.extend(re.findall(r'def\s+(\w+)', block))
            code_keywords.extend(re.findall(r'class\s+(\w+)', block))
            code_keywords.extend(re.findall(r'function\s+(\w+)', block))
        keywords.extend(code_keywords[:5])
        
        # 4. 提取API端点
        api_endpoints = re.findall(
            r'(GET|POST|PUT|DELETE|PATCH)\s+(/[\w/{}.-]+)',
            content
        )
        keywords.extend([f"{method} {path}" for method, path in api_endpoints[:3]])
        
        # 去重
        seen = set()
        unique_keywords = []
        for kw in keywords:
            kw_clean = kw.strip()
            if kw_clean and kw_clean not in seen:
                seen.add(kw_clean)
                unique_keywords.append(kw_clean)
        
        return unique_keywords[:self.config.max_keywords]
    
    def _generate_summary(self, content: str) -> str:
        """生成摘要"""
        # 移除代码块
        content_no_code = re.sub(r'```[\s\S]*?```', '', content)
        content_no_code = re.sub(r'`[^`]+`', '', content_no_code)
        
        # 获取第一段（通常是概述）
        paragraphs = content_no_code.split('\n\n')
        first_para = ""
        for para in paragraphs:
            para = para.strip()
            # 跳过纯标题
            if para and not re.match(r'^#{1,6}\s+', para):
                first_para = para
                break
        
        if not first_para:
            first_para = paragraphs[0] if paragraphs else content[:200]
        
        # 截取合适长度
        if len(first_para) > self.config.max_summary_length:
            # 尝试在句号处截断
            sentences = re.split(r'[。！？.!?]', first_para)
            summary = ""
            for sent in sentences:
                if len(summary) + len(sent) <= self.config.max_summary_length:
                    summary += sent
                else:
                    break
            if not summary:
                summary = first_para[:self.config.max_summary_length]
        else:
            summary = first_para
        
        return summary.strip()
    
    def _extract_entities(self, content: str, doc_type: str = None) -> List[Dict[str, str]]:
        """提取实体"""
        entities = []
        
        # API相关实体
        if doc_type in ["api_doc", None]:
            # API端点
            endpoints = re.findall(
                r'(GET|POST|PUT|DELETE|PATCH)\s+(/[\w/{}.-]+)',
                content
            )
            for method, path in endpoints:
                entities.append({
                    "type": "api_endpoint",
                    "value": f"{method} {path}"
                })
            
            # 参数
            params = re.findall(r'(?:参数|parameter|字段)[：:]\s*(\w+)', content, re.IGNORECASE)
            for param in params[:5]:
                entities.append({
                    "type": "parameter",
                    "value": param
                })
        
        # 代码相关实体
        if doc_type in ["technical", None]:
            # 函数
            functions = re.findall(r'def\s+(\w+)', content)
            for func in functions[:5]:
                entities.append({
                    "type": "function",
                    "value": func
                })
            
            # 类
            classes = re.findall(r'class\s+(\w+)', content)
            for cls in classes[:5]:
                entities.append({
                    "type": "class",
                    "value": cls
                })
        
        # 数据库相关实体
        if doc_type in ["technical", "api_doc", None]:
            # 表名
            tables = re.findall(r'CREATE\s+TABLE\s+(\w+)', content, re.IGNORECASE)
            for table in tables[:3]:
                entities.append({
                    "type": "database_table",
                    "value": table
                })
        
        return entities
    
    def _extract_structure(self, content: str) -> Dict[str, Any]:
        """提取结构信息"""
        structure = {
            "headings": [],
            "code_blocks": 0,
            "tables": 0,
            "lists": 0
        }
        
        # 提取标题结构
        headings = re.findall(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE)
        for level, title in headings:
            structure["headings"].append({
                "level": len(level),
                "title": title.strip()
            })
        
        # 统计代码块
        structure["code_blocks"] = len(re.findall(r'```[\s\S]*?```', content))
        
        # 统计表格
        structure["tables"] = len(re.findall(r'\|[\s\S]*?\|\n\|[\s\S]*?\|', content))
        
        # 统计列表
        structure["lists"] = len(re.findall(r'^\s*[-*+]\s+', content, re.MULTILINE))
        structure["lists"] += len(re.findall(r'^\s*\d+\.\s+', content, re.MULTILINE))
        
        return structure
    
    def _format_structure(self, structure: Dict) -> str:
        """格式化结构信息"""
        parts = []
        
        if structure.get("headings"):
            heading_titles = [h["title"] for h in structure["headings"][:5]]
            parts.append(f"[文档结构: {' > '.join(heading_titles)}]")
        
        stats = []
        if structure.get("code_blocks", 0) > 0:
            stats.append(f"{structure['code_blocks']}个代码块")
        if structure.get("tables", 0) > 0:
            stats.append(f"{structure['tables']}个表格")
        if structure.get("lists", 0) > 0:
            stats.append(f"{structure['lists']}个列表项")
        
        if stats:
            parts.append(f"[内容统计: {', '.join(stats)}]")
        
        return "\n".join(parts)
    
    def _format_entities(self, entities: List[Dict]) -> str:
        """格式化实体信息"""
        if not entities:
            return ""
        
        # 按类型分组
        by_type = {}
        for entity in entities:
            e_type = entity.get("type", "unknown")
            if e_type not in by_type:
                by_type[e_type] = []
            by_type[e_type].append(entity.get("value", ""))
        
        # 格式化
        parts = []
        for e_type, values in by_type.items():
            type_name = {
                "api_endpoint": "API端点",
                "parameter": "参数",
                "function": "函数",
                "class": "类",
                "database_table": "数据库表"
            }.get(e_type, e_type)
            
            parts.append(f"[{type_name}: {', '.join(values[:5])}]")
        
        return "\n".join(parts)
    
    def enhance_batch(
        self,
        chunks: List[Dict[str, Any]],
        metadata: Dict[str, Any] = None,
        doc_type: str = None
    ) -> List[EnhancedChunk]:
        """批量增强"""
        results = []
        for chunk in chunks:
            content = chunk.get("content", "")
            chunk_meta = {**metadata, **chunk.get("metadata", {})}
            
            enhanced = self.enhance(content, chunk_meta, doc_type)
            results.append(enhanced)
        
        return results


class RetrievalEnhancer:
    """
    检索增强器
    
    在检索时为结果添加更多上下文信息
    """
    
    def __init__(self):
        self.content_enhancer = ContentEnhancer()
    
    def enhance_results(
        self,
        results: List[Tuple[Any, float]],
        query: str,
        metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        增强检索结果
        
        Args:
            results: 原始检索结果 (chunk, score)
            query: 查询文本
            metadata: 共享元数据
            
        Returns:
            增强后的结果
        """
        enhanced = []
        
        for chunk, score in results:
            # 提取内容
            content = getattr(chunk, 'content', str(chunk))
            
            # 计算与查询的相关性
            relevance_info = self._compute_relevance(content, query)
            
            # 增强内容
            enhanced_chunk = self.content_enhancer.enhance(
                content,
                metadata or {}
            )
            
            # 构建增强结果
            result = {
                "chunk": chunk,
                "score": score,
                "content": enhanced_chunk.enhanced_content,
                "original_content": content,
                "summary": enhanced_chunk.summary,
                "keywords": enhanced_chunk.keywords,
                "relevance": relevance_info,
                "enhancements": enhanced_chunk.enhancements
            }
            
            enhanced.append(result)
        
        return enhanced
    
    def _compute_relevance(self, content: str, query: str) -> Dict[str, Any]:
        """计算内容与查询的相关性"""
        # 简单实现：计算关键词重叠
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        
        overlap = query_words & content_words
        relevance_score = len(overlap) / max(len(query_words), 1)
        
        return {
            "score": relevance_score,
            "matched_terms": list(overlap),
            "query_terms": list(query_words)
        }


# 便捷函数
def enhance_content(
    content: str,
    metadata: Dict[str, Any] = None,
    doc_type: str = None
) -> EnhancedChunk:
    """增强内容的便捷函数"""
    enhancer = ContentEnhancer()
    return enhancer.enhance(content, metadata, doc_type)


def enhance_retrieval_results(
    results: List[Tuple[Any, float]],
    query: str,
    metadata: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """增强检索结果的便捷函数"""
    enhancer = RetrievalEnhancer()
    return enhancer.enhance_results(results, query, metadata)


if __name__ == "__main__":
    # 测试
    test_content = """
# 用户管理API

## 获取用户列表

GET /api/v1/users

获取所有用户列表，支持分页。

### 请求参数

| 名称 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码 |
| size | int | 否 | 每页数量 |

### 响应示例

```json
{
  "code": 0,
  "data": [
    {
      "id": 1,
      "name": "张三",
      "email": "zhangsan@example.com"
    }
  ]
}
```

## 创建用户

POST /api/v1/users

创建新用户。
"""
    
    enhancer = ContentEnhancer()
    result = enhancer.enhance(test_content, {"doc_type": "api_doc"})
    
    print("=== 原始内容 ===")
    print(result.original_content[:200])
    print("\n=== 增强内容 ===")
    print(result.enhanced_content[:500])
    print("\n=== 摘要 ===")
    print(result.summary)
    print("\n=== 关键词 ===")
    print(result.keywords)
    print("\n=== 实体 ===")
    print(result.entities)
    print("\n=== 结构 ===")
    print(result.structure)

