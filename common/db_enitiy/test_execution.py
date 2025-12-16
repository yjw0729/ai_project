# common/db_entity/test_execution.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, Enum, DateTime, ForeignKey
from sqlalchemy.dialects.mysql import JSON
from datetime import datetime
import enum
import uuid

# 生成ORM基类
Base = declarative_base()


class ExecutionStatus(enum.Enum):
    """测试执行状态枚举"""
    PENDING = "pending"  # 待执行
    RUNNING = "running"  # 执行中
    PASSED = "passed"  # 通过
    FAILED = "failed"  # 失败
    SKIPPED = "skipped"  # 跳过
    ERROR = "error"  # 错误
    CANCELLED = "cancelled"  # 取消


class TestExecution(Base):
    """测试执行结果表实体类"""
    __tablename__ = 'test_execution'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')

    # 关联信息
    plan_id = Column(Integer, nullable=False, comment='测试计划ID')
    suite_id = Column(Integer, nullable=False, comment='测试套件ID')
    case_id = Column(Integer, nullable=False, comment='测试案例ID')

    # 执行标识
    execution_id = Column(String(100), nullable=False, unique=True, comment='执行ID(UUID)')

    # 环境信息
    environment_id = Column(Integer, nullable=False, comment='环境ID')
    case_version = Column(Integer, nullable=False, comment='案例版本')

    # 执行状态
    status = Column(
        Enum('pending', 'running', 'passed', 'failed', 'skipped', 'error', 'cancelled'),
        nullable=False,
        default='pending',
        comment='执行状态'
    )

    # 执行结果
    result_details = Column(JSON, comment='详细结果')

    # 执行配置
    retry_count = Column(Integer, default=0, comment='重试次数')
    executed_by = Column(String(50), comment='执行人/系统')

    # 时间信息
    start_time = Column(DateTime, comment='开始时间')
    end_time = Column(DateTime, comment='结束时间')
    created_time = Column(DateTime, default=datetime.now, comment='创建时间')

    def __repr__(self):
        return f"<TestExecution(execution_id='{self.execution_id}', status='{self.status}')>"

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

    def calculate_duration(self):
        """计算执行持续时间（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        elif self.start_time and not self.end_time:
            return (datetime.now() - self.start_time).total_seconds()
        return 0

    def is_completed(self):
        """检查执行是否完成"""
        completed_statuses = ['passed', 'failed', 'skipped', 'error', 'cancelled']
        return self.status in completed_statuses

    def is_successful(self):
        """检查执行是否成功"""
        return self.status == 'passed'

    def is_failed(self):
        """检查执行是否失败"""
        return self.status in ['failed', 'error']

    def can_retry(self, max_retries=3):
        """检查是否可以重试"""
        return (self.is_failed() and
                self.retry_count < max_retries and
                self.status != 'cancelled')

    def get_result_summary(self):
        """获取结果摘要"""
        if not self.result_details:
            return {
                'status': self.status,
                'duration': self.calculate_duration(),
                'message': 'No result details available'
            }

        # 从result_details中提取摘要信息
        summary = {
            'status': self.status,
            'duration': self.calculate_duration(),
            'steps_passed': 0,
            'steps_failed': 0,
            'steps_skipped': 0,
            'total_steps': 0,
            'error_message': None
        }

        # 解析result_details中的步骤结果
        if isinstance(self.result_details, dict):
            steps = self.result_details.get('steps', [])
            if isinstance(steps, list):
                summary['total_steps'] = len(steps)
                for step in steps:
                    step_status = step.get('status', 'unknown')
                    if step_status == 'passed':
                        summary['steps_passed'] += 1
                    elif step_status == 'failed':
                        summary['steps_failed'] += 1
                    elif step_status == 'skipped':
                        summary['steps_skipped'] += 1

            # 提取错误信息
            if self.is_failed():
                summary['error_message'] = self.result_details.get('error_message')

        return summary

    def start_execution(self, executed_by='system'):
        """开始执行"""
        if self.status != 'pending':
            raise ValueError(f"无法开始执行，当前状态为: {self.status}")

        self.status = 'running'
        self.executed_by = executed_by
        self.start_time = datetime.now()
        self.retry_count = 0

    def complete_execution(self, status, result_details=None):
        """完成执行"""
        if self.status != 'running':
            raise ValueError(f"无法完成执行，当前状态为: {self.status}")

        if status not in ['passed', 'failed', 'skipped', 'error', 'cancelled']:
            raise ValueError(f"无效的完成状态: {status}")

        self.status = status
        self.end_time = datetime.now()

        if result_details:
            self.result_details = result_details

    def fail_execution(self, error_message, error_details=None):
        """标记执行失败"""
        result_details = {
            'error_message': error_message,
            'error_details': error_details,
            'failed_at': datetime.now().isoformat()
        }
        self.complete_execution('failed', result_details)

    def skip_execution(self, reason=None):
        """跳过执行"""
        result_details = {
            'skipped_reason': reason,
            'skipped_at': datetime.now().isoformat()
        }
        self.complete_execution('skipped', result_details)

    def cancel_execution(self, reason=None):
        """取消执行"""
        result_details = {
            'cancellation_reason': reason,
            'cancelled_at': datetime.now().isoformat()
        }
        self.complete_execution('cancelled', result_details)

    def retry_execution(self, executed_by=None):
        """重试执行"""
        if not self.can_retry():
            raise ValueError("当前执行无法重试")

        # 创建新的执行记录（基于当前记录）
        new_execution = TestExecution(
            plan_id=self.plan_id,
            suite_id=self.suite_id,
            case_id=self.case_id,
            execution_id=str(uuid.uuid4()),
            environment_id=self.environment_id,
            case_version=self.case_version,
            status='pending',
            retry_count=self.retry_count + 1,
            executed_by=executed_by or self.executed_by
        )

        return new_execution

    def add_step_result(self, step_number, step_status, details=None, duration=None):
        """添加步骤执行结果"""
        if not self.result_details:
            self.result_details = {
                'steps': [],
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'end_time': self.end_time.isoformat() if self.end_time else None
            }

        step_result = {
            'step_number': step_number,
            'status': step_status,
            'timestamp': datetime.now().isoformat()
        }

        if details:
            step_result['details'] = details

        if duration is not None:
            step_result['duration'] = duration

        # 初始化steps列表
        if 'steps' not in self.result_details:
            self.result_details['steps'] = []

        # 更新或添加步骤结果
        for i, step in enumerate(self.result_details['steps']):
            if step.get('step_number') == step_number:
                self.result_details['steps'][i] = step_result
                return

        # 如果步骤不存在，添加新步骤
        self.result_details['steps'].append(step_result)

    def get_step_results(self):
        """获取步骤执行结果"""
        if not self.result_details or 'steps' not in self.result_details:
            return []

        return self.result_details.get('steps', [])

    @classmethod
    def create_execution_record(cls, plan_id, suite_id, case_id, environment_id,
                                case_version, executed_by='system'):
        """创建执行记录"""
        return cls(
            plan_id=plan_id,
            suite_id=suite_id,
            case_id=case_id,
            execution_id=str(uuid.uuid4()),
            environment_id=environment_id,
            case_version=case_version,
            status='pending',
            executed_by=executed_by,
            created_time=datetime.now()
        )

    @classmethod
    def create_bulk_execution_records(cls, plan_id, suite_id, case_ids,
                                      environment_id, case_versions, executed_by='system'):
        """批量创建执行记录"""
        executions = []
        for i, case_id in enumerate(case_ids):
            case_version = case_versions[i] if i < len(case_versions) else 1
            execution = cls.create_execution_record(
                plan_id=plan_id,
                suite_id=suite_id,
                case_id=case_id,
                environment_id=environment_id,
                case_version=case_version,
                executed_by=executed_by
            )
            executions.append(execution)

        return executions