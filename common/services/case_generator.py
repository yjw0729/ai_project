"""
测试用例生成服务模块

根据接口信息和异常码库生成测试用例，支持正向用例和异常用例的批量生成。
提供用例导出功能（YAML/JSON格式）。
"""

import json
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from common.models.assertion import AssertionField, AssertionConfig
from common.services.assertion_engine import AssertionEngine


@dataclass
class TestCase:
    """测试用例"""
    name: str                              # 用例名称
    description: str = ""                  # 用例描述
    interface_id: Optional[int] = None     # 接口ID
    interface_name: str = ""              # 接口名称
    method: str = ""                        # 请求方法
    path: str = ""                          # 请求路径
    request_params: Dict[str, Any] = None  # 请求参数
    
    # 断言
    assertions: List[Dict[str, Any]] = None  # 断言配置
    
    # 用例类型
    case_type: str = "positive"             # positive / negative
    
    # 元数据
    tags: List[str] = None                 # 标签
    priority: str = "P1"                   # 优先级 P0/P1/P2/P3
    
    def __post_init__(self):
        if self.request_params is None:
            self.request_params = {}
        if self.assertions is None:
            self.assertions = []
        if self.tags is None:
            self.tags = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "interface_id": self.interface_id,
            "interface_name": self.interface_name,
            "method": self.method,
            "path": self.path,
            "request_params": self.request_params,
            "assertions": self.assertions,
            "case_type": self.case_type,
            "tags": self.tags,
            "priority": self.priority
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TestCase':
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            interface_id=data.get("interface_id"),
            interface_name=data.get("interface_name", ""),
            method=data.get("method", ""),
            path=data.get("path", ""),
            request_params=data.get("request_params", {}),
            assertions=data.get("assertions", []),
            case_type=data.get("case_type", "positive"),
            tags=data.get("tags", []),
            priority=data.get("priority", "P1")
        )


class CaseGenerator:
    """
    测试用例生成器
    
    根据接口信息和异常码库生成测试用例
    """
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self._assertion_engine = AssertionEngine(db_path)
        self._assertion_config = AssertionConfig()
    
    def generate_cases_for_interface(
        self,
        interface_info: Dict[str, Any],
        include_negative: bool = True
    ) -> List[TestCase]:
        """
        为单个接口生成测试用例
        
        Args:
            interface_info: 接口信息
            include_negative: 是否包含异常用例
            
        Returns:
            测试用例列表
        """
        cases = []
        
        # 1. 生成正向用例
        positive_case = self._generate_positive_case(interface_info)
        cases.append(positive_case)
        
        # 2. 生成异常用例
        if include_negative:
            negative_cases = self._generate_negative_cases(interface_info)
            cases.extend(negative_cases)
        
        return cases
    
    def _generate_positive_case(
        self,
        interface_info: Dict[str, Any]
    ) -> TestCase:
        """生成正向用例"""
        # 构建断言
        assertions = [
            AssertionField(
                field="code",
                source="fixed",
                type="equals",
                expected="00000",
                message="响应码应为成功"
            ),
            AssertionField(
                field="data",
                source="response",
                type="not_null",
                message="响应数据不应为空"
            )
        ]
        
        # 根据接口信息添加更多断言
        request_params = interface_info.get("request_params", {})
        for param_name in request_params.keys():
            if request_params[param_name].get("required"):
                assertions.append(
                    AssertionField(
                        field=f"data.{param_name}",
                        source="response",
                        type="not_null",
                        message=f"返回数据应包含 {param_name}"
                    )
                )
        
        return TestCase(
            name=f"{interface_info.get('interface_name', '接口')} - 正向用例",
            description="验证正常业务流程",
            interface_name=interface_info.get("interface_name", ""),
            method=interface_info.get("method", ""),
            path=interface_info.get("path", ""),
            request_params=interface_info.get("request_params", {}),
            assertions=[a.to_dict() for a in assertions],
            case_type="positive",
            tags=["正向", "主流程"],
            priority="P0"
        )
    
    def _generate_negative_cases(
        self,
        interface_info: Dict[str, Any]
    ) -> List[TestCase]:
        """生成异常用例"""
        cases = []
        
        # 获取该模块的异常码
        exception_codes = self._get_exception_codes()
        
        # 为每个异常码生成用例
        for exc in exception_codes:
            assertions = [
                AssertionField(
                    field="code",
                    source="exception_code",
                    type="equals",
                    exception_code=exc["code"],
                    expected=exc["response_code"],
                    message=exc.get("description", "")
                )
            ]
            
            # 根据异常码调整请求参数
            modified_params = self._get_modifed_params_for_exception(
                interface_info.get("request_params", {}),
                exc["code"]
            )
            
            cases.append(TestCase(
                name=f"{interface_info.get('interface_name', '接口')} - {exc['code']}",
                description=exc.get("description", ""),
                interface_name=interface_info.get("interface_name", ""),
                method=interface_info.get("method", ""),
                path=interface_info.get("path", ""),
                request_params=modified_params,
                assertions=[a.to_dict() for a in assertions],
                case_type="negative",
                tags=["异常", exc["module"]],
                priority="P1"
            ))
        
        return cases
    
    def _get_exception_codes(self) -> List[Dict[str, Any]]:
        """获取异常码列表"""
        if not self.db_path:
            return []
        
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT code, response_code, http_status, description, module
                FROM exception_codes
                ORDER BY module, code
            """)
            
            results = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "code": r[0],
                    "response_code": r[1],
                    "http_status": r[2],
                    "description": r[3],
                    "module": r[4]
                }
                for r in results
            ]
            
        except Exception as e:
            print(f"获取异常码失败: {e}")
            return []
    
    def _get_modifed_params_for_exception(
        self,
        params: Dict[str, Any],
        exception_code: str
    ) -> Dict[str, Any]:
        """根据异常码修改请求参数"""
        modified = params.copy()
        
        # 根据异常码类型调整参数
        if exception_code.startswith("ORDER"):
            # 订单模块异常 - 可能需要特定订单状态
            pass
        elif exception_code.startswith("PAY"):
            # 支付模块异常 - 可能需要特定金额
            pass
        elif exception_code.startswith("REFUND"):
            # 退款模块异常 - 可能需要特定退款金额
            pass
        
        return modified
    
    def generate_batch(
        self,
        interfaces: List[Dict[str, Any]],
        threads: int = 3
    ) -> List[TestCase]:
        """
        批量生成用例（多线程）
        
        Args:
            interfaces: 接口列表
            threads: 线程数
            
        Returns:
            所有生成的用例
        """
        all_cases = []
        
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {
                executor.submit(self.generate_cases_for_interface, iface): iface
                for iface in interfaces
            }
            
            for future in as_completed(futures):
                try:
                    cases = future.result()
                    all_cases.extend(cases)
                except Exception as e:
                    print(f"用例生成失败: {e}")
        
        return all_cases


def export_cases_to_yaml(cases: List[TestCase], output_path: str):
    """导出用例到YAML"""
    import yaml
    
    data = [case.to_dict() for case in cases]
    
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


def export_cases_to_json(cases: List[TestCase], output_path: str):
    """导出用例到JSON"""
    data = [case.to_dict() for case in cases]
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
