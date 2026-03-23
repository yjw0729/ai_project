# platform/

主测试平台服务目录。

## 目录结构

```
platform/
├── __init__.py
├── README.md
├── api/                      # API 层 - HTTP 接口 Blueprint
│     └── __init__.py
├── service/                  # 服务层 - 核心业务逻辑
│     ├── __init__.py
│     ├── task_service.py     # 任务管理（Redis + MySQL 双写）
│     ├── mq_client.py         # RabbitMQ 客户端封装
│     ├── rate_limiter.py     # 基于 Redis 的限流器
│     ├── async_api_helpers.py # 异步 API 辅助函数
│     └── mq_client.py
└── db/                       # 数据访问层 - 数据库操作
      └── __init__.py
```

## 分层说明

### api/ - API 层
HTTP 接口层，负责处理外部请求，调用 service 层完成业务逻辑。
**由原有的 `api/` 迁移而来。**

### service/ - 服务层
核心业务逻辑层，包含：
- `TaskService`: 任务管理，支持 Redis + MySQL 双写模式
- `MQClient`: RabbitMQ 消息发布与订阅
- `RateLimiter`: 基于 Redis 的滑动窗口限流

### db/ - 数据访问层
数据持久化操作层，封装数据库访问。
**由原有的 `common/db_mapper/` 和 `common/db_enitiy/` 迁移而来。**

## 依赖关系

```
外部请求 → api/ → service/ → db/
                 ↓
            RabbitMQ → workers/
```

## 状态

- `platform/` ✅ 新骨架（Step 1 完成）
- `platform_core/` ⚠️ 旧骨架（与 `platform/` 重复，待迁移/清理）
