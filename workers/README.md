# workers/

独立运行的 Worker 进程目录。

## 目录结构

```
workers/
├── __init__.py
├── start_workers.py          # 统一启动脚本
└── test_worker.py            # 测试执行 Worker（已实现）
```

## Worker 类型

| Worker | 文件 | 状态 | 说明 |
|--------|------|------|------|
| **test_worker** | `test_worker.py` | ✅ 已实现 | 消费 `test.execute` 队列，执行测试用例 |
| **llm_worker** | - | 🔜 待实现 | 消费 `llm.generate` 队列，生成测试用例 |
| **rag_worker** | - | 🔜 待实现 | 消费 `rag.index` 队列，索引文档向量 |

## 启动方式

```bash
cd d:\pythonProject\pytest_sxp
python workers/start_workers.py
```

## 消息队列依赖

Worker 依赖 RabbitMQ 服务，请确保 `infrastructure/rabbitmq/` 已启动。

```bash
cd infrastructure/rabbitmq
docker-compose up -d
```
