# 服务启动指南

本文档说明如何启动 pytest_sxp 项目的各项服务。

---

## 一、基础设施服务

项目依赖以下基础设施服务，请确保它们已启动：

| 服务 | 默认地址 | 说明 |
|------|---------|------|
| **Redis** | `localhost:6379` | 任务状态缓存、限流（默认无密码） |
| **MySQL** | `localhost:3306` | 持久化存储 |
| **RabbitMQ** | `localhost:5672` | 消息队列（可选，无则降级同步模式） |

### 1.1 RabbitMQ（Docker 启动）

```bash
cd infrastructure/rabbitmq
docker-compose up -d
```

验证：
- 管理界面：http://localhost:15672
- 用户名：`admin`
- 密码：`pytest_sxp_2026`

### 1.2 Redis（本地或 Docker）

```bash
# Docker 方式
docker run -d --name pytest_sxp_redis -p 6379:6379 redis:7-alpine

# 或本地已安装 Redis，直接启动
redis-server
```

### 1.3 MySQL

请确保 MySQL 服务已运行，数据库 `crosstest` 已创建：

```bash
# 连接 MySQL
mysql -u root -p

# 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS crosstest DEFAULT CHARSET=utf8mb4;
```

首次运行还需创建任务追踪表：

```bash
mysql -u root -p crosstest < common/sql/task_execution_create.sql
```

---

## 二、快速启动

### 方式一：使用启动脚本（推荐）

```bash
# 进入项目根目录
cd d:\pythonProject\pytest_sxp

# 检查所有依赖服务状态
python scripts/start_services.py --check-only

# 启动 Flask API 服务（默认端口 5000）
python scripts/start_services.py

# 或指定端口和 debug 模式
python scripts/start_services.py --port 5001 --debug
```

### 方式二：直接启动 Worker

```bash
# 启动 Worker 进程（独立终端）
cd d:\pythonProject\pytest_sxp\workers
python start_workers.py
```

### 方式三：直接启动 Flask 应用

```bash
cd d:\pythonProject\pytest_sxp
python app/application.py
```

---

## 三、启动顺序

```
1. 基础设施（Redis、MySQL、RabbitMQ）已启动
   ↓
2. 可选：启动 Worker 进程（独立终端）
   python workers/start_workers.py
   ↓
3. 启动 Flask API 服务
   python scripts/start_services.py
```

---

## 四、功能说明

### 4.1 同步模式 vs 异步模式

| 基础设施 | 模式 | 说明 |
|---------|------|------|
| Redis + RabbitMQ 不可用 | **同步模式** | API 立即返回结果，无任务追踪 |
| Redis + RabbitMQ 可用 | **异步模式** | API 立即返回 task_id，后台执行 |

### 4.2 新增异步接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/auto_test/execute-async` | POST | 异步执行测试用例 |
| `/api/auto_test/task/<task_id>` | GET | 查询任务状态 |
| `/api/auto_test/task/<task_id>/cancel` | POST | 取消任务 |
| `/api/auto_test/task/list` | GET | 获取用户所有任务 |

### 4.3 健壮性功能

- **任务追踪**：所有异步操作记录到 `crosstest_task_execution` 表
- **乐观锁**：用例更新时版本检查，防止并发冲突
- **限流**：防止高频调用（默认 10 次/分钟）
- **执行隔离**：多用户同时执行，结果互不干扰

---

## 五、常见问题

### Q1: 启动时报 `ModuleNotFoundError: structlog`

```bash
pip install structlog pika
```

### Q2: RabbitMQ 连接失败

确保已通过 `docker-compose up -d` 启动 RabbitMQ，并检查端口 5672 是否被占用。

### Q3: Redis 连接失败

Redis 默认无密码。如果有密码需求，修改 `platform_core/service/` 下各服务文件中的 Redis 配置。

### Q4: 任务状态始终为 pending

检查 Worker 进程是否已启动，以及 RabbitMQ 是否正常运行。
