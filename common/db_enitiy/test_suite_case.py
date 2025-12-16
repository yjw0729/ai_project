# common/db_entity/test_suite_case.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import json

# 生成ORM基类
Base = declarative_base()


class TestSuiteCase(Base):
    """测试套件案例关联表实体类"""
    __tablename__ = 'test_suite_case'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')

    # 外键关联
    suite_id = Column(Integer, ForeignKey('test_suite.id', ondelete='CASCADE'), nullable=False, comment='套件ID')
    case_id = Column(Integer, ForeignKey('test_case.id', ondelete='CASCADE'), nullable=False, comment='案例ID')

    # 关联配置
    execution_order = Column(Integer, default=0, comment='执行顺序')
    config = Column(JSON, comment='案例在套件中的特殊配置')

    # 时间字段
    created_time = Column(DateTime, default=datetime.now, comment='创建时间')

    # 关系定义（可选，用于关联查询）
    # test_suite = relationship("TestSuite", back_populates="suite_cases")
    # test_case = relationship("TestCase", back_populates="case_suites")

    def __repr__(self):
        return f"<TestSuiteCase(suite_id={self.suite_id}, case_id={self.case_id}, order={self.execution_order})>"

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

    def validate_association(self):
        """验证关联完整性"""
        errors = []

        if not self.suite_id:
            errors.append("套件ID不能为空")

        if not self.case_id:
            errors.append("案例ID不能为空")

        if self.execution_order < 0:
            errors.append("执行顺序不能为负数")

        # 验证配置格式
        if self.config and not isinstance(self.config, (dict, list)):
            try:
                json.loads(self.config)
            except:
                errors.append("配置必须是有效的JSON格式")

        return errors

    def is_enabled(self):
        """检查关联是否启用（通过配置控制）"""
        return self.get_config_value('enabled', True)

    def get_timeout(self, default_timeout=30):
        """获取案例在套件中的超时时间"""
        return self.get_config_value('timeout', default_timeout)

    def get_retry_count(self, default_retry=0):
        """获取案例在套件中的重试次数"""
        return self.get_config_value('retry_count', default_retry)

    def get_priority(self, default_priority='medium'):
        """获取案例在套件中的优先级"""
        return self.get_config_value('priority', default_priority)

    def should_skip_on_failure(self):
        """检查失败时是否跳过后续案例"""
        return self.get_config_value('skip_on_failure', False)

    def get_preconditions(self):
        """获取前置条件"""
        return self.get_config_value('preconditions')

    def get_postconditions(self):
        """获取后置条件"""
        return self.get_config_value('postconditions')

    def update_execution_config(self, timeout=None, retry_count=None, priority=None, skip_on_failure=None):
        """更新执行配置"""
        if timeout is not None:
            self.set_config_value('timeout', timeout)

        if retry_count is not None:
            self.set_config_value('retry_count', retry_count)

        if priority is not None:
            self.set_config_value('priority', priority)

        if skip_on_failure is not None:
            self.set_config_value('skip_on_failure', skip_on_failure)

    @classmethod
    def create_association(cls, suite_id, case_id, execution_order=0, config=None):
        """创建关联记录"""
        return cls(
            suite_id=suite_id,
            case_id=case_id,
            execution_order=execution_order,
            config=config or {}
        )

    @classmethod
    def create_with_default_config(cls, suite_id, case_id, execution_order=0,
                                   timeout=30, retry_count=0, priority='medium'):
        """使用默认配置创建关联"""
        config = {
            'timeout': timeout,
            'retry_count': retry_count,
            'priority': priority,
            'enabled': True,
            'skip_on_failure': False
        }

        return cls.create_association(suite_id, case_id, execution_order, config)