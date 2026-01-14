# 数据库连接超时问题解决方案

## 🚨 问题描述

当后端在测试环境运行正常时，前端页面调用后端查询接口会出现数据库超时。这通常是数据库连接管理不当导致的。

## 🔍 问题根源分析

### 1. 连接池配置不完整
**现象**：连接池大小不足，高并发时连接耗尽
**原因**：pool_size 和 max_overflow 设置过小

### 2. 连接超时设置不当
**现象**：网络波动或数据库负载高时连接超时
**原因**：缺少连接超时、读取超时等参数

### 3. 连接回收机制缺失
**现象**：长时间闲置的连接被数据库服务器断开
**原因**：没有设置连接回收时间

### 4. 连接健康检查缺失
**现象**：使用已失效的连接导致查询失败
**原因**：没有连接前置检查机制

## ✅ 解决方案

### 1. 优化数据库连接配置

已更新的 `common/datacase_function/contect_db.py` 包含以下改进：

```python
engine = create_engine(
    f"{db_type}://{user}:{quote_plus(password)}@{host}:{port}/{db_name}",
    echo=False,

    # 连接池配置
    pool_size=10,              # 连接池大小（从5增加到10）
    max_overflow=20,           # 最大溢出连接数（从10增加到20）
    pool_timeout=30,           # 获取连接的超时时间
    pool_recycle=3600,         # 连接回收时间（1小时）
    pool_pre_ping=True,        # 连接前检查连接健康状态

    # 连接超时配置
    connect_args={
        'connect_timeout': 10,     # 连接超时
        'read_timeout': 30,        # 读取超时
        'write_timeout': 30,       # 写入超时
        'autocommit': True,        # 自动提交
    }
)
```

### 2. 添加连接监控API

#### 获取连接状态
```bash
GET /data_service/database/connection/status?db_key=default
```

响应：
```json
{
  "code": 200,
  "msg": "查询成功",
  "data": {
    "db_key": "default",
    "connection_status": "正常",
    "pool_info": {
      "pool_size": 10,
      "checked_out": 2,
      "checked_in": 8,
      "invalid_count": 0
    }
  }
}
```

#### 测试连接
```bash
POST /data_service/database/connection/test
Content-Type: application/json

{
  "db_key": "default"
}
```

### 3. 部署环境优化建议

#### Nginx 配置（如果使用Nginx作为反向代理）

```nginx
# nginx.conf
upstream flask_app {
    server 127.0.0.1:8080;
    keepalive 32;  # 保持连接
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://flask_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # 超时设置
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;

        # 保持连接
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
}
```

#### Gunicorn 配置（生产环境）

```python
# gunicorn.conf.py
bind = "0.0.0.0:8080"
workers = 4
worker_class = "gevent"
worker_connections = 1000

# 超时设置
timeout = 30
keepalive = 10

# 数据库连接优化
preload_app = True  # 预加载应用，避免fork时重新连接数据库
```

#### 系统层面优化

```bash
# Linux 系统参数优化
echo "net.core.somaxconn = 65536" >> /etc/sysctl.conf
echo "net.ipv4.tcp_tw_reuse = 1" >> /etc/sysctl.conf
sysctl -p

# 数据库连接数限制
# MySQL: max_connections = 200
# PostgreSQL: max_connections = 200
```

### 4. 应用层面优化

#### 数据库查询优化

```python
# 使用连接上下文管理器
from common.datacase_function.contect_db import db_session

def query_data():
    with db_session("default") as session:
        # 查询操作
        results = session.query(SomeModel).filter(...).all()
        return results
```

#### 连接重试机制

```python
import time
from sqlalchemy.exc import OperationalError

def query_with_retry(db_key="default", max_retries=3):
    for attempt in range(max_retries):
        try:
            with db_session(db_key) as session:
                return session.query(...).all()
        except OperationalError as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2 ** attempt)  # 指数退避
```

### 5. 监控和诊断

#### 定期检查连接状态

```python
# 在应用中添加定时任务
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.add_job(
    func=lambda: check_database_connections(),
    trigger="interval",
    minutes=5
)
scheduler.start()

def check_database_connections():
    """定期检查所有数据库连接"""
    db_keys = ["default", "opts", "localhost"]
    for db_key in db_keys:
        status = get_connection_status(db_key)
        if not test_connection(db_key):
            logger.warning(f"数据库连接异常: {db_key}")
            # 可以发送告警或尝试重连
```

#### 应用启动检查

应用启动时会自动显示：
```
📊 数据库状态: MySQL数据库连接正常 | 连接池: 2/10使用中
🤖 RAG服务状态: 本地ChromaDB (持久化存储, 2个文件, 228.0KB)
```

## 🔧 故障排除

### 连接池耗尽
**现象**：`TimeoutError: QueuePool limit of size 10 overflow 20 reached`
**解决**：
1. 增加 `pool_size` 和 `max_overflow`
2. 检查是否有连接泄露（未正确关闭连接）
3. 添加连接监控

### 连接超时
**现象**：`OperationalError: (2003, "Can't connect to MySQL server")`
**解决**：
1. 检查网络连接
2. 增加 `connect_timeout`
3. 配置连接重试

### 读取超时
**现象**：查询长时间无响应
**解决**：
1. 增加 `read_timeout`
2. 优化查询性能
3. 添加查询超时

## 📊 性能监控

### 关键指标

1. **连接池使用率**：`checked_out / pool_size`
2. **连接创建频率**
3. **查询响应时间**
4. **连接错误率**

### 告警阈值

- 连接池使用率 > 80%
- 连接错误率 > 5%
- 查询平均响应时间 > 5秒

## 🎯 总结

通过以上优化，可以有效解决前端调用后端数据库查询接口的超时问题：

1. ✅ **连接池优化**：增大池大小，添加超时配置
2. ✅ **连接管理**：自动回收，健康检查
3. ✅ **监控接口**：实时查看连接状态
4. ✅ **部署优化**：反向代理和应用服务器配置
5. ✅ **故障恢复**：连接重试和自动恢复机制

现在您的系统应该能够稳定处理前端的高并发请求，而不会出现数据库连接超时的问题！🚀

