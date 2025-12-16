# common/db_entity/test_plan.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, Enum, DateTime, ForeignKey
from sqlalchemy.dialects.mysql import JSON
from datetime import datetime
import enum
import json

# 生成ORM基类
Base = declarative_base()


class PlanType(enum.Enum):
    """测试计划类型枚举"""
    MANUAL = "manual"  # 手动执行
    SCHEDULED = "scheduled"  # 定时执行
    CI_CD = "ci_cd"  # CI/CD集成


class PlanStatus(enum.Enum):
    """测试计划状态枚举"""
    PENDING = "pending"  # 待执行
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 已失败
    CANCELLED = "cancelled"  # 已取消


class TestPlan(Base):
    """测试计划表实体类"""
    __tablename__ = 'test_plan'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')

    # 基础信息
    name = Column(String(200), nullable=False, comment='计划名称')
    description = Column(String(1000), comment='计划描述')

    # 计划类型
    plan_type = Column(
        Enum('manual', 'scheduled', 'ci_cd'),
        nullable=False,
        default='manual',
        comment='计划类型: manual-手动, scheduled-定时, ci_cd-持续集成'
    )

    # 环境配置
    environment_id = Column(Integer, nullable=False, comment='环境ID')

    # 包含的套件
    suites = Column(JSON, nullable=False, comment='包含的套件ID数组')

    # 配置信息
    config = Column(JSON, nullable=False, comment='计划配置')
    schedule_config = Column(JSON, comment='调度配置(用于定时任务)')

    # 状态管理
    status = Column(
        Enum('pending', 'running', 'completed', 'failed', 'cancelled'),
        nullable=False,
        default='pending',
        comment='状态: pending-待执行, running-执行中, completed-已完成, failed-已失败, cancelled-已取消'
    )

    # 执行信息
    creator = Column(String(50), nullable=False, comment='创建人')
    scheduled_time = Column(DateTime, comment='计划执行时间')
    start_time = Column(DateTime, comment='实际开始时间')
    end_time = Column(DateTime, comment='实际结束时间')

    # 审计字段
    created_time = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    def __repr__(self):
        return f"<TestPlan(name='{self.name}', type='{self.plan_type}', status='{self.status}')>"

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

    def get_schedule_config(self, key, default=None):
        """获取调度配置值"""
        if self.schedule_config and isinstance(self.schedule_config, dict):
            return self.schedule_config.get(key, default)
        return default

    def set_schedule_config(self, key, value):
        """设置调度配置值"""
        if not self.schedule_config:
            self.schedule_config = {}

        if isinstance(self.schedule_config, dict):
            self.schedule_config[key] = value
        else:
            try:
                schedule_dict = json.loads(self.schedule_config) if isinstance(self.schedule_config, str) else {}
                schedule_dict[key] = value
                self.schedule_config = schedule_dict
            except:
                self.schedule_config = {key: value}

    def get_suite_ids(self):
        """获取套件ID列表"""
        if isinstance(self.suites, list):
            return self.suites
        elif isinstance(self.suites, str):
            try:
                return json.loads(self.suites)
            except:
                return []
        return []

    def add_suite(self, suite_id):
        """添加套件ID"""
        suite_ids = self.get_suite_ids()
        if suite_id not in suite_ids:
            suite_ids.append(suite_id)
            self.suites = suite_ids

    def remove_suite(self, suite_id):
        """移除套件ID"""
        suite_ids = self.get_suite_ids()
        if suite_id in suite_ids:
            suite_ids.remove(suite_id)
            self.suites = suite_ids

    def has_suite(self, suite_id):
        """检查是否包含套件"""
        return suite_id in self.get_suite_ids()

    def calculate_estimated_duration(self, case_count, avg_case_duration=120):
        """估算计划执行时间（秒）"""
        # 基础时间 + 每个案例的平均时间
        base_time = 300  # 5分钟基础时间
        return base_time + (case_count * avg_case_duration)

    def get_estimated_case_count(self):
        """估算包含的案例数量（需要从套件中获取）"""
        # 这里需要从套件关联的案例中获取，实际实现需要查询数据库
        return len(self.get_suite_ids()) * 10  # 假设每个套件平均10个案例

    def can_start(self):
        """检查计划是否可以开始执行"""
        return self.status in ['pending', 'failed']

    def can_cancel(self):
        """检查计划是否可以取消"""
        return self.status in ['pending', 'running']

    def can_retry(self):
        """检查计划是否可以重试"""
        return self.status in ['failed', 'cancelled']

    def start_execution(self):
        """开始执行计划"""
        if not self.can_start():
            raise ValueError(f"计划当前状态为 {self.status}，无法开始执行")

        self.status = 'running'
        self.start_time = datetime.now()

        # 清除之前的结束时间（如果是重试）
        self.end_time = None

    def complete_execution(self, success=True):
        """完成计划执行"""
        if self.status != 'running':
            raise ValueError(f"计划当前状态为 {self.status}，无法完成执行")

        self.status = 'completed' if success else 'failed'
        self.end_time = datetime.now()

    def cancel_execution(self, reason=None):
        """取消计划执行"""
        if not self.can_cancel():
            raise ValueError(f"计划当前状态为 {self.status}，无法取消")

        self.status = 'cancelled'
        self.end_time = datetime.now()

        # 记录取消原因
        if reason:
            self.set_config_value('cancellation_reason', reason)

    def retry_execution(self):
        """重试计划执行"""
        if not self.can_retry():
            raise ValueError(f"计划当前状态为 {self.status}，无法重试")

        self.status = 'pending'
        self.start_time = None
        self.end_time = None

        # 增加重试计数
        retry_count = self.get_config_value('retry_count', 0)
        self.set_config_value('retry_count', retry_count + 1)

    def is_overdue(self):
        """检查计划是否已过期（超过预定执行时间）"""
        if self.scheduled_time and self.status == 'pending':
            return datetime.now() > self.scheduled_time
        return False

    def get_duration(self):
        """获取执行持续时间（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        elif self.start_time and not self.end_time:
            return (datetime.now() - self.start_time).total_seconds()
        return 0

    def validate_plan(self):
        """验证计划完整性"""
        errors = []

        if not self.name:
            errors.append("计划名称不能为空")

        if not self.environment_id:
            errors.append("必须指定执行环境")

        suite_ids = self.get_suite_ids()
        if not suite_ids:
            errors.append("必须包含至少一个测试套件")

        if self.scheduled_time and self.scheduled_time < datetime.now():
            errors.append("计划执行时间不能早于当前时间")

        # 验证配置格式
        if self.config and not isinstance(self.config, (dict, list)):
            try:
                json.loads(self.config)
            except:
                errors.append("计划配置必须是有效的JSON格式")

        if self.schedule_config and not isinstance(self.schedule_config, (dict, list)):
            try:
                json.loads(self.schedule_config)
            except:
                errors.append("调度配置必须是有效的JSON格式")

        return errors

    @classmethod
    def create_manual_plan(cls, name, environment_id, suite_ids, creator, description=None, config=None):
        """创建手动执行计划"""
        return cls(
            name=name,
            description=description or f"{name}手动测试计划",
            plan_type='manual',
            environment_id=environment_id,
            suites=suite_ids,
            config=config or {},
            status='pending',
            creator=creator
        )

    @classmethod
    def create_scheduled_plan(cls, name, environment_id, suite_ids, schedule_config,
                              creator, description=None, config=None):
        """创建定时执行计划"""
        plan = cls.create_manual_plan(name, environment_id, suite_ids, creator, description, config)
        plan.plan_type = 'scheduled'
        plan.schedule_config = schedule_config
        plan.scheduled_time = schedule_config.get('next_run_time')
        return plan

    @classmethod
    def create_ci_cd_plan(cls, name, environment_id, suite_ids, ci_config,
                          creator, description=None, config=None):
        """创建CI/CD集成计划"""
        plan = cls.create_manual_plan(name, environment_id, suite_ids, creator, description, config)
        plan.plan_type = 'ci_cd'
        plan.config = {**(config or {}), 'ci_cd': ci_config}
        return plan

    @classmethod
    def create_smoke_test_plan(cls, environment_id, suite_ids, creator):
        """创建冒烟测试计划模板"""
        return cls.create_manual_plan(
            name="冒烟测试计划",
            environment_id=environment_id,
            suite_ids=suite_ids,
            creator=creator,
            description="冒烟测试验证核心功能",
            config={
                'priority': 'high',
                'timeout': 3600,  # 1小时
                'notify_on_failure': True,
                'stop_on_failure': True,
                'max_retries': 0
            }
        )

    @classmethod
    def create_regression_test_plan(cls, environment_id, suite_ids, creator):
        """创建回归测试计划模板"""
        return cls.create_manual_plan(
            name="回归测试计划",
            environment_id=environment_id,
            suite_ids=suite_ids,
            creator=creator,
            description="全面回归测试",
            config={
                'priority': 'medium',
                'timeout': 7200,  # 2小时
                'notify_on_completion': True,
                'parallel_execution': True,
                'max_workers': 5
            }
        )

    @classmethod
    def create_performance_test_plan(cls, environment_id, suite_ids, creator):
        """创建性能测试计划模板"""
        return cls.create_manual_plan(
            name="性能测试计划",
            environment_id=environment_id,
            suite_ids=suite_ids,
            creator=creator,
            description="系统性能测试",
            config={
                'priority': 'high',
                'timeout': 10800,  # 3小时
                'performance_thresholds': {
                    'response_time': 2000,  # 2秒
                    'throughput': 100,  # 100请求/秒
                    'error_rate': 0.01  # 1%错误率
                },
                'collect_metrics': True
            }
        )