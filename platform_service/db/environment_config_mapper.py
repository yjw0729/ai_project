# common/db_mapper/environment_config_mapper.py
from sqlalchemy import or_, and_
from platform_service.models.environment_config import EnvironmentConfig
from contextlib import contextmanager
from common.datacase_function.contect_db import db_session
import json


class EnvironmentConfigMapper:
    """EnvironmentConfig表的数据访问类"""

    def __init__(self):
        self.entity_class = EnvironmentConfig

    @contextmanager
    def session_scope(self):
        """提供数据库会话的上下文管理"""
        with db_session() as session:
            yield session

    # 基础CRUD操作
    def get_by_id(self, id):
        """根据ID获取环境配置"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()
            if entity is not None:
                session.expunge(entity)
            return entity

    def get_by_name(self, name):
        """根据名称获取环境配置"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.name == name,
                self.entity_class.is_active == True
            ).first()
            if entity is not None:
                session.expunge(entity)
            return entity

    def get_all(self, active_only=True):
        """获取所有环境配置"""
        with self.session_scope() as session:
            query = session.query(self.entity_class)
            if active_only:
                query = query.filter(self.entity_class.is_active == True)
            results = query.order_by(
                self.entity_class.env_type,
                self.entity_class.name
            ).all()
            for r in results:
                session.expunge(r)
            return results

    def create(self, entity):
        """创建新环境配置"""
        # 验证配置
        errors = entity.validate_config()
        if errors:
            raise ValueError(f"环境配置验证失败: {', '.join(errors)}")

        with self.session_scope() as session:
            session.add(entity)
            session.flush()
            session.refresh(entity)
            session.expunge(entity)
            return entity

    def update(self, id, update_data):
        """更新环境配置"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

            if entity:
                for key, value in update_data.items():
                    if hasattr(entity, key) and key != 'id':  # 防止更新主键
                        setattr(entity, key, value)

                # 验证更新后的配置
                errors = entity.validate_config()
                if errors:
                    session.rollback()
                    raise ValueError(f"更新后配置验证失败: {', '.join(errors)}")

                return entity
            return None

    def delete(self, id, soft_delete=True):
        """删除环境配置（支持软删除）"""
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
    def get_by_env_type(self, env_type, active_only=True):
        """获取指定类型的所有环境配置"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.env_type == env_type
            )

            if active_only:
                query = query.filter(self.entity_class.is_active == True)

            results = query.order_by(self.entity_class.name).all()
            for r in results:
                session.expunge(r)
            return results

    def get_by_base_url_pattern(self, url_pattern, active_only=True):
        """根据URL模式搜索环境配置"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.base_url.like(f'%{url_pattern}%')
            )

            if active_only:
                query = query.filter(self.entity_class.is_active == True)

            results = query.order_by(
                self.entity_class.env_type,
                self.entity_class.name
            ).all()
            for r in results:
                session.expunge(r)
            return results

    def search_environments(self, keyword=None, env_type=None, active_only=True):
        """搜索环境配置"""
        with self.session_scope() as session:
            query = session.query(self.entity_class)

            if active_only:
                query = query.filter(self.entity_class.is_active == True)

            if keyword:
                query = query.filter(or_(
                    self.entity_class.name.ilike(f'%{keyword}%'),
                    self.entity_class.description.ilike(f'%{keyword}%'),
                    self.entity_class.base_url.ilike(f'%{keyword}%')
                ))

            if env_type:
                query = query.filter(self.entity_class.env_type == env_type)

            results = query.order_by(
                self.entity_class.env_type,
                self.entity_class.name
            ).all()
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

            # 按加密状态统计
            encryption_stats = session.query(
                self.entity_class.is_encryption,
                self.entity_class.id
            ).filter(
                self.entity_class.is_active == True
            ).group_by(
                self.entity_class.is_encryption
            ).all()

            return {
                'by_env_type': {row.env_type: row[1] for row in env_stats},
                'by_encryption': {row.is_encryption: row[1] for row in encryption_stats},
                'total_active': session.query(self.entity_class).filter(
                    self.entity_class.is_active == True
                ).count()
            }

    def get_environments_with_database(self):
        """获取关联了数据库配置的环境"""
        with self.session_scope() as session:
            results = session.query(self.entity_class).filter(
                self.entity_class.database_config_id.isnot(None),
                self.entity_class.is_active == True
            ).order_by(
                self.entity_class.env_type,
                self.entity_class.name
            ).all()
            for r in results:
                session.expunge(r)
            return results

    def update_environment_url(self, id, new_base_url):
        """更新环境的基础URL"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

            if entity:
                old_url = entity.base_url
                entity.base_url = new_base_url.rstrip('/')  # 确保URL格式一致

                # 验证新URL
                errors = entity.validate_config()
                if errors:
                    session.rollback()
                    raise ValueError(f"URL更新验证失败: {', '.join(errors)}")

                return {
                    'success': True,
                    'old_url': old_url,
                    'new_url': entity.base_url
                }
            return {'success': False, 'error': '环境配置不存在'}

    def bulk_update_env_type(self, old_env_type, new_env_type):
        """批量更新环境类型"""
        with self.session_scope() as session:
            updated_count = session.query(self.entity_class).filter(
                self.entity_class.env_type == old_env_type
            ).update({
                'env_type': new_env_type
            })

            return updated_count

    def get_active_environment_names(self):
        """获取所有激活环境的名称列表"""
        with self.session_scope() as session:
            results = session.query(
                self.entity_class.name
            ).filter(
                self.entity_class.is_active == True
            ).order_by(
                self.entity_class.name
            ).all()

            return [row[0] for row in results]

    def get_environment_for_api_test(self, api_config):
        """根据API配置选择最适合的环境"""
        with self.session_scope() as session:
            # 默认选择测试环境
            env = session.query(self.entity_class).filter(
                self.entity_class.env_type == 'test',
                self.entity_class.is_active == True
            ).first()

            # 如果没有测试环境，选择第一个激活的环境
            if not env:
                env = session.query(self.entity_class).filter(
                    self.entity_class.is_active == True
                ).first()

            return env

    def duplicate_environment(self, original_id, new_name, new_description=None):
        """复制环境配置"""
        original = self.get_by_id(original_id)
        if not original:
            raise ValueError(f"源环境配置不存在: {original_id}")

        # 创建副本
        duplicate = EnvironmentConfig(
            name=new_name,
            description=new_description or f"{original.name}的副本",
            base_url=original.base_url,
            env_type=original.env_type,
            database_config_id=original.database_config_id,
            headers=original.headers.copy() if original.headers else None,
            variables=original.variables.copy() if original.variables else None,
            timeout=original.timeout,
            is_encryption=original.is_encryption,
            encryption_config=original.encryption_config.copy() if original.encryption_config else None,
            is_active=original.is_active,
            created_by=original.created_by
        )

        return self.create(duplicate)