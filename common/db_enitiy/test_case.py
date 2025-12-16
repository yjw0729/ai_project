# common/db_entity/test_case.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, Enum, Boolean, DateTime, JSON
from datetime import datetime
import json
import enum

# 生成ORM基类
Base = declarative_base()


class TestCasePriority(enum.Enum):
    """测试案例优先级枚举"""
    P0 = "P0"  # 最高优先级
    P1 = "P1"  # 高优先级
    P2 = "P2"  # 中优先级（默认）
    P3 = "P3"  # 低优先级


class TestCaseStatus(enum.Enum):
    """测试案例状态枚举"""
    DRAFT = "draft"  # 草稿
    ACTIVE = "active"  # 激活
    INACTIVE = "inactive"  # 未激活
    DEPRECATED = "deprecated"  # 废弃


class ReviewStatus(enum.Enum):
    """评审状态枚举"""
    PENDING = "pending"  # 待评审
    APPROVED = "approved"  # 已通过
    REJECTED = "rejected"  # 已拒绝


class TestCase(Base):
    """测试案例表实体类"""
    __tablename__ = 'test_case'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')

    # 基础信息
    name = Column(String(200), nullable=False, comment='测试案例名称')
    description = Column(String(1000), comment='案例描述')
    module = Column(String(100), nullable=False, comment='所属模块')

    # 优先级和分类
    priority = Column(
        Enum('P0', 'P1', 'P2', 'P3'),
        nullable=False,
        default='P2',
        comment='优先级: P0-最高, P1-高, P2-中, P3-低'
    )
    tags = Column(JSON, comment='标签数组')

    # 关联接口配置
    api_config_id = Column(Integer, comment='关联 api_config.id')

    # 测试内容
    preconditions = Column(Text, comment='前置条件')
    test_steps = Column(JSON, nullable=False, comment='测试步骤(JSON数组)')
    setup_scripts = Column(JSON, comment='前置脚本')
    teardown_scripts = Column(JSON, comment='后置脚本')
    expected_results = Column(JSON, comment='期望结果')
    test_data = Column(JSON, comment='测试数据')
    variables = Column(JSON, comment='案例级变量')

    # 执行配置
    max_retry_times = Column(Integer, default=0, comment='最大重试次数')
    timeout = Column(Integer, comment='超时时间(秒)')

    # 状态管理
    status = Column(
        Enum('draft', 'active', 'inactive', 'deprecated'),
        nullable=False,
        default='draft',
        comment='状态: draft-草稿, active-激活, inactive-未激活, deprecated-废弃'
    )
    version = Column(Integer, default=1, comment='版本号')

    # 评审信息
    creator = Column(String(50), nullable=False, comment='创建人')
    reviewer = Column(String(50), comment='评审人')
    review_status = Column(
        Enum('pending', 'approved', 'rejected'),
        default='pending',
        comment='评审状态: pending-待评审, approved-已通过, rejected-已拒绝'
    )
    review_comment = Column(Text, comment='评审意见')

    # 审计字段
    created_time = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    def __repr__(self):
        return f"<TestCase(name='{self.name}', module='{self.module}', priority='{self.priority}')>"

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

    def get_step_count(self):
        """获取测试步骤数量"""
        if self.test_steps and isinstance(self.test_steps, list):
            return len(self.test_steps)
        return 0

    def get_estimated_duration(self):
        """估算测试执行时间（秒）"""
        step_count = self.get_step_count()
        base_time = 30  # 每个步骤基础时间
        return step_count * base_time + (self.timeout or 0)

    def validate_case(self):
        """验证案例完整性"""
        errors = []

        if not self.name:
            errors.append("案例名称不能为空")

        if not self.module:
            errors.append("所属模块不能为空")

        if not self.test_steps or not isinstance(self.test_steps, list):
            errors.append("测试步骤不能为空且必须是数组")
        elif len(self.test_steps) == 0:
            errors.append("至少需要一个测试步骤")

        if self.max_retry_times < 0:
            errors.append("最大重试次数不能为负数")

        if self.timeout and self.timeout <= 0:
            errors.append("超时时间必须大于0")

        if self.version <= 0:
            errors.append("版本号必须大于0")

        # 验证测试步骤格式
        if self.test_steps:
            for i, step in enumerate(self.test_steps):
                if not isinstance(step, dict):
                    errors.append(f"步骤{i + 1}必须是字典格式")
                    continue

                if 'step_number' not in step:
                    errors.append(f"步骤{i + 1}缺少step_number字段")
                if 'description' not in step:
                    errors.append(f"步骤{i + 1}缺少description字段")
                if 'expected' not in step:
                    errors.append(f"步骤{i + 1}缺少expected字段")

        return errors

    def is_ready_for_execution(self):
        """检查案例是否准备好执行"""
        return (self.status == 'active' and
                self.review_status == 'approved' and
                self.get_step_count() > 0)

    def can_be_reviewed(self):
        """检查案例是否可以评审"""
        return (self.status in ['draft', 'active'] and
                self.review_status == 'pending' and
                self.get_step_count() > 0)

    def add_test_step(self, step_number, description, expected, action=None, data=None):
        """添加测试步骤"""
        if not self.test_steps:
            self.test_steps = []

        step = {
            'step_number': step_number,
            'description': description,
            'expected': expected
        }

        if action:
            step['action'] = action
        if data:
            step['data'] = data

        self.test_steps.append(step)
        # 按步骤号排序
        self.test_steps.sort(key=lambda x: x['step_number'])

    def update_test_step(self, step_number, updates):
        """更新测试步骤"""
        if not self.test_steps:
            return False

        for step in self.test_steps:
            if step.get('step_number') == step_number:
                step.update(updates)
                return True

        return False

    def remove_test_step(self, step_number):
        """删除测试步骤"""
        if not self.test_steps:
            return False

        original_length = len(self.test_steps)
        self.test_steps = [step for step in self.test_steps if step.get('step_number') != step_number]

        return len(self.test_steps) < original_length

    def get_step_by_number(self, step_number):
        """根据步骤号获取步骤"""
        if not self.test_steps:
            return None

        for step in self.test_steps:
            if step.get('step_number') == step_number:
                return step

        return None

    def add_tag(self, tag):
        """添加标签"""
        if not self.tags:
            self.tags = []

        if tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag):
        """移除标签"""
        if self.tags and tag in self.tags:
            self.tags.remove(tag)

    def has_tag(self, tag):
        """检查是否包含标签"""
        return self.tags and tag in self.tags

    def increment_version(self):
        """增加版本号"""
        self.version += 1

    def approve(self, reviewer, comment=None):
        """通过评审"""
        if not self.can_be_reviewed():
            raise ValueError("案例当前状态不能进行评审")

        self.review_status = 'approved'
        self.reviewer = reviewer
        if comment:
            self.review_comment = comment

        # 如果之前是草稿状态，自动激活
        if self.status == 'draft':
            self.status = 'active'

    def reject(self, reviewer, comment):
        """拒绝评审"""
        if not self.can_be_reviewed():
            raise ValueError("案例当前状态不能进行评审")

        self.review_status = 'rejected'
        self.reviewer = reviewer
        self.review_comment = comment

    def reset_review(self):
        """重置评审状态"""
        self.review_status = 'pending'
        self.reviewer = None
        self.review_comment = None

    @classmethod
    def create_simple_case(cls, name, module, steps, creator, priority='P2'):
        """创建简单测试案例"""
        case = cls(
            name=name,
            module=module,
            priority=priority,
            test_steps=steps,
            creator=creator,
            status='draft'
        )

        # 自动生成描述
        if not case.description:
            case.description = f"测试{module}模块的{name}功能"

        return case

    @classmethod
    def create_api_test_case(cls, name, module, api_config, test_data, creator, priority='P2'):
        """创建API测试案例模板"""
        steps = [
            {
                'step_number': 1,
                'description': f"准备测试数据",
                'action': 'setup',
                'data': test_data,
                'expected': '测试数据准备完成'
            },
            {
                'step_number': 2,
                'description': f"发送{api_config.get('method', 'GET')}请求到{api_config.get('path', '')}",
                'action': 'api_call',
                'data': api_config,
                'expected': '接口返回成功响应'
            },
            {
                'step_number': 3,
                'description': "验证响应结果",
                'action': 'validation',
                'data': api_config.get('expected_response', {}),
                'expected': '响应数据符合预期'
            }
        ]

        case = cls.create_simple_case(name, module, steps, creator, priority)
        case.test_data = test_data

        return case

    @classmethod
    def create_ui_test_case(cls, name, module, ui_flows, creator, priority='P2'):
        """创建UI测试案例模板"""
        steps = []

        for i, flow in enumerate(ui_flows, 1):
            steps.append({
                'step_number': i,
                'description': flow.get('description', f'UI操作步骤{i}'),
                'action': 'ui_action',
                'data': flow,
                'expected': flow.get('expected', '操作成功完成')
            })

        case = cls.create_simple_case(name, module, steps, creator, priority)
        return case

    @classmethod
    def create_database_test_case(cls, name, module, db_operations, creator, priority='P2'):
        """创建数据库测试案例模板"""
        steps = []

        for i, operation in enumerate(db_operations, 1):
            steps.append({
                'step_number': i,
                'description': operation.get('description', f'数据库操作步骤{i}'),
                'action': 'db_operation',
                'data': operation,
                'expected': operation.get('expected', '数据库操作成功')
            })

        case = cls.create_simple_case(name, module, steps, creator, priority)
        return case