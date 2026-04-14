# common/db_entity/test_suite.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, Enum, DateTime, Numeric
from sqlalchemy.dialects.mysql import JSON
from datetime import datetime
import enum
import json

# 生成ORM基类
Base = declarative_base()


class SuiteType(enum.Enum):
    """测试套件类型枚举"""
    SMOKE = "smoke"  # 冒烟测试
    REGRESSION = "regression"  # 回归测试
    FUNCTION = "function"  # 功能测试
    PERFORMANCE = "performance"  # 性能测试
    CUSTOM = "custom"  # 自定义


class SuiteStatus(enum.Enum):
    """测试套件状态枚举"""
    ACTIVE = "active"  # 激活
    INACTIVE = "inactive"  # 未激活


class ExecutionStatus(enum.Enum):
    """执行状态枚举"""
    NOT_RUN = "not_run"  # 未执行
    RUNNING = "running"  # 执行中
    PASSED = "passed"  # 通过
    FAILED = "failed"  # 失败
    STOPPED = "stopped"  # 停止


class TestSuite(Base):
    """测试套件表实体类"""
    __tablename__ = 'crosstest_test_suite'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')

    # 基础信息
    name = Column(String(200), nullable=False, unique=True, comment='套件名称')
    description = Column(String(1000), comment='套件描述')

    # 分类信息
    suite_type = Column(
        Enum('smoke', 'regression', 'function', 'performance', 'custom'),
        nullable=False,
        default='custom',
        comment='套件类型: smoke-冒烟, regression-回归, function-功能, performance-性能, custom-自定义'
    )
    module = Column(String(100), comment='所属模块')

    # 配置信息
    tags = Column(JSON, comment='标签数组')
    config = Column(JSON, comment='套件配置')

    # ===== 新增: 执行状态字段 =====
    last_execution_status = Column(
        Enum('not_run', 'running', 'passed', 'failed', 'stopped'),
        nullable=False,
        default='not_run',
        comment='最近一次执行状态: not_run-未执行, running-执行中, passed-通过, failed-失败, stopped-停止'
    )
    last_execution_time = Column(DateTime, nullable=True, comment='最近一次执行时间')
    last_execution_id = Column(String(50), nullable=True, comment='最近一次执行的执行ID')
    total_executions = Column(Integer, nullable=False, default=0, comment='累计执行次数')
    success_rate = Column(Numeric(5, 2), nullable=False, default=0.00, comment='累计成功率(%)')

    # ===== 新增: 套件级默认请求配置 =====
    # 说明: 这些配置会被套件下所有用例继承（如果用例没有单独配置）
    case_default_config = Column(JSON, nullable=True, comment='套件下所有用例的默认请求配置(headers/params/body等)')

    # 状态管理
    status = Column(
        Enum('active', 'inactive'),
        nullable=False,
        default='active',
        comment='状态: active-激活, inactive-未激活'
    )

    # 审计字段
    creator = Column(String(50), nullable=False, comment='创建人')
    created_time = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    def __repr__(self):
        return f"<TestSuite(name='{self.name}', type='{self.suite_type}', module='{self.module}')>"

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

    def get_config_value(self, key, default=None):
        """获取配置值"""
        if self.config and isinstance(self.config, dict):
            return self.config.get(key, default)
        return default

    def set_config_value(self, key, value):
        """设置配置值"""
        if not self.config:
            self.config = {}

        if isinstance(self.config, dict):
            self.config[key] = value
        else:
            # 如果config不是字典，尝试转换
            try:
                config_dict = json.loads(self.config) if isinstance(self.config, str) else {}
                config_dict[key] = value
                self.config = config_dict
            except:
                self.config = {key: value}

    def get_tags(self):
        """获取标签列表"""
        if isinstance(self.tags, list):
            return self.tags
        elif isinstance(self.tags, str):
            try:
                return json.loads(self.tags)
            except:
                return []
        return []

    def add_tag(self, tag):
        """添加标签"""
        tags = self.get_tags()
        if tag not in tags:
            tags.append(tag)
            self.tags = tags

    def remove_tag(self, tag):
        """移除标签"""
        tags = self.get_tags()
        if tag in tags:
            tags.remove(tag)
            self.tags = tags

    def has_tag(self, tag):
        """检查是否包含标签"""
        return tag in self.get_tags()

    def is_active(self):
        """检查套件是否激活"""
        return self.status == 'active'

    def activate(self):
        """激活套件"""
        self.status = 'active'

    def deactivate(self):
        """停用套件"""
        self.status = 'inactive'

    def validate_suite(self):
        """验证套件完整性"""
        errors = []

        if not self.name:
            errors.append("套件名称不能为空")

        if len(self.name) > 200:
            errors.append("套件名称长度不能超过200个字符")

        if self.description and len(self.description) > 1000:
            errors.append("套件描述长度不能超过1000个字符")

        if self.module and len(self.module) > 100:
            errors.append("模块名称长度不能超过100个字符")

        # 验证配置格式
        if self.config and not isinstance(self.config, (dict, list)):
            try:
                json.loads(self.config)
            except:
                errors.append("套件配置必须是有效的JSON格式")

        return errors

    def get_default_config(self):
        """获取默认配置（根据套件类型）"""
        default_configs = {
            'smoke': {
                'priority': 'high',
                'timeout': 1800,  # 30分钟
                'stop_on_failure': True,
                'notify_on_failure': True,
                'max_retries': 0
            },
            'regression': {
                'priority': 'medium',
                'timeout': 7200,  # 2小时
                'stop_on_failure': False,
                'notify_on_completion': True,
                'max_retries': 1,
                'parallel_execution': True
            },
            'function': {
                'priority': 'medium',
                'timeout': 3600,  # 1小时
                'stop_on_failure': False,
                'max_retries': 1
            },
            'performance': {
                'priority': 'low',
                'timeout': 10800,  # 3小时
                'collect_metrics': True,
                'performance_thresholds': {}
            },
            'custom': {
                'priority': 'medium',
                'timeout': 3600,
                'max_retries': 0
            }
        }

        return default_configs.get(self.suite_type, {})

    def apply_default_config(self):
        """应用默认配置"""
        if not self.config:
            self.config = self.get_default_config()
        else:
            # 合并默认配置
            default_config = self.get_default_config()
            for key, value in default_config.items():
                if key not in self.config:
                    self.config[key] = value

    @classmethod
    def create_smoke_suite(cls, name, module, creator, description=None):
        """创建冒烟测试套件"""
        return cls(
            name=name,
            description=description or f"{module}模块冒烟测试套件",
            suite_type='smoke',
            module=module,
            creator=creator,
            config=cls._get_smoke_config()
        )

    @classmethod
    def create_regression_suite(cls, name, module, creator, description=None):
        """创建回归测试套件"""
        return cls(
            name=name,
            description=description or f"{module}模块回归测试套件",
            suite_type='regression',
            module=module,
            creator=creator,
            config=cls._get_regression_config()
        )

    @classmethod
    def create_function_suite(cls, name, module, creator, description=None):
        """创建功能测试套件"""
        return cls(
            name=name,
            description=description or f"{module}模块功能测试套件",
            suite_type='function',
            module=module,
            creator=creator,
            config=cls._get_function_config()
        )

    @classmethod
    def create_performance_suite(cls, name, module, creator, description=None):
        """创建性能测试套件"""
        return cls(
            name=name,
            description=description or f"{module}模块性能测试套件",
            suite_type='performance',
            module=module,
            creator=creator,
            config=cls._get_performance_config()
        )

    @classmethod
    def create_custom_suite(cls, name, module, creator, description=None, config=None):
        """创建自定义套件"""
        return cls(
            name=name,
            description=description or f"{module}模块自定义测试套件",
            suite_type='custom',
            module=module,
            creator=creator,
            config=config or {}
        )

    @classmethod
    def _get_smoke_config(cls):
        """获取冒烟测试配置"""
        return {
            'priority': 'high',
            'timeout': 1800,  # 30分钟
            'stop_on_failure': True,
            'notify_on_failure': True,
            'max_retries': 0,
            'case_selection': 'critical',
            'execution_order': 'priority'
        }

    @classmethod
    def _get_regression_config(cls):
        """获取回归测试配置"""
        return {
            'priority': 'medium',
            'timeout': 7200,  # 2小时
            'stop_on_failure': False,
            'notify_on_completion': True,
            'max_retries': 1,
            'parallel_execution': True,
            'case_selection': 'all',
            'execution_order': 'module'
        }

    @classmethod
    def _get_function_config(cls):
        """获取功能测试配置"""
        return {
            'priority': 'medium',
            'timeout': 3600,  # 1小时
            'stop_on_failure': False,
            'max_retries': 1,
            'case_selection': 'functional',
            'execution_order': 'testcase'
        }

    @classmethod
    def _get_performance_config(cls):
        """获取性能测试配置"""
        return {
            'priority': 'low',
            'timeout': 10800,  # 3小时
            'collect_metrics': True,
            'performance_thresholds': {
                'response_time': 2000,  # 2秒
                'throughput': 100,  # 100请求/秒
                'error_rate': 0.01  # 1%错误率
            },
            'load_profile': {
                'users': 100,
                'ramp_up': 300,  # 5分钟
                'duration': 1800  # 30分钟
            }
        }

    def get_suite_icon(self):
        """获取套件类型图标（用于UI显示）"""
        icons = {
            'smoke': '🔥',
            'regression': '🔄',
            'function': '⚙️',
            'performance': '📈',
            'custom': '🔧'
        }
        return icons.get(self.suite_type, '📁')

    def get_suite_color(self):
        """获取套件类型颜色（用于UI显示）"""
        colors = {
            'smoke': '#ff6f3cd',  # 浅黄色
            'regression': '#d1ecf1',  # 浅蓝色
            'function': '#d4edda',  # 浅绿色
            'performance': '#e2e3e5',  # 浅灰色
            'custom': '#f8d7da'  # 浅红色
        }
        return colors.get(self.suite_type, '#ffffff')

    def can_be_executed(self):
        """检查套件是否可以执行"""
        return self.is_active()

    def get_estimated_duration(self, avg_case_duration=120):
        """估算套件执行时间（秒）"""
        # 基础时间 + 每个案例的平均时间
        # 实际实现需要从关联的案例中获取案例数量
        base_time = 300  # 5分钟基础时间
        estimated_cases = 10  # 假设平均10个案例
        return base_time + (estimated_cases * avg_case_duration)

    def duplicate(self, new_name, new_creator, description=None):
        """复制套件"""
        return TestSuite(
            name=new_name,
            description=description or f"{self.description} (副本)",
            suite_type=self.suite_type,
            module=self.module,
            tags=self.tags.copy() if self.tags else [],
            config=self.config.copy() if self.config else {},
            # 新增: 复制套件级默认配置
            case_default_config=self.case_default_config.copy() if self.case_default_config else None,
            # 新增: 复制套件的执行状态字段
            last_execution_status='not_run',
            total_executions=0,
            success_rate=0.00,
            status='active',
            creator=new_creator
        )

    # ===== 新增: 执行状态相关方法 =====

    def update_execution_status(self, status, execution_id=None, duration=None):
        """更新执行状态"""
        self.last_execution_status = status
        if execution_id:
            self.last_execution_id = execution_id
        if status in ['passed', 'failed', 'stopped']:
            self.last_execution_time = datetime.now()

    def increment_execution_count(self, passed_count, total_count):
        """更新执行统计"""
        self.total_executions = (self.total_executions or 0) + 1
        if total_count > 0:
            new_rate = (passed_count / total_count) * 100
            # 简单移动平均
            if self.success_rate is None or self.success_rate == 0:
                self.success_rate = new_rate
            else:
                self.success_rate = (self.success_rate + new_rate) / 2

    def get_execution_summary(self):
        """获取执行摘要"""
        return {
            'last_execution_status': self.last_execution_status,
            'last_execution_time': self.last_execution_time.isoformat() if self.last_execution_time else None,
            'last_execution_id': self.last_execution_id,
            'total_executions': self.total_executions or 0,
            'success_rate': float(self.success_rate or 0),
        }