"""
TestDataConfig 测试数据配置模型

定义测试数据配置的数据结构。
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Any, Dict
import json


@dataclass
class TestDataConfig:
    """测试数据配置数据模型"""
    dataset_name: str
    param_configs: Dict[str, Any]
    interface_id: Optional[int] = None
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if self.param_configs is None:
            self.param_configs = {}

    def to_dict(self) -> dict:
        """转换为字典"""
        data = asdict(self)
        if isinstance(self.param_configs, dict):
            data['param_configs'] = json.dumps(self.param_configs)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'TestDataConfig':
        """从字典创建实例"""
        param_configs = data.get('param_configs')
        if isinstance(param_configs, str):
            param_configs = json.loads(param_configs)

        return cls(
            id=data.get('id'),
            interface_id=data.get('interface_id'),
            dataset_name=data['dataset_name'],
            param_configs=param_configs or {},
            created_at=data.get('created_at', datetime.now()),
            updated_at=data.get('updated_at', datetime.now()),
        )

    def add_param(self, param_name: str, param_config: Dict[str, Any]):
        """添加参数配置"""
        self.param_configs[param_name] = param_config
        self.updated_at = datetime.now()

    def remove_param(self, param_name: str):
        """移除参数配置"""
        if param_name in self.param_configs:
            del self.param_configs[param_name]
            self.updated_at = datetime.now()

    def get_param_types(self) -> list:
        """获取所有参数类型"""
        types = set()
        for config in self.param_configs.values():
            if isinstance(config, dict):
                types.add(config.get('type', 'unknown'))
        return sorted(types)
