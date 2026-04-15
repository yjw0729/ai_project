# common/db_mapper/test_suite_case_mapper.py
from sqlalchemy import and_, or_, func, desc, asc
from common.db_enitiy.test_suite_case import TestSuiteCase
from contextlib import contextmanager
from common.datacase_function.contect_db import db_session
from datetime import datetime, timedelta
import json


class TestSuiteCaseMapper:
    """TestSuiteCase表的数据访问类"""

    def __init__(self):
        self.entity_class = TestSuiteCase

    @contextmanager
    def session_scope(self):
        """提供数据库会话的上下文管理"""
        with db_session() as session:
            yield session

    # 基础CRUD操作
    def get_by_id(self, id):
        """根据ID获取关联记录"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()
            if entity is None:
                return None
            return {
                "id": entity.id,
                "suite_id": entity.suite_id,
                "case_id": entity.case_id,
                "name": entity.name,
                "case_id_str": entity.case_id_str,
                "execution_order": entity.execution_order,
                "enabled": entity.enabled,
                "url": entity.url,
                "request_headers": entity.request_headers,
                "request_params": entity.request_params,
                "request_body": entity.request_body,
                "timeout": entity.timeout,
                "assertions": entity.assertions,
                "config": entity.config,
                "preconditions": entity.preconditions,
                "test_steps": entity.test_steps,
                "test_data": entity.test_data,
                "created_time": entity.created_time,
                "updated_time": entity.updated_time,
            }

    def get_by_suite_and_case(self, suite_id, case_id):
        """根据套件ID和案例ID获取关联记录"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.suite_id == suite_id,
                self.entity_class.case_id == case_id
            ).first()
            if entity is None:
                return None
            return {
                "id": entity.id,
                "suite_id": entity.suite_id,
                "case_id": entity.case_id,
            }

    def get_case_count(self, suite_id):
        """获取指定套件的用例数量"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.suite_id == suite_id
            ).count()

    def get_all(self):
        """获取所有关联记录"""
        with self.session_scope() as session:
            return session.query(self.entity_class).order_by(
                self.entity_class.suite_id,
                self.entity_class.execution_order,
                self.entity_class.case_id
            ).all()

    def create(self, entity):
        """创建关联记录"""
        # 验证关联
        errors = entity.validate_association()
        if errors:
            raise ValueError(f"关联验证失败: {', '.join(errors)}")

        # 检查是否已存在
        existing = self.get_by_suite_and_case(entity.suite_id, entity.case_id)
        if existing:
            raise ValueError(f"套件-案例关联已存在: suite_id={entity.suite_id}, case_id={entity.case_id}")

        with self.session_scope() as session:
            session.add(entity)
            session.flush()
            session.refresh(entity)
            return entity

    def update(self, id, update_data):
        """更新关联记录"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

            if entity:
                for key, value in update_data.items():
                    if hasattr(entity, key) and key != 'id':
                        setattr(entity, key, value)

                # 验证更新后的关联
                errors = entity.validate_association()
                if errors:
                    session.rollback()
                    raise ValueError(f"更新后关联验证失败: {', '.join(errors)}")

                return entity
            return None

    def delete(self, id):
        """删除关联记录"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

            if entity:
                session.delete(entity)
                return True
            return False

    def delete_by_suite_and_case(self, suite_id, case_id):
        """根据套件ID和案例ID删除关联记录"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.suite_id == suite_id,
                self.entity_class.case_id == case_id
            ).first()

            if entity:
                session.delete(entity)
                return True
            return False

    # 特定查询方法
    def get_cases_by_suite(self, suite_id, enabled_only=True, order_by_execution=True):
        """获取套件中的所有案例"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.suite_id == suite_id
            )

            if enabled_only:
                # 启用判断逻辑：enabled字段为True或NULL，或config中enabled=true，或config为空/NULL
                query = query.filter(
                    or_(
                        self.entity_class.enabled == True,
                        self.entity_class.enabled.is_(None),
                        self.entity_class.config.is_(None),
                        self.entity_class.config == 'null',
                        self.entity_class.config == {},
                        self.entity_class.config['enabled'] == True
                    )
                )

            if order_by_execution:
                query = query.order_by(
                    asc(self.entity_class.execution_order),
                    asc(self.entity_class.case_id)
                )
            else:
                query = query.order_by(asc(self.entity_class.case_id))

            entities = query.all()

            results = []
            for e in entities:
                results.append({
                    "id": e.id,
                    "suite_id": e.suite_id,
                    "case_id": e.case_id,
                    "name": e.name,
                    "case_id_str": e.case_id_str,
                    "execution_order": e.execution_order,
                    "enabled": e.enabled,
                    "url": e.url,
                    "request_headers": e.request_headers,
                    "request_params": e.request_params,
                    "request_body": e.request_body,
                    "timeout": e.timeout,
                    "assertions": e.assertions,
                    "config": e.config,
                    "preconditions": e.preconditions,
                    "test_steps": e.test_steps,
                    "test_data": e.test_data,
                    "created_time": e.created_time,
                    "updated_time": e.updated_time,
                })
            return results

    def get_suites_by_case(self, case_id):
        """获取包含指定案例的所有套件"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.case_id == case_id
            ).order_by(
                asc(self.entity_class.suite_id)
            ).all()

    def get_case_count_by_suite(self, suite_id, enabled_only=True):
        """获取套件中的案例数量"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.suite_id == suite_id
            )

            if enabled_only:
                query = query.filter(
                    or_(
                        self.entity_class.enabled == True,
                        self.entity_class.enabled.is_(None),
                        self.entity_class.config.is_(None),
                        self.entity_class.config == 'null',
                        self.entity_class.config == {},
                        self.entity_class.config['enabled'] == True
                    )
                )

            return query.count()

    def get_suite_count_by_case(self, case_id):
        """获取案例所属的套件数量"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.case_id == case_id
            ).count()

    def get_execution_order(self, suite_id, case_id):
        """获取案例在套件中的执行顺序"""
        association = self.get_by_suite_and_case(suite_id, case_id)
        return association.execution_order if association else None

    def update_execution_order(self, suite_id, case_id, new_order):
        """更新案例在套件中的执行顺序"""
        with self.session_scope() as session:
            updated_count = session.query(self.entity_class).filter(
                self.entity_class.suite_id == suite_id,
                self.entity_class.case_id == case_id
            ).update({
                'execution_order': new_order
            }, synchronize_session=False)

            return updated_count > 0

    def reorder_suite_cases(self, suite_id, new_order_list):
        """重新排序套件中的案例"""
        with self.session_scope() as session:
            for index, case_id in enumerate(new_order_list):
                session.query(self.entity_class).filter(
                    self.entity_class.suite_id == suite_id,
                    self.entity_class.case_id == case_id
                ).update({
                    'execution_order': index + 1
                }, synchronize_session=False)

            return len(new_order_list)

    def get_next_execution_order(self, suite_id):
        """获取套件中下一个可用的执行顺序"""
        with self.session_scope() as session:
            max_order = session.query(
                func.max(self.entity_class.execution_order)
            ).filter(
                self.entity_class.suite_id == suite_id
            ).scalar()

            return (max_order or 0) + 1

    # 批量操作方法
    def bulk_add_cases_to_suite(self, suite_id, case_ids, configs=None):
        """批量添加案例到套件"""
        if not case_ids:
            return 0

        if configs is None:
            configs = [{}] * len(case_ids)
        elif isinstance(configs, dict):
            configs = [configs] * len(case_ids)

        added_count = 0
        start_order = self.get_next_execution_order(suite_id)

        for i, case_id in enumerate(case_ids):
            try:
                association = TestSuiteCase.create_association(
                    suite_id=suite_id,
                    case_id=case_id,
                    execution_order=start_order + i,
                    config=configs[i] if i < len(configs) else {}
                )

                self.create(association)
                added_count += 1
            except Exception as e:
                # 如果关联已存在，跳过
                if "已存在" not in str(e):
                    raise e

        return added_count

    def bulk_remove_cases_from_suite(self, suite_id, case_ids):
        """批量从套件中移除案例"""
        with self.session_scope() as session:
            deleted_count = session.query(self.entity_class).filter(
                self.entity_class.suite_id == suite_id,
                self.entity_class.case_id.in_(case_ids)
            ).delete(synchronize_session=False)

            return deleted_count

    def bulk_update_case_configs(self, suite_id, case_configs):
        """批量更新案例配置"""
        updated_count = 0

        for case_id, config in case_configs.items():
            association = self.get_by_suite_and_case(suite_id, case_id)
            if association:
                update_data = {'config': {**association.config, **config} if association.config else config}
                self.update(association.id, update_data)
                updated_count += 1

        return updated_count

    def bulk_enable_cases(self, suite_id, case_ids, enabled=True):
        """批量启用/禁用套件中的案例"""
        with self.session_scope() as session:
            associations = session.query(self.entity_class).filter(
                self.entity_class.suite_id == suite_id,
                self.entity_class.case_id.in_(case_ids)
            ).all()

            updated_count = 0
            for association in associations:
                if not association.config:
                    association.config = {}

                association.config['enabled'] = enabled
                updated_count += 1

            return updated_count

    # 统计和分析方法
    def get_suite_statistics(self, suite_id):
        """获取套件统计信息"""
        with self.session_scope() as session:
            # 总案例数
            total_cases = session.query(self.entity_class).filter(
                self.entity_class.suite_id == suite_id
            ).count()

            # 启用案例数
            enabled_cases = session.query(self.entity_class).filter(
                self.entity_class.suite_id == suite_id,
                or_(
                    self.entity_class.enabled == True,
                    self.entity_class.enabled.is_(None),
                    self.entity_class.config.is_(None),
                    self.entity_class.config == 'null',
                    self.entity_class.config == {},
                    self.entity_class.config['enabled'] == True
                )
            ).count()

            # 平均执行顺序
            avg_order = session.query(
                func.avg(self.entity_class.execution_order)
            ).filter(
                self.entity_class.suite_id == suite_id
            ).scalar() or 0

            # 配置使用情况
            config_stats = session.query(
                func.count(self.entity_class.id)
            ).filter(
                self.entity_class.suite_id == suite_id,
                self.entity_class.config.isnot(None),
                self.entity_class.config != 'null'
            ).scalar() or 0

            return {
                'total_cases': total_cases,
                'enabled_cases': enabled_cases,
                'disabled_cases': total_cases - enabled_cases,
                'enabled_rate': round((enabled_cases / total_cases * 100), 2) if total_cases > 0 else 0,
                'average_execution_order': round(avg_order, 2),
                'cases_with_config': config_stats,
                'cases_without_config': total_cases - config_stats
            }

    def get_case_usage_statistics(self, case_id):
        """获取案例使用情况统计"""
        with self.session_scope() as session:
            suite_count = session.query(self.entity_class).filter(
                self.entity_class.case_id == case_id
            ).count()

            # 获取案例所在的套件类型分布
            from common.db_enitiy.test_suite import TestSuite
            type_stats = session.query(
                TestSuite.suite_type,
                func.count(self.entity_class.id)
            ).join(
                TestSuite, self.entity_class.suite_id == TestSuite.id
            ).filter(
                self.entity_class.case_id == case_id,
                TestSuite.status == 'active'
            ).group_by(
                TestSuite.suite_type
            ).all()

            return {
                'suite_count': suite_count,
                'by_suite_type': {row[0]: row[1] for row in type_stats},
                'usage_level': self._get_usage_level(suite_count)
            }

    def _get_usage_level(self, suite_count):
        """获取使用级别"""
        if suite_count >= 5:
            return 'high'
        elif suite_count >= 2:
            return 'medium'
        elif suite_count >= 1:
            return 'low'
        else:
            return 'none'

    def get_most_used_cases(self, limit=10):
        """获取最常用的案例（被最多套件使用）"""
        with self.session_scope() as session:
            results = session.query(
                self.entity_class.case_id,
                func.count(self.entity_class.id).label('usage_count')
            ).group_by(
                self.entity_class.case_id
            ).order_by(
                desc('usage_count')
            ).limit(limit).all()

            return [{'case_id': row[0], 'usage_count': row[1]} for row in results]

    def get_largest_suites(self, limit=10):
        """获取包含案例最多的套件"""
        with self.session_scope() as session:
            results = session.query(
                self.entity_class.suite_id,
                func.count(self.entity_class.id).label('case_count')
            ).group_by(
                self.entity_class.suite_id
            ).order_by(
                desc('case_count')
            ).limit(limit).all()

            return [{'suite_id': row[0], 'case_count': row[1]} for row in results]

    def get_case_dependencies(self, case_id):
        """获取案例的依赖关系（通过套件关联）"""
        with self.session_scope() as session:
            # 获取包含该案例的所有套件
            suite_associations = session.query(self.entity_class).filter(
                self.entity_class.case_id == case_id
            ).all()

            dependencies = []
            for association in suite_associations:
                # 获取同一套件中的其他案例
                suite_cases = session.query(self.entity_class).filter(
                    self.entity_class.suite_id == association.suite_id,
                    self.entity_class.case_id != case_id
                ).order_by(
                    self.entity_class.execution_order
                ).all()

                for suite_case in suite_cases:
                    dependencies.append({
                        'suite_id': association.suite_id,
                        'dependent_case_id': suite_case.case_id,
                        'execution_order': suite_case.execution_order,
                        'relationship': 'precedes' if suite_case.execution_order > association.execution_order else 'follows'
                    })

            return dependencies

    # 导入导出方法
    def export_suite_structure(self, suite_id):
        """导出套件结构"""
        cases = self.get_cases_by_suite(suite_id, enabled_only=False, order_by_execution=True)

        suite_structure = {
            'suite_id': suite_id,
            'total_cases': len(cases),
            'cases': []
        }

        for association in cases:
            case_info = {
                'case_id': association.case_id,
                'execution_order': association.execution_order,
                'config': association.config or {},
                'enabled': association.is_enabled(),
                'timeout': association.get_timeout(),
                'retry_count': association.get_retry_count(),
                'priority': association.get_priority()
            }
            suite_structure['cases'].append(case_info)

        return json.dumps(suite_structure, indent=2, ensure_ascii=False)

    def import_suite_structure(self, suite_id, structure_data, clear_existing=False):
        """导入套件结构"""
        if isinstance(structure_data, str):
            structure = json.loads(structure_data)
        else:
            structure = structure_data

        if clear_existing:
            # 清空现有案例
            self.clear_suite_cases(suite_id)

        imported_count = 0
        errors = []

        for case_info in structure.get('cases', []):
            try:
                association = TestSuiteCase.create_association(
                    suite_id=suite_id,
                    case_id=case_info['case_id'],
                    execution_order=case_info.get('execution_order', 0),
                    config=case_info.get('config', {})
                )

                self.create(association)
                imported_count += 1
            except Exception as e:
                errors.append(f"导入案例失败 case_id={case_info['case_id']}: {str(e)}")

        return {
            'imported_count': imported_count,
            'total_cases': len(structure.get('cases', [])),
            'errors': errors
        }

    def clear_suite_cases(self, suite_id):
        """清空套件中的所有案例"""
        with self.session_scope() as session:
            deleted_count = session.query(self.entity_class).filter(
                self.entity_class.suite_id == suite_id
            ).delete(synchronize_session=False)

            return deleted_count

    def duplicate_suite_structure(self, source_suite_id, target_suite_id, copy_config=True):
        """复制套件结构"""
        source_cases = self.get_cases_by_suite(source_suite_id, enabled_only=False, order_by_execution=True)
        copied_count = 0

        for source_association in source_cases:
            try:
                config = source_association.config if copy_config else {}

                association = TestSuiteCase.create_association(
                    suite_id=target_suite_id,
                    case_id=source_association.case_id,
                    execution_order=source_association.execution_order,
                    config=config
                )

                self.create(association)
                copied_count += 1
            except Exception as e:
                # 如果关联已存在，跳过
                if "已存在" not in str(e):
                    raise e

        return copied_count

    # 验证方法
    def validate_suite_integrity(self, suite_id):
        """验证套件完整性"""
        issues = []

        # 检查执行顺序是否连续
        cases = self.get_cases_by_suite(suite_id, enabled_only=False, order_by_execution=True)
        orders = [case.execution_order for case in cases]

        if orders:
            # 检查重复的执行顺序
            if len(orders) != len(set(orders)):
                issues.append("存在重复的执行顺序")

            # 检查顺序是否连续
            expected_orders = list(range(1, len(orders) + 1))
            if sorted(orders) != expected_orders:
                issues.append("执行顺序不连续")

        # 检查配置格式
        for case in cases:
            if case.config and not isinstance(case.config, (dict, list)):
                try:
                    json.loads(case.config)
                except:
                    issues.append(f"案例 {case.case_id} 的配置格式无效")

        return {
            'suite_id': suite_id,
            'total_cases': len(cases),
            'enabled_cases': len([c for c in cases if c.is_enabled()]),
            'issues': issues,
            'is_valid': len(issues) == 0
        }

    def fix_suite_execution_order(self, suite_id):
        """修复套件执行顺序（使其连续）"""
        cases = self.get_cases_by_suite(suite_id, enabled_only=False, order_by_execution=False)
        cases.sort(key=lambda x: x.execution_order)

        fixed_count = 0
        for i, case in enumerate(cases):
            if case.execution_order != i + 1:
                self.update_execution_order(suite_id, case.case_id, i + 1)
                fixed_count += 1

        return fixed_count

    # 高级查询方法
    def search_cases_in_suites(self, suite_ids, case_filters=None, enabled_only=True):
        """在多个套件中搜索案例"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.suite_id.in_(suite_ids)
            )

            if enabled_only:
                query = query.filter(
                    or_(
                        self.entity_class.enabled == True,
                        self.entity_class.enabled.is_(None),
                        self.entity_class.config.is_(None),
                        self.entity_class.config == 'null',
                        self.entity_class.config == {},
                        self.entity_class.config['enabled'] == True
                    )
                )

            # 应用案例过滤器（需要关联TestCase表）
            if case_filters:
                from common.db_enitiy.test_case import TestCase
                query = query.join(TestCase, self.entity_class.case_id == TestCase.id)

                if case_filters.get('module'):
                    query = query.filter(TestCase.module == case_filters['module'])

                if case_filters.get('priority'):
                    query = query.filter(TestCase.priority == case_filters['priority'])

                if case_filters.get('keyword'):
                    query = query.filter(or_(
                        TestCase.name.ilike(f'%{case_filters["keyword"]}%'),
                        TestCase.description.ilike(f'%{case_filters["keyword"]}%')
                    ))

            return query.order_by(
                self.entity_class.suite_id,
                self.entity_class.execution_order
            ).all()

    def get_cross_suite_dependencies(self, case_id):
        """获取案例的跨套件依赖关系"""
        # 获取包含该案例的所有套件
        suite_associations = self.get_suites_by_case(case_id)

        dependencies = []
        for association in suite_associations:
            suite_id = association.suite_id

            # 获取套件中的其他案例
            suite_cases = self.get_cases_by_suite(suite_id, enabled_only=True, order_by_execution=True)

            for suite_case in suite_cases:
                if suite_case.case_id != case_id:
                    # 检查执行顺序关系
                    if suite_case.execution_order < association.execution_order:
                        relationship = 'preceded_by'  # 被...前置
                    else:
                        relationship = 'followed_by'  # 被...后置

                    dependencies.append({
                        'suite_id': suite_id,
                        'related_case_id': suite_case.case_id,
                        'relationship': relationship,
                        'execution_order_diff': abs(suite_case.execution_order - association.execution_order)
                    })

        return dependencies