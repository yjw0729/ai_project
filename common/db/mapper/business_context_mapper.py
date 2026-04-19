"""
业务上下文 Mapper
提供数据库操作方法
"""

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from common.db.entity.business_context import BusinessContext

logger = logging.getLogger(__name__)


class BusinessContextMapper:
    """业务上下文数据库操作类"""

    def __init__(self, db_key: str = "default"):
        self.db_key = db_key

    def _get_session(self) -> Session:
        """获取数据库会话"""
        from common.db.datacase.contect_db import db_session
        return db_session(self.db_key)

    def create(self, context: BusinessContext) -> int:
        """创建业务上下文"""
        with self._get_session() as session:
            session.add(context)
            session.flush()
            session.refresh(context)
            return context.id

    def get_by_id(self, context_id: int) -> Optional[BusinessContext]:
        """根据ID获取业务上下文"""
        with self._get_session() as session:
            return session.query(BusinessContext).filter(
                BusinessContext.id == context_id,
                BusinessContext.is_deprecated == False
            ).first()

    def get_by_hash(self, content_hash: str) -> Optional[BusinessContext]:
        """根据内容哈希获取业务上下文"""
        with self._get_session() as session:
            return session.query(BusinessContext).filter(
                BusinessContext.content_hash == content_hash,
                BusinessContext.is_deprecated == False
            ).first()

    def get_by_api_config(self, api_config_id: int) -> List[BusinessContext]:
        """根据API配置ID获取关联的业务上下文"""
        with self._get_session() as session:
            return session.query(BusinessContext).filter(
                BusinessContext.api_config_id == api_config_id,
                BusinessContext.is_deprecated == False,
                BusinessContext.is_active == True
            ).all()

    def get_by_module(self, module: str) -> List[BusinessContext]:
        """根据模块获取业务上下文"""
        with self._get_session() as session:
            return session.query(BusinessContext).filter(
                BusinessContext.module == module,
                BusinessContext.is_deprecated == False,
                BusinessContext.is_active == True
            ).all()

    def list_all(self, skip: int = 0, limit: int = 100, module: Optional[str] = None) -> List[BusinessContext]:
        """列出所有业务上下文"""
        with self._get_session() as session:
            query = session.query(BusinessContext).filter(
                BusinessContext.is_deprecated == False
            )
            if module:
                query = query.filter(BusinessContext.module == module)
            return query.order_by(BusinessContext.created_at.desc()).offset(skip).limit(limit).all()

    def update(self, context_id: int, updates: Dict[str, Any]) -> bool:
        """更新业务上下文"""
        with self._get_session() as session:
            context = session.query(BusinessContext).filter(
                BusinessContext.id == context_id
            ).first()
            if not context:
                return False
            for key, value in updates.items():
                if hasattr(context, key):
                    setattr(context, key, value)
            context.updated_at = datetime.now()
            return True

    def soft_delete(self, context_id: int) -> bool:
        """软删除业务上下文"""
        return self.update(context_id, {"is_deprecated": True})

    def hard_delete(self, context_id: int) -> bool:
        """硬删除业务上下文"""
        with self._get_session() as session:
            context = session.query(BusinessContext).filter(
                BusinessContext.id == context_id
            ).first()
            if not context:
                return False
            session.delete(context)
            return True

    @staticmethod
    def compute_hash(content: str) -> str:
        """计算内容哈希"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
