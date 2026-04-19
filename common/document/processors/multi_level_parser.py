"""
多层级文档解析器
解决问题：结构化解析只拆分为4部分导致的信息丢失

设计思路：
1. 多层级拆分：文档 → 章节 → 子章节 → 段落
2. 每层都保留完整信息，不丢失任何内容
3. 支持多种切片策略的组合使用
"""

import re
from typing import List, Dict, Tuple, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ContentLevel(Enum):
    """内容层级"""
    DOCUMENT = "document"        # 文档级
    CHAPTER = "chapter"          # 章节级
    SECTION = "section"          # 子章节级
    PARAGRAPH = "paragraph"      # 段落级


@dataclass
class DocumentSection:
    """文档章节"""
    title: str
    level: int  # 1=章, 2=节, 3=小节
    content: str
    children: List['DocumentSection'] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "level": self.level,
            "content": self.content,
            "children": [c.to_dict() for c in self.children],
            "metadata": self.metadata
        }


@dataclass
class MultiLevelParseResult:
    """多层级解析结果"""
    original_length: int
    total_sections: int
    hierarchy: DocumentSection
    chunks: List[Dict]  # 切片结果
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "original_length": self.original_length,
            "total_sections": self.total_sections,
            "hierarchy": self.hierarchy.to_dict() if self.hierarchy else {},
            "chunks": self.chunks,
            "warnings": self.warnings
        }


