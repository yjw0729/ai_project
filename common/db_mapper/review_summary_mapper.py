# common/db_mapper/review_summary_mapper.py
"""
crosstest_review_summary 表的数据访问类
专用于列表查询，避免全扫描含大字段的 crosstest_review_record 表。
"""
from contextlib import contextmanager
from datetime import datetime
import logging

from common.db_enitiy.review_summary import ReviewSummary
from common.datacase_function.contect_db import db_session

logger = logging.getLogger(__name__)


class ReviewSummaryMapper:
    """ReviewSummary 汇总表的数据访问类"""

    def __init__(self, db_key: str = "default"):
        self.entity_class = ReviewSummary
        self.db_key = db_key

    @contextmanager
    def session_scope(self):
        try:
            with db_session(self.db_key) as session:
                yield session
        except Exception as e:
            logger.error(f"[ReviewSummaryMapper] 数据库会话错误: {e}", exc_info=True)
            raise

    def _to_dict(self, entity) -> dict:
        """将实体转为字典（在 session 关闭前调用）"""
        if entity is None:
            return None
        return entity.to_dict()

    # ------------------------------------------------------------------
    # 写操作
    # ------------------------------------------------------------------

    def create(self, data: dict) -> int:
        """
        根据字典数据创建汇总记录

        参数：
        - data: 包含字段的字典，支持的键：
          doc_id, document_title, business_module, document_type,
          interface_count, image_count, general_image_count, test_case_count,
          status, xmind_file_path, creator, reviewer, review_comment
        """
        logger.info(f"[ReviewSummaryMapper] create doc_id={data.get('doc_id')}")
        with self.session_scope() as session:
            entity = ReviewSummary(
                doc_id=data.get('doc_id'),
                document_title=data.get('document_title'),
                business_module=data.get('business_module'),
                document_type=data.get('document_type'),
                interface_count=data.get('interface_count', 0),
                image_count=data.get('image_count', 0),
                general_image_count=data.get('general_image_count', 0),
                test_case_count=data.get('test_case_count', 0),
                status=data.get('status', 'pending'),
                xmind_file_path=data.get('xmind_file_path'),
                creator=data.get('creator', 'system'),
                reviewer=data.get('reviewer'),
                review_comment=data.get('review_comment'),
                created_time=datetime.now(),
                updated_time=datetime.now(),
            )
            session.add(entity)
            session.flush()
            session.refresh(entity)
            logger.info(f"[ReviewSummaryMapper] 新建汇总记录成功，id={entity.id}")
            return entity.id

    def upsert(self, doc_id: str, document_title: str = None, business_module: str = None,
               document_type: str = None, interface_count: int = 0, image_count: int = 0,
               general_image_count: int = 0, test_case_count: int = 0,
               status: str = 'pending', xmind_file_path: str = None,
               creator: str = 'system', reviewer: str = None,
               review_comment: str = None) -> dict:
        """
        创建或更新汇总记录（按 doc_id 唯一）。
        若记录已存在则覆盖可变字段；若不存在则新建。
        """
        logger.info(f"[ReviewSummaryMapper] upsert doc_id={doc_id}")
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.doc_id == doc_id
            ).first()

            if entity is None:
                entity = ReviewSummary(
                    doc_id=doc_id,
                    document_title=document_title,
                    business_module=business_module,
                    document_type=document_type,
                    interface_count=interface_count,
                    image_count=image_count,
                    general_image_count=general_image_count,
                    test_case_count=test_case_count,
                    status=status,
                    xmind_file_path=xmind_file_path,
                    creator=creator,
                    reviewer=reviewer,
                    review_comment=review_comment,
                    created_time=datetime.now(),
                    updated_time=datetime.now(),
                )
                session.add(entity)
                logger.info(f"[ReviewSummaryMapper] 新建汇总记录 doc_id={doc_id}")
            else:
                # 只更新明确传入的字段，避免把已存在字段覆盖为 None
                update_vals = {"updated_time": datetime.now()}
                if document_title is not None:
                    update_vals["document_title"] = document_title
                if business_module is not None:
                    update_vals["business_module"] = business_module
                if document_type is not None:
                    update_vals["document_type"] = document_type
                update_vals["interface_count"] = interface_count
                update_vals["image_count"] = image_count
                update_vals["general_image_count"] = general_image_count
                update_vals["test_case_count"] = test_case_count
                update_vals["status"] = status
                if xmind_file_path is not None:
                    update_vals["xmind_file_path"] = xmind_file_path
                if reviewer is not None:
                    update_vals["reviewer"] = reviewer
                if review_comment is not None:
                    update_vals["review_comment"] = review_comment
                session.execute(
                    self.entity_class.__table__.update()
                    .where(self.entity_class.doc_id == doc_id)
                    .values(**update_vals)
                )
                logger.info(f"[ReviewSummaryMapper] 更新汇总记录 doc_id={doc_id}")

            session.flush()
            entity = session.query(self.entity_class).filter(
                self.entity_class.doc_id == doc_id
            ).first()
            return self._to_dict(entity) if entity else None

    def update_status(self, doc_id: str, status: str,
                      reviewer: str = None, review_comment: str = None) -> dict:
        """更新审核状态，同步到汇总表"""
        logger.info(f"[ReviewSummaryMapper] update_status doc_id={doc_id} -> {status}")
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.doc_id == doc_id
            ).first()
            if entity is None:
                logger.warning(f"[ReviewSummaryMapper] 汇总记录不存在 doc_id={doc_id}")
                return None
            session.execute(
                self.entity_class.__table__.update()
                .where(self.entity_class.doc_id == doc_id)
                .values(
                    status=status,
                    reviewer=reviewer,
                    review_comment=review_comment,
                    updated_time=datetime.now(),
                )
            )
            session.flush()
            entity = session.query(self.entity_class).filter(
                self.entity_class.doc_id == doc_id
            ).first()
            return self._to_dict(entity) if entity else None

    def update_generation_result(self, doc_id: str, xmind_file_path: str,
                                  test_case_count: int) -> dict:
        """更新生成结果（XMind路径 + 用例数量）"""
        logger.info(f"[ReviewSummaryMapper] update_generation_result doc_id={doc_id}")
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.doc_id == doc_id
            ).first()
            if entity is None:
                logger.warning(f"[ReviewSummaryMapper] 汇总记录不存在 doc_id={doc_id}")
                return None
            entity.xmind_file_path = xmind_file_path
            entity.test_case_count = test_case_count
            entity.updated_time = datetime.now()
            session.flush()
            session.refresh(entity)
            return self._to_dict(entity)

    def delete_by_doc_id(self, doc_id: str) -> bool:
        """删除汇总记录"""
        logger.info(f"[ReviewSummaryMapper] delete doc_id={doc_id}")
        with self.session_scope() as session:
            rows = session.query(self.entity_class).filter(
                self.entity_class.doc_id == doc_id
            ).delete()
            logger.info(f"[ReviewSummaryMapper] 删除行数: {rows}")
            return rows > 0

    # ------------------------------------------------------------------
    # 读操作
    # ------------------------------------------------------------------

    def list_all(self, status: str = None, business_module: str = None,
                 document_type: str = None,
                 limit: int = 100, offset: int = 0) -> list:
        """
        分页查询汇总列表，支持按状态/业务模块/文档类型过滤。
        返回字典列表，可直接序列化为 JSON。
        """
        with self.session_scope() as session:
            query = session.query(self.entity_class)
            if status:
                query = query.filter(self.entity_class.status == status)
            if business_module:
                query = query.filter(self.entity_class.business_module == business_module)
            if document_type:
                query = query.filter(self.entity_class.document_type == document_type)
            entities = query.order_by(
                self.entity_class.created_time.desc()
            ).offset(offset).limit(limit).all()
            return [self._to_dict(e) for e in entities]

    def get_count(self, status: str = None, business_module: str = None, document_type: str = None) -> int:
        """查询汇总记录总数"""
        from sqlalchemy import func
        with self.session_scope() as session:
            query = session.query(func.count(self.entity_class.id))
            if status:
                query = query.filter(self.entity_class.status == status)
            if business_module:
                query = query.filter(self.entity_class.business_module == business_module)
            if document_type:
                query = query.filter(self.entity_class.document_type == document_type)
            return query.scalar()

    def get_by_doc_id(self, doc_id: str) -> dict:
        """根据 doc_id 查询单条汇总记录"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.doc_id == doc_id
            ).first()
            return self._to_dict(entity)
