# common/db_mapper/database_config_mapper.py
from sqlalchemy import or_, and_
from common.db.entity.database_config import DatabaseConfig
from contextlib import contextmanager
from common.db.datacase.contect_db import db_session
import json


class DatabaseConfigMapper:
    """DatabaseConfig表的数据访问类"""

    def __init__(self, db_key: str = "default"):
        self.entity_class = DatabaseConfig
        self.db_key = db_key

    @contextmanager
    def session_scope(self):
        with db_session(self.db_key) as session:
            yield session

    # 基础CRUD操作
    def get_by_id(self, id):
        """根据ID获取记录"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

    def get_all(self, active_only=True):
        """获取所有记录"""
        with self.session_scope() as session:
            query = session.query(self.entity_class)
            if active_only:
                query = query.filter(self.entity_class.is_active == True)
            return query.order_by(self.entity_class.name).all()

    def create(self, entity):
        """创建新记录"""
        # 验证配置
        errors = entity.validate_config()
        if errors:
            raise ValueError(f"配置验证失败: {', '.join(errors)}")

        with self.session_scope() as session:
            session.add(entity)
            session.flush()
            session.refresh(entity)
            # 解除绑定，避免会话关闭后访问属性触发 DetachedInstanceError
            session.expunge(entity)
            return entity

    def update(self, id, update_data):
        """更新记录"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

            if entity:
                for key, value in update_data.items():
                    if hasattr(entity, key):
                        setattr(entity, key, value)

                # 验证更新后的配置
                errors = entity.validate_config()
                if errors:
                    session.rollback()
                    raise ValueError(f"更新后配置验证失败: {', '.join(errors)}")

                return entity
            return None

    def delete(self, id, soft_delete=True):
        """删除记录（支持软删除）"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

            if entity:
                if soft_delete:
                    # 软删除：标记为未激活
                    entity.is_active = False
                else:
                    # 硬删除
                    session.delete(entity)
                return True
            return False

    # 特定查询方法
    def get_by_name_and_env(self, name, env_type):
        """根据名称和环境类型获取配置（不区分是否激活，用于唯一性校验）"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.name == name,
                self.entity_class.env_type == env_type,
            ).first()

    def get_by_env_type(self, env_type, db_type=None):
        """获取指定环境类型的所有数据库配置"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.env_type == env_type,
                self.entity_class.is_active == True
            )

            if db_type:
                query = query.filter(self.entity_class.db_type == db_type)

            return query.order_by(self.entity_class.name).all()

    def get_by_db_type(self, db_type, env_type=None):
        """获取指定数据库类型的所有配置"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.db_type == db_type,
                self.entity_class.is_active == True
            )

            if env_type:
                query = query.filter(self.entity_class.env_type == env_type)

            return query.order_by(self.entity_class.env_type, self.entity_class.name).all()

    def search_configs(self, keyword=None, env_type=None, db_type=None, name=None, active_only=True):
        """搜索数据库配置"""
        with self.session_scope() as session:
            query = session.query(self.entity_class)

            if active_only:
                query = query.filter(self.entity_class.is_active == True)

            if name:
                query = query.filter(self.entity_class.name == name)

            if keyword:
                query = query.filter(or_(
                    self.entity_class.name.ilike(f'%{keyword}%'),
                    self.entity_class.description.ilike(f'%{keyword}%'),
                    self.entity_class.host.ilike(f'%{keyword}%'),
                    self.entity_class.database_name.ilike(f'%{keyword}%'),
                    self.entity_class.username.ilike(f'%{keyword}%'),
                    self.entity_class.password.ilike(f'%{keyword}%')
                ))

            if env_type:
                query = query.filter(self.entity_class.env_type == env_type)

            if db_type:
                query = query.filter(self.entity_class.db_type == db_type)

            results = query.order_by(
                self.entity_class.env_type,
                self.entity_class.db_type,
                self.entity_class.name
            ).all()

            # 分离对象，避免会话关闭后属性懒加载为空
            for r in results:
                session.expunge(r)
            return results

    def get_environment_stats(self):
        """获取环境统计信息"""
        with self.session_scope() as session:
            # 按环境类型统计
            env_stats = session.query(
                self.entity_class.env_type,
                self.entity_class.id
            ).filter(
                self.entity_class.is_active == True
            ).group_by(
                self.entity_class.env_type
            ).all()

            # 按数据库类型统计
            db_stats = session.query(
                self.entity_class.db_type,
                self.entity_class.id
            ).filter(
                self.entity_class.is_active == True
            ).group_by(
                self.entity_class.db_type
            ).all()

            return {
                'by_env': {row.env_type: row[1] for row in env_stats},
                'by_db_type': {row.db_type: row[1] for row in db_stats},
                'total_active': session.query(self.entity_class).filter(
                    self.entity_class.is_active == True
                ).count()
            }

    def test_connection(self, config_id):
        """测试数据库连接"""
        config = self.get_by_id(config_id)
        if not config:
            raise ValueError(f"数据库配置不存在: {config_id}")

        try:
            # 根据数据库类型使用不同的连接测试方法
            if config.db_type == 'mysql':
                return self._test_mysql_connection(config)
            elif config.db_type == 'postgresql':
                return self._test_postgresql_connection(config)
            elif config.db_type == 'oracle':
                return self._test_oracle_connection(config)
            elif config.db_type == 'sqlserver':
                return self._test_sqlserver_connection(config)
            elif config.db_type == 'mongodb':
                return self._test_mongodb_connection(config)
            else:
                raise ValueError(f"不支持的数据库类型: {config.db_type}")
        except Exception as e:
            return {
                'success': False,
                'message': f"连接测试失败: {str(e)}",
                'config': config.to_json()
            }

    def _test_mysql_connection(self, config):
        """测试MySQL连接"""
        try:
            import pymysql
            connection = pymysql.connect(
                host=config.host,
                port=config.port,
                user=config.username,
                password=config.password,
                database=config.database_name,
                connect_timeout=config.timeout
            )

            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()

            connection.close()

            return {
                'success': True,
                'message': 'MySQL连接测试成功',
                'version': self._get_mysql_version(connection) if hasattr(connection, 'server_version') else '未知',
                'config': config.to_json()
            }
        except Exception as e:
            raise Exception(f"MySQL连接失败: {str(e)}")

    def _test_postgresql_connection(self, config):
        """测试PostgreSQL连接"""
        try:
            import psycopg2
            connection = psycopg2.connect(
                host=config.host,
                port=config.port,
                user=config.username,
                password=config.password,
                database=config.database_name,
                connect_timeout=config.timeout
            )

            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()

            connection.close()

            return {
                'success': True,
                'message': 'PostgreSQL连接测试成功',
                'config': config.to_json()
            }
        except Exception as e:
            raise Exception(f"PostgreSQL连接失败: {str(e)}")

    def _test_oracle_connection(self, config):
        """测试Oracle连接（需要安装cx_Oracle）"""
        try:
            import cx_Oracle
            dsn = cx_Oracle.makedsn(config.host, config.port, service_name=config.database_name)
            connection = cx_Oracle.connect(
                user=config.username,
                password=config.password,
                dsn=dsn
            )

            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM DUAL")
                result = cursor.fetchone()

            connection.close()

            return {
                'success': True,
                'message': 'Oracle连接测试成功',
                'config': config.to_json()
            }
        except Exception as e:
            raise Exception(f"Oracle连接失败: {str(e)}")

    def _test_sqlserver_connection(self, config):
        """测试SQL Server连接（需要安装pymssql）"""
        try:
            import pymssql
            connection = pymssql.connect(
                server=config.host,
                port=config.port,
                user=config.username,
                password=config.password,
                database=config.database_name,
                timeout=config.timeout
            )

            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()

            connection.close()

            return {
                'success': True,
                'message': 'SQL Server连接测试成功',
                'config': config.to_json()
            }
        except Exception as e:
            raise Exception(f"SQL Server连接失败: {str(e)}")

    # def _test_mongodb_connection(self, config):
    #     """测试MongoDB连接（需要安装pymongo）"""
    #     try:
    #         from pymongo import MongoClient
    #         from pymongo.errors import ConnectionFailure
    #
    #         client = MongoClient(
    #             host=config.host,
    #             port=config.port,
    #             username=config.username,
    #             password=config.password,
    #             authSource=config.database_name,
    #             serverSelectionTimeoutMS=config.timeout * 1000
    #         )
    #
    #         # 测试连接
    #         client.admin.command('ismaster')
    #         client.close()
    #
    #         return {
    #             'success': True,
    #             'message': 'MongoDB连接测试成功',
    #             'config': config.to_json()
    #         }
    #     except Exception as e:
    #         raise Exception(f"MongoDB连接失败: {str(e)}")

    def _get_mysql_version(self, connection):
        """获取MySQL版本信息"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT VERSION()")
                result = cursor.fetchone()
                return result[0] if result else '未知'
        except:
            return '未知'

    def bulk_update_env(self, old_env_type, new_env_type):
        """批量更新环境类型"""
        with self.session_scope() as session:
            updated_count = session.query(self.entity_class).filter(
                self.entity_class.env_type == old_env_type
            ).update({
                'env_type': new_env_type
            })

            return updated_count