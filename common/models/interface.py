"""
Interface 接口模型

定义API接口的数据结构。
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, Any, List
import json


class InterfaceStatus(str, Enum):
    """接口状态枚举"""
    PENDING = 'pending'      # 待解析
    PARSED = 'parsed'        # 已解析
    GENERATING = 'generating' # 生成用例中
    GENERATED = 'generated'  # 用例已生成
    APPROVED = 'approved'    # 已审核
    DEPRECATED = 'deprecated' # 已废弃


class HttpMethod(str, Enum):
    """HTTP方法枚举"""
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    DELETE = 'DELETE'
    PATCH = 'PATCH'
    HEAD = 'HEAD'
    OPTIONS = 'OPTIONS'


@dataclass
class Interface:
    """接口数据模型"""
    interface_name: str
    method: HttpMethod
    path: str
    document_id: Optional[int] = None
    id: Optional[int] = None
    request_params: Optional[Any] = None
    response_params: Optional[Any] = None
    business_rules: Optional[List[str]] = None
    status: InterfaceStatus = InterfaceStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if isinstance(self.method, str):
            self.method = HttpMethod(self.method.upper())
        if isinstance(self.status, str):
            self.status = InterfaceStatus(self.status)
        if self.business_rules is None:
            self.business_rules = []

    def to_dict(self) -> dict:
        """转换为字典"""
        data = asdict(self)
        data['method'] = self.method.value if isinstance(self.method, HttpMethod) else self.method
        data['status'] = self.status.value if isinstance(self.status, InterfaceStatus) else self.status
        if isinstance(self.request_params, (dict, list)):
            data['request_params'] = json.dumps(self.request_params)
        if isinstance(self.response_params, (dict, list)):
            data['response_params'] = json.dumps(self.response_params)
        if isinstance(self.business_rules, list):
            data['business_rules'] = json.dumps(self.business_rules)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Interface':
        """从字典创建实例"""
        request_params = data.get('request_params')
        response_params = data.get('response_params')
        business_rules = data.get('business_rules')

        if isinstance(request_params, str):
            request_params = json.loads(request_params)
        if isinstance(response_params, str):
            response_params = json.loads(response_params)
        if isinstance(business_rules, str):
            business_rules = json.loads(business_rules)

        return cls(
            id=data.get('id'),
            document_id=data.get('document_id'),
            interface_name=data['interface_name'],
            method=data['method'],
            path=data['path'],
            request_params=request_params,
            response_params=response_params,
            business_rules=business_rules or [],
            status=data.get('status', InterfaceStatus.PENDING),
            created_at=data.get('created_at', datetime.now()),
            updated_at=data.get('updated_at', datetime.now()),
        )

    @property
    def full_path(self) -> str:
        """完整路径（方法 + 路径）"""
        return f"{self.method.value} {self.path}"

    def update_status(self, status: InterfaceStatus):
        """更新状态"""
        self.status = status
        self.updated_at = datetime.now()
