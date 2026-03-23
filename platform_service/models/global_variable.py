# common/db_entity/global_variable.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, Enum, Boolean, DateTime
from sqlalchemy.dialects.mysql import JSON
from datetime import datetime
import enum
import json

# 生成ORM基类
Base = declarative_base()


class VariableType(enum.Enum):
    """变量类型枚举"""
    STATIC = "static"
    DYNAMIC = "dynamic"
    ENCRYPTED = "encrypted"


class VariableScope(enum.Enum):
    """变量作用域枚举"""
    GLOBAL = "global"
    ENVIRONMENT = "environment"
    MODULE = "module"


class GlobalVariable(Base):
    """全局变量表实体类"""
    __tablename__ = 'crosstest_global_variable'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')

    # 变量基本信息
    name = Column(String(100), nullable=False, comment='变量名')
    value = Column(Text, nullable=False, comment='变量值')
    description = Column(String(500), comment='变量描述')

    # 变量类型和作用域
    variable_type = Column(
        Enum('static', 'dynamic', 'encrypted'),
        nullable=False,
        default='static',
        comment='变量类型: static-静态, dynamic-动态, encrypted-加密'
    )
    scope = Column(
        Enum('global', 'environment', 'module'),
        nullable=False,
        default='global',
        comment='作用域: global-全局, environment-环境, module-模块'
    )
    scope_id = Column(Integer, comment='作用域ID(环境ID或模块ID)')

    # 状态管理
    is_active = Column(Boolean, default=True, comment='是否激活')

    # 审计字段
    created_by = Column(String(50), comment='创建人')
    created_time = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_by = Column(String(50), comment='更新人')
    updated_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    def __repr__(self):
        return f"<GlobalVariable(name='{self.name}', type='{self.variable_type}', scope='{self.scope}')>"

    def to_dict(self):
        """转换为字典"""
        result = {}
        for key, value in self.__dict__.items():
            if not key.startswith('_'):
                result[key] = value
        return result

    def to_json(self):
        """转换为JSON友好的字典"""
        result = self.to_dict()
        for key, value in result.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, enum.Enum):
                result[key] = value.value
        return result

    def get_typed_value(self):
        """获取类型化的值（尝试解析JSON或保持原样）"""
        if not self.value:
            return None

        # 如果是加密变量，需要特殊处理
        if self.variable_type == 'encrypted':
            return f"encrypted:{self.value[:10]}..."  # 不返回完整加密值

        # 尝试解析JSON
        try:
            return json.loads(self.value)
        except (json.JSONDecodeError, TypeError):
            # 如果不是JSON，返回原始字符串
            return self.value

    def set_typed_value(self, value):
        """设置类型化的值（自动序列化复杂对象）"""
        if isinstance(value, (dict, list)):
            self.value = json.dumps(value, ensure_ascii=False)
        else:
            self.value = str(value)

    def validate_variable(self):
        """验证变量完整性"""
        errors = []

        if not self.name:
            errors.append("变量名不能为空")

        if not self.name.replace('_', '').isalnum():
            errors.append("变量名只能包含字母、数字和下划线")

        if self.value is None:
            errors.append("变量值不能为空")

        # 作用域验证
        if self.scope in ['environment', 'module'] and not self.scope_id:
            errors.append(f"{self.scope}作用域的变量必须指定scope_id")

        if self.scope == 'global' and self.scope_id:
            errors.append("全局作用域的变量不应指定scope_id")

        return errors

    def is_encrypted(self):
        """检查是否为加密变量"""
        return self.variable_type == 'encrypted'

    def is_dynamic(self):
        """检查是否为动态变量"""
        return self.variable_type == 'dynamic'

    def get_scope_description(self):
        """获取作用域描述"""
        scope_descriptions = {
            'global': '全局',
            'environment': '环境级',
            'module': '模块级'
        }
        return scope_descriptions.get(self.scope, '未知')

    def get_full_name(self):
        """获取完整变量名（包含作用域信息）"""
        if self.scope == 'global':
            return f"global.{self.name}"
        elif self.scope_id:
            return f"{self.scope}.{self.scope_id}.{self.name}"
        else:
            return f"{self.scope}.{self.name}"

    @classmethod
    def create_global_variable(cls, name, value, description=None, variable_type='static'):
        """创建全局变量"""
        return cls(
            name=name,
            value=value,
            description=description,
            variable_type=variable_type,
            scope='global',
            scope_id=None
        )

    @classmethod
    def create_environment_variable(cls, name, value, environment_id, description=None, variable_type='static'):
        """创建环境级变量"""
        return cls(
            name=name,
            value=value,
            description=description,
            variable_type=variable_type,
            scope='environment',
            scope_id=environment_id
        )

    @classmethod
    def create_module_variable(cls, name, value, module_id, description=None, variable_type='static'):
        """创建模块级变量"""
        return cls(
            name=name,
            value=value,
            description=description,
            variable_type=variable_type,
            scope='module',
            scope_id=module_id
        )

    @classmethod
    def create_common_variables(cls):
        """创建常用系统变量模板"""
        common_vars = [
            # 时间相关变量
            cls.create_global_variable(
                'CURRENT_TIMESTAMP',
                '${__timestamp()}',
                '当前时间戳（动态生成）',
                'dynamic'
            ),
            cls.create_global_variable(
                'CURRENT_DATE',
                '${__date()}',
                '当前日期（动态生成）',
                'dynamic'
            ),
            cls.create_global_variable(
                'CURRENT_DATETIME',
                '${__datetime()}',
                '当前日期时间（动态生成）',
                'dynamic'
            ),

            # 测试数据相关
            cls.create_global_variable(
                'RANDOM_EMAIL',
                'test_${__random(1000,9999)}@example.com',
                '随机邮箱地址',
                'dynamic'
            ),
            cls.create_global_variable(
                'RANDOM_PHONE',
                '13${__random(100000000,999999999)}',
                '随机手机号',
                'dynamic'
            ),
            cls.create_global_variable(
                'RANDOM_ID',
                '${__random(10000,99999)}',
                '随机ID',
                'dynamic'
            ),

            # 系统配置
            cls.create_global_variable(
                'DEFAULT_TIMEOUT',
                '30',
                '默认超时时间（秒）',
                'static'
            ),
            cls.create_global_variable(
                'MAX_RETRY_TIMES',
                '3',
                '最大重试次数',
                'static'
            )
        ]

        return common_vars