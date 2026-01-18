# app/core/data_collector.py
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib
import os

from common.rag.core.models import Document, DocumentType
from common.rag.connectors.file_connector import FileConnector
from common.rag.connectors.database_connector import DatabaseConnector

# 注意：我们暂时不使用Confluence连接器，因为atlassian包有问题
# from app.connectors.confluence_connector import ConfluenceConnector

logger = logging.getLogger(__name__)


class DataCollector:
    """数据采集器 - 负责从多种数据源采集测试相关知识"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.connectors = {}
        self._init_connectors()

    def _init_connectors(self):
        """初始化数据源连接器"""
        # 文件系统连接器（支持Word、Excel、PDF、TXT等）
        self.connectors["file"] = FileConnector(self.config.get("file", {}))

        # 数据库连接器 - 延迟初始化，只有在需要时才创建
        # self.connectors["database"] = None  # 将在collect_from_source时初始化

        # Git连接器（如果需要）
        # if "git" in self.conf ig:
        #     from app.connectors.git_connector import GitConnector
        #     self.connectors["git"] = GitConnector(self.config["git"])

        logger.info(f"已初始化 {len(self.connectors)} 个数据源连接器: {list(self.connectors.keys())}")

    def collect_from_source(
            self,
            source_type: str,
            source_config: Dict[str, Any]
    ) -> List[Document]:
        """
        从指定数据源采集数据

        Args:
            source_type: 数据源类型 (file, database, git, api)
            source_config: 数据源配置

        Returns:
            List[Document]: 原始文档数据
        """
        # 延迟初始化数据库连接器
        if source_type == "database" and source_type not in self.connectors:
            self.connectors["database"] = DatabaseConnector(
                self.config.get("database", {})
            )

        if source_type not in self.connectors:
            raise ValueError(f"不支持的数据源类型: {source_type}")

        connector = self.connectors[source_type]

        try:
            logger.info(f"开始从 {source_type} 采集数据...")
            start_time = datetime.now()

            # 调用连接器收集数据
            documents = connector.collect(source_config)

            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(f"从 {source_type} 采集完成: {len(documents)} 个文档, 耗时 {elapsed:.2f}秒")

            return documents

        except Exception as e:
            logger.error(f"从 {source_type} 采集数据失败: {e}")
            raise

    async def collect_from_multiple_sources(
            self,
            source_configs: List[Dict[str, Any]]
    ) -> List[Document]:
        """
        从多个数据源并发采集数据

        Args:
            source_configs: 数据源配置列表
                [
                    {"source_type": "file", "paths": [...]},
                    {"source_type": "database", "tables": [...]}
                ]

        Returns:
            合并后的文档列表
        """
        tasks = []
        for config in source_configs:
            source_type = config.get("source_type")
            if source_type and source_type in self.connectors:
                task = asyncio.create_task(
                    self._async_collect(source_type, config)
                )
                tasks.append(task)

        # 等待所有采集任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 合并结果
        all_documents = []
        for i, result in enumerate(results):
            source_config = source_configs[i]
            if isinstance(result, Exception):
                logger.error(f"采集任务失败 {source_config.get('source_type')}: {result}")
            elif isinstance(result, list):
                all_documents.extend(result)

        # 去重
        unique_documents = self._deduplicate_documents(all_documents)

        logger.info(f"从多个数据源采集完成: 总共 {len(all_documents)} 个文档, 去重后 {len(unique_documents)} 个")
        return unique_documents

    async def _async_collect(
            self,
            source_type: str,
            source_config: Dict[str, Any]
    ) -> List[Document]:
        """异步采集包装器"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.collect_from_source,
            source_type,
            source_config
        )

    def _deduplicate_documents(self, documents: List[Document]) -> List[Document]:
        """文档去重"""
        seen = set()
        unique_docs = []

        for doc in documents:
            # 基于内容和源URI生成唯一标识
            doc_hash = hashlib.md5(
                f"{doc.source_uri}:{doc.content[:1000]}".encode()
            ).hexdigest()

            if doc_hash not in seen:
                seen.add(doc_hash)
                unique_docs.append(doc)

        return unique_docs

    def schedule_collection(
            self,
            cron_expression: str,
            job_config: Dict[str, Any]
    ) -> str:
        """
        创建定时采集任务

        Args:
            cron_expression: cron表达式，如 "0 2 * * *" 表示每天2点
            job_config: 任务配置

        Returns:
            任务ID
        """
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
            import uuid

            scheduler = BackgroundScheduler()

            def job_function():
                try:
                    logger.info(f"执行定时采集任务: {job_config}")
                    source_type = job_config.get("source_type")
                    source_config = job_config.get("source_config", {})

                    if source_type and source_type in self.connectors:
                        documents = self.collect_from_source(source_type, source_config)
                        logger.info(f"定时采集完成: {len(documents)} 个文档")

                        # 如果有回调函数，调用它
                        callback = job_config.get("callback")
                        if callback and callable(callback):
                            callback(documents)
                except Exception as e:
                    logger.error(f"定时采集任务执行失败: {e}")

            # 创建任务ID
            job_id = f"collect_{uuid.uuid4().hex[:8]}"

            # 解析cron表达式
            parts = cron_expression.split()
            if len(parts) != 5:
                raise ValueError("cron表达式必须是5个部分: 分 时 日 月 周")

            # 添加任务
            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4]
            )

            scheduler.add_job(
                job_function,
                trigger=trigger,
                id=job_id,
                replace_existing=True
            )

            scheduler.start()
            logger.info(f"定时采集任务已创建: {job_id}, cron: {cron_expression}")

            return job_id

        except ImportError:
            logger.warning("APScheduler未安装，无法创建定时任务")
            return ""
        except Exception as e:
            logger.error(f"创建定时采集任务失败: {e}")
            return ""