# common/db_entity/database_config.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, Enum, Boolean, DateTime
from sqlalchemy.dialects.mysql import JSON
from datetime import datetime
import enum

# 生成ORM基类
Base = declarative_base()


# 定义环境类型枚举
class EnvType(enum.Enum):
    DEV = "dev"
    TEST = "test"
    STAGING = "staging"
    PROD = "prod"


# 定义数据库类型枚举
class DbType(enum.Enum):
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    ORACLE = "oracle"
    SQLSERVER = "sqlserver"
    MONGODB = "mongodb"


class DatabaseConfig(Base):
    """数据库连接配置表实体类"""
    __tablename__ = 'database_config'
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    # 基础信息
    name = Column(String(100), nullable=False, comment='数据库配置名称')
    description = Column(String(500), comment='描述')
    # 环境配置
    env_type = Column(
        Enum('dev', 'test', 'staging', 'prod'),
        nullable=False,
        default='test',
        comment='环境类型'
    )
    # 数据库类型
    db_type = Column(
        Enum('mysql', 'postgresql', 'oracle', 'sqlserver', 'mongodb'),
        nullable=False,
        default='mysql',
        comment='数据库类型'
    )
    # 连接配置
    host = Column(String(200), nullable=False, comment='数据库主机')
    port = Column(Integer, default=3306, comment='端口')
    database_name = Column(String(100), nullable=False, comment='数据库名')
    username = Column(String(100), nullable=False, comment='用户名')
    password = Column(String(500), nullable=False, comment='密码(加密存储)')
    # 高级配置
    connection_params = Column(JSON, comment='连接参数')
    pool_size = Column(Integer, default=5, comment='连接池大小')
    timeout = Column(Integer, default=30, comment='连接超时时间(秒)')
    # 状态管理
    is_active = Column(Boolean, default=True, comment='是否激活')
    # 审计字段
    created_by = Column(String(50), comment='创建人')
    created_time = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_by = Column(String(50), comment='更新人')
    updated_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    def __repr__(self):
        return f"<DatabaseConfig(name='{self.name}', type='{self.db_type}', env='{self.env_type}')>"

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

    def get_connection_string(self, show_password=False):
        """获取数据库连接字符串"""
        password_display = self.password if show_password else '***'

        if self.db_type in ['mysql', 'postgresql']:
            return f"{self.db_type}://{self.username}:{password_display}@{self.host}:{self.port}/{self.database_name}"
        elif self.db_type == 'oracle':
            return f"oracle+cx_oracle://{self.username}:{password_display}@{self.host}:{self.port}/?service_name={self.database_name}"
        elif self.db_type == 'sqlserver':
            return f"mssql+pymssql://{self.username}:{password_display}@{self.host}:{self.port}/{self.database_name}"
        elif self.db_type == 'mongodb':
            return f"mongodb://{self.username}:{password_display}@{self.host}:{self.port}/{self.database_name}"
        else:
            return f"未知数据库类型: {self.db_type}"

    def validate_config(self):
        """验证配置完整性"""
        errors = []

        if not self.name:
            errors.append("配置名称不能为空")

        if not self.host:
            errors.append("数据库主机不能为空")

        if not self.database_name:
            errors.append("数据库名不能为空")

        if not self.username:
            errors.append("用户名不能为空")

        if not self.password:
            errors.append("密码不能为空")

        if self.port <= 0 or self.port > 65535:
            errors.append("端口号必须在1-65535范围内")

        if self.pool_size <= 0:
            errors.append("连接池大小必须大于0")

        if self.timeout <= 0:
            errors.append("超时时间必须大于0")

        return errors

    def get_sqlalchemy_url(self):
        """获取SQLAlchemy连接URL"""
        base_url = self.get_connection_string(show_password=False)

        # 添加连接参数
        if self.connection_params:
            import urllib.parse
            params = []
            for key, value in self.connection_params.items():
                if value is not None:
                    params.append(f"{key}={value}")

            if params:
                base_url += "?" + "&".join(params)

        return base_url

    @classmethod
    def create_mysql_config(cls, name, host, database, username, password,
                            env_type='test', port=3306, **kwargs):
        """快速创建MySQL配置"""
        return cls(
            name=name,
            env_type=env_type,
            db_type='mysql',
            host=host,
            port=port,
            database_name=database,
            username=username,
            password=password,
            connection_params=kwargs.get('connection_params', {'charset': 'utf8mb4'}),
            pool_size=kwargs.get('pool_size', 5),
            timeout=kwargs.get('timeout', 30),
            description=kwargs.get('description', f'{env_type}环境MySQL数据库')
        )

    @classmethod
    def create_postgresql_config(cls, name, host, database, username, password,
                                 env_type='test', port=5432, **kwargs):
        """快速创建PostgreSQL配置"""
        return cls(
            name=name,
            env_type=env_type,
            db_type='postgresql',
            host=host,
            port=port,
            database_name=database,
            username=username,
            password=password,
            connection_params=kwargs.get('connection_params', {}),
            pool_size=kwargs.get('pool_size', 5),
            timeout=kwargs.get('timeout', 30),
            description=kwargs.get('description', f'{env_type}环境PostgreSQL数据库')
        )