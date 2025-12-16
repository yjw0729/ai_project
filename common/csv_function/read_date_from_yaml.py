'''
读取测试案例yaml文件中的内容
'''
import yaml
import json
import re
from typing import Dict, List, Optional, Any
from pathlib import Path
from utils.auto_generate.generate_requestId import generate_request_id, generate_random_string, \
    generate_business_order_no, generate_business_sub_order_no, generate_business_trade_order_no, \
    generate_payee_bank_ac_no, generate_payee_bank_ac_name


class YamlTestCaseParser:

    def __init__(self, yaml_file_path: str):
        self.yaml_file_path = yaml_file_path
        self.template_pattern = re.compile(r'{{\s*(\w+)\s*}}')
        self._parser_data = None
        self._load_error = None

    def __load_and_param_yaml(self) -> Dict[str, Any]:
        try:
            if not Path(self.yaml_file_path).exists():
                raise FileNotFoundError(f"yaml文件不存在:{self.yaml_file_path}")

            with open(self.yaml_file_path, 'r', encoding='utf-8') as f:
                connect = f.read()

            parsed_data = yaml.safe_load(connect)

            if not isinstance(parsed_data, dict):
                raise ValueError("YAML文件中不存在字典结构")
            return parsed_data
        except yaml.YAMLError as e:
            raise ValueError(f"YAML语法错误:{e}")
        except Exception as e:
            raise RuntimeError(f"YAML文件加载失败:{e}")

    @property
    def parsed_data(self) -> Dict[str, Any]:
        """懒加载属性：在第一次访问时解析YAML文件"""
        if self._parser_data is None:
            if self._load_error is not None:
                raise self._load_error
            try:
                self._parser_data = self.__load_and_param_yaml()
            except Exception as e:
                self._load_error = e
                raise
        return self._parser_data

    def preload(self) -> None:
        '''主动加载yaml文件'''
        _ = self.parsed_data

    def get_test_suit_info(self) -> Dict[str, Any]:
        '''获取测试套件中的信息'''
        data = self.parsed_data
        return {
            "test_suit": data.get("test_suit", ""),
            "description": data.get("description", ""),
            "base_url": data.get("base_url", ""),
            "endpoint": data.get("endpoint", ""),
            "method": data.get("method", "")
        }

    def get_global_config(self) -> Dict[str, Any]:
        '''获取全局配置'''
        return self.parsed_data.get("global_config", {})

    def get_all_test_case(self) -> List[Dict[str, Any]]:
        '''获取所有案例'''
        return self.parsed_data.get("test_case", [])

    def get_test_case_by_id(self, test_id: str) -> Optional[Dict[str, Any]]:
        '''根据test_id查找测试用例'''
        for test_case in self.get_all_test_case():
            if test_case.get("test_id") == test_id:
                return test_case
        return None

    def get_enabled_test_cases(self) -> List[Dict[str, Any]]:
        ''' 查询启用状态测试'''
        return [case for case in self.get_all_test_case()
                if case.get("enabled", True)]

    def validate_test_case_structure(self, test_case: Dict[str, Any]) -> bool:
        '''验证测试用例是否完整'''
        required_fields = ['test_id', 'name', 'json', 'expected', 'extract_rules']
        return all(field in test_case for field in required_fields)

    def get_test_case_ids(self) -> List[str]:
        '''获取所有测试用例ID的列表'''
        return [case.get("test_id") for case in self.get_all_test_case()
                if case.get("test_id")]

    def parse_json_request(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        '''解析测试用例中的json请求体'''
        json_data = test_case.get("json", {})
        if isinstance(json_data, str):
            try:
                json_str = json_data.replace("'", '"')
                return json.loads(json_str)  # 修正：使用json.loads而不是json.load
            except json.JSONDecodeError as e:
                print(f"JSON解析错误: {e}")
                return {}
        return json_data

    def get_expected_assertions(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """获取预期断言配置"""
        return test_case.get("expected", {})

    def get_extract_rules(self, test_case: Dict[str, Any]) -> Dict[str, str]:
        """获取变量提取规则"""
        return test_case.get("extract_rules", {})

    def validate_file_exists(self) -> bool:
        '''验证yaml文件是否存在'''
        return Path(self.yaml_file_path).exists()

    def validate_test_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        '''验证测试用例完整性'''
        validation_result = {
            "test_id": test_case.get("test_id"),
            "valid": True,
            "errors": []  # 修正：字段名从error改为errors
        }

        required_fields = ['test_id', 'name', 'json', 'expected', 'extract_rules']
        for field in required_fields:
            if field not in test_case or not test_case[field]:
                validation_result["valid"] = False
                validation_result["errors"].append(f"缺少必须字段{field}")  # 修正：字段名从result改为errors

        try:
            json_request = self.parse_json_request(test_case)
            if not json_request:
                validation_result["valid"] = False
                validation_result["errors"].append("JSON请求体格式错误")
        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"JSON格式解析异常：{e}")

        return validation_result


    def _replace_in_json(self, data: Any, variable_values: Dict[str, Any]) -> Any:
        """在JSON数据中替换模板变量"""
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                # 替换键中的模板变量
                processed_key = self._replace_in_string(str(key), variable_values) if isinstance(key, str) else key
                # 递归替换值中的模板变量
                processed_value = self._replace_in_json(value, variable_values)
                result[processed_key] = processed_value
            return result

        elif isinstance(data, list):
            return [self._replace_in_json(item, variable_values) for item in data]

        elif isinstance(data, str):
            return self._replace_in_string(data, variable_values)

        else:
            return data

    def _replace_in_form_data(self, data: Any, variable_values: Dict[str, Any]) -> Any:
        """在表单数据中替换模板变量"""
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                # 替换键
                processed_key = self._replace_in_string(str(key), variable_values) if isinstance(key, str) else key
                # 替换值
                if isinstance(value, str):
                    processed_value = self._replace_in_string(value, variable_values)
                else:
                    processed_value = self._replace_in_form_data(value, variable_values)
                result[processed_key] = processed_value
            return result

        elif isinstance(data, list):
            return [self._replace_in_form_data(item, variable_values) for item in data]

        elif isinstance(data, str):
            return self._replace_in_string(data, variable_values)

        else:
            return data

    def _replace_in_string(self, text: str, variable_values: Dict[str, Any]) -> str:
        """在字符串中替换模板变量"""
        if not isinstance(text, str):
            return text

        def replace_match(match):
            variable_name = match.group(1)
            return str(variable_values.get(variable_name, match.group(0)))

        return self.template_pattern.sub(replace_match, text)

    def _replace_generic(self, data: Any, variable_values: Dict[str, Any]) -> Any:
        """通用替换方法"""
        if isinstance(data, dict):
            return {self._replace_generic(k, variable_values): self._replace_generic(v, variable_values)
                    for k, v in data.items()}

        elif isinstance(data, list):
            return [self._replace_generic(item, variable_values) for item in data]

        elif isinstance(data, str):
            return self._replace_in_string(data, variable_values)

        else:
            return data

    def extract_template_variables_from_data(self, test_case: Dict[str, Any]) -> List[str]:
        """提取JSON请求体中的模板变量（如{{variable}}）"""
        json_data = self.parse_json_request(test_case)
        json_str = json.dumps(json_data)
        variables = self.template_pattern.findall(json_str)  # 修正：使用self.template_pattern
        return list(set(variables))

    def generate_dynamic_value(self, variable_name: str) -> Any:
        '''根据变量名生成对应的动态值'''
        generators = {
            "requestId": generate_request_id,  # 修正：移除括号，传递函数引用而不是调用结果
            "businessOrderNo": generate_business_order_no,
            "businessSubOrderNo": generate_business_sub_order_no,
            "businessTradeOrderNo": generate_business_trade_order_no,
            "payeeBankAcName": generate_payee_bank_ac_name,
            "payeeBankAcNo": generate_payee_bank_ac_no
        }

        default_generator = lambda: f"auto_generated_{variable_name}_{generate_random_string(8)}"
        generator = generators.get(variable_name, default_generator)
        return generator()  # 修正：调用函数而不是返回函数引用

    # ========== 新增：核心模板变量替换方法 ==========

    def replace_template_variables_in_test_case(self, test_case: Dict[str, Any],
                                                custom_values: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        替换测试用例中的模板变量
        这是新增的核心方法
        """
        if custom_values is None:
            custom_values = {}

        # 创建测试用例的副本
        updated_case = test_case.copy()

        # 提取模板变量
        template_variables = self.extract_template_variables_from_data(test_case)

        if not template_variables:
            # 如果没有模板变量，直接返回
            return updated_case

        # 生成动态值
        variable_values = {}
        for var_name in template_variables:
            if var_name in custom_values:
                variable_values[var_name] = custom_values[var_name]
            else:
                variable_values[var_name] = self.generate_dynamic_value(var_name)

        # 替换JSON中的模板变量
        if "json" in updated_case:
            json_data = self.parse_json_request(test_case)
            updated_json = self._replace_in_json(json_data, variable_values)
            updated_case["json"] = updated_json

        return updated_case

    def process_test_case(self, test_case: Dict[str, Any],
                          custom_values: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        处理单个测试用例：提取变量、生成值、替换变量
        这是新增的方法
        """
        if custom_values is None:
            custom_values = {}

        # 提取模板变量
        template_variables = self.extract_template_variables_from_data(test_case)
        print(f"发现的模板变量: {template_variables}")

        if not template_variables:
            print("未发现模板变量，直接返回原始测试用例")
            return test_case

        # 生成动态值
        variable_values = {}
        for var_name in template_variables:
            if var_name in custom_values:
                variable_values[var_name] = custom_values[var_name]
                print(f"使用自定义值: {var_name} = {custom_values[var_name]}")
            else:
                variable_values[var_name] = self.generate_dynamic_value(var_name)
                print(f"生成动态值: {var_name} = {variable_values[var_name]}")

        # 替换模板变量
        processed_case = self.replace_template_variables_in_test_case(test_case, custom_values)

        return processed_case

    def process_all_test_cases(self, custom_values: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        处理所有测试用例
        这是新增的方法
        """
        if custom_values is None:
            custom_values = {}

        # 获取测试套件信息
        test_suite_info = self.get_test_suit_info()
        global_config = self.get_global_config()
        all_test_cases = self.get_all_test_case()

        # 处理所有测试用例
        processed_cases = []
        variables_replaced = 0

        for test_case in all_test_cases:
            test_id = test_case.get("test_id", "unknown")
            print(f"\n处理测试用例: {test_id}")

            try:
                # 处理测试用例
                processed_case = self.process_test_case(test_case, custom_values)
                processed_cases.append(processed_case)

                # 统计替换的变量数量
                variables_count = len(self.extract_template_variables_from_data(test_case))
                variables_replaced += variables_count

                print(f"测试用例 {test_id} 处理完成")

            except Exception as e:
                print(f"处理测试用例 {test_id} 时出错: {e}")
                # 如果处理失败，保留原始测试用例
                processed_cases.append(test_case)

        # 返回完整的接口结果
        result = {
            "test_suite_info": test_suite_info,
            "global_config": global_config,
            "processed_cases": processed_cases,
            "summary": {
                "total_cases": len(all_test_cases),
                "successful_cases": len(processed_cases),
                "variables_replaced": variables_replaced
            }
        }

        return result

    def strate_processing(self, custom_values: Dict[str, Any] = None):
        """
        演示处理功能
        这是新增的方法
        """
        if custom_values is None:
            custom_values = {}

        print("=" * 60)
        print("YAML测试用例处理器开始执行")
        print("=" * 60)

        # 1. 显示基本信息
        print("\n1. 基本信息")
        test_suite_info = self.get_test_suit_info()
        print(f"测试套件-test_suite_info['test_suit']: {test_suite_info['test_suit']}")
        print(f"描述-test_suite_info['description']: {test_suite_info['description']}")
        print(f"基础URL-test_suite_info['base_url']: {test_suite_info['base_url']}")
        print(f"接口地址-test_suite_info['endpoint']: {test_suite_info['endpoint']}")
        print(f"接口请求方式-test_suite_info['method']：{test_suite_info['method']}")

        all_cases = self.get_all_test_case()
        print(f"测试用例数量: {len(all_cases)}")

        # 2. 处理单个测试用例
        print("\n2. 处理单个测试用例")
        if all_cases:
            test_case = all_cases[0]
            test_id = test_case.get("test_id", "unknown")
            print(f"处理测试用例: {test_id} - {test_case.get('name')}")

            # 显示原始JSON
            original_json = self.parse_json_request(test_case)
            print("原始JSON请求体:")
            print(json.dumps(original_json, indent=2, ensure_ascii=False))

            # 处理测试用例
            processed_case = self.process_test_case(test_case, custom_values)

            # 显示处理后的JSON
            processed_json = processed_case.get("json", {})
            print("\n处理后的JSON请求体:")
            print(json.dumps(processed_json, indent=2, ensure_ascii=False))
            if test_case.get("expected") != None:
                print(f'{test_id} 配置了接口响应断言信息分别为')
                assertions = self.get_expected_assertions(test_case=test_case)
                for title in assertions:
                    print(f"{title}预期是{assertions[title]}")
            print("\n")
            if test_case.get("extract_rules") != None:
                print(f"{test_id}配置了后置参数处理")
                rules = self.get_extract_rules(test_case=test_case)
                for title in rules:
                    print(f"{title}预期取值是{rules[title]}")



        # 3. 处理所有测试用例
        print("\n3. 处理所有测试用例")
        result = self.process_all_test_cases(custom_values)

        # 显示摘要信息
        summary = result["summary"]
        print(f"\n处理摘要:")
        print(f"  总计用例: {summary['total_cases']}")
        print(f"  成功处理: {summary['successful_cases']}")
        print(f"  替换变量: {summary['variables_replaced']}")

        return result

