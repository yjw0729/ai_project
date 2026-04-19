# common/db_entity/environment_config.py
from sqlalchemy import Column, Integer, String, Text, Enum, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from common.db.entity import Base


class EnvironmentConfig(Base):
    """运行环境配置表实体类"""
    __tablename__ = 'crosstest_environment_config'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')

    # 基础信息
    name = Column(String(100), nullable=False, unique=True, comment='环境名称')
    description = Column(String(500), comment='环境描述')
    base_url = Column(String(500), nullable=False, comment='基础URL')

    # 环境类型
    env_type = Column(
        Enum('dev', 'test', 'staging', 'prod'),
        nullable=False,
        default='test',
        comment='环境类型: dev,test,staging,prod'
    )

    # 关联配置（仅保存关联ID，不在ORM层声明外键，避免跨Base引用问题）
    database_config_id = Column(Integer, comment='关联的数据库配置ID')

    # 请求配置
    headers = Column(JSON, comment='环境级默认请求头')
    variables = Column(JSON, comment='环境级变量')
    timeout = Column(Integer, default=30, comment='请求超时时间(秒)')

    # 安全配置
    is_encryption = Column(Boolean, default=False, comment='是否需要加密')
    encryption_config = Column(JSON, comment='加密配置')

    # 状态管理
    is_active = Column(Boolean, default=True, comment='是否激活')

    # 审计字段
    created_by = Column(String(50), comment='创建人')
    created_time = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_by = Column(String(50), comment='更新人')
    updated_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 关系定义（可选，如果需要关联查询）
    # database_config = relationship("DatabaseConfig", back_populates="environments")

    def __repr__(self):
        return f"<EnvironmentConfig(name='{self.name}', type='{self.env_type}', url='{self.base_url}')>"

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

    def get_full_url(self, api_path):
        """获取完整的API URL"""
        if api_path.startswith('/'):
            # 如果base_url以/结尾，去掉一个/
            if self.base_url.endswith('/'):
                return self.base_url[:-1] + api_path
            else:
                return self.base_url + api_path
        else:
            # 如果api_path不以/开头，确保base_url以/结尾
            if not self.base_url.endswith('/'):
                return self.base_url + '/' + api_path
            else:
                return self.base_url + api_path

    def get_headers(self):
        """获取合并后的请求头（环境级默认 + 自定义）"""
        default_headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'AutoTestPlatform/1.0'
        }

        # 合并环境级默认头
        if self.headers:
            default_headers.update(self.headers)

        return default_headers

    def get_variables(self):
        """获取环境变量（包含系统默认变量）"""
        default_vars = {
            'env_type': self.env_type,
            'base_url': self.base_url,
            'timeout': self.timeout
        }

        # 合并自定义变量
        if self.variables:
            default_vars.update(self.variables)

        return default_vars

    def validate_config(self):
        """验证配置完整性"""
        errors = []

        if not self.name:
            errors.append("环境名称不能为空")

        if not self.base_url:
            errors.append("基础URL不能为空")

        if self.timeout <= 0:
            errors.append("超时时间必须大于0")

        # 验证URL格式
        if self.base_url and not (self.base_url.startswith('http://') or self.base_url.startswith('https://')):
            errors.append("基础URL必须以http://或https://开头")

        return errors

    def is_encryption_enabled(self):
        """检查是否启用了加密"""
        return self.is_encryption and self.encryption_config

    @classmethod
    def create_environment(cls, name, base_url, env_type='test', **kwargs):
        """快速创建环境配置"""
        return cls(
            name=name,
            base_url=base_url.rstrip('/'),  # 移除末尾的/
            env_type=env_type,
            description=kwargs.get('description', f'{env_type}环境配置'),
            headers=kwargs.get('headers', {'Content-Type': 'application/json'}),
            variables=kwargs.get('variables', {}),
            timeout=kwargs.get('timeout', 30),
            is_encryption=kwargs.get('is_encryption', False),
            encryption_config=kwargs.get('encryption_config'),
            is_active=kwargs.get('is_active', True)
        )

    @classmethod
    def create_development_env(cls):
        """创建开发环境模板"""
        return cls.create_environment(
            name="开发环境",
            base_url="http://localhost:8080",
            env_type="dev",
            description="本地开发环境",
            variables={"debug": True, "log_level": "DEBUG"}
        )

    @classmethod
    def create_test_env(cls):
        """创建测试环境模板"""
        return cls.create_environment(
            name="测试环境",
            base_url="https://test-api.example.com",
            env_type="test",
            description="测试环境",
            variables={"debug": False, "log_level": "INFO"}
        )

    @classmethod
    def create_production_env(cls):
        """创建生产环境模板"""
        return cls.create_environment(
            name="生产环境",
            base_url="https://api.example.com",
            env_type="prod",
            description="生产环境",
            timeout=60,  # 生产环境超时时间更长
            variables={"debug": False, "log_level": "WARNING"}
        )