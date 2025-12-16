# common/db_mapper/test_suite_mapper.py
from sqlalchemy import and_, or_, func, desc, asc
from common.db_enitiy.test_suite import TestSuite
from contextlib import contextmanager
from common.datacase_function.contect_db import db_session
from datetime import datetime, timedelta
import json


class TestSuiteMapper:
    """TestSuite表的数据访问类"""

    def __init__(self):
        self.entity_class = TestSuite

    @contextmanager
    def session_scope(self):
        """提供数据库会话的上下文管理"""
        with db_session() as session:
            yield session

    # 基础CRUD操作
    def get_by_id(self, id):
        """根据ID获取测试套件"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

    def get_by_name(self, name):
        """根据名称获取测试套件"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.name == name
            ).first()

    def get_all(self, active_only=True):
        """获取所有测试套件"""
        with self.session_scope() as session:
            query = session.query(self.entity_class)

            if active_only:
                query = query.filter(self.entity_class.status == 'active')

            return query.order_by(
                self.entity_class.module,
                self.entity_class.suite_type,
                self.entity_class.name
            ).all()

    def create(self, entity):
        """创建测试套件"""
        # 验证套件
        errors = entity.validate_suite()
        if errors:
            raise ValueError(f"测试套件验证失败: {', '.join(errors)}")

        # 检查名称唯一性
        existing = self.get_by_name(entity.name)
        if existing:
            raise ValueError(f"测试套件名称已存在: {entity.name}")

        # 应用默认配置
        entity.apply_default_config()

        with self.session_scope() as session:
            session.add(entity)
            session.flush()
            session.refresh(entity)
            return entity

    def update(self, id, update_data):
        """更新测试套件"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

            if entity:
                # 检查是否修改了名称
                if 'name' in update_data and update_data['name'] != entity.name:
                    # 检查新名称是否已存在
                    existing = session.query(self.entity_class).filter(
                        self.entity_class.name == update_data['name'],
                        self.entity_class.id != id
                    ).first()

                    if existing:
                        raise ValueError(f"测试套件名称已存在: {update_data['name']}")

                for key, value in update_data.items():
                    if hasattr(entity, key) and key != 'id':
                        setattr(entity, key, value)

                # 验证更新后的套件
                errors = entity.validate_suite()
                if errors:
                    session.rollback()
                    raise ValueError(f"更新后套件验证失败: {', '.join(errors)}")

                return entity
            return None

    def delete(self, id, soft_delete=True):
        """删除测试套件（支持软删除）"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

            if entity:
                if soft_delete:
                    # 软删除：标记为未激活
                    entity.status = 'inactive'
                else:
                    # 硬删除
                    session.delete(entity)
                return True
            return False

    # 特定查询方法
    def get_by_type(self, suite_type, active_only=True):
        """获取指定类型的测试套件"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.suite_type == suite_type
            )

            if active_only:
                query = query.filter(self.entity_class.status == 'active')

            return query.order_by(
                self.entity_class.module,
                self.entity_class.name
            ).all()

    def get_by_module(self, module, active_only=True):
        """获取指定模块的测试套件"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.module == module
            )

            if active_only:
                query = query.filter(self.entity_class.status == 'active')

            return query.order_by(
                self.entity_class.suite_type,
                self.entity_class.name
            ).all()

    def get_by_tag(self, tag, active_only=True):
        """获取包含指定标签的测试套件"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.tags.contains([tag])
            )

            if active_only:
                query = query.filter(self.entity_class.status == 'active')

            return query.order_by(
                self.entity_class.module,
                self.entity_class.name
            ).all()

    def get_active_suites(self):
        """获取所有激活的测试套件"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.status == 'active'
            ).order_by(
                self.entity_class.module,
                self.entity_class.name
            ).all()

    def get_suites_with_tag(self, tag, active_only=True):
        """获取包含指定标签的套件"""
        return self.get_by_tag(tag, active_only)

    def search_suites(self, keyword=None, suite_type=None, module=None,
                      tags=None, active_only=True):
        """搜索测试套件"""
        with self.session_scope() as session:
            query = session.query(self.entity_class)

            if active_only:
                query = query.filter(self.entity_class.status == 'active')

            if keyword:
                query = query.filter(or_(
                    self.entity_class.name.ilike(f'%{keyword}%'),
                    self.entity_class.description.ilike(f'%{keyword}%')
                ))

            if suite_type:
                query = query.filter(self.entity_class.suite_type == suite_type)

            if module:
                query = query.filter(self.entity_class.module == module)

            # 标签过滤
            if tags and isinstance(tags, list):
                for tag in tags:
                    query = query.filter(
                        self.entity_class.tags.contains([tag])
                    )

            return query.order_by(
                self.entity_class.module,
                self.entity_class.suite_type,
                self.entity_class.name
            ).all()

    def get_suite_statistics(self):
        """获取测试套件统计信息"""
        with self.session_scope() as session:
            # 按类型统计
            type_stats = session.query(
                self.entity_class.suite_type,
                func.count(self.entity_class.id)
            ).filter(
                self.entity_class.status == 'active'
            ).group_by(
                self.entity_class.suite_type
            ).all()

            # 按模块统计
            module_stats = session.query(
                self.entity_class.module,
                func.count(self.entity_class.id)
            ).filter(
                self.entity_class.status == 'active'
            ).group_by(
                self.entity_class.module
            ).all()

            # 标签统计
            tag_stats = {}
            suites = session.query(self.entity_class).filter(
                self.entity_class.status == 'active'
            ).all()

            for suite in suites:
                tags = suite.get_tags()
                for tag in tags:
                    if tag not in tag_stats:
                        tag_stats[tag] = 0
                    tag_stats[tag] += 1

            return {
                'by_type': {row[0]: row[1] for row in type_stats},
                'by_module': {row[0]: row[1] for row in module_stats},
                'by_tag': tag_stats,
                'total_active': session.query(self.entity_class).filter(
                    self.entity_class.status == 'active'
                ).count(),
                'total_inactive': session.query(self.entity_class).filter(
                    self.entity_class.status == 'inactive'
                ).count()
            }

    def get_module_coverage(self):
        """获取模块覆盖率统计"""
        with self.session_scope() as session:
            # 获取所有模块
            all_modules = session.query(
                self.entity_class.module.distinct()
            ).filter(
                self.entity_class.status == 'active'
            ).all()

            module_stats = []
            for module_row in all_modules:
                module = module_row[0]
                if not module:
                    continue

                suite_count = session.query(self.entity_class).filter(
                    self.entity_class.module == module,
                    self.entity_class.status == 'active'
                ).count()

                # 按类型统计
                type_counts = session.query(
                    self.entity_class.suite_type,
                    func.count(self.entity_class.id)
                ).filter(
                    self.entity_class.module == module,
                    self.entity_class.status == 'active'
                ).group_by(
                    self.entity_class.suite_type
                ).all()

                module_stats.append({
                    'module': module,
                    'suite_count': suite_count,
                    'by_type': {row[0]: row[1] for row in type_counts},
                    'coverage_score': self._calculate_coverage_score(suite_count)
                })

            return sorted(module_stats, key=lambda x: x['suite_count'], reverse=True)

    def _calculate_coverage_score(self, suite_count):
        """计算覆盖率分数（基于套件数量）"""
        if suite_count >= 5:
            return 100
        elif suite_count >= 3:
            return 80
        elif suite_count >= 1:
            return 60
        else:
            return 0

    def get_recently_created(self, days=7):
        """获取最近创建的测试套件"""
        cutoff_date = datetime.now() - timedelta(days=days)

        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.created_time >= cutoff_date
            ).order_by(
                desc(self.entity_class.created_time)
            ).all()

    def get_recently_updated(self, days=7):
        """获取最近更新的测试套件"""
        cutoff_date = datetime.now() - timedelta(days=days)

        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.updated_time >= cutoff_date
            ).order_by(
                desc(self.entity_class.updated_time)
            ).all()

    # 批量操作方法
    def bulk_update_status(self, suite_ids, new_status):
        """批量更新套件状态"""
        with self.session_scope() as session:
            updated_count = session.query(self.entity_class).filter(
                self.entity_class.id.in_(suite_ids)
            ).update({
                'status': new_status
            }, synchronize_session=False)

            return updated_count

    def bulk_activate(self, suite_ids):
        """批量激活套件"""
        return self.bulk_update_status(suite_ids, 'active')

    def bulk_deactivate(self, suite_ids):
        """批量停用套件"""
        return self.bulk_update_status(suite_ids, 'inactive')

    def bulk_add_tags(self, suite_ids, tags):
        """批量添加标签"""
        if not isinstance(tags, list):
            tags = [tags]

        with self.session_scope() as session:
            suites = session.query(self.entity_class).filter(
                self.entity_class.id.in_(suite_ids)
            ).all()

            updated_count = 0
            for suite in suites:
                for tag in tags:
                    if tag not in suite.get_tags():
                        suite.add_tag(tag)
                        updated_count += 1

            return updated_count

    def bulk_remove_tags(self, suite_ids, tags):
        """批量移除标签"""
        if not isinstance(tags, list):
            tags = [tags]

        with self.session_scope() as session:
            suites = session.query(self.entity_class).filter(
                self.entity_class.id.in_(suite_ids)
            ).all()

            updated_count = 0
            for suite in suites:
                for tag in tags:
                    if tag in suite.get_tags():
                        suite.remove_tag(tag)
                        updated_count += 1

            return updated_count

    def bulk_update_module(self, suite_ids, new_module):
        """批量更新模块"""
        with self.session_scope() as session:
            updated_count = session.query(self.entity_class).filter(
                self.entity_class.id.in_(suite_ids)
            ).update({
                'module': new_module
            }, synchronize_session=False)

            return updated_count

    def duplicate_suite(self, original_id, new_name, new_creator, description=None):
        """复制测试套件"""
        original = self.get_by_id(original_id)
        if not original:
            raise ValueError(f"源测试套件不存在: {original_id}")

        duplicate = original.duplicate(new_name, new_creator, description)
        return self.create(duplicate)

    def get_suites_for_execution(self, suite_type=None, module=None, tags=None):
        """获取适合执行的测试套件"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.status == 'active'
            )

            if suite_type:
                query = query.filter(self.entity_class.suite_type == suite_type)

            if module:
                query = query.filter(self.entity_class.module == module)

            if tags:
                for tag in tags:
                    query = query.filter(
                        self.entity_class.tags.contains([tag])
                    )

            return query.order_by(
                self.entity_class.suite_type,
                self.entity_class.module,
                self.entity_class.name
            ).all()

    def get_suite_hierarchy(self):
        """获取套件层次结构（按模块和类型分组）"""
        with self.session_scope() as session:
            # 按模块和类型分组
            results = session.query(
                self.entity_class.module,
                self.entity_class.suite_type,
                func.count(self.entity_class.id).label('suite_count')
            ).filter(
                self.entity_class.status == 'active'
            ).group_by(
                self.entity_class.module,
                self.entity_class.suite_type
            ).order_by(
                self.entity_class.module,
                self.entity_class.suite_type
            ).all()

            hierarchy = {}
            for row in results:
                module = row.module or '未分类'
                suite_type = row.suite_type
                count = row.suite_count

                if module not in hierarchy:
                    hierarchy[module] = {}

                hierarchy[module][suite_type] = count

            return hierarchy

    def export_suites_to_json(self, suite_ids=None, include_config=True):
        """导出测试套件为JSON"""
        with self.session_scope() as session:
            if suite_ids:
                suites = session.query(self.entity_class).filter(
                    self.entity_class.id.in_(suite_ids)
                ).all()
            else:
                suites = self.get_all(active_only=True)

            export_data = []
            for suite in suites:
                suite_data = suite.to_json()

                if not include_config:
                    # 移除配置信息
                    if 'config' in suite_data:
                        suite_data['config'] = {'exported': True}

                export_data.append(suite_data)

        return json.dumps(export_data, indent=2, ensure_ascii=False)

    def import_suites_from_json(self, json_data, creator):
        """从JSON导入测试套件"""
        if isinstance(json_data, str):
            data = json.loads(json_data)
        else:
            data = json_data

        imported_count = 0
        errors = []

        for suite_data in data:
            try:
                # 检查是否已存在
                existing = self.get_by_name(suite_data['name'])

                if existing:
                    # 如果已存在，更新
                    suite_data['creator'] = creator
                    self.update(existing.id, suite_data)
                else:
                    # 创建新套件
                    suite = TestSuite(**suite_data)
                    suite.creator = creator
                    self.create(suite)

                imported_count += 1
            except Exception as e:
                errors.append(f"导入套件 '{suite_data.get('name', 'unknown')}' 失败: {str(e)}")

        return {
            'imported_count': imported_count,
            'total_count': len(data),
            'errors': errors
        }

    def cleanup_unused_suites(self, days_threshold=365):
        """清理长期未使用的套件"""
        cutoff_date = datetime.now() - timedelta(days=days_threshold)

        with self.session_scope() as session:
            # 查找长期未更新的非活跃套件
            unused_suites = session.query(self.entity_class).filter(
                self.entity_class.status == 'inactive',
                self.entity_class.updated_time < cutoff_date
            ).all()

            deleted_count = 0
            for suite in unused_suites:
                # 检查是否有计划或执行关联（这里需要关联其他表）
                # 如果没有关联，可以安全删除
                can_delete = self._can_safely_delete(suite.id)

                if can_delete:
                    session.delete(suite)
                    deleted_count += 1

            return deleted_count

    def _can_safely_delete(self, suite_id):
        """检查套件是否可以安全删除（没有关联的计划或执行）"""
        # 这里需要查询test_plan和test_execution表来检查关联
        # 简化实现，假设可以删除
        return True

    def get_suite_recommendations(self, module, suite_type=None):
        """获取套件推荐（基于模块和类型）"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.module == module,
                self.entity_class.status == 'active'
            )

            if suite_type:
                query = query.filter(self.entity_class.suite_type == suite_type)

            similar_suites = query.order_by(
                desc(self.entity_class.updated_time)
            ).limit(5).all()

            recommendations = []
            for suite in similar_suites:
                recommendations.append({
                    'id': suite.id,
                    'name': suite.name,
                    'type': suite.suite_type,
                    'description': suite.description,
                    'tags': suite.get_tags(),
                    'similarity_score': self._calculate_similarity_score(suite, module, suite_type)
                })

            return sorted(recommendations, key=lambda x: x['similarity_score'], reverse=True)

    def _calculate_similarity_score(self, suite, target_module, target_type):
        """计算相似度分数"""
        score = 0

        # 模块匹配
        if suite.module == target_module:
            score += 50

        # 类型匹配
        if target_type and suite.suite_type == target_type:
            score += 30

        # 标签匹配（如果有共同标签）
        # 这里可以添加更复杂的相似度计算逻辑

        return score