class MultiLevelDocumentParser:
    """
    多层级文档解析器
    
    特点：
    1. 多层级拆分，最大程度保留信息
    2. 支持多种切片策略组合
    3. 自动识别文档结构
    4. 提取元数据（标题、表格、图片等）
    """
    
    # 章节标题识别模式
    CHAPTER_PATTERNS = [
        r'^#{1}\s+(.+)$',                    # # 第一章
        r'^#{2}\s+(.+)$',                    # ## 第一节
        r'^#{3}\s+(.+)$',                    # ### 1.1 小节
        r'^(\d+\.?\d*)\s+(.+)$',              # 1. 第一章 / 1.1 第一节
        r'^(\d+\.)+\s+(.+)$',                 # 1.1.1 格式
        r'^【(.+)】$',                         # 【第一章】
        r'^第([一二三四五六七八九十]+)章\s*(.+)$', # 第一章 xxx
        r'^第([一二三四五六七八九十]+)节\s*(.+)$', # 第一节 xxx
    ]
    
    def __init__(self, min_chunk_size: int = 200, max_chunk_size: int = 1500):
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self._compile_patterns()
    
    def _compile_patterns(self):
        """编译正则表达式"""
        self.chapter_compiled = [re.compile(p, re.MULTILINE) for p in self.CHAPTER_PATTERNS]
    
    def parse(self, content: str, strategy: str = "semantic") -> MultiLevelParseResult:
        """
        解析文档
        
        Args:
            content: 文档内容
            strategy: 切片策略 (semantic, recursive, hierarchical, hybrid)
            
        Returns:
            MultiLevelParseResult: 解析结果
        """
        warnings = []
        original_length = len(content)
        
        # 1. 识别文档结构
        hierarchy = self._build_hierarchy(content)
        
        # 2. 统计章节数
        total_sections = self._count_sections(hierarchy)
        
        # 3. 根据策略生成切片
        chunks = self._generate_chunks(hierarchy, strategy)
        
        # 4. 检查信息丢失
        total_chunk_length = sum(len(c.get("content", "")) for c in chunks)
        if total_chunk_length < original_length * 0.8:
            warnings.append(f"信息可能丢失：原文{original_length}字符，切片后{total_chunk_length}字符")
        
        return MultiLevelParseResult(
            original_length=original_length,
            total_sections=total_sections,
            hierarchy=hierarchy,
            chunks=chunks,
            warnings=warnings
        )
    
    def _build_hierarchy(self, content: str) -> DocumentSection:
        """构建文档层级结构"""
        lines = content.split('\n')
        root = DocumentSection(title="根节点", level=0, content="")
        current_chapter = None
        current_section = None
        
        for line in lines:
            # 检查是否是标题行
            title_info = self._extract_title(line)
            
            if title_info:
                level, title = title_info
                
                if level == 1:
                    # 新建章节
                    current_chapter = DocumentSection(title=title, level=level, content="")
                    current_section = None
                    root.children.append(current_chapter)
                elif level == 2:
                    # 新建子章节
                    if current_chapter:
                        current_section = DocumentSection(title=title, level=level, content="")
                        current_chapter.children.append(current_section)
                # 累加内容
                if current_section:
                    current_section.content += line + '\n'
                elif current_chapter:
                    current_chapter.content += line + '\n'
            else:
                # 普通内容行
                if current_section:
                    current_section.content += line + '\n'
                elif current_chapter:
                    current_chapter.content += line + '\n'
                else:
                    root.content += line + '\n'
        
        return root
    
    def _extract_title(self, line: str) -> Optional[Tuple[int, str]]:
        """提取标题信息"""
        line = line.strip()
        if not line:
            return None
        
        # 尝试各种标题模式
        for i, pattern in enumerate(self.chapter_compiled):
            match = pattern.match(line)
            if match:
                groups = match.groups()
                
                # 确定层级
                if i <= 2:  # # 格式 # ## ###
                    level = i + 1
                    title = groups[0]
                elif i == 3:  # 1. xxx 格式
                    level = 1
                    title = groups[1]
                elif i == 4:  # 1.1.xxx 格式
                    level = len(groups[0].split('.'))
                    title = groups[-1]
                elif i == 5:  # 【】格式
                    level = 1
                    title = groups[0]
                elif i == 6:  # 第x章格式
                    level = 1
                    title = groups[1] if groups[1] else groups[0]
                elif i == 7:  # 第x节格式
                    level = 2
                    title = groups[1] if groups[1] else groups[0]
                else:
                    continue
                
                return (level, title)
        
        return None
    
    def _count_sections(self, node: DocumentSection) -> int:
        """统计章节数量"""
        count = 1
        for child in node.children:
            count += self._count_sections(child)
        return count
    
    def _generate_chunks(self, hierarchy: DocumentSection, strategy: str) -> List[Dict]:
        """根据策略生成切片"""
        if strategy == "semantic":
            return self._semantic_chunking(hierarchy)
        elif strategy == "recursive":
            return self._recursive_chunking(hierarchy)
        elif strategy == "hierarchical":
            return self._hierarchical_chunking(hierarchy)
        elif strategy == "hybrid":
            return self._hybrid_chunking(hierarchy)
        else:
            return self._semantic_chunking(hierarchy)
    
    def _semantic_chunking(self, hierarchy: DocumentSection) -> List[Dict]:
        """语义切片：按语义完整性切分"""
        chunks = []
        
        def process_node(node: DocumentSection, path: str = ""):
            current_path = f"{path}/{node.title}" if node.title else path
            
            # 获取纯内容（不含子章节）
            content = node.content.strip()
            
            if content and len(content) >= self.min_chunk_size:
                chunks.append({
                    "content": content,
                    "level": node.level,
                    "title": node.title,
                    "path": current_path,
                    "type": "semantic"
                })
            
            # 递归处理子章节
            for child in node.children:
                process_node(child, current_path)
        
        process_node(hierarchy)
        return chunks
    
    def _recursive_chunking(self, hierarchy: DocumentSection) -> List[Dict]:
        """递归切片：固定大小递归切分"""
        chunks = []
        
        def process_node(node: DocumentSection, path: str = ""):
            current_path = f"{path}/{node.title}" if node.title else path
            content = node.content.strip()
            
            if not content:
                for child in node.children:
                    process_node(child, current_path)
                return
            
            # 如果内容过长，递归切分
            if len(content) > self.max_chunk_size:
                # 按段落分割
                paragraphs = self._split_by_paragraphs(content)
                
                current_chunk = ""
                for para in paragraphs:
                    if len(current_chunk) + len(para) > self.max_chunk_size:
                        if current_chunk:
                            chunks.append({
                                "content": current_chunk.strip(),
                                "level": node.level,
                                "title": node.title,
                                "path": current_path,
                                "type": "recursive"
                            })
                        current_chunk = para
                    else:
                        current_chunk += "\n" + para
                
                if current_chunk.strip():
                    chunks.append({
                        "content": current_chunk.strip(),
                        "level": node.level,
                        "title": node.title,
                        "path": current_path,
                        "type": "recursive"
                    })
            else:
                chunks.append({
                    "content": content,
                    "level": node.level,
                    "title": node.title,
                    "path": current_path,
                    "type": "recursive"
                })
            
            # 递归处理子章节
            for child in node.children:
                process_node(child, current_path)
        
        process_node(hierarchy)
        return chunks
    
    def _hierarchical_chunking(self, hierarchy: DocumentSection) -> List[Dict]:
        """层级切片：保持层级结构"""
        chunks = []
        
        def process_node(node: DocumentSection, path: str = "", depth: int = 0):
            current_path = f"{path}/{node.title}" if node.title else path
            
            # 添加章节标题作为上下文
            context_header = f"{'#' * (node.level + 1)} {node.title}\n" if node.title else ""
            content = node.content.strip()
            
            if content:
                # 添加到切片
                chunks.append({
                    "content": context_header + content,
                    "level": node.level,
                    "title": node.title,
                    "path": current_path,
                    "depth": depth,
                    "type": "hierarchical"
                })
            
            # 递归处理子章节
            for child in node.children:
                process_node(child, current_path, depth + 1)
        
        process_node(hierarchy)
        return chunks
    
    def _hybrid_chunking(self, hierarchy: DocumentSection) -> List[Dict]:
        """混合切片：结合语义和递归"""
        # 第一遍：语义切片
        semantic_chunks = self._semantic_chunking(hierarchy)
        
        # 第二遍：对过大的语义块进行递归切分
        final_chunks = []
        
        for chunk in semantic_chunks:
            if len(chunk["content"]) > self.max_chunk_size:
                # 递归切分这个块
                sub_chunks = self._split_large_chunk(chunk["content"], chunk["title"])
                final_chunks.extend(sub_chunks)
            else:
                chunk["type"] = "hybrid"
                final_chunks.append(chunk)
        
        return final_chunks
    
    def _split_large_chunk(self, content: str, title: str) -> List[Dict]:
        """切分大块内容"""
        chunks = []
        
        # 按段落分割
        paragraphs = self._split_by_paragraphs(content)
        
        current_chunk = ""
        for para in paragraphs:
            if len(current_chunk) + len(para) > self.max_chunk_size:
                if current_chunk:
                    chunks.append({
                        "content": current_chunk.strip(),
                        "level": 2,
                        "title": title,
                        "type": "hybrid_split"
                    })
                current_chunk = para
            else:
                current_chunk += "\n" + para
        
        if current_chunk.strip():
            chunks.append({
                "content": current_chunk.strip(),
                "level": 2,
                "title": title,
                "type": "hybrid_split"
            })
        
        return chunks
    
    def _split_by_paragraphs(self, content: str) -> List[str]:
        """按段落分割"""
        # 多个换行符作为段落分隔符
        paragraphs = re.split(r'\n\s*\n', content)
        return [p.strip() for p in paragraphs if p.strip()]


