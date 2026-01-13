# app/connectors/database_connector.py
import os
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json
from decimal import Decimal

from common.rag.connectors.base_connector import BaseConnector
from common.rag.core.models import Document, DocumentType


class DatabaseConnector(BaseConnector):
    """数据库连接器 - 支持多种数据库"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.db_client = None
        self.db_type = None
        # 延迟初始化，collect时再连接

    def _init_database_client(self):
        """初始化数据库客户端"""
        db_type = self.config.get('db_type', 'mysql').lower()

        try:
            if db_type == 'mysql':
                import pymysql
                self.db_client = pymysql.connect(
                    host=self.config.get('host', '22.50.6.73'),
                    port=self.config.get('port', 3306),
                    user=self.config.get('qa'),
                    password=self.config.get('qa_tester'),
                    database=self.config.get('quantumqa'),
                    charset=self.config.get('charset', 'utf8mb4'),
                    cursorclass=pymysql.cursors.DictCursor
                )

            elif db_type == 'postgresql':
                import psycopg2
                from psycopg2.extras import RealDictCursor

                self.db_client = psycopg2.connect(
                    host=self.config.get('host', 'localhost'),
                    port=self.config.get('port', 5432),
                    user=self.config.get('username'),
                    password=self.config.get('password'),
                    database=self.config.get('database'),
                    cursor_factory=RealDictCursor
                )

            elif db_type == 'sqlite':
                import sqlite3
                db_path = self.config.get('database', ':memory:')
                self.db_client = sqlite3.connect(db_path)
                self.db_client.row_factory = sqlite3.Row

            elif db_type == 'mongodb':
                from pymongo import MongoClient
                self.db_client = MongoClient(
                    host=self.config.get('host', 'localhost'),
                    port=self.config.get('port', 27017),
                    username=self.config.get('username'),
                    password=self.config.get('password'),
                    authSource=self.config.get('auth_source', 'admin')
                )

            else:
                raise ValueError(f"不支持的数据库类型: {db_type}")

            self.db_type = db_type
            self.logger.info(f"数据库连接成功: {db_type}")

        except Exception as e:
            self.logger.error(f"数据库连接失败: {e}")
            raise

    def collect(self, source_config: Dict[str, Any]) -> List[Document]:
        """
        从数据库采集数据

        Args:
            source_config: 配置参数
                - tables: 表名列表
                - queries: 自定义SQL查询列表
                - collections: MongoDB集合列表
                - include_schema: 是否包含表结构
                - include_data: 是否包含数据
                - row_limit: 每表最大行数
                - where_clause: 额外的WHERE条件

        Returns:
            文档列表
        """
        # 延迟初始化数据库连接
        if self.db_client is None:
            self._init_database_client()

        tables = source_config.get('tables', [])
        queries = source_config.get('queries', [])
        collections = source_config.get('collections', [])
        include_schema = source_config.get('include_schema', True)
        include_data = source_config.get('include_data', True)
        row_limit = source_config.get('row_limit', 1000)
        where_clause = source_config.get('where_clause', '')

        all_documents = []

        try:
            # 1. 执行自定义查询
            for query_info in queries:
                query_name = query_info.get('name', 'custom_query')
                query_sql = query_info.get('sql')
                query_params = query_info.get('params', {})

                if query_sql:
                    documents = self._execute_custom_query(
                        query_name=query_name,
                        query_sql=query_sql,
                        query_params=query_params
                    )
                    all_documents.extend(documents)

            # 2. 处理关系型数据库
            if self.db_type in ['mysql', 'postgresql', 'sqlite']:
                # 获取所有表
                if not tables:
                    tables = self._get_all_tables()

                for table_name in tables:
                    table_documents = self._process_relation_table(
                        table_name=table_name,
                        include_schema=include_schema,
                        include_data=include_data,
                        row_limit=row_limit,
                        where_clause=where_clause
                    )
                    all_documents.extend(table_documents)

            # 3. 处理MongoDB
            elif self.db_type == 'mongodb':
                # 获取所有集合
                if not collections:
                    collections = self.db_client[self.config.get('database')].list_collection_names()

                for collection_name in collections:
                    collection_documents = self._process_mongodb_collection(
                        collection_name=collection_name,
                        include_schema=include_schema,
                        include_data=include_data,
                        document_limit=row_limit
                    )
                    all_documents.extend(collection_documents)

            self.logger.info(f"从数据库采集到 {len(all_documents)} 个文档")
            return all_documents

        except Exception as e:
            self.logger.error(f"数据库采集失败: {e}")
            return []

    def _get_all_tables(self) -> List[str]:
        """获取所有表名"""
        try:
            cursor = self.db_client.cursor()

            if self.db_type == 'mysql':
                cursor.execute("SHOW TABLES")
                tables = [row[0] for row in cursor.fetchall()]

            elif self.db_type == 'postgresql':
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                tables = [row['table_name'] for row in cursor.fetchall()]

            elif self.db_type == 'sqlite':
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]

            cursor.close()
            return tables

        except Exception as e:
            self.logger.error(f"获取表列表失败: {e}")
            return []

    def _process_relation_table(
            self,
            table_name: str,
            include_schema: bool,
            include_data: bool,
            row_limit: int,
            where_clause: str
    ) -> List[Document]:
        """处理关系型数据库表"""
        documents = []

        try:
            metadata = {
                'table_name': table_name,
                'database_name': self.config.get('database', ''),
                'database_type': self.db_type,
            }

            # 1. 获取表结构
            if include_schema:
                schema_doc = self._get_table_schema(table_name)
                if schema_doc:
                    documents.append(schema_doc)

            # 2. 获取表数据
            if include_data:
                data_docs = self._get_table_data(
                    table_name=table_name,
                    row_limit=row_limit,
                    where_clause=where_clause
                )
                documents.extend(data_docs)

            self.logger.debug(f"处理表 {table_name}: {len(documents)} 个文档")

        except Exception as e:
            self.logger.error(f"处理表 {table_name} 失败: {e}")

        return documents

    def _get_table_schema(self, table_name: str) -> Optional[Document]:
        """获取表结构"""
        try:
            cursor = self.db_client.cursor()

            if self.db_type == 'mysql':
                cursor.execute(f"DESCRIBE {table_name}")
                columns = cursor.fetchall()

                schema_lines = [f"表结构: {table_name}", "=" * 50]
                for col in columns:
                    col_name = col.get('Field', '')
                    col_type = col.get('Type', '')
                    col_null = "NULL" if col.get('Null') == 'YES' else "NOT NULL"
                    col_key = col.get('Key', '')
                    col_default = col.get('Default', '')
                    col_extra = col.get('Extra', '')

                    schema_lines.append(
                        f"{col_name:20} {col_type:20} {col_null:10} "
                        f"{col_key:5} DEFAULT={col_default:10} {col_extra}"
                    )

            elif self.db_type == 'postgresql':
                cursor.execute(f"""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                """, (table_name,))

                columns = cursor.fetchall()
                schema_lines = [f"表结构: {table_name}", "=" * 50]
                for col in columns:
                    col_name = col['column_name']
                    col_type = col['data_type']
                    col_null = col['is_nullable']
                    col_default = col['column_default']

                    schema_lines.append(
                        f"{col_name:20} {col_type:20} {col_null:10} "
                        f"DEFAULT={str(col_default or ''):20}"
                    )

            elif self.db_type == 'sqlite':
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()

                schema_lines = [f"表结构: {table_name}", "=" * 50]
                for col in columns:
                    col_name = col[1]  # name
                    col_type = col[2]  # type
                    col_notnull = "NOT NULL" if col[3] else "NULL"
                    col_default = col[4]  # dflt_value

                    schema_lines.append(
                        f"{col_name:20} {col_type:20} {col_notnull:10} "
                        f"DEFAULT={str(col_default or ''):20}"
                    )

            cursor.close()

            if not schema_lines:
                return None

            schema_content = '\n'.join(schema_lines)

            metadata = {
                'table_name': table_name,
                'document_type': 'table_schema',
                'column_count': len(columns) if 'columns' in locals() else 0,
            }

            return self._create_document(
                content=schema_content,
                source_type=f'database_{self.db_type}',
                source_uri=f"{self.config.get('database')}.{table_name}.schema",
                doc_type=DocumentType.API_DOC,
                metadata=metadata
            )

        except Exception as e:
            self.logger.error(f"获取表结构失败 {table_name}: {e}")
            return None

    def _get_table_data(
            self,
            table_name: str,
            row_limit: int,
            where_clause: str
    ) -> List[Document]:
        """获取表数据"""
        documents = []

        try:
            cursor = self.db_client.cursor()

            # 构建查询
            where_sql = f"WHERE {where_clause}" if where_clause else ""
            limit_sql = f"LIMIT {row_limit}" if row_limit > 0 else ""

            if self.db_type in ['mysql', 'sqlite']:
                query = f"SELECT * FROM {table_name} {where_sql} {limit_sql}"
            elif self.db_type == 'postgresql':
                query = f"SELECT * FROM {table_name} {where_sql} LIMIT %s"
                limit_sql = row_limit

            # 执行查询
            if self.db_type == 'postgresql':
                cursor.execute(query, (row_limit,))
            else:
                cursor.execute(query)

            rows = cursor.fetchall()
            cursor.close()

            if not rows:
                return documents

            # 将数据转换为文本
            batch_size = 100
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]

                # 转换行数据
                data_lines = [f"表数据: {table_name} (行 {i + 1} 到 {i + len(batch)})", "=" * 50]

                for row_idx, row in enumerate(batch, 1):
                    data_lines.append(f"\n行 {i + row_idx}:")

                    if isinstance(row, dict):
                        for key, value in row.items():
                            # 处理特殊数据类型
                            if value is None:
                                display_value = "NULL"
                            elif isinstance(value, (datetime, Decimal)):
                                display_value = str(value)
                            else:
                                display_value = str(value)

                            data_lines.append(f"  {key}: {display_value}")
                    else:
                        data_lines.append(f"  {row}")

                data_content = '\n'.join(data_lines)

                metadata = {
                    'table_name': table_name,
                    'document_type': 'table_data',
                    'row_start': i + 1,
                    'row_end': i + len(batch),
                    'total_rows': len(rows),
                }

                document = self._create_document(
                    content=data_content,
                    source_type=f'database_{self.db_type}',
                    source_uri=f"{self.config.get('database')}.{table_name}.data.{i}",
                    doc_type=DocumentType.TECH_SPEC,
                    metadata=metadata
                )

                if document:
                    documents.append(document)

            self.logger.debug(f"表 {table_name} 获取到 {len(rows)} 行数据")

        except Exception as e:
            self.logger.error(f"获取表数据失败 {table_name}: {e}")

        return documents

    def _execute_custom_query(
            self,
            query_name: str,
            query_sql: str,
            query_params: Dict[str, Any]
    ) -> List[Document]:
        """执行自定义查询"""
        documents = []

        try:
            cursor = self.db_client.cursor()

            # 执行查询
            if query_params:
                cursor.execute(query_sql, query_params)
            else:
                cursor.execute(query_sql)

            rows = cursor.fetchall()
            cursor.close()

            if not rows:
                return documents

            # 转换结果
            if isinstance(rows[0], dict):
                # 字典格式结果
                columns = list(rows[0].keys())
                data_lines = [f"查询: {query_name}", "=" * 50]
                data_lines.append("列: " + ", ".join(columns))
                data_lines.append("=" * 50)

                for i, row in enumerate(rows[:50], 1):  # 限制显示50行
                    row_values = []
                    for col in columns:
                        value = row.get(col)
                        if value is None:
                            display_value = "NULL"
                        elif isinstance(value, (datetime, Decimal)):
                            display_value = str(value)
                        else:
                            display_value = str(value)
                        row_values.append(display_value)

                    data_lines.append(f"行 {i}: " + " | ".join(row_values))

                if len(rows) > 50:
                    data_lines.append(f"... 还有 {len(rows) - 50} 行未显示")
            else:
                # 元组格式结果
                data_lines = [f"查询: {query_name}", "=" * 50]
                for i, row in enumerate(rows[:50], 1):
                    data_lines.append(f"行 {i}: {row}")

                if len(rows) > 50:
                    data_lines.append(f"... 还有 {len(rows) - 50} 行未显示")

            data_content = '\n'.join(data_lines)

            metadata = {
                'query_name': query_name,
                'query_sql': query_sql,
                'document_type': 'custom_query',
                'row_count': len(rows),
                'parameters': query_params,
            }

            document = self._create_document(
                content=data_content,
                source_type=f'database_{self.db_type}',
                source_uri=f"{self.config.get('database')}.query.{query_name}",
                doc_type=DocumentType.TECH_SPEC,
                metadata=metadata
            )

            if document:
                documents.append(document)

            self.logger.debug(f"自定义查询 {query_name} 返回 {len(rows)} 行")

        except Exception as e:
            self.logger.error(f"执行自定义查询失败 {query_name}: {e}")

        return documents

    def _process_mongodb_collection(
            self,
            collection_name: str,
            include_schema: bool,
            include_data: bool,
            document_limit: int
    ) -> List[Document]:
        """处理MongoDB集合"""
        documents = []

        try:
            db = self.db_client[self.config.get('database')]
            collection = db[collection_name]

            metadata = {
                'collection_name': collection_name,
                'database_name': self.config.get('database', ''),
                'database_type': 'mongodb',
            }

            # 1. 获取集合统计信息
            if include_schema:
                stats = db.command('collstats', collection_name)

                schema_lines = [f"MongoDB集合: {collection_name}", "=" * 50]
                schema_lines.append(f"文档数量: {stats.get('count', 0)}")
                schema_lines.append(f"存储大小: {stats.get('size', 0)} 字节")
                schema_lines.append(f"索引数量: {len(stats.get('indexSizes', {}))}")

                # 分析样本文档的结构
                sample_doc = collection.find_one({})
                if sample_doc:
                    schema_lines.append("\n文档结构示例:")
                    self._format_mongodb_document(sample_doc, schema_lines, indent=2)

                schema_content = '\n'.join(schema_lines)

                schema_metadata = metadata.copy()
                schema_metadata.update({
                    'document_type': 'collection_schema',
                    'count': stats.get('count', 0),
                    'size': stats.get('size', 0),
                })

                schema_doc = self._create_document(
                    content=schema_content,
                    source_type='database_mongodb',
                    source_uri=f"{self.config.get('database')}.{collection_name}.schema",
                    doc_type=DocumentType.API_DOC,
                    metadata=schema_metadata
                )

                if schema_doc:
                    documents.append(schema_doc)

            # 2. 获取文档数据
            if include_data and document_limit > 0:
                cursor = collection.find().limit(document_limit)
                data_docs = list(cursor)

                if data_docs:
                    batch_size = 20
                    for i in range(0, len(data_docs), batch_size):
                        batch = data_docs[i:i + batch_size]

                        data_lines = [
                            f"MongoDB数据: {collection_name} "
                            f"(文档 {i + 1} 到 {i + len(batch)})",
                            "=" * 50
                        ]

                        for doc_idx, doc in enumerate(batch, 1):
                            data_lines.append(f"\n文档 {i + doc_idx}:")
                            self._format_mongodb_document(doc, data_lines, indent=2)

                        data_content = '\n'.join(data_lines)

                        data_metadata = metadata.copy()
                        data_metadata.update({
                            'document_type': 'collection_data',
                            'doc_start': i + 1,
                            'doc_end': i + len(batch),
                            'total_docs': len(data_docs),
                        })

                        data_doc = self._create_document(
                            content=data_content,
                            source_type='database_mongodb',
                            source_uri=f"{self.config.get('database')}.{collection_name}.data.{i}",
                            doc_type=DocumentType.TECH_SPEC,
                            metadata=data_metadata
                        )

                        if data_doc:
                            documents.append(data_doc)

            self.logger.debug(f"MongoDB集合 {collection_name}: {len(documents)} 个文档")

        except Exception as e:
            self.logger.error(f"处理MongoDB集合失败 {collection_name}: {e}")

        return documents

    def _format_mongodb_document(
            self,
            doc: Dict[str, Any],
            lines: List[str],
            indent: int = 0
    ):
        """格式化MongoDB文档"""
        indent_str = ' ' * indent

        for key, value in doc.items():
            if key == '_id':
                lines.append(f"{indent_str}{key}: ObjectId({str(value)})")
            elif isinstance(value, dict):
                lines.append(f"{indent_str}{key}: {{")
                self._format_mongodb_document(value, lines, indent + 2)
                lines.append(f"{indent_str}}}")
            elif isinstance(value, list):
                lines.append(f"{indent_str}{key}: [")
                for i, item in enumerate(value[:5]):  # 限制显示5个元素
                    if isinstance(item, dict):
                        lines.append(f"{indent_str}  {{")
                        self._format_mongodb_document(item, lines, indent + 4)
                        lines.append(f"{indent_str}  }}")
                    else:
                        lines.append(f"{indent_str}  {item}")
                if len(value) > 5:
                    lines.append(f"{indent_str}  ... 还有 {len(value) - 5} 个元素")
                lines.append(f"{indent_str}]")
            else:
                lines.append(f"{indent_str}{key}: {value}")

    def _test_connection_internal(self) -> bool:
        """测试数据库连接"""
        try:
            cursor = self.db_client.cursor()

            if self.db_type in ['mysql', 'postgresql']:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                success = result[0] == 1
            elif self.db_type == 'sqlite':
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                success = result[0] == 1
            elif self.db_type == 'mongodb':
                # MongoDB ping命令
                result = self.db_client.admin.command('ping')
                success = result.get('ok', 0) == 1

            cursor.close() if 'cursor' in locals() else None

            if success:
                self.logger.info(f"数据库连接测试成功: {self.db_type}")
                return True

        except Exception as e:
            self.logger.error(f"数据库连接测试失败: {e}")

        return False

    def close(self):
        """关闭数据库连接"""
        if self.db_client:
            try:
                self.db_client.close()
                self.logger.info("数据库连接已关闭")
            except:
                pass
            finally:
                self.db_client = None