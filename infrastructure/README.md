# infrastructure/

基础设施配置目录。

## 目录结构

```
infrastructure/
└── rabbitmq/          # RabbitMQ 消息队列服务
      ├── docker-compose.yml   # 服务编排配置
      └── data/               # RabbitMQ 数据持久化（mnesia）
```

## rabbitmq/

通过 Docker Compose 启动 RabbitMQ 服务：

```bash
cd infrastructure/rabbitmq
docker-compose up -d
```

- 管理界面: http://localhost:15672
- 默认用户: `admin` / `pytest_sxp_2026`
- AMQP 端口: `5672`
