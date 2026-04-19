"""
业务上下文管理器

核心设计理念：
1. 先清洗后存储 - RAG 中存储的是干净的、清洗后的内容
2. 清洗流程独立 - 可单独调用

流程：
  原始文档/文件 → 文本提取 → LLM清洗 → 存入RAG → 查询使用
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from common.llm.llm_client import OpenAILLMClient

logger = logging.getLogger(__name__)


@dataclass
class ContextSource:
    """业务上下文来源"""
    source_type: str  # text/file/image/vector_db/context_id
    content: str = ""  # 原始文本内容
    file_path: str = ""  # 文件路径
    vector_query: str = ""  # 向量查询词
    collection_name: str = "documents"  # 向量库集合名
    top_k: int = 5  # 查询返回数量
    context_id: int = None  # 已有的上下文ID


@dataclass
class CleanedContext:
    """清洗后的业务上下文"""
    original_content: str  # 原始内容
    cleaned_content: str  # 清洗后的内容
    structured_knowledge: Dict[str, Any]  # 结构化知识
    summary: str  # 内容摘要
    keywords: List[str] = field(default_factory=list)  # 关键词
    errors: List[str] = field(default_factory=list)  # 处理过程中的错误


class BusinessContextManager:
    """
    业务上下文管理器

    核心功能：
    1. 从多种来源提取原始内容（文件、文本、图片）
    2. 调用 LLM 清洗内容
    3. 将清洗后的内容存入 RAG（而不是存"脏"数据）
    4. 从 RAG 查询干净的业务上下文
    5. 复用已清洗的上下文

    重要设计：
    - RAG 中只存储干净的内容
    - 清洗发生在存入 RAG 之前
    - 查询 RAG 直接得到干净内容，无需再次清洗
    """

    # LLM 清洗 Prompt
    CLEANING_PROMPT = """你是一个专业的业务分析师和技术文档专家。请对以下原始业务文档内容进行清洗和优化。

## 原始内容
{original_content}

## 清洗要求

1. **修正识别错误**
   - 修正 OCR 识别或文档解析产生的错误
   - 修正不完整的句子和段落
   - 修正乱码和格式问题

2. **补全缺失上下文**
   - 补全被截断的内容
   - 补充隐含的业务流程步骤
   - 说明业务规则的前提条件

3. **提炼核心知识**
   - 提取关键的业务实体（如：用户、订单、商品）
   - 提炼核心业务流程（如：下单流程、支付流程）
   - 明确业务规则和约束条件
   - 识别异常情况和边界条件

4. **结构化输出**
   - 按主题分类组织信息
   - 使用清晰的层次结构

## 输出格式（JSON）
```json
{{
  "cleaned_content": "清洗后的完整文本，保持段落结构和关键细节",
  "summary": "100字以内的内容摘要",
  "structured_knowledge": {{
    "entities": ["业务实体列表"],
    "processes": [
      {{
        "name": "流程名称",
        "steps": ["步骤1", "步骤2", "..."],
        "description": "流程描述"
      }}
    ],
    "rules": ["业务规则1", "业务规则2"],
    "constraints": ["约束条件1", "约束条件2"],
    "error_cases": ["异常情况1", "异常情况2"]
  }},
  "keywords": ["关键词1", "关键词2", "关键词3"]
}}
```

请直接返回 JSON，不要包含其他文字。"""

    # 长内容分段清洗 Prompt
    CHUNK_CLEANING_PROMPT = """你是一个专业的业务分析师。请对以下业务内容片段进行清洗和优化。

## 内容片段
{chunk_content}

## 上下文信息
{context_info}

## 要求
1. 修正识别错误和不完整内容
2. 与上下文信息保持一致性
3. 提炼该片段的核心业务知识

