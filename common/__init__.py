# common/__init__.py
"""
common/ 模块索引。

本目录包含项目的核心业务代码，按以下层次组织：

├── llm/              # 大模型层：调用大模型生成内容
├── document/         # 文档处理层：各类文档解析、分块、连接器
├── pytest/           # pytest 层：用例生成、执行、断言、fixtures
├── test_executor/    # 测试执行层：用例执行、参数解析
├── db/               # 数据库层：entity / mapper / datacase
├── services/        # 业务服务层：断言引擎、文档解析、数据工厂
├── models/          # 数据模型层：通用数据结构定义
├── error_code/      # 错误码库
├── worker/          # 异步任务处理
├── mq/              # 消息队列
├── assertion/       # 断言自动生成
└── sql/             # SQL脚本
"""

__version__ = "1.0.0"
