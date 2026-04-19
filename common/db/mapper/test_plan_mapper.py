# common/db_mapper/test_plan_mapper.py
from sqlalchemy import and_, or_, func, desc, asc, case
from common.db.entity.test_plan import TestPlan
from contextlib import contextmanager
from common.db.datacase.contect_db import db_session
from datetime import datetime, timedelta
import json


class TestPlanMapper:
    """TestPlan表的数据访问类"""

    def __init__(self):
        self.entity_class = TestPlan

    @contextmanager
    def session_scope(self):
        """提供数据库会话的上下文管理"""
        with db_session() as session:
            yield session

    # 基础CRUD操作
    def get_by_id(self, id):
        """根据ID获取测试计划"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

    def get_by_name(self, name):
        """根据名称获取测试计划"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.name == name
            ).first()

    def get_all(self, include_completed=True, include_cancelled=False):
        """获取所有测试计划"""
        with self.session_scope() as session:
            query = session.query(self.entity_class)

            if not include_completed:
                query = query.filter(self.entity_class.status != 'completed')

            if not include_cancelled:
                query = query.filter(self.entity_class.status != 'cancelled')

            return query.order_by(
                desc(self.entity_class.created_time)
            ).all()

    def create(self, entity):
        """创建测试计划"""
        # 验证计划
        errors = entity.validate_plan()
        if errors:
            raise ValueError(f"测试计划验证失败: {', '.join(errors)}")

        with self.session_scope() as session:
            session.add(entity)
            session.flush()
            session.refresh(entity)
            return entity

    def update(self, id, update_data):
        """更新测试计划"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

            if entity:
                for key, value in update_data.items():
                    if hasattr(entity, key) and key != 'id':
                        setattr(entity, key, value)

                # 验证更新后的计划
                errors = entity.validate_plan()
                if errors:
                    session.rollback()
                    raise ValueError(f"更新后计划验证失败: {', '.join(errors)}")

                return entity
            return None

    def delete(self, id):
        """删除测试计划"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

            if entity:
                session.delete(entity)
                return True
            return False

    # 特定查询方法
    def get_by_type(self, plan_type, status=None):
        """获取指定类型的测试计划"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.plan_type == plan_type
            )

            if status:
                query = query.filter(self.entity_class.status == status)

            return query.order_by(
                desc(self.entity_class.created_time)
            ).all()

    def get_by_environment(self, environment_id, status=None):
        """获取指定环境的测试计划"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.environment_id == environment_id
            )

            if status:
                query = query.filter(self.entity_class.status == status)

            return query.order_by(
                desc(self.entity_class.created_time)
            ).all()

    def get_by_status(self, status):
        """获取指定状态的测试计划"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.status == status
            ).order_by(
                desc(self.entity_class.created_time)
            ).all()

    def get_by_creator(self, creator, status=None):
        """获取指定创建人的测试计划"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.creator == creator
            )

            if status:
                query = query.filter(self.entity_class.status == status)

            return query.order_by(
                desc(self.entity_class.created_time)
            ).all()

    def get_pending_plans(self):
        """获取待执行的计划"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.status == 'pending'
            ).order_by(
                asc(self.entity_class.scheduled_time)
            ).all()

    def get_running_plans(self):
        """获取执行中的计划"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.status == 'running'
            ).order_by(
                asc(self.entity_class.start_time)
            ).all()

    def get_overdue_plans(self):
        """获取过期的计划（已超过预定时间但未执行）"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.status == 'pending',
                self.entity_class.scheduled_time < datetime.now()
            ).order_by(
                asc(self.entity_class.scheduled_time)
            ).all()

    def get_scheduled_plans(self, start_date=None, end_date=None):
        """获取预定执行的计划"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.plan_type == 'scheduled',
                self.entity_class.status.in_(['pending', 'running'])
            )

            if start_date:
                query = query.filter(self.entity_class.scheduled_time >= start_date)

            if end_date:
                query = query.filter(self.entity_class.scheduled_time <= end_date)

            return query.order_by(
                asc(self.entity_class.scheduled_time)
            ).all()

    def search_plans(self, keyword=None, plan_type=None, environment_id=None,
                     status=None, creator=None, start_date=None, end_date=None):
        """搜索测试计划"""
        with self.session_scope() as session:
            query = session.query(self.entity_class)

            if keyword:
                query = query.filter(or_(
                    self.entity_class.name.ilike(f'%{keyword}%'),
                    self.entity_class.description.ilike(f'%{keyword}%')
                ))

            if plan_type:
                query = query.filter(self.entity_class.plan_type == plan_type)

            if environment_id:
                query = query.filter(self.entity_class.environment_id == environment_id)

            if status:
                query = query.filter(self.entity_class.status == status)

            if creator:
                query = query.filter(self.entity_class.creator == creator)

            if start_date:
                query = query.filter(self.entity_class.created_time >= start_date)

            if end_date:
                query = query.filter(self.entity_class.created_time <= end_date)

            return query.order_by(
                desc(self.entity_class.created_time)
            ).all()

    # 统计和分析方法
    def get_plan_statistics(self, days=30):
        """获取测试计划统计信息"""
        cutoff_date = datetime.now() - timedelta(days=days)

        with self.session_scope() as session:
            # 按类型统计
            type_stats = session.query(
                self.entity_class.plan_type,
                func.count(self.entity_class.id)
            ).filter(
                self.entity_class.created_time >= cutoff_date
            ).group_by(
                self.entity_class.plan_type
            ).all()

            # 按状态统计
            status_stats = session.query(
                self.entity_class.status,
                func.count(self.entity_class.id)
            ).filter(
                self.entity_class.created_time >= cutoff_date
            ).group_by(
                self.entity_class.status
            ).all()

            # 按环境统计
            env_stats = session.query(
                self.entity_class.environment_id,
                func.count(self.entity_class.id)
            ).filter(
                self.entity_class.created_time >= cutoff_date
            ).group_by(
                self.entity_class.environment_id
            ).all()

            # 执行时间统计
            duration_stats = session.query(
                func.avg(
                    func.timestampdiff(
                        func.second,
                        self.entity_class.start_time,
                        self.entity_class.end_time
                    )
                ).label('avg_duration'),
                func.max(
                    func.timestampdiff(
                        func.second,
                        self.entity_class.start_time,
                        self.entity_class.end_time
                    )
                ).label('max_duration'),
                func.min(
                    func.timestampdiff(
                        func.second,
                        self.entity_class.start_time,
                        self.entity_class.end_time
                    )
                ).label('min_duration')
            ).filter(
                self.entity_class.status.in_(['completed', 'failed']),
                self.entity_class.start_time.isnot(None),
                self.entity_class.end_time.isnot(None),
                self.entity_class.created_time >= cutoff_date
            ).first()

            return {
                'by_type': {row[0]: row[1] for row in type_stats},
                'by_status': {row[0]: row[1] for row in status_stats},
                'by_environment': {row[0]: row[1] for row in env_stats},
                'duration_stats': {
                    'avg_duration': round(duration_stats[0] or 0, 2),
                    'max_duration': duration_stats[1] or 0,
                    'min_duration': duration_stats[2] or 0
                },
                'total_plans': session.query(self.entity_class).filter(
                    self.entity_class.created_time >= cutoff_date
                ).count(),
                'success_rate': self._calculate_success_rate(session, cutoff_date)
            }

    def _calculate_success_rate(self, session, cutoff_date):
        """计算成功率"""
        total_completed = session.query(self.entity_class).filter(
            self.entity_class.status.in_(['completed', 'failed']),
            self.entity_class.created_time >= cutoff_date
        ).count()

        if total_completed == 0:
            return 0

        successful = session.query(self.entity_class).filter(
            self.entity_class.status == 'completed',
            self.entity_class.created_time >= cutoff_date
        ).count()

        return round((successful / total_completed) * 100, 2)

    def get_environment_usage(self):
        """获取环境使用情况统计"""
        with self.session_scope() as session:
            results = session.query(
                self.entity_class.environment_id,
                func.count(self.entity_class.id).label('total_plans'),
                func.sum(
                    case(
                    (self.entity_class.status == 'completed', 1),
                    else_=0
                )).label('completed_plans'),
                func.sum(
                    case(
                    (self.entity_class.status == 'failed', 1),
                    else_=0
                )).label('failed_plans')
            ).group_by(
                self.entity_class.environment_id
            ).all()

            return [
                {
                    'environment_id': row[0],
                    'total_plans': row[1],
                    'completed_plans': row[2] or 0,
                    'failed_plans': row[3] or 0,
                    'success_rate': round(
                        (row[2] or 0) / (row[1] or 1) * 100, 2
                    ) if row[1] > 0 else 0
                }
                for row in results
            ]

    def get_recent_activity(self, days=7):
        """获取最近活动"""
        cutoff_date = datetime.now() - timedelta(days=days)

        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.created_time >= cutoff_date
            ).order_by(
                desc(self.entity_class.updated_time)
            ).all()

    def get_upcoming_schedules(self, hours=24):
        """获取即将执行的计划"""
        start_time = datetime.now()
        end_time = datetime.now() + timedelta(hours=hours)

        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.plan_type == 'scheduled',
                self.entity_class.status == 'pending',
                self.entity_class.scheduled_time >= start_time,
                self.entity_class.scheduled_time <= end_time
            ).order_by(
                asc(self.entity_class.scheduled_time)
            ).all()

    # 批量操作方法
    def bulk_update_status(self, plan_ids, new_status, reason=None):
        """批量更新计划状态"""
        with self.session_scope() as session:
            update_data = {'status': new_status}

            if new_status in ['completed', 'failed', 'cancelled']:
                update_data['end_time'] = datetime.now()
            elif new_status == 'running':
                update_data['start_time'] = datetime.now()

            if reason and new_status == 'cancelled':
                # 对于取消状态，记录原因
                plans = session.query(self.entity_class).filter(
                    self.entity_class.id.in_(plan_ids)
                ).all()

                for plan in plans:
                    plan.set_config_value('cancellation_reason', reason)

            updated_count = session.query(self.entity_class).filter(
                self.entity_class.id.in_(plan_ids)
            ).update(update_data, synchronize_session=False)

            return updated_count

    def bulk_start_plans(self, plan_ids):
        """批量开始计划"""
        return self.bulk_update_status(plan_ids, 'running')

    def bulk_complete_plans(self, plan_ids, success=True):
        """批量完成计划"""
        status = 'completed' if success else 'failed'
        return self.bulk_update_status(plan_ids, status)

    def bulk_cancel_plans(self, plan_ids, reason=None):
        """批量取消计划"""
        return self.bulk_update_status(plan_ids, 'cancelled', reason)

    def bulk_retry_plans(self, plan_ids):
        """批量重试计划"""
        with self.session_scope() as session:
            updated_count = session.query(self.entity_class).filter(
                self.entity_class.id.in_(plan_ids),
                self.entity_class.status.in_(['failed', 'cancelled'])
            ).update({
                'status': 'pending',
                'start_time': None,
                'end_time': None
            }, synchronize_session=False)

            return updated_count

    def cleanup_old_plans(self, days_to_keep=365):
        """清理旧的计划记录"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)

        with self.session_scope() as session:
            deleted_count = session.query(self.entity_class).filter(
                self.entity_class.created_time < cutoff_date,
                self.entity_class.status.in_(['completed', 'failed', 'cancelled'])
            ).delete(synchronize_session=False)

            return deleted_count

    # 计划执行管理
    def start_plan_execution(self, plan_id):
        """开始计划执行"""
        with self.session_scope() as session:
            plan = session.query(self.entity_class).filter(
                self.entity_class.id == plan_id
            ).first()

            if plan and plan.can_start():
                plan.start_execution()
                return True
            return False

    def complete_plan_execution(self, plan_id, success=True, execution_stats=None):
        """完成计划执行"""
        with self.session_scope() as session:
            plan = session.query(self.entity_class).filter(
                self.entity_class.id == plan_id
            ).first()

            if plan and plan.status == 'running':
                plan.complete_execution(success)

                if execution_stats:
                    plan.set_config_value('execution_stats', execution_stats)

                return True
            return False

    def cancel_plan_execution(self, plan_id, reason=None):
        """取消计划执行"""
        with self.session_scope() as session:
            plan = session.query(self.entity_class).filter(
                self.entity_class.id == plan_id
            ).first()

            if plan and plan.can_cancel():
                plan.cancel_execution(reason)
                return True
            return False

    def retry_plan_execution(self, plan_id):
        """重试计划执行"""
        with self.session_scope() as session:
            plan = session.query(self.entity_class).filter(
                self.entity_class.id == plan_id
            ).first()

            if plan and plan.can_retry():
                plan.retry_execution()
                return True
            return False

    def get_plan_progress(self, plan_id):
        """获取计划执行进度（需要结合test_execution表）"""
        # 这里需要查询test_execution表来获取实际执行进度
        # 简化实现，实际项目需要关联查询
        with self.session_scope() as session:
            plan = session.query(self.entity_class).filter(
                self.entity_class.id == plan_id
            ).first()

            if not plan:
                return None

            # 模拟进度计算（实际需要从test_execution表统计）
            total_cases = plan.get_estimated_case_count()
            completed_cases = total_cases * 0.7  # 模拟70%完成

            return {
                'plan_id': plan_id,
                'plan_name': plan.name,
                'status': plan.status,
                'total_cases': total_cases,
                'completed_cases': completed_cases,
                'progress_percentage': round((completed_cases / total_cases) * 100, 2) if total_cases > 0 else 0,
                'start_time': plan.start_time.isoformat() if plan.start_time else None,
                'duration': plan.get_duration()
            }

    # 导入导出方法
    def export_plan_to_json(self, plan_id, include_execution_data=False):
        """导出计划为JSON"""
        plan = self.get_by_id(plan_id)
        if not plan:
            return None

        export_data = plan.to_json()

        if include_execution_data:
            # 这里可以添加执行数据（需要关联test_execution表）
            pass

        return json.dumps(export_data, indent=2, ensure_ascii=False)

    def import_plan_from_json(self, json_data, creator):
        """从JSON导入计划"""
        if isinstance(json_data, str):
            data = json.loads(json_data)
        else:
            data = json_data

        # 创建新计划
        plan = TestPlan(
            name=data.get('name'),
            description=data.get('description'),
            plan_type=data.get('plan_type', 'manual'),
            environment_id=data.get('environment_id'),
            suites=data.get('suites', []),
            config=data.get('config', {}),
            schedule_config=data.get('schedule_config'),
            status='pending',
            creator=creator
        )

        return self.create(plan)

    def duplicate_plan(self, original_id, new_name, new_creator, new_description=None):
        """复制计划"""
        original = self.get_by_id(original_id)
        if not original:
            raise ValueError(f"源计划不存在: {original_id}")

        # 创建副本
        duplicate_data = original.to_dict()
        duplicate_data.pop('id', None)  # 移除ID
        duplicate_data['name'] = new_name
        duplicate_data['creator'] = new_creator
        duplicate_data['status'] = 'pending'
        duplicate_data['start_time'] = None
        duplicate_data['end_time'] = None

        if new_description:
            duplicate_data['description'] = new_description

        duplicate = TestPlan(**duplicate_data)
        return self.create(duplicate)