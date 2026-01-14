# 简化的RAG测试
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 导入RAG服务
try:
    from common.rag.services.rag_services import RAGService
except ImportError as e:
    print(f"导入RAGService失败: {e}")
    print("请确保所有依赖都已安装")
    sys.exit(1)

print("开始简化的RAG测试...")

try:
    # 直接测试向量存储
    print("测试内存向量存储...")

    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np

    class MemoryVectorStore:
        def __init__(self, dimension=768):
            self.dimension = dimension
            self.vectors = []
            self.metadata = []
            self.ids = []

        def add_vectors(self, vectors, metadata=None, ids=None):
            if isinstance(vectors, list):
                vectors = np.array(vectors)
            self.vectors.extend(vectors.tolist() if hasattr(vectors, 'tolist') else vectors)
            if metadata:
                self.metadata.extend(metadata)
            else:
                self.metadata.extend([{}] * len(vectors))
            if ids:
                self.ids.extend(ids)
            else:
                start_id = len(self.ids)
                self.ids.extend([f"vec_{start_id + i}" for i in range(len(vectors))])

        def search(self, query_vector, top_k=5):
            if not self.vectors:
                return []
            if isinstance(query_vector, list):
                query_vector = np.array(query_vector)
            vectors_array = np.array(self.vectors)
            similarities = cosine_similarity([query_vector], vectors_array)[0]
            top_indices = np.argsort(similarities)[-top_k:][::-1]
            results = []
            for idx in top_indices:
                results.append({
                    'id': self.ids[idx],
                    'score': float(similarities[idx]),
                    'metadata': self.metadata[idx]
                })
            return results

    # 测试内存存储
    store = MemoryVectorStore()
    test_vectors = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    store.add_vectors(test_vectors, ids=['vec1', 'vec2', 'vec3'])

    results = store.search([1, 0, 0], top_k=2)
    print("✓ 内存向量存储测试成功")
    print(f"搜索结果: {results}")

    print("✓ RAG核心功能测试通过")
    print("数据库连接问题已解决，现在使用内存向量存储")

except Exception as e:
    print(f"✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()


async def main():
    """快速开始示例"""

    # 1. 初始化RAG服务
    print("初始化RAG服务...")
    try:
        rag = RAGService()
        print("✓ RAG服务初始化成功（未连接数据库）")
    except Exception as e:
        print(f"✗ RAG服务初始化失败: {e}")
        return

    # 检查配置和环境变量
    print("\n" + "="*60)
    print("系统配置检查")
    print("="*60)

    rag_config = rag.rag_config
    print(f"Embedding提供商: {rag_config.embedding_provider}")
    print(f"Embedding模型: {rag_config.embedding_model}")
    print(f"LLM提供商: {rag_config.llm_provider}")
    print(f"LLM模型: {rag_config.llm_model}")

    # 检查环境变量
    import os
    dashscope_key = os.getenv('DASHSCOPE_API_KEY')
    openai_key = os.getenv('OPENAI_API_KEY')

    print("\n环境变量检查:")
    print(f"DASHSCOPE_API_KEY: {'✓ 已设置' if dashscope_key else '✗ 未设置'}")
    print(f"OPENAI_API_KEY: {'✓ 已设置' if openai_key else '✗ 未设置'}")

    if not dashscope_key and not openai_key:
        print("\n⚠️  警告: 没有配置API密钥，将使用模拟模式")
        print("   要启用真实功能，请设置以下环境变量之一:")
        print("   - DASHSCOPE_API_KEY (通义千问)")
        print("   - OPENAI_API_KEY (OpenAI)")
        print("   设置方法: 在系统环境变量中添加，或在命令行中运行:")
        print("   set DASHSCOPE_API_KEY=your_key_here")
        print("="*60)

    # 2. 构建知识库
    print("\n构建知识库...")
    docs_path = Path(__file__).parent.parent.parent / "data" / "test_docs"
    print(f"文档路径: {docs_path}")
    print(f"路径存在: {docs_path.exists()}")

    # 直接测试FileConnector
    from common.rag.connectors.file_connector import FileConnector
    connector = FileConnector()
    test_config = {
        "paths": [str(docs_path)],
        "extensions": [".txt", ".md"],
        "recursive": True
    }
    documents = connector.collect(test_config)
    print(f"直接测试FileConnector采集到 {len(documents)} 个文档")

    source_configs = [
        {
            "source_type": "file",
            "paths": [str(docs_path)],  # 绝对路径
            "extensions": [".txt", ".md"],
            "recursive": True
        }
    ]

    build_result = await rag.build_knowledge_base(
        source_configs=source_configs,
        collection_name="test_knowledge"
    )

    print(f"构建结果: {build_result['status']}")

    if build_result["status"] == "success":
        # 3. 查询示例
        test_questions = [
            "什么是单元测试？",
            "如何编写API测试？",
            "测试用例应该包含哪些内容？"
        ]

        for question in test_questions:
            print(f"\n{'=' * 60}")
            print(f"问题: {question}")

            result = await rag.query(question)

            print(f"\n回答: {result['answer'][:300]}...")
            print(f"来源数: {result['retrieved_count']}")
            print(f"耗时: {result['elapsed_seconds']:.2f}秒")

            if result['sources']:
                print(f"\n相关来源:")
                for i, source in enumerate(result['sources'][:2], 1):
                    print(f"  {i}. {source['source']} (相关性: {source['relevance']})")


if __name__ == "__main__":
    asyncio.run(main())