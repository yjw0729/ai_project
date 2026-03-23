# RabbitMQ 配置

通过 Docker Compose 启动 RabbitMQ 服务。

## 快速启动

```bash
cd infrastructure/rabbitmq
docker-compose up -d
```

## 服务信息

| 项目 | 值 |
|------|-----|
| AMQP 端口 | `5672` |
| 管理界面 | http://localhost:15672 |
| Prometheus 指标 | http://localhost:15692/metrics |
| 默认用户 | `admin` / `pytest_sxp_2026` |
| Virtual Host | `/` |

## 健康检查

容器启动后会自动执行 `rabbitmq-diagnostics -q ping` 验证服务可用性。

## 启用 Prometheus 插件

配置中已通过 `rabbitmq-plugins enable --offline rabbitmq_prometheus` 启用，指标通过 `15692` 端口暴露。

## 数据持久化

数据卷 `rabbitmq_data` 挂载到 `/var/lib/rabbitmq`，重启后消息和配置不丢失。

## 停止服务

```bash
cd infrastructure/rabbitmq
docker-compose down
```

如需清除所有数据（含持久化消息）：

```bash
docker-compose down -v
```