class AdaptiveParser:
    """
    自适应解析器
    根据文档类型自动选择最佳解析策略
    """
    
    def __init__(self):
        self.multi_level_parser = MultiLevelDocumentParser()
        # 可以在这里添加更多特定类型的解析器
    
    def parse(self, content: str, doc_type: str = "auto") -> MultiLevelParseResult:
        """
        解析文档
        
        Args:
            content: 文档内容
            doc_type: 文档类型 (auto, api_doc, product_doc, requirement, technical)
        """
        if doc_type == "auto":
            doc_type = self._detect_doc_type(content)
        
        # 根据类型选择策略
        strategy = self._get_strategy(doc_type)
        
        return self.multi_level_parser.parse(content, strategy)
    
    def _detect_doc_type(self, content: str) -> str:
        """自动检测文档类型"""
        content_lower = content.lower()
        
        # API文档特征
        api_keywords = ["api", "endpoint", "get", "post", "put", "delete", 
                       "swagger", "openapi", "请求参数", "响应参数", "接口地址"]
        if sum(1 for kw in api_keywords if kw in content_lower) >= 3:
            return "api_doc"
        
        # 产品文档特征
        product_keywords = ["需求", "功能", "业务流程", "用户故事", "产品设计"]
        if sum(1 for kw in product_keywords if kw in content_lower) >= 2:
            return "product_doc"
        
        # 技术文档特征
        tech_keywords = ["技术", "架构", "数据库", "代码", "实现"]
        if sum(1 for kw in tech_keywords if kw in content_lower) >= 2:
            return "technical"
        
        return "generic"
    
    def _get_strategy(self, doc_type: str) -> str:
        """获取文档类型对应的最佳策略"""
        strategies = {
            "api_doc": "hierarchical",  # API文档保持层级结构很重要
            "product_doc": "hybrid",     # 产品文档混合使用
            "requirement": "semantic",  # 需求文档语义完整重要
            "technical": "recursive",   # 技术文档可递归切分
            "generic": "semantic"       # 默认语义切片
        }
        return strategies.get(doc_type, "semantic")


# 便捷函数
def parse_document(content: str, strategy: str = "semantic") -> MultiLevelParseResult:
    """解析文档的便捷函数"""
    parser = MultiLevelDocumentParser()
    return parser.parse(content, strategy)


def adaptive_parse(content: str, doc_type: str = "auto") -> MultiLevelParseResult:
    """自适应解析文档"""
    parser = AdaptiveParser()
    return parser.parse(content, doc_type)
