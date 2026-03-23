# common/db_mapper/test_execution_mapper.py
from sqlalchemy import and_, or_, func, desc, asc
from platform_service.models.test_execution import TestExecution
from contextlib import contextmanager
from common.datacase_function.contect_db import db_session
from datetime import datetime, timedelta
import json
import statistics


class TestExecutionMapper:
    """TestExecution表的数据访问类"""

    def __init__(self):
        self.entity_class = TestExecution

    @contextmanager
    def session_scope(self):
        """提供数据库会话的上下文管理"""
        with db_session() as session:
            yield session

    # 基础CRUD操作
    def get_by_id(self, id):
        """根据ID获取执行记录"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

    def get_by_execution_id(self, execution_id):
        """根据执行ID获取记录"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.execution_id == execution_id
            ).first()

    def get_all(self, limit=1000, offset=0):
        """获取所有执行记录（分页）"""
        with self.session_scope() as session:
            return session.query(self.entity_class).order_by(
                desc(self.entity_class.created_time)
            ).offset(offset).limit(limit).all()

    def create(self, entity):
        """创建执行记录"""
        with self.session_scope() as session:
            session.add(entity)
            session.flush()
            session.refresh(entity)
            return entity

    def bulk_create(self, entities):
        """批量创建执行记录"""
        with self.session_scope() as session:
            session.add_all(entities)
            session.flush()
            for entity in entities:
                session.refresh(entity)
            return entities

    def update(self, id, update_data):
        """更新执行记录"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

            if entity:
                for key, value in update_data.items():
                    if hasattr(entity, key) and key != 'id':
                        setattr(entity, key, value)
                return entity
            return None

    def delete(self, id):
        """删除执行记录"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

            if entity:
                session.delete(entity)
                return True
            return False

    # 特定查询方法
    def get_by_plan(self, plan_id, status=None, limit=100):
        """获取指定计划的执行记录"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.plan_id == plan_id
            )

            if status:
                query = query.filter(self.entity_class.status == status)

            return query.order_by(
                desc(self.entity_class.created_time)
            ).limit(limit).all()

    def get_by_suite(self, suite_id, status=None, limit=100):
        """获取指定套件的执行记录"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.suite_id == suite_id
            )

            if status:
                query = query.filter(self.entity_class.status == status)

            return query.order_by(
                desc(self.entity_class.created_time)
            ).limit(limit).all()

    def get_by_case(self, case_id, limit=50):
        """获取指定案例的执行记录"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.case_id == case_id
            ).order_by(
                desc(self.entity_class.created_time)
            ).limit(limit).all()

    def get_by_environment(self, environment_id, days=30):
        """获取指定环境的执行记录"""
        cutoff_date = datetime.now() - timedelta(days=days)

        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.environment_id == environment_id,
                self.entity_class.created_time >= cutoff_date
            ).order_by(
                desc(self.entity_class.created_time)
            ).all()

    def get_pending_executions(self, limit=100):
        """获取待执行的记录"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.status == 'pending'
            ).order_by(
                asc(self.entity_class.created_time)
            ).limit(limit).all()

    def get_running_executions(self):
        """获取执行中的记录"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.status == 'running'
            ).all()

    def get_recent_executions(self, hours=24, limit=100):
        """获取最近N小时的执行记录"""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.created_time >= cutoff_time
            ).order_by(
                desc(self.entity_class.created_time)
            ).limit(limit).all()

    def search_executions(self, plan_id=None, suite_id=None, case_id=None,
                          environment_id=None, status=None, executed_by=None,
                          start_date=None, end_date=None, limit=100):
        """搜索执行记录"""
        with self.session_scope() as session:
            query = session.query(self.entity_class)

            if plan_id:
                query = query.filter(self.entity_class.plan_id == plan_id)

            if suite_id:
                query = query.filter(self.entity_class.suite_id == suite_id)

            if case_id:
                query = query.filter(self.entity_class.case_id == case_id)

            if environment_id:
                query = query.filter(self.entity_class.environment_id == environment_id)

            if status:
                query = query.filter(self.entity_class.status == status)

            if executed_by:
                query = query.filter(self.entity_class.executed_by == executed_by)

            if start_date:
                query = query.filter(self.entity_class.created_time >= start_date)

            if end_date:
                query = query.filter(self.entity_class.created_time <= end_date)

            return query.order_by(
                desc(self.entity_class.created_time)
            ).limit(limit).all()

    # 统计和分析方法
    def get_execution_statistics(self, plan_id=None, suite_id=None, days=30):
        """获取执行统计信息"""
        cutoff_date = datetime.now() - timedelta(days=days)

        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.created_time >= cutoff_date
            )

            if plan_id:
                query = query.filter(self.entity_class.plan_id == plan_id)

            if suite_id:
                query = query.filter(self.entity_class.suite_id == suite_id)

            total_count = query.count()

            # 按状态统计
            status_stats = session.query(
                self.entity_class.status,
                func.count(self.entity_class.id)
            ).filter(
                self.entity_class.created_time >= cutoff_date
            )

            if plan_id:
                status_stats = status_stats.filter(self.entity_class.plan_id == plan_id)

            if suite_id:
                status_stats = status_stats.filter(self.entity_class.suite_id == suite_id)

            status_stats = status_stats.group_by(
                self.entity_class.status
            ).all()

            # 计算通过率
            passed_count = session.query(self.entity_class).filter(
                self.entity_class.status == 'passed',
                self.entity_class.created_time >= cutoff_date
            )

            if plan_id:
                passed_count = passed_count.filter(self.entity_class.plan_id == plan_id)

            if suite_id:
                passed_count = passed_count.filter(self.entity_class.suite_id == suite_id)

            passed_count = passed_count.count()

            pass_rate = round((passed_count / total_count * 100), 2) if total_count > 0 else 0

            return {
                'total_executions': total_count,
                'by_status': {row[0]: row[1] for row in status_stats},
                'pass_rate': pass_rate,
                'time_period': f"最近{days}天"
            }

    def get_case_execution_history(self, case_id, limit=20):
        """获取案例执行历史"""
        with self.session_scope() as session:
            executions = session.query(self.entity_class).filter(
                self.entity_class.case_id == case_id
            ).order_by(
                desc(self.entity_class.created_time)
            ).limit(limit).all()

            history = []
            for execution in executions:
                history.append({
                    'execution_id': execution.execution_id,
                    'status': execution.status,
                    'start_time': execution.start_time.isoformat() if execution.start_time else None,
                    'end_time': execution.end_time.isoformat() if execution.end_time else None,
                    'duration': execution.calculate_duration(),
                    'environment_id': execution.environment_id,
                    'executed_by': execution.executed_by
                })

            return history

    def get_performance_metrics(self, case_id=None, environment_id=None, days=30):
        """获取性能指标"""
        cutoff_date = datetime.now() - timedelta(days=days)

        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.status.in_(['passed', 'failed']),
                self.entity_class.start_time.isnot(None),
                self.entity_class.end_time.isnot(None),
                self.entity_class.created_time >= cutoff_date
            )

            if case_id:
                query = query.filter(self.entity_class.case_id == case_id)

            if environment_id:
                query = query.filter(self.entity_class.environment_id == environment_id)

            executions = query.all()

            if not executions:
                return {
                    'total_executions': 0,
                    'average_duration': 0,
                    'min_duration': 0,
                    'max_duration': 0,
                    'duration_std_dev': 0
                }

            durations = [e.calculate_duration() for e in executions if e.calculate_duration() > 0]

            if not durations:
                return {
                    'total_executions': len(executions),
                    'average_duration': 0,
                    'min_duration': 0,
                    'max_duration': 0,
                    'duration_std_dev': 0
                }

            return {
                'total_executions': len(executions),
                'average_duration': round(statistics.mean(durations), 2),
                'min_duration': round(min(durations), 2),
                'max_duration': round(max(durations), 2),
                'duration_std_dev': round(statistics.stdev(durations), 2) if len(durations) > 1 else 0
            }

    def get_failure_analysis(self, days=30):
        """获取失败分析"""
        cutoff_date = datetime.now() - timedelta(days=days)

        with self.session_scope() as session:
            # 失败案例统计
            failed_cases = session.query(
                self.entity_class.case_id,
                func.count(self.entity_class.id).label('failure_count')
            ).filter(
                self.entity_class.status.in_(['failed', 'error']),
                self.entity_class.created_time >= cutoff_date
            ).group_by(
                self.entity_class.case_id
            ).order_by(
                desc('failure_count')
            ).limit(10).all()

            # 失败环境统计
            failed_environments = session.query(
                self.entity_class.environment_id,
                func.count(self.entity_class.id).label('failure_count')
            ).filter(
                self.entity_class.status.in_(['failed', 'error']),
                self.entity_class.created_time >= cutoff_date
            ).group_by(
                self.entity_class.environment_id
            ).order_by(
                desc('failure_count')
            ).all()

            # 失败趋势
            failure_trend = session.query(
                func.date(self.entity_class.created_time).label('date'),
                func.count(self.entity_class.id).label('failure_count')
            ).filter(
                self.entity_class.status.in_(['failed', 'error']),
                self.entity_class.created_time >= cutoff_date
            ).group_by(
                func.date(self.entity_class.created_time)
            ).order_by(
                asc('date')
            ).all()

            return {
                'top_failed_cases': [{'case_id': row[0], 'failure_count': row[1]} for row in failed_cases],
                'failed_environments': [{'environment_id': row[0], 'failure_count': row[1]} for row in
                                        failed_environments],
                'failure_trend': [{'date': row[0].isoformat(), 'failure_count': row[1]} for row in failure_trend]
            }

    # 批量操作方法
    def bulk_update_status(self, execution_ids, new_status, result_details=None):
        """批量更新执行状态"""
        with self.session_scope() as session:
            update_data = {
                'status': new_status,
                'end_time': datetime.now() if new_status in ['passed', 'failed', 'skipped', 'error',
                                                             'cancelled'] else None
            }

            if result_details:
                update_data['result_details'] = result_details

            updated_count = session.query(self.entity_class).filter(
                self.entity_class.id.in_(execution_ids)
            ).update(update_data, synchronize_session=False)

            return updated_count

    def bulk_start_executions(self, execution_ids, executed_by='system'):
        """批量开始执行"""
        with self.session_scope() as session:
            updated_count = session.query(self.entity_class).filter(
                self.entity_class.id.in_(execution_ids),
                self.entity_class.status == 'pending'
            ).update({
                'status': 'running',
                'executed_by': executed_by,
                'start_time': datetime.now()
            }, synchronize_session=False)

            return updated_count

    def bulk_cancel_executions(self, execution_ids, reason=None):
        """批量取消执行"""
        result_details = {
            'cancellation_reason': reason or 'Bulk cancellation',
            'cancelled_at': datetime.now().isoformat()
        }

        return self.bulk_update_status(execution_ids, 'cancelled', result_details)

    def cleanup_old_executions(self, days_to_keep=90):
        """清理旧的执行记录"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)

        with self.session_scope() as session:
            deleted_count = session.query(self.entity_class).filter(
                self.entity_class.created_time < cutoff_date
            ).delete(synchronize_session=False)

            return deleted_count

    # 执行管理方法
    def start_execution(self, execution_id, executed_by='system'):
        """开始执行"""
        with self.session_scope() as session:
            execution = session.query(self.entity_class).filter(
                self.entity_class.execution_id == execution_id
            ).first()

            if execution and execution.status == 'pending':
                execution.status = 'running'
                execution.executed_by = executed_by
                execution.start_time = datetime.now()
                return True
            return False

    def complete_execution(self, execution_id, status, result_details=None):
        """完成执行"""
        with self.session_scope() as session:
            execution = session.query(self.entity_class).filter(
                self.entity_class.execution_id == execution_id
            ).first()

            if execution and execution.status == 'running':
                execution.status = status
                execution.end_time = datetime.now()

                if result_details:
                    execution.result_details = result_details

                return True
            return False

    def get_execution_progress(self, plan_id):
        """获取执行进度"""
        with self.session_scope() as session:
            total = session.query(self.entity_class).filter(
                self.entity_class.plan_id == plan_id
            ).count()

            completed = session.query(self.entity_class).filter(
                self.entity_class.plan_id == plan_id,
                self.entity_class.status.in_(['passed', 'failed', 'skipped', 'error', 'cancelled'])
            ).count()

            running = session.query(self.entity_class).filter(
                self.entity_class.plan_id == plan_id,
                self.entity_class.status == 'running'
            ).count()

            pending = session.query(self.entity_class).filter(
                self.entity_class.plan_id == plan_id,
                self.entity_class.status == 'pending'
            ).count()

            return {
                'total': total,
                'completed': completed,
                'running': running,
                'pending': pending,
                'completion_rate': round((completed / total * 100), 2) if total > 0 else 0
            }