# app/services/rag_service.py
import asyncio
import logging
import json
import hashlib
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path

from common.rag.core.knowledge_base import KnowledgeBase
from common.rag.core.config_manager import ConfigManager, RAGConfig
from common.rag.core.models import DocumentChunk

logger = logging.getLogger(__name__)


class RAGService:
    """RAG服务 - 提供完整的检索增强生成功能"""

    def __init__(self, config_dir: str = "app/config"):
        """
        初始化RAG服务

        Args:
            config_dir: 配置文件目录
        """
        # 加载配置
        self.config_manager = ConfigManager(config_dir).load_configs()
        self.rag_config = self.config_manager.get_rag_config()
        self.vector_db_config = self.config_manager.get_vector_db_config()

        # 加载业务模块配置
        self.business_modules_config = self._load_business_modules_config(config_dir)

        # 初始化知识库
        self.knowledge_base = KnowledgeBase(config_dir)

        # 初始化LLM客户端
        self.llm_client = self._init_llm_client()

        # 缓存目录
        self.cache_dir = Path("./cache")
        self.cache_dir.mkdir(exist_ok=True)

        # 记录详细的初始化信息
        logger.info("="*50)
        logger.info("🤖 RAG服务初始化详情:")
        logger.info(f"   📊 向量数据库: {self.vector_db_config.db_type}")
        logger.info(f"   🧠 Embedding模型: {self.rag_config.embedding_provider}/{self.rag_config.embedding_model}")
        logger.info(f"   💬 LLM模型: {self.rag_config.llm_provider}/{self.rag_config.llm_model}")
        logger.info(f"   📁 缓存目录: {self.cache_dir.absolute()}")
        logger.info(f"   🏢 业务模块: {len(self.business_modules_config.get('modules', {}))} 个已配置")
        logger.info("="*50)
        logger.info("✅ RAG服务初始化完成")

    def _init_llm_client(self):
        """初始化LLM客户端"""
        provider = self.rag_config.llm_provider.lower()
        model = self.rag_config.llm_model

        try:
            if provider == "tongyi":
                return self._init_tongyi_client()
            elif provider == "openai":
                return self._init_openai_client()
            elif provider == "ollama":
                return self._init_ollama_client()
            else:
                logger.warning(f"不支持的LLM provider: {provider}, 将使用模拟客户端")
                return self._init_mock_client()

        except Exception as e:
            logger.error(f"初始化LLM客户端失败: {e}")
        logger.warning("将使用模拟客户端")
        return self._init_mock_client()

    def _load_business_modules_config(self, config_dir: str) -> Dict[str, Any]:
        """加载业务模块配置"""
        config_path = os.path.join(config_dir, "rag", "business_modules.json")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info(f"加载业务模块配置成功，共 {len(config.get('modules', {}))} 个模块")
                return config
        except Exception as e:
            logger.warning(f"加载业务模块配置文件失败: {e}, 使用默认配置")
            return {
                "modules": {},
                "categories": {},
                "settings": {
                    "allow_custom_modules": False,
                    "default_module": None,
                    "require_module_specification": False
                }
            }

    def get_business_modules(self) -> Dict[str, Any]:
        """获取所有可用的业务模块"""
        return self.business_modules_config.get("modules", {})

    def validate_business_module(self, module_key: str) -> bool:
        """验证业务模块是否存在且启用"""
        modules = self.business_modules_config.get("modules", {})
        module_config = modules.get(module_key)
        if not module_config:
            return False
        return module_config.get("enabled", False)

    def _init_tongyi_client(self):
        """初始化通义千问客户端"""
        try:
            import dashscope
            from dashscope import Generation

            # 设置API密钥
            api_key = os.getenv('DASHSCOPE_API_KEY')
            if not api_key:
                logger.warning("未设置DASHSCOPE_API_KEY环境变量，将使用模拟客户端")
                return self._init_mock_client()

            dashscope.api_key = api_key

            # 测试连接
            try:
                Generation.call(
                    model=self.rag_config.llm_model,
                    prompt="test",
                    max_tokens=1
                )
                logger.info(f"通义千问客户端初始化成功: {self.rag_config.llm_model}")
                return Generation
            except Exception as e:
                logger.warning(f"通义千问连接测试失败: {e}, 将使用模拟客户端")
                return self._init_mock_client()

        except ImportError:
            logger.warning("未安装dashscope包，将使用模拟客户端")
            return self._init_mock_client()
        except Exception as e:
            logger.error(f"初始化通义千问客户端失败: {e}")
            return self._init_mock_client()

    def _init_openai_client(self):
        """初始化OpenAI客户端"""
        try:
            from openai import OpenAI

            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                logger.warning("未设置OPENAI_API_KEY环境变量，将使用模拟客户端")
                return self._init_mock_client()

            client = OpenAI(api_key=api_key)

            # 测试连接
            try:
                client.chat.completions.create(
                    model=self.rag_config.llm_model,
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1
                )
                logger.info(f"OpenAI客户端初始化成功: {self.rag_config.llm_model}")
                return client
            except Exception as e:
                logger.warning(f"OpenAI连接测试失败: {e}, 将使用模拟客户端")
                return self._init_mock_client()

        except ImportError:
            logger.warning("未安装openai包，将使用模拟客户端")
            return self._init_mock_client()
        except Exception as e:
            logger.error(f"初始化OpenAI客户端失败: {e}")
            return self._init_mock_client()

    def _init_ollama_client(self):
        """初始化Ollama客户端"""
        try:
            from openai import OpenAI

            # Ollama使用OpenAI兼容的API
            client = OpenAI(
                base_url='http://localhost:11434/v1',
                api_key='ollama'  # 不需要真实的API密钥
            )

            # 测试连接
            try:
                client.chat.completions.create(
                    model=self.rag_config.llm_model,
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1
                )
                logger.info(f"Ollama客户端初始化成功: {self.rag_config.llm_model}")
                return client
            except Exception as e:
                logger.warning(f"Ollama连接测试失败: {e}, 将使用模拟客户端")
                return self._init_mock_client()

        except ImportError:
            logger.warning("未安装openai包，将使用模拟客户端")
            return self._init_mock_client()
        except Exception as e:
            logger.error(f"初始化Ollama客户端失败: {e}")
            return self._init_mock_client()

    def _init_mock_client(self):
        """初始化模拟客户端（用于测试）"""
        logger.info("使用模拟LLM客户端（仅用于测试）")

        class MockClient:
            def call(self, model, prompt, temperature, max_tokens):
                class Response:
                    status_code = 200
                    output = type('obj', (object,), {'text': f"[模拟响应] 这是对 '{prompt[:50]}...' 的模拟回答。请安装并配置真正的LLM客户端。"})

                return Response()

            def chat(self):
                class Chat:
                    class completions:
                        @staticmethod
                        def create(model, messages, temperature, max_tokens):
                            class Choice:
                                class message:
                                    content = f"[模拟响应] 这是对 '{messages[-1]['content'][:50]}...' 的模拟回答。请安装并配置真正的LLM客户端。"

                            class Response:
                                choices = [Choice()]

                            return Response()

                return Chat()

        return MockClient()

    async def query(
            self,
            question: str,
            collection_name: str = None,
            top_k: int = None,
            temperature: float = None,
            max_tokens: int = None,
            filters: Dict[str, Any] = None,
            use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        完整的RAG查询流程

        Args:
            question: 用户问题
            collection_name: 集合名称
            top_k: 检索结果数量
            temperature: LLM温度
            max_tokens: 最大token数
            filters: 过滤条件 (如 {"business_module": "cross_border_opening"})
            use_cache: 是否使用缓存

        Returns:
            完整的回答
        """
        start_time = datetime.now()

        try:
            logger.info(f"RAG查询: {question}")

            # 1. 检查缓存
            cache_key = None
            if use_cache and self.rag_config.enable_cache:
                cache_key = self._generate_cache_key(
                    question, collection_name, top_k, temperature, max_tokens
                )
                cached_result = self._get_cache(cache_key)
                if cached_result:
                    logger.info("从缓存中获取结果")
                    return cached_result

            # 2. 检索相关文档
            search_results = await self.knowledge_base.search(
                query=question,
                collection_name=collection_name,
                top_k=top_k or self.rag_config.top_k,
                filters=filters
            )

            if not search_results:
                result = {
                    "question": question,
                    "answer": "抱歉，我没有找到相关的信息来回答这个问题。",
                    "sources": [],
                    "retrieved_count": 0,
                    "from_cache": False,
                    "elapsed_seconds": (datetime.now() - start_time).total_seconds(),
                    "timestamp": datetime.now().isoformat()
                }

                # 缓存结果
                if cache_key and self.rag_config.enable_cache:
                    self._set_cache(cache_key, result)

                return result

            # 3. 准备上下文
            context_chunks = []
            for chunk, score in search_results:
                context_chunks.append({
                    "content": chunk.content,
                    "score": float(score),
                    "source": chunk.source_uri or "未知来源",
                    "metadata": chunk.metadata
                })

            # 4. 构建prompt
            prompt = self._build_prompt(question, context_chunks)

            # 5. 调用LLM生成答案
            answer = await self._generate_answer(
                prompt=prompt,
                temperature=temperature or self.rag_config.temperature,
                max_tokens=max_tokens or self.rag_config.max_tokens
            )

            # 6. 构建结果
            result = {
                "question": question,
                "answer": answer,
                "sources": [
                    {
                        "content": chunk["content"][:200] + ("..." if len(chunk["content"]) > 200 else ""),
                        "score": chunk["score"],
                        "source": chunk["source"],
                        "relevance": self._get_relevance_label(chunk["score"])
                    }
                    for chunk in context_chunks
                ],
                "retrieved_count": len(context_chunks),
                "context_length": len(prompt),
                "from_cache": False,
                "elapsed_seconds": (datetime.now() - start_time).total_seconds(),
                "timestamp": datetime.now().isoformat()
            }

            # 7. 缓存结果
            if cache_key and self.rag_config.enable_cache:
                self._set_cache(cache_key, result)

            logger.info(f"RAG查询完成: 耗时 {result['elapsed_seconds']:.2f}秒")

            return result

        except Exception as e:
            logger.error(f"RAG查询失败: {e}")
            return {
                "question": question,
                "answer": f"抱歉，处理请求时发生错误: {str(e)[:100]}",
                "error": str(e),
                "elapsed_seconds": (datetime.now() - start_time).total_seconds(),
                "timestamp": datetime.now().isoformat()
            }

    def _generate_cache_key(
            self,
            question: str,
            collection_name: str = None,
            top_k: int = None,
            temperature: float = None,
            max_tokens: int = None
    ) -> str:
        """生成缓存键"""
        params = {
            "question": question,
            "collection": collection_name or getattr(self.knowledge_base.vector_db_config, 'collection_name',
                                                     'default'),
            "top_k": top_k or self.rag_config.top_k,
            "temperature": temperature or self.rag_config.temperature,
            "max_tokens": max_tokens or self.rag_config.max_tokens
        }

        params_str = json.dumps(params, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(params_str.encode()).hexdigest()

    def _get_cache(self, key: str) -> Optional[Dict]:
        """从缓存获取数据"""
        cache_file = self.cache_dir / f"{key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 检查是否过期
            if 'timestamp' in data:
                cache_time = datetime.fromisoformat(data['timestamp'])
                age = (datetime.now() - cache_time).total_seconds()

                if age > self.rag_config.cache_ttl:
                    # 缓存过期，删除文件
                    cache_file.unlink(missing_ok=True)
                    return None

            return data

        except Exception as e:
            logger.error(f"读取缓存失败: {e}")
            return None

    def _set_cache(self, key: str, data: Dict):
        """设置缓存"""
        cache_file = self.cache_dir / f"{key}.json"

        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"写入缓存失败: {e}")

    def _build_prompt(self, question: str, context_chunks: List[Dict]) -> str:
        """构建prompt"""
        # 合并上下文
        context_text = ""
        for i, chunk in enumerate(context_chunks, 1):
            context_text += f"[来源 {i} - 相关性分数: {chunk['score']:.3f}]\n"
            context_text += f"内容: {chunk['content']}\n\n"

        # 构建prompt模板
        prompt_template = """你是一个智能问答助手，请根据提供的参考信息来回答问题。

参考信息：
{context}

用户问题：{question}

请根据参考信息回答用户问题，回答时：
1. 只基于参考信息中的内容
2. 保持回答简洁、准确
3. 可以引用参考信息的编号来说明来源

请用中文回答："""

        prompt = prompt_template.format(
            context=context_text,
            question=question
        )

        # 检查token长度
        token_count = self._count_tokens(prompt)
        max_context = self.rag_config.max_context_length

        if token_count > max_context:
            logger.warning(f"Prompt过长: {token_count} tokens, 最大 {max_context}")
            # 截断上下文
            prompt = self._truncate_prompt(prompt, max_context)

        return prompt

    def _count_tokens(self, text: str) -> int:
        """计算token数量"""
        try:
            import tiktoken
            encoder = tiktoken.get_encoding("cl100k_base")
            return len(encoder.encode(text))
        except:
            # 简单估算：1个token ≈ 4个英文字符或2个中文字符
            chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
            other_chars = len(text) - chinese_chars
            return (chinese_chars // 2) + (other_chars // 4)

    def _truncate_prompt(self, prompt: str, max_tokens: int) -> str:
        """截断prompt以适应token限制"""
        # 简单实现：保留开头的系统提示和结尾的用户问题，截断中间
        system_end = prompt.find("用户问题：")

        if system_end > 0:
            system_part = prompt[:system_end]
            question_part = prompt[system_end:]

            # 计算系统部分token
            system_tokens = self._count_tokens(system_part)
            question_tokens = self._count_tokens(question_part)

            # 计算可用token
            available_tokens = max_tokens - system_tokens - question_tokens

            if available_tokens > 100:  # 至少保留100个token给上下文
                # 找到上下文部分
                context_start = prompt.find("参考信息：")
                context_end = prompt.find("用户问题：")

                if context_start > 0 and context_end > context_start:
                    context_part = prompt[context_start:context_end]
                    context_tokens = self._count_tokens(context_part)

                    if context_tokens > available_tokens:
                        # 需要截断上下文
                        # 简单实现：取上下文的前2/3
                        truncate_chars = int(len(context_part) * 2 / 3)
                        context_part = context_part[:truncate_chars] + "\n\n[上下文被截断...]"

                        # 重新组合
                        prompt = system_part[:context_start] + context_part + question_part

        return prompt

    async def _generate_answer(
            self,
            prompt: str,
            temperature: float = None,
            max_tokens: int = None
    ) -> str:
        """调用LLM生成答案"""
        if not self.llm_client:
            return "LLM客户端未初始化，无法生成答案。"

        provider = self.rag_config.llm_provider.lower()

        try:
            if provider == "tongyi":
                return await self._generate_tongyi_answer(prompt, temperature, max_tokens)
            elif provider in ["openai", "ollama"]:
                return await self._generate_openai_answer(prompt, temperature, max_tokens)
            else:
                return await self._generate_mock_answer(prompt)

        except Exception as e:
            logger.error(f"生成答案失败: {e}")
            return f"生成答案时发生错误: {str(e)[:100]}"

    async def _generate_tongyi_answer(self, prompt: str, temperature: float, max_tokens: int) -> str:
        """使用通义千问生成答案"""
        try:
            response = self.llm_client.call(
                model=self.rag_config.llm_model,
                prompt=prompt,
                temperature=temperature or self.rag_config.temperature,
                max_tokens=max_tokens or self.rag_config.max_tokens
            )

            if response.status_code == 200:
                return response.output.text
            else:
                return f"通义千问API错误: {response.message}"

        except Exception as e:
            logger.error(f"通义千问生成失败: {e}")
            return f"通义千问调用失败: {str(e)}"

    async def _generate_openai_answer(self, prompt: str, temperature: float, max_tokens: int) -> str:
        """使用OpenAI/Ollama生成答案"""
        try:
            response = self.llm_client.chat.completions.create(
                model=self.rag_config.llm_model,
                messages=[
                    {"role": "system", "content": "你是一个有帮助的助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature or self.rag_config.temperature,
                max_tokens=max_tokens or self.rag_config.max_tokens
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI生成失败: {e}")
            return f"OpenAI调用失败: {str(e)}"

    async def _generate_mock_answer(self, prompt: str) -> str:
        """生成模拟答案"""
        return f"[模拟响应] 这是对 '{prompt[:100]}...' 的模拟回答。请安装并配置真正的LLM客户端。"

    def _get_relevance_label(self, score: float) -> str:
        """获取相关性标签"""
        if score >= 0.9:
            return "极高"
        elif score >= 0.8:
            return "高"
        elif score >= 0.6:
            return "中"
        elif score >= 0.4:
            return "低"
        else:
            return "极低"

    async def build_knowledge_base(
            self,
            source_configs: List[Dict[str, Any]],
            collection_name: str = None,
            chunking_strategy: str = None
    ) -> Dict[str, Any]:
        """
        构建知识库

        Args:
            source_configs: 数据源配置
            collection_name: 集合名称
            chunking_strategy: 分块策略

        Returns:
            构建结果
        """
        return await self.knowledge_base.build_knowledge_base(
            source_configs=source_configs,
            collection_name=collection_name,
            chunking_strategy=chunking_strategy
        )

    async def search_only(
            self,
            query: str,
            collection_name: str = None,
            top_k: int = None
    ) -> Dict[str, Any]:
        """
        只搜索，不生成答案

        Args:
            query: 查询文本
            collection_name: 集合名称
            top_k: 返回数量

        Returns:
            搜索结果
        """
        return await self.knowledge_base.query_with_context(
            query=query,
            collection_name=collection_name,
            top_k=top_k
        )

    def get_collection_info(self, collection_name: str = None) -> Dict[str, Any]:
        """获取集合信息"""
        return self.knowledge_base.get_collection_info(collection_name)

    def list_collections(self) -> List[Dict[str, Any]]:
        """列出所有集合"""
        return self.knowledge_base.list_collections()

    def clear_cache(self):
        """清除缓存"""
        try:
            for file in self.cache_dir.glob("*.json"):
                file.unlink(missing_ok=True)
            logger.info("缓存已清除")
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")


# 简单使用示例
async def test_rag_service():
    """测试RAG服务"""
    # 初始化
    rag = RAGService()

    # 构建知识库
    print("构建知识库...")
    result = await rag.build_knowledge_base(
        source_configs=[
            {
                "source_type": "file",
                "paths": ["data/docs"],
                "extensions": [".txt", ".md"]
            }
        ],
        collection_name="test_kb"
    )

    print(f"构建结果: {result.get('status')}")

    if result.get("status") == "success":
        # 查询
        print("\n测试查询...")
        answer = await rag.query("什么是测试驱动开发？")

        print(f"问题: {answer['question']}")
        print(f"回答: {answer['answer'][:200]}...")
        print(f"来源数: {answer['retrieved_count']}")
        print(f"耗时: {answer['elapsed_seconds']:.2f}秒")


if __name__ == "__main__":
    asyncio.run(test_rag_service())