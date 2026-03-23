from contextlib import contextmanager
from sqlalchemy import or_, func

from platform_service.models.api_config import ApiConfig
from common.datacase_function.contect_db import db_session


class ApiConfigMapper:
    """ApiConfig表的数据访问类"""

    def __init__(self, db_key : str = "default"):
        self.entity_class = ApiConfig
        self.db_key = db_key

    @contextmanager
    def session_scope(self):
        with db_session() as session:
            yield session

    # 基础 CRUD
    def create(self, entity: ApiConfig):
        errors = entity.validate_config()
        if errors:
            raise ValueError(f"接口配置验证失败: {', '.join(errors)}")
        with self.session_scope() as session:
            session.add(entity)
            session.flush()
            session.refresh(entity)
            session.expunge(entity)
            return entity

    def get_by_id(self, id: int):
        with self.session_scope() as session:
            obj = session.query(self.entity_class).filter(self.entity_class.id == id).first()
            if obj:
                session.expunge(obj)
            return obj

    def get_by_unique(self, module: str, api_path: str, method: str):
        method_val = (method or "").upper()
        with self.session_scope() as session:
            obj = session.query(self.entity_class).filter(
                self.entity_class.module == module,
                self.entity_class.api_path == api_path,
                self.entity_class.method == method_val,
                self.entity_class.is_deprecated == False,
            ).first()
            if obj:
                session.expunge(obj)
            return obj

    def get_all(self, include_deprecated=False):
        with self.session_scope() as session:
            query = session.query(self.entity_class)
            if not include_deprecated:
                query = query.filter(self.entity_class.is_deprecated == False)
            results = query.order_by(self.entity_class.module, self.entity_class.api_path).all()
            for r in results:
                session.expunge(r)
            return results

    def update(self, id: int, update_data: dict):
        with self.session_scope() as session:
            obj = session.query(self.entity_class).filter(self.entity_class.id == id).first()
            if not obj:
                return None
            for k, v in update_data.items():
                if hasattr(obj, k):
                    setattr(obj, k, v)
            errors = obj.validate_config()
            if errors:
                session.rollback()
                raise ValueError(f"接口配置验证失败: {', '.join(errors)}")
            session.flush()
            session.refresh(obj)
            session.expunge(obj)
            return obj

    def delete(self, id: int):
        with self.session_scope() as session:
            obj = session.query(self.entity_class).filter(self.entity_class.id == id).first()
            if not obj:
                return False
            # 仅支持硬删除
            session.delete(obj)
            return True

    # 扩展查询
    def search_configs(self, keyword=None, module=None, method=None, request_type=None, include_deprecated=False):
        with self.session_scope() as session:
            query = session.query(self.entity_class)
            if keyword:
                query = query.filter(or_(
                    self.entity_class.name.ilike(f"%{keyword}%"),
                    self.entity_class.description.ilike(f"%{keyword}%"),
                    self.entity_class.api_path.ilike(f"%{keyword}%")
                ))
            if module:
                query = query.filter(self.entity_class.module == module)
            if method:
                query = query.filter(self.entity_class.method == method.upper())
            if request_type:
                query = query.filter(self.entity_class.request_type == request_type.lower())
            if not include_deprecated:
                query = query.filter(self.entity_class.is_deprecated == False)
            results = query.order_by(self.entity_class.module, self.entity_class.api_path).all()
            for r in results:
                session.expunge(r)
            return results

    # 兼容旧接口
    def get_by_module_and_path(self, module, api_path, method=None):
        return self.get_by_unique(module, api_path, method or "")

    def get_by_module(self, module, include_deprecated=False):
        return self.search_configs(module=module, include_deprecated=include_deprecated)

    def search_apis(self, keyword=None, module=None, method=None, tags=None):
        return self.search_configs(keyword=keyword, module=module, method=method)

    def get_modules(self):
        with self.session_scope() as session:
            results = session.query(self.entity_class.module).filter(
                self.entity_class.is_deprecated == False
            ).distinct().all()
            return [r[0] for r in results]

    def get_api_statistics(self):
        with self.session_scope() as session:
            module_stats = session.query(
                self.entity_class.module,
                self.entity_class.method,
                func.count(self.entity_class.id)
            ).filter(
                self.entity_class.is_deprecated == False
            ).group_by(
                self.entity_class.module,
                self.entity_class.method
            ).all()

            method_stats = session.query(
                self.entity_class.method,
                func.count(self.entity_class.id)
            ).filter(
                self.entity_class.is_deprecated == False
            ).group_by(
                self.entity_class.method
            ).all()

            total = session.query(func.count(self.entity_class.id)).filter(
                self.entity_class.is_deprecated == False
            ).scalar() or 0

            return {
                'by_module': {f"{row.module}.{row.method}": row[2] for row in module_stats},
                'by_method': {row.method: row[1] for row in method_stats},
                'total': total
            }

    def get_apis_with_similar_path(self, api_path, limit=5):
        with self.session_scope() as session:
            results = session.query(self.entity_class).filter(
                self.entity_class.api_path.ilike(f"%{api_path}%"),
                self.entity_class.is_deprecated == False
            ).limit(limit).all()
            for r in results:
                session.expunge(r)
            return results

    def validate_and_save(self, api_config):
        return self.create(api_config)