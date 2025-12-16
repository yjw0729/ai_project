# common/db_mapper/global_variable_mapper.py
from sqlalchemy import or_, and_
from common.db_enitiy.global_variable import GlobalVariable
from contextlib import contextmanager
from common.datacase_function.contect_db import db_session
import json
import re


class GlobalVariableMapper:
    """GlobalVariable表的数据访问类"""

    def __init__(self):
        self.entity_class = GlobalVariable

    @contextmanager
    def session_scope(self):
        """提供数据库会话的上下文管理"""
        with db_session() as session:
            yield session

    # 基础CRUD操作
    def get_by_id(self, id):
        """根据ID获取变量"""
        with self.session_scope() as session:
            return session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

    def get_by_name(self, name, scope='global', scope_id=None):
        """根据名称和作用域获取变量"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.name == name,
                self.entity_class.scope == scope,
                self.entity_class.is_active == True
            )

            if scope_id is not None:
                query = query.filter(self.entity_class.scope_id == scope_id)
            else:
                query = query.filter(self.entity_class.scope_id.is_(None))

            return query.first()

    def get_all(self, active_only=True):
        """获取所有变量"""
        with self.session_scope() as session:
            query = session.query(self.entity_class)
            if active_only:
                query = query.filter(self.entity_class.is_active == True)
            return query.order_by(
                self.entity_class.scope,
                self.entity_class.scope_id,
                self.entity_class.name
            ).all()

    def create(self, entity):
        """创建新变量"""
        # 验证变量
        errors = entity.validate_variable()
        if errors:
            raise ValueError(f"变量验证失败: {', '.join(errors)}")

        # 检查变量名是否已存在（相同作用域）
        existing = self.get_by_name(entity.name, entity.scope, entity.scope_id)
        if existing:
            raise ValueError(f"变量名 '{entity.name}' 在作用域 '{entity.scope}' 中已存在")

        with self.session_scope() as session:
            session.add(entity)
            session.flush()
            session.refresh(entity)
            return entity

    def update(self, id, update_data):
        """更新变量"""
        with self.session_scope() as session:
            entity = session.query(self.entity_class).filter(
                self.entity_class.id == id
            ).first()

            if entity:
                # 检查是否修改了名称或作用域
                name_changed = 'name' in update_data and update_data['name'] != entity.name
                scope_changed = 'scope' in update_data and update_data['scope'] != entity.scope
                scope_id_changed = 'scope_id' in update_data and update_data['scope_id'] != entity.scope_id

                for key, value in update_data.items():
                    if hasattr(entity, key) and key != 'id':
                        setattr(entity, key, value)

                # 如果名称或作用域改变，检查唯一性约束
                if name_changed or scope_changed or scope_id_changed:
                    existing = self.get_by_name(entity.name, entity.scope, entity.scope_id)
                    if existing and existing.id != entity.id:
                        session.rollback()
                        raise ValueError(f"变量名 '{entity.name}' 在作用域 '{entity.scope}' 中已存在")

                # 验证更新后的变量
                errors = entity.validate_variable()
                if errors:
                    session.rollback()
                    raise ValueError(f"更新后变量验证失败: {', '.join(errors)}")

                return entity
            return None

    def delete(self, id, soft_delete=True):
        """删除变量（支持软删除）"""
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
    def get_by_scope(self, scope, scope_id=None, active_only=True):
        """获取指定作用域的变量"""
        with self.session_scope() as session:
            query = session.query(self.entity_class).filter(
                self.entity_class.scope == scope
            )

            if scope_id is not None:
                query = query.filter(self.entity_class.scope_id == scope_id)
            else:
                query = query.filter(self.entity_class.scope_id.is_(None))

            if active_only:
                query = query.filter(self.entity_class.is_active == True)

            return query.order_by(self.entity_class.name).all()

    def get_global_variables(self, active_only=True):
        """获取全局变量"""
        return self.get_by_scope('global', None, active_only)

    def get_environment_variables(self, environment_id, active_only=True):
        """获取环境级变量"""
        return self.get_by_scope('environment', environment_id, active_only)

    def get_module_variables(self, module_id, active_only=True):
        """获取模块级变量"""
        return self.get_by_scope('module', module_id, active_only)

    def search_variables(self, keyword=None, variable_type=None, scope=None, active_only=True):
        """搜索变量"""
        with self.session_scope() as session:
            query = session.query(self.entity_class)

            if active_only:
                query = query.filter(self.entity_class.is_active == True)

            if keyword:
                query = query.filter(or_(
                    self.entity_class.name.ilike(f'%{keyword}%'),
                    self.entity_class.description.ilike(f'%{keyword}%'),
                    self.entity_class.value.ilike(f'%{keyword}%')
                ))

            if variable_type:
                query = query.filter(self.entity_class.variable_type == variable_type)

            if scope:
                query = query.filter(self.entity_class.scope == scope)

            return query.order_by(
                self.entity_class.scope,
                self.entity_class.scope_id,
                self.entity_class.name
            ).all()

    def get_variables_dict(self, scope='global', scope_id=None, include_inactive=False):
        """获取变量字典（name: value）"""
        variables = self.get_by_scope(scope, scope_id, not include_inactive)
        return {var.name: var.get_typed_value() for var in variables}

    def get_all_variables_dict(self, environment_id=None, module_id=None):
        """获取所有相关变量的合并字典（优先级：模块 > 环境 > 全局）"""
        variables = {}

        # 1. 全局变量（最低优先级）
        global_vars = self.get_global_variables()
        for var in global_vars:
            variables[var.name] = var.get_typed_value()

        # 2. 环境变量（中优先级）
        if environment_id:
            env_vars = self.get_environment_variables(environment_id)
            for var in env_vars:
                variables[var.name] = var.get_typed_value()

        # 3. 模块变量（最高优先级）
        if module_id:
            module_vars = self.get_module_variables(module_id)
            for var in module_vars:
                variables[var.name] = var.get_typed_value()

        return variables

    def get_variable_stats(self):
        """获取变量统计信息"""
        with self.session_scope() as session:
            # 按作用域统计
            scope_stats = session.query(
                self.entity_class.scope,
                self.entity_class.id
            ).filter(
                self.entity_class.is_active == True
            ).group_by(
                self.entity_class.scope
            ).all()

            # 按类型统计
            type_stats = session.query(
                self.entity_class.variable_type,
                self.entity_class.id
            ).filter(
                self.entity_class.is_active == True
            ).group_by(
                self.entity_class.variable_type
            ).all()

            return {
                'by_scope': {row.scope: row[1] for row in scope_stats},
                'by_type': {row.variable_type: row[1] for row in type_stats},
                'total_active': session.query(self.entity_class).filter(
                    self.entity_class.is_active == True
                ).count()
            }

    def bulk_create_variables(self, variables_data):
        """批量创建变量"""
        created_count = 0
        errors = []

        for var_data in variables_data:
            try:
                variable = GlobalVariable(**var_data)
                self.create(variable)
                created_count += 1
            except Exception as e:
                errors.append(f"创建变量 '{var_data.get('name', 'unknown')}' 失败: {str(e)}")

        return {
            'created_count': created_count,
            'total_count': len(variables_data),
            'errors': errors
        }

    def import_variables_from_json(self, json_data, scope='global', scope_id=None):
        """从JSON导入变量"""
        if isinstance(json_data, str):
            data = json.loads(json_data)
        else:
            data = json_data

        variables_data = []
        for var_name, var_value in data.items():
            variables_data.append({
                'name': var_name,
                'value': str(var_value),
                'scope': scope,
                'scope_id': scope_id,
                'variable_type': 'static'
            })

        return self.bulk_create_variables(variables_data)

    def export_variables_to_json(self, scope='global', scope_id=None):
        """导出变量为JSON"""
        variables = self.get_by_scope(scope, scope_id)
        result = {}

        for var in variables:
            result[var.name] = var.get_typed_value()

        return json.dumps(result, indent=2, ensure_ascii=False)

    def find_variable_usage(self, variable_name, scope='global', scope_id=None):
        """查找变量使用情况（在哪些其他变量值中被引用）"""
        target_var = self.get_by_name(variable_name, scope, scope_id)
        if not target_var:
            return []

        usage_pattern = f"${{{variable_name}}}"
        all_variables = self.get_all(active_only=True)

        usage_list = []
        for var in all_variables:
            if var.value and usage_pattern in var.value:
                usage_list.append({
                    'variable': var.name,
                    'scope': var.scope,
                    'scope_id': var.scope_id,
                    'value_snippet': var.value
                })

        return usage_list

    def resolve_variable_references(self, variable_value, context_variables=None):
        """解析变量引用（支持嵌套引用）"""
        if not variable_value or not isinstance(variable_value, str):
            return variable_value

        if context_variables is None:
            context_variables = self.get_all_variables_dict()

        # 匹配 ${variable_name} 模式
        pattern = r'\$\{([^}]+)\}'

        def replace_match(match):
            var_name = match.group(1)
            # 检查是否有默认值语法：${var_name:default_value}
            if ':' in var_name:
                var_name, default_value = var_name.split(':', 1)
            else:
                default_value = None

            # 查找变量值
            if var_name in context_variables:
                return str(context_variables[var_name])
            elif default_value is not None:
                return default_value
            else:
                # 未找到变量，保持原样（可能是动态函数）
                return match.group(0)

        # 多次解析以处理嵌套引用
        max_iterations = 10
        for _ in range(max_iterations):
            new_value = re.sub(pattern, replace_match, variable_value)
            if new_value == variable_value:
                break  # 没有更多引用需要解析
            variable_value = new_value

        return variable_value

    def evaluate_dynamic_variable(self, variable_name, context_variables=None):
        """评估动态变量值"""
        variable = self.get_by_name(variable_name, 'global')
        if not variable or not variable.is_dynamic():
            return None

        if context_variables is None:
            context_variables = self.get_all_variables_dict()

        # 解析变量引用
        resolved_value = self.resolve_variable_references(variable.value, context_variables)

        # 这里可以添加更复杂的动态函数处理
        # 例如：${__timestamp()}, ${__random(min,max)}, ${__date()}, 等

        return resolved_value

    def duplicate_variables(self, source_scope, source_scope_id, target_scope, target_scope_id):
        """复制变量到新的作用域"""
        source_vars = self.get_by_scope(source_scope, source_scope_id)
        created_count = 0

        for source_var in source_vars:
            try:
                # 创建副本
                duplicate = GlobalVariable(
                    name=source_var.name,
                    value=source_var.value,
                    description=f"{source_var.description} (复制自 {source_scope})",
                    variable_type=source_var.variable_type,
                    scope=target_scope,
                    scope_id=target_scope_id,
                    is_active=source_var.is_active,
                    created_by=source_var.created_by
                )

                self.create(duplicate)
                created_count += 1
            except Exception as e:
                # 如果变量已存在，跳过
                if "已存在" not in str(e):
                    raise e

        return created_count