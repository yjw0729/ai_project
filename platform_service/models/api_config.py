# common/db_entity/api_config.py
from sqlalchemy import Column, Integer, String, Text, Enum, Boolean, DateTime
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.ext.declarative import declarative_base
import enum

Base = declarative_base()


# 定义请求方法枚举
class HttpMethod(enum.Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ApiConfig(Base):
    """接口配置表实体类"""
    __tablename__ = 'crosstest_api_config'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    # 基础信息
    name = Column(String(200), nullable=False, comment='接口名称')
    description = Column(String(500), comment='接口描述')
    module = Column(String(100), nullable=False, comment='所属模块')
    api_path = Column(String(500), nullable=False, comment='接口路径')
    # 请求配置
    method = Column(
        Enum('GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'),
        nullable=False,
        default='GET',
        comment='请求方法'
    )
    # 请求参数配置
    request_type = Column(
        Enum('json', 'form', 'file'),
        nullable=False,
        default='json',
        comment='请求类型(json/form/file)'
    )
    headers = Column(JSON, comment='接口级默认请求头')
    default_params = Column(JSON, comment='默认参数')
    request_body_template = Column(JSON, comment='请求体模板')
    # 安全配置
    is_encryption = Column(Boolean, default=False, comment='是否需要加密')
    encryption_config = Column(JSON, comment='加密配置')
    # 响应配置
    expected_response = Column(JSON, comment='期望响应模板')
    # 执行配置
    timeout = Column(Integer, comment='超时时间(为空则使用环境配置)')
    retry_times = Column(Integer, default=0, comment='重试次数')
    # 状态管理
    is_deprecated = Column(Boolean, default=False, comment='是否废弃')

    def __repr__(self):
        return f"<ApiConfig(name='{self.name}', method='{self.method}', path='{self.api_path}')>"

    def to_dict(self, include_related=False):
        """
        转换为字典，支持自定义序列化
        """
        # 基础字段序列化
        result = {}
        for key, value in self.__dict__.items():
            if key.startswith("_"):
                continue
            result[key] = value

        # 处理枚举字段
        if hasattr(self.method, "value"):
            result["method"] = self.method.value
        if hasattr(self.request_type, "value"):
            result["request_type"] = self.request_type.value
        else:
            result["request_type"] = result.get("request_type")

        # 处理布尔字段
        result["is_encryption"] = bool(self.is_encryption)
        result["is_deprecated"] = bool(self.is_deprecated)

        return result

    def get_full_url(self, base_url):
        """获取完整URL"""
        if base_url.endswith('/') and self.api_path.startswith('/'):
            return base_url + self.api_path[1:]
        elif not base_url.endswith('/') and not self.api_path.startswith('/'):
            return base_url + '/' + self.api_path
        else:
            return base_url + self.api_path

    def validate_config(self):
        """验证配置完整性"""
        errors = []

        if not self.name:
            errors.append("接口名称不能为空")

        if not self.api_path:
            errors.append("接口路径不能为空")

        if not self.module:
            errors.append("所属模块不能为空")

        # 验证请求体模板格式
        if self.request_body_template and not isinstance(self.request_body_template, (dict, list)):
            errors.append("请求体模板必须是JSON对象或数组")

        if self.request_type and str(self.request_type).lower() not in ("json", "form", "file"):
            errors.append("请求类型必须是 json/form/file")

        return errors

    @classmethod
    def create_from_template(cls, template_name, **kwargs):
        """根据模板创建接口配置"""
        templates = {
            'rest_get': cls(
                method='GET',
                headers={"Content-Type": "application/json"},
                expected_response={"code": 0, "message": "success", "data": {}}
            ),
            'rest_post': cls(
                method='POST',
                headers={"Content-Type": "application/json"},
                request_body_template={},
                expected_response={"code": 0, "message": "success", "data": {}}
            ),
            'form_post': cls(
                method='POST',
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                request_body_template={},
                expected_response={"success": True}
            )
        }

        if template_name not in templates:
            raise ValueError(f"未知的模板类型: {template_name}")

        template = templates[template_name]

        # 更新模板属性
        for key, value in kwargs.items():
            if hasattr(template, key):
                setattr(template, key, value)

        return template