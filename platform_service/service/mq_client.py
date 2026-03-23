"""
RabbitMQ 客户端封装。

提供功能：
- MQClient: RabbitMQ 连接管理和消息发布
- MQConsumer: 消息消费者基类（各 Worker 继承）

设计要点：
- 连接复用（单例模式）
- 消息持久化（delivery_mode=2）
- 自动重连
- 死信队列（DLX）
"""

import json
import time
import threading
import pika
import structlog
from typing import Callable, Optional, Dict, Any

from shared.common_proto.mq_messages import MQMessage

logger = structlog.get_logger()


class MQClient:
    """
    RabbitMQ 发布客户端（单例）。
    用于 API 层发布消息到队列。
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, config: Optional[Dict[str, Any]] = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if self._initialized:
            return

        self.config = config or {
            "host": "localhost",
            "port": 5672,
            "username": "admin",
            "password": "pytest_sxp_2026",
            "virtual_host": "/",
        }
        self.connection = None
        self.channel = None
        self._initialized = True

    def connect(self) -> bool:
        try:
            credentials = pika.PlainCredentials(
                self.config["username"],
                self.config["password"]
            )
            self.connection = pika.BlockingConnection(pika.ConnectionParameters(
                host=self.config["host"],
                port=self.config["port"],
                virtual_host=self.config["virtual_host"],
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300,
            ))
            self.channel = self.connection.channel()
            self._declare_exchanges()
            logger.info("RabbitMQ连接成功", host=self.config["host"], port=self.config["port"])
            return True
        except Exception as e:
            logger.error("RabbitMQ连接失败", error=str(e))
            return False

    def _ensure_connection(self):
        if not self.connection or self.connection.is_closed:
            self.connect()
        elif not self.channel or self.channel.is_closed:
            self.channel = self.connection.channel()
            self._declare_exchanges()

    def _declare_exchanges(self):
        exchanges = ["llm", "test", "rag", "report"]
        for ex in exchanges:
            self.channel.exchange_declare(
                exchange=ex,
                exchange_type="direct",
                durable=True
            )

        self.channel.exchange_declare(
            exchange="dlx",
            exchange_type="direct",
            durable=True
        )

    def publish(
        self,
        routing_key: str,
        message: MQMessage,
        delay_seconds: int = 0,
    ) -> bool:
        try:
            self._ensure_connection()

            body = json.dumps(message.model_dump(), default=str)

            properties = pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
                message_id=message.message_id,
                headers={"x-delay": delay_seconds * 1000} if delay_seconds else None,
            )

            exchange = routing_key.split(".")[0]

            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=body,
                properties=properties,
            )

            logger.info("消息已发布",
                message_id=message.message_id,
                routing_key=routing_key,
                task_type=message.task_type,
                user_id=message.user_id,
            )
            return True

        except Exception as e:
            logger.error("消息发布失败",
                message_id=getattr(message, "message_id", "unknown"),
                routing_key=routing_key,
                error=str(e)
            )
            return False

    def close(self):
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("RabbitMQ连接已关闭")


_mq_client: Optional[MQClient] = None


def get_mq_client() -> MQClient:
    global _mq_client
    if _mq_client is None:
        _mq_client = MQClient()
    return _mq_client


def publish_llm_generate(task_id: str, user_id: str, payload: Dict[str, Any], trace_id: str = "") -> bool:
    from shared.common_proto.mq_messages import build_llm_generate_message, LLM_GENERATE_QUEUE

    message = build_llm_generate_message(task_id, user_id, payload, trace_id)
    return get_mq_client().publish(LLM_GENERATE_QUEUE.routing_key, message)


def publish_test_execute(task_id: str, user_id: str, payload: Dict[str, Any], trace_id: str = "") -> bool:
    from shared.common_proto.mq_messages import build_test_execute_message, TEST_EXECUTE_QUEUE

    message = build_test_execute_message(task_id, user_id, payload, trace_id)
    return get_mq_client().publish(TEST_EXECUTE_QUEUE.routing_key, message)


class MQConsumer:
    """
    RabbitMQ 消费者基类。
    各 Worker 继承此类并实现 _handle_message 方法。
    """

    def __init__(self, config: Dict[str, Any], queue_name: str, prefetch_count: int = 1):
        self.config = config
        self.queue_name = queue_name
        self.prefetch_count = prefetch_count
        self.connection = None
        self.channel = None
        self._running = False

    def connect(self):
        credentials = pika.PlainCredentials(
            self.config["username"],
            self.config["password"]
        )
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=self.config["host"],
            port=self.config["port"],
            virtual_host=self.config["virtual_host"],
            credentials=credentials,
            heartbeat=600,
        ))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.queue_name, durable=True)
        self.channel.basic_qos(prefetch_count=self.prefetch_count)
        logger.info("Consumer已连接", queue=self.queue_name)

    def start(self):
        self._running = True
        self.channel.basic_consume(
            queue=self.queue_name,
            on_message_callback=self._on_message,
            auto_ack=False,
        )
        logger.info("Consumer开始消费", queue=self.queue_name)
        self.channel.start_consuming()

    def stop(self):
        self._running = False
        if self.channel:
            self.channel.stop_consuming()
        if self.connection:
            self.connection.close()

    def _on_message(self, channel, method, properties, body):
        try:
            message = json.loads(body)
            logger.info("收到消息",
                message_id=message.get("message_id"),
                task_id=message.get("task_id"),
                task_type=message.get("task_type"),
            )

            success = self._handle_message(message)

            if success:
                channel.basic_ack(delivery_tag=method.delivery_tag)
            else:
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        except json.JSONDecodeError as e:
            logger.error("消息解析失败", body=body[:200], error=str(e))
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error("消息处理异常", error=str(e), exc_info=True)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def _handle_message(self, message: Dict[str, Any]) -> bool:
        raise NotImplementedError
