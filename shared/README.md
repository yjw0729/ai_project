# shared/

跨服务共享包目录。独立发布为 pip 包，供各服务安装使用。

## 目录结构

```
shared/
├── __init__.py
├── setup.py                   # pip 包打包配置
├── README.md
├── common_proto/               # 共享协议（schemas + MQ + trace）
│     ├── __init__.py
│     ├── schemas.py            # Pydantic 共享数据模型
│     ├── mq_messages.py         # RabbitMQ 消息格式定义
│     └── trace.py               # 链路追踪基础设施
└── llm-sdk/                    # LLM 客户端 SDK（独立 pip 包）
      ├── __init__.py
      └── llm_client.py         # LLM 客户端实现
```

## common-proto/

跨服务共享的数据协议，包括：

| 模块 | 文件 | 说明 |
|------|------|------|
| **schemas** | `schemas.py` | 统一请求/响应格式（Pydantic 模型） |
| **mq_messages** | `mq_messages.py` | RabbitMQ 消息体 + 队列配置 |
| **trace** | `trace.py` | trace_id 链路追踪 + 结构化日志 |

## llm-sdk/

LLM 客户端共享包，可独立发布为 pip 包：

```bash
cd shared
pip install -e .
```

## 使用方式

```python
# 导入共享协议
from shared.common_proto import TaskStatus, MQMessage

# 导入 LLM 客户端
from shared.llm_sdk import LLMClient, MockLLMClient
```
