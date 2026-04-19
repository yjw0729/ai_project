# common/db_mapper/review_record_mapper.py
from sqlalchemy import or_, and_, func
from common.db.entity.review_record import ReviewRecord, ReviewRecordStatus
from contextlib import contextmanager
from common.db.datacase.contect_db import db_session
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class ReviewRecordMapper:
    """ReviewRecord表的数据访问类"""

    def __init__(self, db_key: str = "default"):
        self.entity_class = ReviewRecord
        self.db_key = db_key

    @contextmanager
    def session_scope(self):
        """提供数据库会话的上下文管理"""
        logger.info(f"[ReviewRecordMapper] 获取数据库会话, db_key: {self.db_key}")
        try:
            with db_session(self.db_key) as session:
                yield session
        except Exception as e:
            logger.error(f"[ReviewRecordMapper] 数据库会话错误: {e}", exc_info=True)
            raise

    def _to_dict(self, entity):
        """将实体转换为字典（在session关闭前调用）"""
        if entity is None:
            return None
        result = {}
        for key in ['id', 'doc_id', 'document_title', 'business_module', 'project_background',
                    'business_summary',
                    # 接口专有字段
                    'record_type', 'interface_name', 'interface_method', 'interface_path',
                    'interface_description', 'request_params', 'request_json_sample', 'response_json_sample',
                    'response_params',
                    'process_flow', 'flow_chart_desc', 'detail_flow_analysis', 'interface_data',
                    # JSON字段
                    'flow_chart_analysis', 'image_analysis',
                    # 原始文档字段
                    'api_section', 'document_content',
                    # 状态与结果字段
                    'status', 'xmind_file_path', 'test_case_count',
                    'creator', 'reviewer', 'review_comment', 'created_time', 'updated_time']:
            value = getattr(entity, key, None)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif hasattr(value, 'value'):  # Enum
                value = value.value
            result[key] = value
        return result

    # 基础CRUD操作
    def get_by_id(self, id):
        """根据ID获取审核记录"""
        logger.info(f"[ReviewRecordMapper] 查询记录, id: {id}")
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()
            return self._to_dict(entity)

    def get_by_doc_id(self, doc_id: str):
        """根据doc_id获取审核记录（返回单条，如果有多条则返回第一条）"""
        logger.info(f"[ReviewRecordMapper] 查询记录, doc_id: {doc_id}")
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.doc_id == doc_id
            ).first()
            return self._to_dict(entity)

    def get_all_by_doc_id(self, doc_id: str):
        """根据doc_id获取所有审核记录（返回列表）"""
        logger.info(f"[ReviewRecordMapper] 查询所有记录, doc_id: {doc_id}")
        with self.session_scope() as session:
            entities = session.query(self.entity_class).filter(
                self.entity_class.doc_id == doc_id
            ).order_by(self.entity_class.id).all()
            return [self._to_dict(e) for e in entities]

    def get_all(self, status=None, business_module=None, limit=100, offset=0):
        """获取所有审核记录，支持按状态、业务模块筛选"""
        with self.session_scope() as session:
            query = session.query(self.entity_class)

            if status:
                if isinstance(status, str):
                    status = ReviewRecordStatus(status)
                query = query.filter(self.entity_class.status == status)

            if business_module:
                query = query.filter(self.entity_class.business_module == business_module)

            entities = query.order_by(
                self.entity_class.created_time.desc()
            ).offset(offset).limit(limit).all()

            # 转换为字典列表
            return [self._to_dict(e) for e in entities]

    def get_count(self, status=None, business_module=None):
        """获取审核记录总数"""
        with self.session_scope() as session:
            query = session.query(func.count(self.entity_class.id))

            if status:
                if isinstance(status, str):
                    status = ReviewRecordStatus(status)
                query = query.filter(self.entity_class.status == status)

            if business_module:
                query = query.filter(self.entity_class.business_module == business_module)

            return query.scalar()

    def create(self, entity):
        """创建新审核记录"""
        logger.info(f"[ReviewRecordMapper] 创建审核记录, doc_id: {entity.doc_id}, title: {entity.document_title}")
        try:
            with self.session_scope() as session:
                session.add(entity)
                session.flush()
                session.refresh(entity)
                # 获取ID后再转换为字典返回
                result = self._to_dict(entity)
                logger.info(f"[ReviewRecordMapper] 创建成功, 返回ID: {result.get('id')}")
                return result
        except Exception as e:
            logger.error(f"[ReviewRecordMapper] 创建失败: {e}", exc_info=True)
            raise

    def update(self, entity):
        """更新审核记录"""
        logger.info(f"[ReviewRecordMapper] 更新审核记录, doc_id: {entity.doc_id}")
        try:
            with self.session_scope() as session:
                session.merge(entity)
                session.flush()
                logger.info(f"[ReviewRecordMapper] 更新成功")
                return self._to_dict(entity)
        except Exception as e:
            logger.error(f"[ReviewRecordMapper] 更新失败: {e}", exc_info=True)
            raise

    def delete(self, id):
        """删除审核记录"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()
            if entity:
                session.delete(entity)
                return True
            return False

    def delete_by_doc_id(self, doc_id: str):
        """根据doc_id删除审核记录，并同步清理汇总表"""
        with self.session_scope() as session:
            deleted = session.query(self.entity_class).filter(
                self.entity_class.doc_id == doc_id
            ).delete()
        # 同步删除汇总表记录
        try:
            from common.db.mapper.review_summary_mapper import ReviewSummaryMapper
            ReviewSummaryMapper(db_key=self.db_key).delete_by_doc_id(doc_id)
        except Exception as se:
            logger.warning(f"[ReviewRecordMapper] 同步删除汇总表失败: {se}")
        return deleted > 0

    # 业务方法
    def update_status(self, doc_id: str, status: str, reviewer: str = None, review_comment: str = None):
        """更新审核状态"""
        logger.info(f"[ReviewRecordMapper] 更新审核状态, doc_id: {doc_id}, status: {status}")
        try:
            with self.session_scope() as session:
                # 更新所有匹配doc_id的记录
                update_values = {
                    'status': status,
                    'updated_time': datetime.now()
                }
                if reviewer:
                    update_values['reviewer'] = reviewer
                if review_comment:
                    update_values['review_comment'] = review_comment

                updated_count = session.query(self.entity_class).filter(
                    self.entity_class.doc_id == doc_id
                ).update(update_values, synchronize_session=False)

                session.flush()
                logger.info(f"[ReviewRecordMapper] 更新成功, 共更新 {updated_count} 条记录")

                # 获取更新后的记录（返回第一条作为代表）
                entity = session.query(self.entity_class).filter(
                    self.entity_class.doc_id == doc_id
                ).first()

                result = self._to_dict(entity) if entity else None

            # 同步更新汇总表状态
            try:
                from common.db.mapper.review_summary_mapper import ReviewSummaryMapper
                ReviewSummaryMapper(db_key=self.db_key).update_status(
                    doc_id=doc_id, status=status,
                    reviewer=reviewer, review_comment=review_comment
                )
            except Exception as se:
                logger.warning(f"[ReviewRecordMapper] 同步汇总表状态失败: {se}")
            return result
        except Exception as e:
            logger.error(f"[ReviewRecordMapper] 更新审核状态失败: {e}", exc_info=True)
            raise

    def update_generation_result(self, doc_id: str, xmind_file_path: str, test_case_count: int):
        """更新生成结果"""
        logger.info(f"[ReviewRecordMapper] 更新生成结果, doc_id: {doc_id}, test_case_count: {test_case_count}")
        try:
            with self.session_scope() as session:
                # 更新所有匹配doc_id的记录
                update_values = {
                    'xmind_file_path': xmind_file_path,
                    'test_case_count': test_case_count,
                    'updated_time': datetime.now()
                }

                updated_count = session.query(self.entity_class).filter(
                    self.entity_class.doc_id == doc_id
                ).update(update_values, synchronize_session=False)

                session.flush()
                logger.info(f"[ReviewRecordMapper] 生成结果更新成功, 共更新 {updated_count} 条记录")

                # 获取更新后的记录（返回第一条作为代表）
                entity = session.query(self.entity_class).filter(
                    self.entity_class.doc_id == doc_id
                ).first()

                result = entity

            # 同步更新汇总表
            try:
                from common.db.mapper.review_summary_mapper import ReviewSummaryMapper
                ReviewSummaryMapper(db_key=self.db_key).update_generation_result(
                    doc_id=doc_id,
                    xmind_file_path=xmind_file_path,
                    test_case_count=test_case_count,
                )
            except Exception as se:
                logger.warning(f"[ReviewRecordMapper] 同步汇总表生成结果失败: {se}")
            return result
        except Exception as e:
            logger.error(f"[ReviewRecordMapper] 更新生成结果失败: {e}", exc_info=True)
            raise

    def update_json_samples(self, record_id: int, request_json: str = None, response_json: str = None):
        """更新接口的JSON示例"""
        logger.info(f"[ReviewRecordMapper] 更新JSON示例, record_id: {record_id}")
        try:
            with self.session_scope() as session:
                update_values = {'updated_time': datetime.now()}
                if request_json is not None:
                    update_values['request_json_sample'] = request_json
                if response_json is not None:
                    update_values['response_json_sample'] = response_json

                updated_count = session.query(self.entity_class).filter(
                    self.entity_class.id == record_id
                ).update(update_values, synchronize_session=False)

                session.flush()
                logger.info(f"[ReviewRecordMapper] JSON示例更新成功")

                entity = session.query(self.entity_class).filter(
                    self.entity_class.id == record_id
                ).first()
                return self._to_dict(entity) if entity else None
        except Exception as e:
            logger.error(f"[ReviewRecordMapper] 更新JSON示例失败: {e}", exc_info=True)
            raise

    def update_fields(
        self,
        doc_id: str,
        document_title: str = None,
        project_background: str = None,
        business_summary: str = None,
        business_module: str = None,
        interface_list: list = None,
        flow_chart_analysis: list = None,
        image_analysis: list = None,
        status: str = None,
        reviewer: str = None,
        review_comment: str = None,
        sync_summary: bool = True,
    ) -> dict:
        """
        精细化字段更新：只更新传入了非 None 值的字段，其他字段保持原样。

        接口列表 diff 逻辑（interface_list is not None 时生效）：
        - DB 中已有（按 interface_name+interface_path+interface_method 匹配）：
          → 只更新 interface_info dict 中非 None 的子字段，其他字段保留
        - DB 中没有 → create 新行
        - DB 中有但前端未传 → delete 该行

        文档级字段（project_background / business_summary 等）：
        → bulk update 所有 doc_id 匹配的行，只 SET 非 None 的列

        参数：
        - doc_id: 文档UUID（必填）
        - document_title / project_background / business_summary / business_module: 文档级文本字段
        - interface_list: 前端传来的完整接口列表（None → 不做接口列表 diff）
        - flow_chart_analysis / image_analysis: JSON 列表，文档级
        - status / reviewer / review_comment: 审核元数据
        - sync_summary: 是否同步 summary 表（默认 True）
        """
        logger.info(f"[ReviewRecordMapper.update_fields] doc_id={doc_id}, "
                    f"doc_fields={bool(document_title or project_background or business_summary)}, "
                    f"interface_list={interface_list is not None}, "
                    f"flow_chart={flow_chart_analysis is not None}, "
                    f"status={status}")

        try:
            with self.session_scope() as session:
                # 1. 收集需要 bulk update 的文档级字段
                doc_level_values = {'updated_time': datetime.now()}
                if document_title is not None:
                    doc_level_values['document_title'] = document_title
                if project_background is not None:
                    doc_level_values['project_background'] = project_background
                if business_summary is not None:
                    doc_level_values['business_summary'] = business_summary
                if business_module is not None:
                    doc_level_values['business_module'] = business_module
                if status is not None:
                    doc_level_values['status'] = status
                if reviewer is not None:
                    doc_level_values['reviewer'] = reviewer
                if review_comment is not None:
                    doc_level_values['review_comment'] = review_comment
                if flow_chart_analysis is not None:
                    doc_level_values['flow_chart_analysis'] = flow_chart_analysis
                if image_analysis is not None:
                    doc_level_values['image_analysis'] = image_analysis

                # 执行 bulk update（所有 doc_id 匹配的行）
                if doc_level_values:
                    updated_count = session.query(self.entity_class).filter(
                        self.entity_class.doc_id == doc_id
                    ).update(doc_level_values, synchronize_session=False)
                    logger.info(f"[ReviewRecordMapper.update_fields] 批量更新文档级字段，"
                                f"影响 {updated_count} 条记录")

                # 2. 接口列表 diff（仅当 interface_list 非 None 时执行）
                if interface_list is not None:
                    # 读取 DB 中所有接口记录（按 interface_name + interface_path + interface_method 定位）
                    db_interface_records = session.query(self.entity_class).filter(
                        self.entity_class.doc_id == doc_id,
                        self.entity_class.interface_name.isnot(None),
                        self.entity_class.interface_name != ''
                    ).all()

                    # 构建 DB 端唯一键 → entity 映射
                    db_key_to_entity = {}
                    for ent in db_interface_records:
                        key = (ent.interface_name or '').strip().lower() + '|' + \
                              (ent.interface_path or '').strip().lower() + '|' + \
                              (ent.interface_method or '').strip().upper()
                        db_key_to_entity[key] = ent

                    # 构建前端唯一键集合
                    fe_keys = set()
                    for iface in interface_list:
                        key = (iface.get('name', '') or '').strip().lower() + '|' + \
                              (iface.get('path', '') or '').strip().lower() + '|' + \
                              (iface.get('method', 'GET') or 'GET').strip().upper()
                        fe_keys.add(key)

                    # 2a. 找出 DB 有但前端没有的 → delete
                    keys_to_delete = set(db_key_to_entity.keys()) - fe_keys
                    for key in keys_to_delete:
                        ent = db_key_to_entity[key]
                        logger.info(f"[ReviewRecordMapper.update_fields] 删除接口记录: "
                                    f"{ent.interface_name} {ent.interface_method} {ent.interface_path}")
                        session.delete(ent)

                    # 2b. 遍历前端接口列表 → update 或 create
                    new_interface_records = []
                    for iface in interface_list:
                        key = (iface.get('name', '') or '').strip().lower() + '|' + \
                              (iface.get('path', '') or '').strip().lower() + '|' + \
                              (iface.get('method', 'GET') or 'GET').strip().upper()

                        if key in db_key_to_entity:
                            # update：只 SET 前端传了非 None 的字段
                            ent = db_key_to_entity[key]
                            if iface.get('name') is not None:
                                ent.interface_name = iface.get('name')
                            if iface.get('method') is not None:
                                ent.interface_method = iface.get('method')
                            if iface.get('path') is not None:
                                ent.interface_path = iface.get('path')
                            if iface.get('description') is not None:
                                ent.interface_description = iface.get('description')
                            if iface.get('request_params') is not None:
                                ent.request_params = iface.get('request_params')
                            if iface.get('request_json_sample') is not None:
                                ent.request_json_sample = iface.get('request_json_sample')
                            # 兼容前端字段名 request_json
                            if iface.get('request_json') is not None:
                                ent.request_json_sample = iface.get('request_json')
                            if iface.get('response_json_sample') is not None:
                                ent.response_json_sample = iface.get('response_json_sample')
                            if iface.get('response_json') is not None:
                                ent.response_json_sample = iface.get('response_json')
                            if iface.get('response_params') is not None:
                                ent.response_params = iface.get('response_params')
                            if iface.get('process_flow') is not None:
                                ent.process_flow = iface.get('process_flow')
                            if iface.get('flow_chart_desc') is not None:
                                ent.flow_chart_desc = iface.get('flow_chart_desc')
                            if iface.get('detail_flow_analysis') is not None:
                                ent.detail_flow_analysis = iface.get('detail_flow_analysis')
                            if iface.get('interface_data') is not None:
                                ent.interface_data = iface.get('interface_data')
                            if iface.get('image_analysis') is not None:
                                ent.image_analysis = iface.get('image_analysis')
                            ent.updated_time = datetime.now()
                            logger.info(f"[ReviewRecordMapper.update_fields] 更新接口: {key}")
                        else:
                            # create 新行
                            new_ent = self.entity_class(
                                doc_id=doc_id,
                                record_type='interface',
                                document_title=document_title or '',
                                business_module=business_module or '',
                                project_background=project_background or '',
                                business_summary=business_summary or '',
                                interface_name=iface.get('name', ''),
                                interface_method=iface.get('method', 'GET'),
                                interface_path=iface.get('path', ''),
                                interface_description=iface.get('description', ''),
                                request_params=iface.get('request_params', ''),
                                request_json_sample=iface.get('request_json') or iface.get('request_json_sample', ''),
                                response_json_sample=iface.get('response_json') or iface.get('response_json_sample', ''),
                                response_params=iface.get('response_params', ''),
                                process_flow=iface.get('process_flow', ''),
                                flow_chart_desc=iface.get('flow_chart_desc', ''),
                                detail_flow_analysis=iface.get('detail_flow_analysis', ''),
                                interface_data=iface.get('interface_data') or iface,
                                image_analysis=iface.get('image_analysis', []),
                                status=status or 'pending',
                                reviewer=reviewer,
                                review_comment=review_comment,
                                creator='system',
                            )
                            session.add(new_ent)
                            new_interface_records.append(new_ent)
                            logger.info(f"[ReviewRecordMapper.update_fields] 新增接口: {key}")

                    logger.info(f"[ReviewRecordMapper.update_fields] 接口 diff 完成，"
                                f"新增 {len(new_interface_records)}，删除 {len(keys_to_delete)}")

                session.flush()

                # 返回代表记录
                entity = session.query(self.entity_class).filter(
                    self.entity_class.doc_id == doc_id
                ).first()
                result = self._to_dict(entity) if entity else None

            # 3. 同步 summary 表（只同步文档级计数和状态）
            if sync_summary:
                try:
                    from common.db.mapper.review_summary_mapper import ReviewSummaryMapper
                    if status is not None or reviewer is not None or review_comment is not None:
                        ReviewSummaryMapper(db_key=self.db_key).update_status(
                            doc_id=doc_id,
                            status=status,
                            reviewer=reviewer,
                            review_comment=review_comment,
                        )
                    if interface_list is not None:
                        ReviewSummaryMapper(db_key=self.db_key).upsert(
                            doc_id=doc_id,
                            document_title=document_title,
                            interface_count=len(interface_list),
                        )
                except Exception as se:
                    logger.warning(f"[ReviewRecordMapper.update_fields] 同步 summary 表失败（不影响主流程）: {se}")

            logger.info(f"[ReviewRecordMapper.update_fields] 完成, doc_id={doc_id}")
            return result

        except Exception as e:
            logger.error(f"[ReviewRecordMapper.update_fields] 失败: {e}", exc_info=True)
            raise

    def check_json_samples_completed(self, doc_id: str) -> dict:
        """检查所有接口的JSON示例是否都已获取完成"""
        logger.info(f"[ReviewRecordMapper] 检查JSON示例完成状态, doc_id: {doc_id}")
        try:
            with self.session_scope() as session:
                # 获取所有接口记录
                entities = session.query(self.entity_class).filter(
                    self.entity_class.doc_id == doc_id,
                    self.entity_class.interface_name.isnot(None),
                    self.entity_class.interface_name != ''
                ).all()

                if not entities:
                    return {"completed": True, "message": "无接口记录", "pending_count": 0}

                total = len(entities)
                completed = 0
                pending_interfaces = []

                for entity in entities:
                    # 如果两个JSON示例都为空或None，则认为未完成
                    req_json = entity.request_json_sample or ""
                    resp_json = entity.response_json_sample or ""

                    if req_json and resp_json:
                        completed += 1
                    else:
                        pending_interfaces.append(entity.interface_name)

                return {
                    "completed": completed == total,
                    "total": total,
                    "completed_count": completed,
                    "pending_count": total - completed,
                    "pending_interfaces": pending_interfaces
                }
        except Exception as e:
            logger.error(f"[ReviewRecordMapper] 检查JSON示例完成状态失败: {e}", exc_info=True)
            return {"completed": False, "error": str(e), "pending_count": -1}

    def save_from_review_data(self, review_data, creator: str = "system"):
        """
        从ReviewData对象保存审核记录
        为每个接口创建一条独立记录，同时保留文档级别的公共信息
        新增：区分接口详细流程图片和基础知识图片
        保存完成后同步写 crosstest_review_summary 汇总表
        """
        import re
        logger.info(f"[ReviewRecordMapper] 开始保存审核记录, doc_id: {review_data.doc_id}")
        logger.info(f"[ReviewRecordMapper] 接口数量: {len(review_data.interface_list)}")
        logger.info(f"[ReviewRecordMapper] 流程图分析数量: {len(review_data.flow_chart_analysis)}")
        logger.info(f"[ReviewRecordMapper] 图片分析数量: {len(review_data.image_analysis)}")

        created_records = []

        try:
            # 先删除该doc_id下的所有已有记录（避免重复）
            logger.info(f"[ReviewRecordMapper] 删除已有记录, doc_id: {review_data.doc_id}")
            self._delete_by_doc_id_session(review_data.doc_id)

            # 如果没有接口列表，只创建一条文档级别记录
            if not review_data.interface_list:
                logger.info("[ReviewRecordMapper] 无接口列表，创建文档级别记录")
                entity = ReviewRecord.from_review_data(review_data, creator=creator)
                result = self.create(entity)
                self._upsert_summary(
                    review_data=review_data,
                    interface_count=0,
                    image_count=len(review_data.image_analysis),
                    general_image_count=len(review_data.image_analysis),
                    creator=creator,
                )
                return [result]

            # ====== 新增：先对图片进行分析分类 ======
            image_classification = self._classify_image_analysis(
                interface_list=review_data.interface_list,
                image_analysis=review_data.image_analysis,
                flow_chart_list=review_data.flow_chart_analysis
            )

            interface_images = image_classification["interface_images"]  # 匹配到接口的图片
            general_images = image_classification["general_images"]      # 基础知识图片

            # 创建接口-图片的映射
            interface_to_images = {}
            for img_item in interface_images:
                interface_name = img_item["matched_interface_name"]
                if interface_name not in interface_to_images:
                    interface_to_images[interface_name] = []
                interface_to_images[interface_name].append(img_item["image_analysis"])

            logger.info(f"[ReviewRecordMapper] 接口图片映射: {len(interface_to_images)} 个接口有匹配图片")

            # 为每个接口创建独立记录
            for idx, interface_info in enumerate(review_data.interface_list):
                interface_name = interface_info.get('name', '未命名')
                logger.info(f"[ReviewRecordMapper] 处理接口 {idx+1}/{len(review_data.interface_list)}: {interface_name}")

                # 从flow_chart_analysis中匹配当前接口的详细流程
                flow_analysis = self._match_flow_analysis(
                    interface_info=interface_info,
                    flow_chart_list=review_data.flow_chart_analysis
                )

                if flow_analysis:
                    logger.info(f"[ReviewRecordMapper] 匹配到流程分析: {flow_analysis[:50]}...")
                else:
                    logger.info(f"[ReviewRecordMapper] 未匹配到流程分析")

                # 获取该接口匹配的图片（仅该接口专有的图片）
                interface_specific_images = interface_to_images.get(interface_name, [])

                # 创建单条记录（传入接口专有的图片列表）
                entity = ReviewRecord.from_review_data(
                    review_data,
                    interface_info=interface_info,
                    flow_analysis=flow_analysis,
                    interface_images=interface_specific_images,
                    creator=creator
                )
                result = self.create(entity)
                created_records.append(result)
                logger.info(f"[ReviewRecordMapper] 接口记录创建成功, ID: {result.get('id')}, 图片数量: {len(interface_specific_images)}")

            # ====== 创建文档级别的记录（保存所有基础知识图片） ======
            logger.info("[ReviewRecordMapper] 创建文档级别记录（包含基础知识图片）")
            entity = ReviewRecord.from_review_data(
                review_data,
                interface_info=None,
                flow_analysis="",
                interface_images=[],  # 接口记录不包含基础知识图片
                general_images=general_images,  # 文档级别记录包含所有基础知识图片
                creator=creator
            )
            result = self.create(entity)
            created_records.append(result)
            logger.info(f"[ReviewRecordMapper] 文档级别记录创建成功, ID: {result.get('id')}, 基础知识图片: {len(general_images)}")

            logger.info(f"[ReviewRecordMapper] 共创建 {len(created_records)} 条记录")

            # ====== 同步写汇总表 ======
            self._upsert_summary(
                review_data=review_data,
                interface_count=len(review_data.interface_list),
                image_count=len(review_data.image_analysis),
                general_image_count=len(general_images),
                creator=creator,
            )

            return created_records

        except Exception as e:
            logger.error(f"[ReviewRecordMapper] 保存审核记录失败: {e}", exc_info=True)
            raise

    def _match_flow_analysis(self, interface_info: dict, flow_chart_list: list) -> str:
        """
        从流程图分析列表中匹配当前接口的详细流程
        匹配逻辑：基于接口名称、路径中的关键词与流程图描述进行匹配

        返回：
        - str: 匹配到的流程图分析文本，如果没有匹配则返回空字符串
        """
        import re
        if not flow_chart_list or not interface_info:
            return ""

        interface_name = interface_info.get('name', '').lower()
        interface_path = interface_info.get('path', '').lower()
        process_flow = interface_info.get('process_flow', '').lower()

        best_match = ""
        best_score = 0

        for flow_item in flow_chart_list:
            # flow_item 可能是字符串或字典
            if isinstance(flow_item, dict):
                flow_text = str(flow_item.get('analysis', '')) + str(flow_item.get('description', ''))
            else:
                flow_text = str(flow_item)

            flow_text_lower = flow_text.lower()

            # 计算匹配分数
            score = 0

            # 1. 接口名称在流程图中
            if interface_name and interface_name in flow_text_lower:
                score += 10

            # 2. 接口路径关键词在流程图中
            if interface_path:
                path_keywords = [w for w in re.split(r'[/_\-]', interface_path) if len(w) > 2]
                for kw in path_keywords:
                    if kw in flow_text_lower:
                        score += 5

            # 3. 处理流程关键词在流程图中
            if process_flow:
                flow_keywords = [w for w in re.split(r'[,，、\n]', process_flow) if len(w) > 2]
                for kw in flow_keywords:
                    if kw in flow_text_lower:
                        score += 3

            if score > best_score:
                best_score = score
                best_match = flow_text

        # 只有匹配分数大于0才返回
        return best_match if best_score > 0 else ""

    def _calculate_match_score(self, interface_info: dict, flow_text: str) -> tuple:
        """
        计算接口与流程图的匹配分数

        返回: (score, matched_keywords) - 分数和匹配到的关键词列表
        """
        import re

        interface_name = interface_info.get('name', '')

        # 跳过空接口名
        if not interface_name:
            return 0, []

        interface_path = interface_info.get('path', '')
        process_flow = interface_info.get('process_flow', '')

        flow_lower = flow_text.lower()
        score = 0
        matched_keywords = []

        # 定义同义词映射（更完整）
        synonyms = {
            '登录': ['登入', '登陆', 'login'],
            '登入': ['登录', '登陆', 'login'],
            '获取': ['查询', '获取', '拉取', 'request'],
            '查询': ['获取', '查询', '拉取', '获取', '检索'],
            '登出': ['退出', 'logout', '登出', 'signout'],
            '退出': ['登出', 'logout', '退出', 'signout'],
            '详情': ['详细', '详情', 'detail'],
            '详细': ['详情', '详细', 'detail'],
            '商品': ['产品', '商品', 'product'],
            '产品': ['商品', '产品', 'product'],
            '创建': ['新建', '创建', '新增', 'add', 'create'],
            '新增': ['创建', '新建', '新增', 'add', 'create'],
            '订单': ['定单', '订单', 'order'],
            '支付': ['付款', '支付', '缴费', 'pay', 'payment'],
            '列表': ['list', '列表', '清单', 'list'],
            '用户': ['user', '用户'],
            '信息': ['info', '信息', '资料'],
        }

        def get_synonyms(word):
            """获取词的所有同义词"""
            result = {word}
            for key, values in synonyms.items():
                if word == key:
                    result.update(values)
                elif word in values:
                    result.add(key)
                    result.update(values)
            return result

        # 1. 接口名称精确匹配（完整名称出现在流程图中）
        if interface_name.lower() in flow_lower:
            score += 25
            matched_keywords.append(interface_name)

        # 2. 接口名称的关键词匹配（去除常见后缀后检查）
        name_clean = interface_name
        for suffix in ['接口', 'API', '服务', '方法']:
            name_clean = name_clean.replace(suffix, '').strip()

        if name_clean:
            if name_clean.lower() in flow_lower:
                score += 20
                matched_keywords.append(name_clean)
            else:
                # 3. 拆分去后缀后的名称，检查每个关键词是否都在流程图中
                name_parts = re.findall(r'[\u4e00-\u9fa5]{2,}', name_clean)
                if name_parts:
                    matched_count = 0
                    for part in name_parts:
                        part_lower = part.lower()
                        # 检查原词或同义词
                        synonym_set = get_synonyms(part_lower)
                        for syn in synonym_set:
                            if syn in flow_lower:
                                matched_count += 1
                                break

                    # 如果所有核心词都匹配，给高分
                    if matched_count == len(name_parts) and matched_count >= 2:
                        score += 18
                        matched_keywords.append(f"{name_clean}(全匹配)")
                    elif matched_count >= 1:
                        # 只要有一个词匹配，也给部分分数
                        score += 8 * matched_count
                        matched_keywords.extend(name_parts[:matched_count])

        # 4. 提取接口名中的核心词汇进行检查（支持同义词匹配）
        name_parts = re.findall(r'[\u4e00-\u9fa5]{2,}', interface_name)
        for part in name_parts:
            part_lower = part.lower()
            # 获取同义词集合
            synonym_set = get_synonyms(part_lower)

            # 检查任何同义词是否在流程图中
            matched = False
            for syn in synonym_set:
                if syn in flow_lower:
                    score += 10
                    matched_keywords.append(part)
                    matched = True
                    break

        # 5. 双向匹配：检查流程图中的关键词是否出现在接口名中（包括同义词）
        flow_parts = re.findall(r'[\u4e00-\u9fa5]{2,}', flow_text)
        for fp in flow_parts:
            fp_lower = fp.lower()
            # 只排除非常常见的无意义词
            if fp_lower in ['流程图', '系统', '第三方', '前端', '后端', '数据库', '交互', '支持', '基本']:
                continue
            if fp_lower in interface_name.lower():
                score += 8
                matched_keywords.append(fp)
            else:
                # 检查同义词是否在接口名中
                fp_synonyms = get_synonyms(fp_lower)
                for syn in fp_synonyms:
                    if syn in interface_name.lower():
                        score += 6
                        matched_keywords.append(fp)
                        break

        # 6. 接口路径关键词匹配
        if interface_path:
            path_keywords = [w for w in re.split(r'[/_\-]', interface_path) if len(w) > 2]
            for kw in path_keywords:
                if kw.lower() in flow_lower:
                    score += 5
                    matched_keywords.append(kw)

        # 7. 处理流程关键词匹配
        if process_flow:
            flow_keywords = [w for w in re.split(r'[,，、\n]', process_flow) if len(w) > 2]
            for kw in flow_keywords:
                if kw.lower() in flow_lower:
                    score += 5
                    matched_keywords.append(kw)

        # 8. 额外加分：如果flow_text提到了"流程图"或"流程"
        if '流程' in flow_text:
            score += 2

        # 去重
        matched_keywords = list(set(matched_keywords))

        return score, matched_keywords

    def _classify_image_analysis(self, interface_list: list, image_analysis: list, flow_chart_list: list) -> dict:
        """
        将图片分析结果分类：哪些是接口详细流程，哪些是基础知识

        参数：
        - interface_list: 接口列表
        - image_analysis: 图片分析结果列表
        - flow_chart_list: 流程图分析列表（包含图片分析结果）

        返回：
        - dict: {
            "interface_images": [{image_analysis, matched_interface_name, flow_text}, ...],
            "general_images": [image_analysis, ...]
        }
        """
        import re

        result = {
            "interface_images": [],  # 匹配到接口的图片
            "general_images": []      # 未匹配到接口的图片（基础知识）
        }

        if not image_analysis:
            return result

        # 如果没有接口，则所有图片都是基础知识
        if not interface_list:
            result["general_images"] = image_analysis
            return result

        # 跟踪哪些图片已被匹配到接口
        matched_image_indices = set()

        # 遍历每个接口，尝试匹配图片
        for interface_info in interface_list:
            interface_name = interface_info.get('name', '')

            best_match_img = None
            best_match_score = 0
            best_match_flow_text = ""

            for img_analysis in image_analysis:
                if not img_analysis.get('success'):
                    continue

                img_index = img_analysis.get('image_index', -1)
                if img_index in matched_image_indices:
                    continue

                # 在flow_chart_list中查找对应的分析结果
                flow_text = ""
                for flow_item in flow_chart_list:
                    if isinstance(flow_item, dict) and flow_item.get('source') == 'image':
                        if flow_item.get('filename') == img_analysis.get('filename'):
                            flow_text = str(flow_item.get('analysis', ''))
                            break

                if not flow_text:
                    flow_text = img_analysis.get('analysis', '')

                # 计算匹配分数
                score, matched_kw = self._calculate_match_score(interface_info, flow_text)

                if score > best_match_score:
                    best_match_score = score
                    best_match_img = img_analysis
                    best_match_flow_text = flow_text

            # 降低阈值到2分，只要有任何匹配就认为是接口图片
            if best_match_img and best_match_score >= 2:
                img_index = best_match_img.get('image_index', -1)
                matched_image_indices.add(img_index)
                result["interface_images"].append({
                    "image_analysis": best_match_img,
                    "matched_interface_name": interface_name,
                    "flow_text": best_match_flow_text
                })
                logger.info(f"[ReviewRecordMapper] 图片匹配到接口 '{interface_name}': score={best_match_score}")

        # 未匹配到任何接口的图片作为基础知识
        for img_analysis in image_analysis:
            img_index = img_analysis.get('image_index', -1)
            if img_index not in matched_image_indices:
                result["general_images"].append(img_analysis)
                logger.info(f"[ReviewRecordMapper] 图片作为基础知识保留: index={img_index}")

        logger.info(f"[ReviewRecordMapper] 图片分类完成: 接口图片={len(result['interface_images'])}, 基础知识图片={len(result['general_images'])}")

        return result

    def _upsert_summary(self, review_data, interface_count: int, image_count: int,
                        general_image_count: int, creator: str = "system"):
        """在保存明细记录后同步写（或更新）汇总表"""
        try:
            from common.db.mapper.review_summary_mapper import ReviewSummaryMapper
            summary_mapper = ReviewSummaryMapper(db_key=self.db_key)
            summary_mapper.upsert(
                doc_id=review_data.doc_id,
                document_title=review_data.document_title or '',
                business_module=getattr(review_data, 'business_module', None),
                interface_count=interface_count,
                image_count=image_count,
                general_image_count=general_image_count,
                creator=creator,
            )
            logger.info(f"[ReviewRecordMapper] 汇总表已同步 doc_id={review_data.doc_id}")
        except Exception as e:
            logger.warning(f"[ReviewRecordMapper] 同步汇总表失败（不影响主流程）: {e}", exc_info=True)

    def _delete_by_doc_id_session(self, doc_id: str):
        """在session中删除doc_id对应的所有记录"""
        with self.session_scope() as session:
            session.query(self.entity_class).filter(
                self.entity_class.doc_id == doc_id
            ).delete()
            logger.info(f"[ReviewRecordMapper] 已有记录已删除, doc_id: {doc_id}")

    def get_pending_reviews(self):
        """获取待审核的记录"""
        return self.get_all(status=ReviewRecordStatus.PENDING)

    def get_approved_reviews(self):
        """获取已通过的审核记录"""
        return self.get_all(status=ReviewRecordStatus.APPROVED)

    def get_rejected_reviews(self):
        """获取已拒绝的审核记录"""
        return self.get_all(status=ReviewRecordStatus.REJECTED)

    def search_by_title(self, keyword: str, limit=50):
        """根据文档标题关键字搜索"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.document_title.like(f'%{keyword}%')
            ).order_by(
                self.entity_class.created_time.desc()
            ).limit(limit).all()
