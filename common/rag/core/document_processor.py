# app/core/document_processor.py
import re
import logging
import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from common.rag.core.models import Document, DocumentChunk

logger = logging.getLogger(__name__)


@dataclass
class ChunkingConfig:
    """分块配置"""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    separators: List[str] = field(default_factory=lambda: [
        "\n\n", "\n", ".", "!", "?", ";", ":", "|", "}", ")", "]", ">", "。", "！", "？", "；", "：", "》", "）", "】"
    ])
    min_chunk_size: int = 50
    max_chunk_size: int = 2000
    chunking_strategy: str = "semantic"  # fixed, semantic, recursive, hierarchical

    def __post_init__(self):
        """验证配置"""
        if self.chunk_size <= 0:
            raise ValueError("chunk_size 必须大于0")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap 必须小于 chunk_size")


class DocumentProcessor:
    """文档处理模块 - 对采集的文档进行清洗、分块、预处理"""

    def __init__(self, config: ChunkingConfig = None):
        self.config = config or ChunkingConfig()
        self.encoder = tiktoken.get_encoding("cl100k_base")
        logger.info(f"文档处理器初始化: chunk_size={self.config.chunk_size}, strategy={self.config.chunking_strategy}")

    def process_documents(
            self,
            documents: List[Document],
            chunking_strategy: str = None
    ) -> List[DocumentChunk]:
        """
        处理文档：清洗 -> 分块 -> 预处理

        Args:
            documents: 原始文档列表
            chunking_strategy: 分块策略，覆盖默认配置

        Returns:
            List[DocumentChunk]: 标准化的文本块
        """
        all_chunks = []
        total_original_chars = 0
        total_processed_chars = 0

        for doc in documents:
            try:
                # 统计原始字符数
                total_original_chars += len(doc.content)

                # 1. 文本清洗
                cleaned_content = self._clean_text(doc.content)
                if not cleaned_content.strip():
                    logger.warning(f"文档 {doc.id} 清洗后内容为空，跳过")
                    continue

                # 2. 智能分块
                strategy = chunking_strategy or self.config.chunking_strategy
                chunks = self._chunk_document(cleaned_content, doc, strategy)

                # 3. 去重和过滤
                unique_chunks = self._deduplicate_chunks(chunks)
                valid_chunks = self._filter_chunks(unique_chunks)

                # 统计处理后的字符数
                for chunk in valid_chunks:
                    total_processed_chars += len(chunk.content)

                all_chunks.extend(valid_chunks)
                logger.info(f"文档 {doc.id} 分块为 {len(valid_chunks)} 个块")

            except Exception as e:
                logger.error(f"处理文档 {doc.id} 失败: {e}")
                continue

        logger.info(f"文档处理完成: 原始 {len(documents)} 文档 -> {len(all_chunks)} 个块, "
                    f"字符数: {total_original_chars:,} -> {total_processed_chars:,}")

        return all_chunks

    def _clean_text(self, text: str) -> str:
        """
        文本清洗
        - 统一编码（UTF-8）
        - 去除多余空白字符
        - 去重和噪音过滤
        """
        if not text:
            return ""

        # 1. 统一编码，确保UTF-8
        try:
            text = text.encode('utf-8', 'ignore').decode('utf-8')
        except:
            # 如果编码失败，尝试其他常见编码
            for encoding in ['gbk', 'gb2312', 'latin-1']:
                try:
                    text = text.encode(encoding, 'ignore').decode(encoding)
                    break
                except:
                    continue

        # 2. 统一换行符
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        # 3. 去除多余空白字符
        # 合并多个空白字符为单个空格
        text = re.sub(r'[ \t]+', ' ', text)
        # 合并多个换行符为单个换行符
        text = re.sub(r'\n\s*\n+', '\n\n', text)

        # 4. 去除不可见字符（保留常见标点）
        text = ''.join(char for char in text if char.isprintable() or char in '\n\t')

        # 5. 去除特定的噪音模式
        # 去除连续的标点符号
        text = re.sub(r'[.,;:!?。，；：！？]{3,}', '。', text)
        # 去除纯数字的行
        text = re.sub(r'^\d+$', '', text, flags=re.MULTILINE)
        # 去除过短的行（可能只是符号）
        lines = text.split('\n')
        cleaned_lines = [line for line in lines if len(line.strip()) > 2 or not re.match(r'^[\W\d]+$', line.strip())]
        text = '\n'.join(cleaned_lines)

        return text.strip()

    def _chunk_document(
            self,
            text: str,
            original_doc: Document,
            strategy: str
    ) -> List[DocumentChunk]:
        """智能分块策略"""
        if strategy == "fixed":
            return self._fixed_size_chunking(text, original_doc)
        elif strategy == "semantic":
            return self._semantic_chunking(text, original_doc)
        elif strategy == "recursive":
            return self._recursive_chunking(text, original_doc)
        elif strategy == "hierarchical":
            return self._hierarchical_chunking(text, original_doc)
        else:
            return self._semantic_chunking(text, original_doc)

    def _fixed_size_chunking(
            self,
            text: str,
            original_doc: Document
    ) -> List[DocumentChunk]:
        """固定大小分块"""
        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            # 计算分块结束位置
            end = min(start + self.config.chunk_size, len(text))

            # 避免在单词或句子中间切分
            if end < len(text):
                # 尝试在句子边界切分
                sentence_end = end
                while sentence_end > start and text[sentence_end] not in '.!?。！？\n':
                    sentence_end -= 1

                if sentence_end > start and sentence_end - start > self.config.chunk_size * 0.5:
                    end = sentence_end + 1
                else:
                    # 尝试在单词边界切分
                    while end > start and text[end] not in ' \n\t.,;!?。，；！？':
                        end -= 1

                    if end == start:  # 没有找到合适的切分点
                        end = start + self.config.chunk_size

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunk = self._create_chunk(
                    chunk_text, original_doc, chunk_index, start, end
                )
                chunks.append(chunk)
                chunk_index += 1

            # 移动起始位置，考虑重叠
            start = end - self.config.chunk_overlap
            if start < 0:
                start = 0

        return chunks

    def _semantic_chunking(
            self,
            text: str,
            original_doc: Document
    ) -> List[DocumentChunk]:
        """语义分块（基于句子和段落）"""
        # 首先按段落分割
        paragraphs = re.split(r'\n\s*\n', text)

        chunks = []
        current_chunk = []
        current_length = 0
        chunk_index = 0
        start_pos = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_length = len(self.encoder.encode(para))

            # 如果段落本身已经超过chunk_size，需要进一步分割
            if para_length > self.config.chunk_size:
                sub_chunks = self._recursive_chunking(para, original_doc)
                for sub_chunk in sub_chunks:
                    if current_length + len(self.encoder.encode(sub_chunk.content)) > self.config.chunk_size:
                        if current_chunk:
                            chunk = self._merge_chunks(
                                current_chunk, original_doc, chunk_index, start_pos
                            )
                            chunks.append(chunk)
                            chunk_index += 1
                            current_chunk = []
                            current_length = 0
                    current_chunk.append(sub_chunk)
                    current_length += len(self.encoder.encode(sub_chunk.content))
            else:
                # 如果添加当前段落后会超过限制，先保存当前块
                if current_length + para_length > self.config.chunk_size and current_chunk:
                    chunk = self._merge_chunks(
                        current_chunk, original_doc, chunk_index, start_pos
                    )
                    chunks.append(chunk)
                    chunk_index += 1
                    current_chunk = []
                    current_length = 0
                    start_pos += len(chunk.content)

                current_chunk.append(para)
                current_length += para_length

        # 处理最后一个块
        if current_chunk:
            chunk = self._merge_chunks(
                current_chunk, original_doc, chunk_index, start_pos
            )
            chunks.append(chunk)

        return chunks

    def _recursive_chunking(
            self,
            text: str,
            original_doc: Document
    ) -> List[DocumentChunk]:
        """递归分块（使用langchain的RecursiveCharacterTextSplitter）"""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            length_function=lambda x: len(self.encoder.encode(x)),
            separators=self.config.separators
        )

        texts = splitter.split_text(text)
        chunks = []

        for i, chunk_text in enumerate(texts):
            chunk = self._create_chunk(
                chunk_text, original_doc, i, 0, len(chunk_text)
            )
            chunks.append(chunk)

        return chunks

    def _hierarchical_chunking(
            self,
            text: str,
            original_doc: Document
    ) -> List[DocumentChunk]:
        """层次化分块（针对API文档等结构化内容）"""
        # 识别文档结构：标题、段落、列表、代码块
        lines = text.split('\n')
        chunks = []
        current_chunk_lines = []
        current_section = ""
        chunk_index = 0
        start_pos = 0

        for line in lines:
            line_stripped = line.strip()

            # 检测标题（Markdown风格或数字标题）
            is_title = (
                    line_stripped.startswith('#') or
                    re.match(r'^[A-Z][A-Z0-9._\s-]+$', line_stripped) or
                    re.match(r'^\d+\.\s+', line_stripped) or
                    re.match(r'^[一二三四五六七八九十]、', line_stripped)
            )

            # 检测代码块开始/结束
            is_code_block = line_stripped.startswith('```') or line_stripped.startswith('    ')

            if is_title or is_code_block:
                # 如果当前块有内容，先保存
                if current_chunk_lines and len('\n'.join(current_chunk_lines)) > self.config.min_chunk_size:
                    chunk_text = '\n'.join(current_chunk_lines)
                    chunk = self._create_chunk(
                        chunk_text, original_doc, chunk_index, start_pos, start_pos + len(chunk_text)
                    )
                    chunks.append(chunk)
                    chunk_index += 1
                    start_pos += len(chunk_text)
                    current_chunk_lines = []

                if is_title:
                    current_section = line_stripped

            current_chunk_lines.append(line)

            # 如果当前块达到大小限制，切分
            if len('\n'.join(current_chunk_lines)) >= self.config.chunk_size:
                chunk_text = '\n'.join(current_chunk_lines)
                chunk = self._create_chunk(
                    chunk_text, original_doc, chunk_index, start_pos, start_pos + len(chunk_text)
                )
                chunks.append(chunk)
                chunk_index += 1
                start_pos += len(chunk_text)
                current_chunk_lines = []

        # 处理最后一块
        if current_chunk_lines:
            chunk_text = '\n'.join(current_chunk_lines)
            chunk = self._create_chunk(
                chunk_text, original_doc, chunk_index, start_pos, start_pos + len(chunk_text)
            )
            chunks.append(chunk)

        return chunks

    def _create_chunk(
            self,
            text: str,
            original_doc: Document,
            chunk_index: int,
            start_pos: int,
            end_pos: int
    ) -> DocumentChunk:
        """创建文档块对象"""
        chunk = DocumentChunk(
            content=text,
            source_type=original_doc.source_type,
            source_uri=original_doc.source_uri,
            doc_type=original_doc.doc_type,
            metadata=original_doc.metadata.copy(),
            parent_doc_id=original_doc.id,
            chunk_index=chunk_index,
            start_pos=start_pos,
            end_pos=end_pos
        )

        # 更新元数据
        chunk.metadata.update({
            "chunk_size": len(text),
            "token_count": len(self.encoder.encode(text)),
            "is_chunk": True,
            "chunk_hash": hashlib.md5(text.encode()).hexdigest()[:16]
        })

        return chunk

    def _merge_chunks(
            self,
            chunk_parts,
            original_doc: Document,
            chunk_index: int,
            start_pos: int
    ) -> DocumentChunk:
        """合并多个部分为一个块"""
        if isinstance(chunk_parts[0], str):
            content = '\n\n'.join(chunk_parts)
        else:  # DocumentChunk
            content = '\n\n'.join([chunk.content for chunk in chunk_parts])

        return self._create_chunk(
            content, original_doc, chunk_index, start_pos, start_pos + len(content)
        )

    def _deduplicate_chunks(
            self,
            chunks: List[DocumentChunk]
    ) -> List[DocumentChunk]:
        """去重文档块"""
        seen = set()
        unique_chunks = []

        for chunk in chunks:
            # 基于内容哈希去重
            content_hash = hashlib.md5(chunk.content.encode()).hexdigest()
            if content_hash not in seen:
                seen.add(content_hash)
                unique_chunks.append(chunk)

        return unique_chunks

    def _filter_chunks(
            self,
            chunks: List[DocumentChunk]
    ) -> List[DocumentChunk]:
        """过滤无效文档块"""
        valid_chunks = []

        for chunk in chunks:
            # 检查长度
            if len(chunk.content.strip()) < self.config.min_chunk_size:
                continue

            # 检查是否为无意义内容
            if self._is_noise_content(chunk.content):
                continue

            # 检查token数量
            token_count = len(self.encoder.encode(chunk.content))
            if token_count > self.config.max_chunk_size * 3:
                logger.warning(f"文档块过长: {token_count} tokens")
                continue

            valid_chunks.append(chunk)

        return valid_chunks

    def _is_noise_content(self, text: str) -> bool:
        """判断是否为噪音内容"""
        # 移除空白字符
        clean_text = re.sub(r'\s+', '', text)

        # 检查是否为空或过短
        if len(clean_text) < 10:
            return True

        # 检查是否大部分是特殊字符
        special_chars = re.sub(r'[\w\u4e00-\u9fff]', '', clean_text)
        if len(special_chars) / len(clean_text) > 0.8:
            return True

        # 检查是否大部分是数字
        digits = re.sub(r'\D', '', clean_text)
        if len(digits) / len(clean_text) > 0.7:
            return True

        return False