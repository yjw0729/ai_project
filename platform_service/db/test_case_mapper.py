# common/db_mapper/test_case_mapper.py
from sqlalchemy import or_, and_, func, case
from platform_service.models.test_case import TestCase, TestCaseStatus, ReviewStatus
from contextlib import contextmanager
from common.datacase_function.contect_db import db_session
import json
from datetime import datetime, timedelta
from typing import Optional


class OptimisticLockError(Exception):
    """乐观锁冲突异常"""
    def __init__(self, message, server_version, client_version):
        super().__init__(message)
        self.server_version = server_version
        self.client_version = client_version


class TestCaseMapper:
    """TestCase表的数据访问类"""

    def __init__(self, db_key: str = "default"):
        self.entity_class = TestCase
        self.db_key = db_key

    @contextmanager
    def session_scope(self):
        """提供数据库会话的上下文管理"""
        with db_session(self.db_key) as session:
            yield session

    # 基础CRUD操作
    def get_by_id(self, id):
        """根据ID获取测试案例"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

    def get_by_name_and_module(self, name, module):
        """根据名称和模块获取测试案例"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.name == name,
                self.entity_class.module == module
            ).first()

    def get_all(self, active_only=True, include_deprecated=False):
        """获取所有测试案例"""
        with self.session_scope() as session:
            query = session.query(self.entity_class)

            if active_only:
                query = query.filter(self.entity_class.status == 'active')
            elif not include_deprecated:
                query = query.filter(self.entity_class.status != 'deprecated')

            return query.order_by(
                self.entity_class.module,
                self.entity_class.priority,
                self.entity_class.name
            ).all()

    def create(self, entity):
        """创建新测试案例，返回新纪录的ID（避免DetachedInstanceError）"""
        # 验证案例
        errors = entity.validate_case()
        if errors:
            raise ValueError(f"测试案例验证失败: {', '.join(errors)}")

        with self.session_scope() as session:
            session.add(entity)
            # 先 flush 拿到自增主键
            session.flush()
            pk_id = entity.id
            # 按约定生成业务用例编号：TEST_CASE_ + 9位数字
            # 示例：id=1 -> TEST_CASE_000000001
            biz_case_id = f"TEST_CASE_{pk_id:09d}"
            # 仅当未显式指定 case_id 时才写入，避免覆盖外部自定义值
            if not getattr(entity, "case_id", None):
                entity.case_id = biz_case_id
            # 再次 flush，确保 case_id 持久化到数据库
            session.flush()
            # 将ID直接写入 __dict__ 以便离开 session 后仍可读取
            entity.__dict__['id'] = pk_id
            # 不返回实体，直接返回主键，避免会话关闭后访问属性触发懒加载
            return pk_id

    def update(self, id, update_data):
        """更新测试案例"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

            if not entity:
                return None

            # ★ 乐观锁：检查版本号是否匹配
            expected_version = update_data.pop("version", None)
            if expected_version is not None and entity.version != expected_version:
                raise OptimisticLockError(
                    message="数据已被其他人修改，请刷新后重试",
                    server_version=entity.version,
                    client_version=expected_version,
                )

            # 如果更新了重要字段，增加版本号
            important_fields = ['test_steps', 'expected_results', 'test_data']
            if any(field in update_data for field in important_fields):
                update_data['version'] = entity.version + 1

            for key, value in update_data.items():
                if hasattr(entity, key) and key != 'id':
                    setattr(entity, key, value)

            # 验证更新后的案例
            errors = entity.validate_case()
            if errors:
                session.rollback()
                raise ValueError(f"更新后案例验证失败: {', '.join(errors)}")

            return entity

    def update_with_version_check(
        self,
        id: int,
        update_data: dict,
        expected_version: Optional[int] = None,
        updated_by: Optional[str] = None
    ) -> Optional[TestCase]:
        """
        【新增】带乐观锁的更新方法。

        Args:
            id: 用例ID
            update_data: 要更新的字段
            expected_version: 期望的版本号（乐观锁检查）
            updated_by: 修改人

        Returns:
            更新后的实体，或 None

        Raises:
            OptimisticLockError: 版本号不匹配时抛出
        """
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.id == id
            )

            # ★ 乐观锁：只有版本号匹配才允许更新
            if expected_version is not None:
                query = query.filter(self.entity_class.version == expected_version)

            entity = query.first()

            if not entity:
                if expected_version is not None:
                    # ID存在但版本不匹配 → 并发冲突
                    current = session.query(self.entity_class).filter(
                        self.entity_class.id == id
                    ).first()
                    if current:
                        raise OptimisticLockError(
                            message="数据已被其他人修改，请刷新后重试",
                            server_version=current.version,
                            client_version=expected_version,
                        )
                return None

            # ★ 版本号递增
            update_data["version"] = entity.version + 1
            if updated_by:
                update_data["updated_by"] = updated_by

            for key, value in update_data.items():
                if hasattr(entity, key) and key not in ("id",):
                    setattr(entity, key, value)

            # 验证更新后的案例
            errors = entity.validate_case()
            if errors:
                session.rollback()
                raise ValueError(f"更新后案例验证失败: {', '.join(errors)}")

            session.flush()
            session.refresh(entity)
            session.expunge(entity)
            return entity

    def delete(self, id, soft_delete=True):
        """删除测试案例（支持软删除）"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

            if entity:
                if soft_delete:
                    # 软删除：标记为废弃
                    entity.status = 'deprecated'
                else:
                    # 硬删除
                    session.delete(entity)
                return True
            return False

    # 特定查询方法
    def get_by_module(self, module, status=None, priority=None):
        """获取指定模块的测试案例"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.module == module
            )

            if status:
                query = query.filter(self.entity_class.status == status)
            else:
                query = query.filter(self.entity_class.status != 'deprecated')

            if priority:
                query = query.filter(self.entity_class.priority == priority)

            return query.order_by(
                self.entity_class.priority,
                self.entity_class.name
            ).all()

    def get_by_priority(self, priority, status='active'):
        """获取指定优先级的测试案例"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.priority == priority,
                self.entity_class.status == status
            ).order_by(
                self.entity_class.module,
                self.entity_class.name
            ).all()

    def get_by_status(self, status):
        """获取指定状态的测试案例"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.status == status
            ).order_by(
                self.entity_class.module,
                self.entity_class.priority,
                self.entity_class.name
            ).all()

    def get_by_review_status(self, review_status, status='active'):
        """获取指定评审状态的测试案例"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.review_status == review_status,
                self.entity_class.status == status
            ).order_by(
                self.entity_class.module,
                self.entity_class.name
            ).all()

    def get_by_creator(self, creator, status='active'):
        """获取指定创建人的测试案例"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.creator == creator,
                self.entity_class.status == status
            ).order_by(
                self.entity_class.module,
                self.entity_class.priority,
                self.entity_class.name
            ).all()

    def search_cases(self, keyword=None, module=None, priority=None, status=None,
                     tags=None, creator=None, review_status=None):
        """搜索测试案例"""
        with self.session_scope() as session:
            query = session.query(self.entity_class)

            # 状态过滤（默认排除废弃的）
            if status:
                query = query.filter(self.entity_class.status == status)
            else:
                query = query.filter(self.entity_class.status != 'deprecated')

            if keyword:
                query = query.filter(or_(
                    self.entity_class.name.ilike(f'%{keyword}%'),
                    self.entity_class.description.ilike(f'%{keyword}%'),
                    self.entity_class.preconditions.ilike(f'%{keyword}%')
                ))

            if module:
                query = query.filter(self.entity_class.module == module)

            if priority:
                query = query.filter(self.entity_class.priority == priority)

            if creator:
                query = query.filter(self.entity_class.creator == creator)

            if review_status:
                query = query.filter(self.entity_class.review_status == review_status)

            # 标签过滤（JSON数组包含）
            if tags and isinstance(tags, list):
                for tag in tags:
                    query = query.filter(
                        self.entity_class.tags.contains([tag])
                    )

            return query.order_by(
                self.entity_class.module,
                self.entity_class.priority,
                self.entity_class.name
            ).all()

    def get_cases_with_tags(self, tags, status='active'):
        """获取包含指定标签的测试案例"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.status == status
            )

            for tag in tags:
                query = query.filter(self.entity_class.tags.contains([tag]))

            return query.order_by(
                self.entity_class.module,
                self.entity_class.priority,
                self.entity_class.name
            ).all()

    def get_ready_cases(self):
        """获取可执行的测试案例（已激活且已通过评审）"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.status == 'active',
                self.entity_class.review_status == 'approved'
            ).order_by(
                self.entity_class.priority,
                self.entity_class.module,
                self.entity_class.name
            ).all()

    def get_pending_review_cases(self):
        """获取待评审的测试案例"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.review_status == 'pending',
                self.entity_class.status.in_(['draft', 'active'])
            ).order_by(
                self.entity_class.created_time
            ).all()

    # 统计和分析方法
    def get_case_statistics(self):
        """获取测试案例统计信息"""
        with self.session_scope() as session:
            # 按模块统计
            module_stats = session.query(
                self.entity_class.module,
                func.count(self.entity_class.id)
            ).filter(
                self.entity_class.status != 'deprecated'
            ).group_by(
                self.entity_class.module
            ).all()

            # 按优先级统计
            priority_stats = session.query(
                self.entity_class.priority,
                func.count(self.entity_class.id)
            ).filter(
                self.entity_class.status != 'deprecated'
            ).group_by(
                self.entity_class.priority
            ).all()

            # 按状态统计
            status_stats = session.query(
                self.entity_class.status,
                func.count(self.entity_class.id)
            ).group_by(
                self.entity_class.status
            ).all()

            # 按评审状态统计
            review_stats = session.query(
                self.entity_class.review_status,
                func.count(self.entity_class.id)
            ).filter(
                self.entity_class.status != 'deprecated'
            ).group_by(
                self.entity_class.review_status
            ).all()

            return {
                'by_module': {row[0]: row[1] for row in module_stats},
                'by_priority': {row[0]: row[1] for row in priority_stats},
                'by_status': {row[0]: row[1] for row in status_stats},
                'by_review_status': {row[0]: row[1] for row in review_stats},
                'total_cases': session.query(self.entity_class).filter(
                    self.entity_class.status != 'deprecated'
                ).count(),
                'ready_cases': session.query(self.entity_class).filter(
                    self.entity_class.status == 'active',
                    self.entity_class.review_status == 'approved'
                ).count()
            }

    def get_module_statistics(self):
        """获取模块统计信息"""
        with self.session_scope() as session:
            # 正确使用 case 函数
            results = session.query(
                self.entity_class.module,
                func.count(self.entity_class.id).label('total_cases'),
                func.sum(
                    case(
                        (self.entity_class.status == 'active', 1),
                        else_=0
                    )
                ).label('active_cases'),
                func.sum(
                    case(
                        (self.entity_class.priority == 'P0', 1),
                        else_=0
                    )
                ).label('p0_cases'),
                func.sum(
                    case(
                        (self.entity_class.review_status == 'approved', 1),
                        else_=0
                    )
                ).label('approved_cases')
            ).filter(
                self.entity_class.status != 'deprecated'
            ).group_by(
                self.entity_class.module
            ).all()

            return [
                {
                    'module': row.module,
                    'total_cases': row.total_cases,
                    'active_cases': row.active_cases or 0,
                    'p0_cases': row.p0_cases or 0,
                    'approved_cases': row.approved_cases or 0,
                    'coverage_rate': round((row.approved_cases or 0) / (row.total_cases or 1) * 100, 2)
                }
                for row in results
            ]

    # 确保 session_scope 方法正确实现，使用 db_session 上下文返回真正的 Session
    @contextmanager
    def session_scope(self):
        """提供数据库会话的上下文管理"""
        with db_session(self.db_key) as session:
            yield session
    def get_recently_created_cases(self, days=7):
        """获取最近创建的测试案例"""
        cutoff_date = datetime.now() - timedelta(days=days)

        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.created_time >= cutoff_date,
                self.entity_class.status != 'deprecated'
            ).order_by(
                self.entity_class.created_time.desc()
            ).all()

    def get_recently_updated_cases(self, days=7):
        """获取最近更新的测试案例"""
        cutoff_date = datetime.now() - timedelta(days=days)

        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.updated_time >= cutoff_date,
                self.entity_class.status != 'deprecated'
            ).order_by(
                self.entity_class.updated_time.desc()
            ).all()

    # 批量操作方法
    def bulk_update_status(self, case_ids, new_status):
        """批量更新案例状态"""
        with self.session_scope() as session:
            updated_count = session.query(self.entity_class).filter(
                self.entity_class.id.in_(case_ids)
            ).update({
                'status': new_status,
                'updated_time': datetime.now()
            }, synchronize_session=False)

            return updated_count

    def bulk_approve_cases(self, case_ids, reviewer):
        """批量通过评审"""
        with self.session_scope() as session:
            updated_count = session.query(self.entity_class).filter(
                self.entity_class.id.in_(case_ids),
                self.entity_class.review_status == 'pending'
            ).update({
                'review_status': 'approved',
                'reviewer': reviewer,
                'updated_time': datetime.now()
            }, synchronize_session=False)

            return updated_count

    def bulk_update_module(self, old_module, new_module):
        """批量更新模块名称"""
        with self.session_scope() as session:
            updated_count = session.query(self.entity_class).filter(
                self.entity_class.module == old_module
            ).update({
                'module': new_module,
                'updated_time': datetime.now()
            }, synchronize_session=False)

            return updated_count

    def bulk_add_tags(self, case_ids, tags):
        """批量添加标签"""
        if not isinstance(tags, list):
            tags = [tags]

        with self.session_scope() as session:
            cases = session.query(self.entity_class).filter(
                self.entity_class.id.in_(case_ids)
            ).all()

            updated_count = 0
            for case in cases:
                if not case.tags:
                    case.tags = []

                for tag in tags:
                    if tag not in case.tags:
                        case.tags.append(tag)
                        updated_count += 1

            return updated_count

    # 导入导出方法
    def export_cases_to_json(self, case_ids=None):
        with self.session_scope() as session:
            """导出测试案例为JSON"""
            if case_ids:
                cases = session.query(self.entity_class).filter(
                    self.entity_class.id.in_(case_ids)
                ).all()
            else:
                cases = self.get_all(include_deprecated=False)

            export_data = []
            for case in cases:
                case_data = case.to_json()
                export_data.append(case_data)

        return json.dumps(export_data, indent=2, ensure_ascii=False)

    def import_cases_from_json(self, json_data, creator):
        """从JSON导入测试案例"""
        if isinstance(json_data, str):
            data = json.loads(json_data)
        else:
            data = json_data

        imported_count = 0
        errors = []

        for case_data in data:
            try:
                # 检查是否已存在
                existing = self.get_by_name_and_module(
                    case_data['name'],
                    case_data['module']
                )

                if existing:
                    # 如果已存在，更新
                    case_data['creator'] = creator
                    case_data['version'] = existing.version + 1
                    self.update(existing.id, case_data)
                else:
                    # 创建新案例
                    case_data['creator'] = creator
                    case = TestCase(**case_data)
                    self.create(case)

                imported_count += 1
            except Exception as e:
                errors.append(f"导入案例 '{case_data.get('name', 'unknown')}' 失败: {str(e)}")

        return {
            'imported_count': imported_count,
            'total_count': len(data),
            'errors': errors
        }

    # 复制和模板方法
    def duplicate_case(self, original_id, new_name, new_description=None, creator=None):
        """复制测试案例"""
        original = self.get_by_id(original_id)
        if not original:
            raise ValueError(f"源测试案例不存在: {original_id}")

        # 创建副本
        duplicate_data = original.to_dict()
        duplicate_data.pop('id', None)  # 移除ID
        duplicate_data['name'] = new_name
        duplicate_data['version'] = 1
        duplicate_data['review_status'] = 'pending'
        duplicate_data['reviewer'] = None
        duplicate_data['review_comment'] = None

        if new_description:
            duplicate_data['description'] = new_description

        if creator:
            duplicate_data['creator'] = creator

        duplicate = TestCase(**duplicate_data)
        return self.create(duplicate)

    def create_case_from_template(self, template_type, name, module, creator, **kwargs):
        """根据模板创建测试案例"""
        templates = {
            'api_smoke': self._create_api_smoke_template,
            'api_regression': self._create_api_regression_template,
            'ui_smoke': self._create_ui_smoke_template,
            'database': self._create_database_template,
            'performance': self._create_performance_template
        }

        if template_type not in templates:
            raise ValueError(f"未知的模板类型: {template_type}")

        return templates[template_type](name, module, creator, **kwargs)

    def _create_api_smoke_template(self, name, module, creator, **kwargs):
        """创建API冒烟测试模板"""
        steps = [
            {
                'step_number': 1,
                'description': '验证服务健康状态',
                'action': 'api_call',
                'data': {'endpoint': '/health', 'method': 'GET'},
                'expected': '服务健康检查通过'
            },
            {
                'step_number': 2,
                'description': '验证基础功能接口',
                'action': 'api_call',
                'data': {'endpoint': '/api/info', 'method': 'GET'},
                'expected': '接口返回基础信息'
            }
        ]

        case = TestCase.create_simple_case(name, module, steps, creator, 'P0')
        case.tags = ['smoke', 'api', 'critical']
        case.description = f"{module}模块API冒烟测试"

        return self.create(case)

    def _create_api_regression_template(self, name, module, creator, **kwargs):
        """创建API回归测试模板"""
        # 更详细的API测试步骤
        steps = [
            {
                'step_number': 1,
                'description': '准备测试数据',
                'action': 'setup',
                'expected': '测试数据准备完成'
            },
            {
                'step_number': 2,
                'description': '执行创建操作',
                'action': 'api_call',
                'expected': '创建操作成功'
            },
            {
                'step_number': 3,
                'description': '执行查询操作',
                'action': 'api_call',
                'expected': '查询操作成功'
            },
            {
                'step_number': 4,
                'description': '执行更新操作',
                'action': 'api_call',
                'expected': '更新操作成功'
            },
            {
                'step_number': 5,
                'description': '执行删除操作',
                'action': 'api_call',
                'expected': '删除操作成功'
            }
        ]

        case = TestCase.create_simple_case(name, module, steps, creator, 'P1')
        case.tags = ['regression', 'api', 'comprehensive']
        case.description = f"{module}模块API回归测试"

        return self.create(case)

    def _create_ui_smoke_template(self, name, module, creator, **kwargs):
        """创建UI冒烟测试模板"""
        steps = [
            {
                'step_number': 1,
                'description': '打开应用首页',
                'action': 'ui_navigate',
                'expected': '首页加载成功'
            },
            {
                'step_number': 2,
                'description': '验证关键页面元素',
                'action': 'ui_verify',
                'expected': '页面元素显示正常'
            },
            {
                'step_number': 3,
                'description': '执行基础用户操作',
                'action': 'ui_interact',
                'expected': '用户操作响应正常'
            }
        ]

        case = TestCase.create_simple_case(name, module, steps, creator, 'P0')
        case.tags = ['smoke', 'ui', 'critical']
        case.description = f"{module}模块UI冒烟测试"

        return self.create(case)

    def _create_database_template(self, name, module, creator, **kwargs):
        """创建数据库测试模板"""
        steps = [
            {
                'step_number': 1,
                'description': '连接数据库',
                'action': 'db_connect',
                'expected': '数据库连接成功'
            },
            {
                'step_number': 2,
                'description': '执行数据查询',
                'action': 'db_query',
                'expected': '查询结果符合预期'
            },
            {
                'step_number': 3,
                'description': '验证数据完整性',
                'action': 'db_verify',
                'expected': '数据完整性验证通过'
            }
        ]

        case = TestCase.create_simple_case(name, module, steps, creator, 'P2')
        case.tags = ['database', 'validation']
        case.description = f"{module}模块数据库验证测试"

        return self.create(case)

    def _create_performance_template(self, name, module, creator, **kwargs):
        """创建性能测试模板"""
        steps = [
            {
                'step_number': 1,
                'description': '设置性能基准',
                'action': 'perf_setup',
                'expected': '性能基准设置完成'
            },
            {
                'step_number': 2,
                'description': '执行性能测试',
                'action': 'perf_execute',
                'expected': '性能测试执行完成'
            },
            {
                'step_number': 3,
                'description': '分析性能结果',
                'action': 'perf_analyze',
                'expected': '性能结果分析完成'
            }
        ]

        case = TestCase.create_simple_case(name, module, steps, creator, 'P2')
        case.tags = ['performance', 'benchmark']
        case.description = f"{module}模块性能测试"
        case.timeout = 300  # 性能测试需要更长时间

        return self.create(case)


# 将异常绑定到类，使 mapper.OptimisticLockError 可访问
TestCaseMapper.OptimisticLockError = OptimisticLockError