## 输出格式（JSON）
```json
{{
  "cleaned_content": "清洗后的文本",
  "summary": "30字以内的摘要",
  "key_points": ["关键点1", "关键点2"]
}}
```
请直接返回 JSON。"""

    def __init__(self, llm_client: Optional[OpenAILLMClient] = None):
        self.llm_client = llm_client

    def _extract_from_source(self, source: ContextSource) -> str:
        """从来源提取原始内容"""
        if source.source_type == "text":
            return source.content
        elif source.source_type == "file":
            return self._extract_from_file(source.file_path)
        elif source.source_type == "image":
            return self._extract_from_image(source.file_path)
        elif source.source_type == "vector_db":
            return self._query_vector_db(source.vector_query, source.collection_name, source.top_k)
        elif source.source_type == "context_id":
            return self._get_context_by_id(source.context_id)
        return ""

    def _extract_from_file(self, file_path: str) -> str:
        """从文件提取文本"""
        try:
            import os
            ext = os.path.splitext(file_path)[1].lower()

            if ext == ".pdf":
                return self._extract_pdf(file_path)
            elif ext in [".docx", ".doc"]:
                return self._extract_docx(file_path)
            elif ext in [".md", ".markdown", ".txt"]:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            return f"不支持的文件类型: {ext}"
        except Exception as e:
            logger.error(f"文件提取失败: {e}")
            return f"文件提取失败: {str(e)}"

    def _extract_pdf(self, file_path: str) -> str:
        """从 PDF 提取文本"""
        text = ""

        try:
            import fitz
            doc = fitz.open(file_path)
            for page in doc:
                text += page.get_text()
            doc.close()
            if text.strip():
                return text
        except:
            pass

        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except:
            pass

        return text or "PDF 提取失败"

    def _extract_docx(self, file_path: str) -> str:
        """从 Word 文档提取文本"""
        try:
            from docx import Document
            doc = Document(file_path)
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            text = "\n".join(paragraphs)

            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_text:
                        text += "\n" + row_text
            return text or "Word 文档提取失败"
        except:
            return "Word 文档提取失败"

    def _extract_from_image(self, image_path: str) -> str:
        """从图片提取文本（OCR）- 使用公共图片分析模块"""
        try:
            from utils.image_analysis.image_analyzer import analyze_image

            # 使用公共模块进行分析（默认使用详细流程图分析提示词）
            result = analyze_image(image_path=image_path, mode="flowchart")

            if result.get("success"):
                return result.get("analysis", "")
            else:
                error = result.get("error", "未知错误")
                logger.error(f"图片 OCR 失败: {error}")
                return f"图片 OCR 失败: {error}"

        except Exception as e:
            logger.error(f"图片 OCR 失败: {e}")
            return f"图片 OCR 失败: {str(e)}"

    def _query_vector_db(self, query: str, collection_name: str = "documents", top_k: int = 5) -> str:
        """从向量数据库查询内容（向量数据库已移除，始终返回空结果）"""
        logger.warning("向量数据库已移除，无法进行向量查询")
        return "向量数据库已移除，请使用其他数据源"

    def _get_context_by_id(self, context_id: int) -> str:
        """从数据库获取已有上下文"""
        try:
            from common.db.mapper.business_context_mapper import BusinessContextMapper
            mapper = BusinessContextMapper()
            context = mapper.get_by_id(context_id)
            if context:
                return context.content or "上下文内容为空"
            return "上下文不存在"
        except Exception as e:
            logger.error(f"获取上下文失败: {e}")
            return f"获取上下文失败: {str(e)}"

    def _parse_cleaning_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """解析 LLM 清洗响应"""
        try:
            text = response_text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            return json.loads(text)
        except Exception as e:
            logger.error(f"解析清洗响应失败: {e}")
            return None

    def _split_long_content(self, content: str, max_chars: int = 4000) -> List[str]:
        """将长内容分段"""
        if len(content) <= max_chars:
            return [content]

        chunks = []
        start = 0
        while start < len(content):
            end = min(start + max_chars, len(content))

            if end < len(content):
                for sep in ['。\n', '。', '.\n', '. ', '\n\n', '\n']:
                    last_sep = content.rfind(sep, start, end)
                    if last_sep > start + max_chars * 0.5:
                        end = last_sep + len(sep)
                        break

            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end - 200  # 200字符重叠

        return chunks

    def clean_context(
        self,
        source: ContextSource,
        save_to_rag: bool = True,
        business_module: str = None,
        document_title: str = None
    ) -> CleanedContext:
        """
        清洗业务上下文：提取 + 清洗

        这是核心方法，会：
        1. 从来源提取原始内容
        2. 调用 LLM 清洗
        3. 可选：将清洗后的内容存入 RAG

        Args:
            source: 业务上下文来源
            save_to_rag: 是否将清洗后的内容存入 RAG
            business_module: 业务模块（用于 RAG 存储）
            document_title: 文档标题（用于 RAG 存储）

        Returns:
            CleanedContext: 清洗后的上下文
        """
        result = CleanedContext(
            original_content="",
            cleaned_content="",
            structured_knowledge={},
            summary="",
            keywords=[],
            errors=[]
        )

        # 1. 提取原始内容
        logger.info(f"开始提取业务上下文: {source.source_type}")
        try:
            result.original_content = self._extract_from_source(source)
            if not result.original_content:
                result.errors.append("提取内容为空")
                return result
            logger.info(f"原始内容提取成功: {len(result.original_content)} 字符")
        except Exception as e:
            result.errors.append(f"内容提取失败: {str(e)}")
            return result

        # 2. 调用 LLM 清洗
        if not self.llm_client:
            result.cleaned_content = result.original_content
            result.summary = result.original_content[:200]
            result.errors.append("未配置 LLM 客户端，使用原始内容")
            return result

        try:
            # 检查内容长度
            if len(result.original_content) > 6000:
                result = self._clean_long_content(result)
            else:
                result = self._clean_short_content(result)

            logger.info(f"LLM 清洗完成: {len(result.cleaned_content)} 字符")

        except Exception as e:
            result.errors.append(f"LLM 清洗失败: {str(e)}")
            result.cleaned_content = result.original_content

        # 3. 存入 RAG（存储干净的、清洗后的内容）
        if save_to_rag and result.cleaned_content:
            self._save_to_rag(result, source, business_module, document_title)

        return result

    def _clean_short_content(self, result: CleanedContext) -> CleanedContext:
        """清洗短内容（直接调用 LLM）"""
        prompt = self.CLEANING_PROMPT.format(
            original_content=result.original_content[:80000]
        )

        response = self.llm_client.chat(prompt)
        response_text = self._extract_text(response)

        cleaned = self._parse_cleaning_response(response_text)
        if cleaned:
            result.cleaned_content = cleaned.get("cleaned_content", result.original_content)
            result.summary = cleaned.get("summary", "")
            result.structured_knowledge = cleaned.get("structured_knowledge", {})
            result.keywords = cleaned.get("keywords", [])
        else:
            result.errors.append("LLM 响应解析失败，使用原始内容")
            result.cleaned_content = result.original_content

        return result

    def _clean_long_content(self, result: CleanedContext) -> CleanedContext:
        """清洗长内容（分段处理后合并）"""
        chunks = self._split_long_content(result.original_content, max_chars=4000)
        logger.info(f"内容分段完成: {len(chunks)} 段")

        cleaned_parts = []
        all_keywords = []

        for i, chunk in enumerate(chunks):
            logger.info(f"清洗第 {i+1}/{len(chunks)} 段...")

            try:
                context_info = f"这是第 {i+1} 段，共 {len(chunks)} 段"
                if i > 0 and cleaned_parts:
                    context_info += f"\n前一段摘要: {cleaned_parts[-1]['summary']}"
                if i < len(chunks) - 1:
                    context_info += "\n提示: 可能存在后续内容"

                prompt = self.CHUNK_CLEANING_PROMPT.format(
                    chunk_content=chunk,
                    context_info=context_info
                )

                response = self.llm_client.chat(prompt)
                response_text = self._extract_text(response)

                cleaned = self._parse_cleaning_response(response_text)
                if cleaned:
                    cleaned_parts.append({
                        "content": cleaned.get("cleaned_content", chunk),
                        "summary": cleaned.get("summary", ""),
                        "key_points": cleaned.get("key_points", [])
                    })
                    all_keywords.extend(cleaned.get("key_points", []))
                    continue
            except Exception as e:
                logger.error(f"分段清洗失败: {e}")

            cleaned_parts.append({
                "content": chunk,
                "summary": chunk[:100],
                "key_points": []
            })

        # 合并结果
        result.cleaned_content = "\n\n".join(p["content"] for p in cleaned_parts)
        result.summary = " | ".join(p["summary"] for p in cleaned_parts[:3])
        if len(cleaned_parts) > 3:
            result.summary += f" ... (共 {len(cleaned_parts)} 段)"
        result.keywords = list(set(all_keywords))

        result.structured_knowledge = {
            "segments_count": len(chunks),
            "segments": cleaned_parts
        }

        return result

    def _save_to_rag(
        self,
        result: CleanedContext,
        source: ContextSource,
        business_module: str = None,
        document_title: str = None
    ) -> bool:
        """将清洗后的内容存入 RAG（向量数据库已移除，该功能不可用）"""
        logger.warning("向量数据库已移除，无法将内容存入 RAG")
        return False

    def _extract_text(self, response: Any) -> str:
        """从 LLM 响应中提取文本"""
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            content = response.get("content", [])
            if isinstance(content, list) and content:
                return content[0].get("text", "")
            return response.get("text", "")
        return str(response)

    def get_from_rag(
        self,
        query: str,
        collection_name: str = "documents",
        top_k: int = 5
    ) -> CleanedContext:
        """
        从 RAG 查询业务上下文（直接返回干净内容）

        因为 RAG 中存储的已经是干净内容，所以直接返回即可
        """
        try:
            content = self._query_vector_db(query, collection_name, top_k)

            # 这里不需要再次清洗，因为 RAG 中存的就是干净内容
            return CleanedContext(
                original_content="",
                cleaned_content=content,
                structured_knowledge={},
                summary=content[:200] if len(content) > 200 else content,
                keywords=[],
                errors=[]
            )

        except Exception as e:
            return CleanedContext(
                original_content="",
                cleaned_content="",
                structured_knowledge={},
                summary="",
                keywords=[],
                errors=[f"RAG 查询失败: {str(e)}"]
            )

    def get_context_by_id(self, context_id: int) -> Optional[CleanedContext]:
        """根据ID获取业务上下文"""
        try:
            from common.db.mapper.business_context_mapper import BusinessContextMapper
            mapper = BusinessContextMapper()
            context = mapper.get_by_id(context_id)

            if not context:
                return None

            return CleanedContext(
                original_content="",
                cleaned_content=context.content or "",
                structured_knowledge=context.metadata or {},
                summary=context.description or "",
                keywords=[]
            )

        except Exception as e:
            logger.error(f"获取业务上下文失败: {e}")
            return None


def extract_and_clean(
    source_type: str,
    content: str = None,
    file_path: str = None,
    image_path: str = None,
    vector_query: str = None,
    collection_name: str = "documents",
    context_id: int = None,
    llm_client: OpenAILLMClient = None,
    save_to_rag: bool = True,
    business_module: str = None,
    document_title: str = None
) -> CleanedContext:
    """
    便捷函数：提取并清洗业务上下文

    流程：
      原始文档 → 文本提取 → LLM清洗 → 存入RAG（可选）

    Args:
        source_type: 来源类型 (text/file/image/vector_db/context_id)
        content: 文本内容
        file_path: 文件路径
        image_path: 图片路径
        vector_query: 向量数据库查询词
        collection_name: RAG 集合名称
        context_id: 已有的上下文ID
        llm_client: LLM 客户端
        save_to_rag: 是否存入 RAG（默认 True）
        business_module: 业务模块
        document_title: 文档标题

    Returns:
        CleanedContext: 清洗后的上下文
    """
    source = ContextSource(
        source_type=source_type,
        content=content or "",
        file_path=file_path or image_path or "",
        vector_query=vector_query or "",
        collection_name=collection_name,
        context_id=context_id
    )

    manager = BusinessContextManager(llm_client)
    return manager.clean_context(source, save_to_rag, business_module, document_title)
