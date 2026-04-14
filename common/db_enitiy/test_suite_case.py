# common/db_entity/test_suite_case.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import json

# 生成ORM基类
Base = declarative_base()


class TestSuiteCase(Base):
    """测试套件案例关联表实体类"""
    __tablename__ = 'crosstest_test_suite_case'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')

    # 外键关联
    suite_id = Column(Integer, ForeignKey('crosstest_test_suite.id', ondelete='CASCADE'), nullable=False, comment='套件ID')
    case_id = Column(Integer, ForeignKey('crosstest_test_case.id', ondelete='CASCADE'), nullable=False, comment='案例ID')

    # 关联配置
    execution_order = Column(Integer, default=0, comment='执行顺序')
    enabled = Column(Boolean, default=True, comment='是否启用')

    # ===== 新增: 独立请求配置字段 =====
    # 说明: 如果这些字段有值，则使用这些值；否则回退到 test_case 表的配置
    url = Column(String(500), nullable=True, comment='请求URL(独立配置，为空则继承用例)')
    request_headers = Column(JSON, nullable=True, comment='请求头(独立配置)')
    request_params = Column(JSON, nullable=True, comment='请求参数(独立配置)')
    request_body = Column(JSON, nullable=True, comment='请求体(独立配置)')
    timeout = Column(Integer, default=30, comment='超时秒数')
    assertions = Column(JSON, nullable=True, comment='断言配置(独立配置)')

    # 保留: 原有 config 字段（用于扩展配置，如前置脚本等）
    config = Column(JSON, nullable=True, comment='其他配置(JSON)')

    # ===== 新增: 用例内容字段（优先级: test_suite_case 自己的 > 从 test_case 复制过来的） =====
    # 说明: 如果这些字段有值则直接用；为空则执行时 fallback 到 test_case 表
    preconditions = Column(Text, nullable=True, comment='前置条件(可独立覆盖)')
    test_steps = Column(JSON, nullable=True, comment='测试步骤(可独立覆盖)')
    test_data = Column(JSON, nullable=True, comment='测试数据(可独立覆盖)')

    # 时间字段
    created_time = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

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
        """检查关联是否启用"""
        return self.enabled is not False  # None 或 True 都视为启用

    def get_timeout(self, default_timeout=30):
        """获取超时时间（优先用自己的，否则用默认值）"""
        return self.timeout if self.timeout else default_timeout

    def get_retry_count(self, default_retry=0):
        """获取重试次数（从 config 中获取）"""
        return self.get_config_value('retry_count', default_retry)

    def get_priority(self, default_priority='medium'):
        """获取优先级（从 config 中获取）"""
        return self.get_config_value('priority', default_priority)

    def should_skip_on_failure(self):
        """检查失败时是否跳过后续案例"""
        return self.get_config_value('skip_on_failure', False)

    # ===== 新增: 请求配置相关方法 =====

    def has_custom_config(self):
        """检查是否有独立配置的请求参数"""
        return any([
            self.url is not None,
            self.request_headers is not None,
            self.request_params is not None,
            self.request_body is not None,
            self.assertions is not None,
            self.preconditions is not None,
            self.test_steps is not None,
            self.test_data is not None
        ])

    def get_custom_config_summary(self):
        """获取自定义配置摘要"""
        summary = []
        if self.url is not None:
            summary.append('URL')
        if self.request_headers is not None:
            summary.append('请求头')
        if self.request_params is not None:
            summary.append('请求参数')
        if self.request_body is not None:
            summary.append('请求体')
        if self.assertions is not None:
            summary.append('断言')
        if self.preconditions is not None:
            summary.append('前置条件')
        if self.test_steps is not None:
            summary.append('测试步骤')
        if self.test_data is not None:
            summary.append('测试数据')
        return summary

    def update_execution_config(self, timeout=None, retry_count=None, priority=None, skip_on_failure=None):
        """更新执行配置"""
        if timeout is not None:
            self.timeout = timeout

        if retry_count is not None:
            self.set_config_value('retry_count', retry_count)

        if priority is not None:
            self.set_config_value('priority', priority)

        if skip_on_failure is not None:
            self.set_config_value('skip_on_failure', skip_on_failure)

    def update_request_config(self, url=None, request_headers=None, request_params=None,
                             request_body=None, timeout=None, assertions=None):
        """更新请求配置"""
        if url is not None:
            self.url = url
        if request_headers is not None:
            self.request_headers = request_headers
        if request_params is not None:
            self.request_params = request_params
        if request_body is not None:
            self.request_body = request_body
        if timeout is not None:
            self.timeout = timeout
        if assertions is not None:
            self.assertions = assertions

    def clear_request_config(self):
        """清除请求配置，恢复继承用例配置"""
        self.url = None
        self.request_headers = None
        self.request_params = None
        self.request_body = None
        self.timeout = None
        self.assertions = None
        self.preconditions = None
        self.test_steps = None
        self.test_data = None

    def copy_from_case(self, test_case):
        """从测试用例复制配置（用于初始化独立配置）"""
        if test_case:
            if self.url is None and hasattr(test_case, 'url'):
                self.url = getattr(test_case, 'url', None)
            if self.request_headers is None and hasattr(test_case, 'request_headers'):
                self.request_headers = getattr(test_case, 'request_headers', None)
            if self.request_params is None and hasattr(test_case, 'request_params'):
                self.request_params = getattr(test_case, 'request_params', None)
            if self.request_body is None and hasattr(test_case, 'request_body'):
                self.request_body = getattr(test_case, 'request_body', None)
            if self.timeout is None and hasattr(test_case, 'timeout'):
                self.timeout = getattr(test_case, 'timeout', None)
            if self.assertions is None and hasattr(test_case, 'assertions'):
                self.assertions = getattr(test_case, 'assertions', None)
            if self.preconditions is None:
                self.preconditions = getattr(test_case, 'preconditions', None)
            if self.test_steps is None:
                self.test_steps = getattr(test_case, 'test_steps', None)
            if self.test_data is None:
                self.test_data = getattr(test_case, 'test_data', None)

    @classmethod
    def create_association(cls, suite_id, case_id, execution_order=0, config=None, enabled=True):
        """创建关联记录"""
        return cls(
            suite_id=suite_id,
            case_id=case_id,
            execution_order=execution_order,
            enabled=enabled,
            config=config or {}
        )

    @classmethod
    def create_with_request_config(cls, suite_id, case_id, execution_order=0,
                                  url=None, request_headers=None, request_params=None,
                                  request_body=None, timeout=30, assertions=None,
                                  preconditions=None, test_steps=None, test_data=None):
        """使用完整请求配置创建关联"""
        return cls(
            suite_id=suite_id,
            case_id=case_id,
            execution_order=execution_order,
            enabled=True,
            url=url,
            request_headers=request_headers,
            request_params=request_params,
            request_body=request_body,
            timeout=timeout,
            assertions=assertions,
            preconditions=preconditions,
            test_steps=test_steps,
            test_data=test_data,
            config={}
        )