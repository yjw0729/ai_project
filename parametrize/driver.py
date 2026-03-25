"""
参数化驱动模块

提供数据驱动测试功能，支持从 YAML/JSON/CSV 读取测试数据，
并实现变量替换功能。

Usage:
    from parametrize.driver import parametrize_data, load_data

    # 使用装饰器方式
    @parametrize_data("data/params/login_data.yaml")
    def test_login(username, password, expected_code):
        assert response.status_code == expected_code

    # 直接加载数据
    data = load_data("data/params/login_data.yaml")
"""

import csv
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pytest
import yaml

# 尝试导入数据生成工具
try:
    from utils.auto_generate.generate_phone import create_phone_no
    from utils.auto_generate.generate_idcardno import create_identity_card
    from utils.auto_generate.generate_address import generate_address
    from utils.auto_generate.generate_cardNo import create_card_number
    from utils.auto_generate.generate_customer import (
        create_customer_information,
        create_name,
        creare_company_name,
        create_email,
        create_time,
    )
except ImportError:
    create_phone_no = None
    create_identity_card = None
    generate_address = None
    create_card_number = None
    create_customer_information = None
    create_name = None
    creare_company_name = None
    create_email = None
    create_time = None

# 尝试导入环境配置和全局变量（不强制依赖数据库）
try:
    from common.db_enitiy.environment_config import EnvironmentConfig
    from common.db_enitiy.global_variable import GlobalVariable
except ImportError:
    EnvironmentConfig = None
    GlobalVariable = None


class DataLoader:
    """数据加载器，支持多种文件格式和编码自动识别"""

    ENCODINGS = ['utf-8', 'gbk', 'gb2312', 'gb18030']

    @classmethod
    def load_yaml(cls, file_path: str) -> List[Dict[str, Any]]:
        """加载 YAML 文件

        Args:
            file_path: YAML 文件路径

        Returns:
            解析后的数据列表
        """
        data = cls._read_file_with_encoding(file_path)
        return yaml.safe_load(data) or []

    @classmethod
    def load_json(cls, file_path: str) -> List[Dict[str, Any]]:
        """加载 JSON 文件

        Args:
            file_path: JSON 文件路径

        Returns:
            解析后的数据列表
        """
        data = cls._read_file_with_encoding(file_path)
        result = json.loads(data)
        # 确保返回列表格式
        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return [result]
        return []

    @classmethod
    def load_csv(cls, file_path: str) -> List[Dict[str, Any]]:
        """加载 CSV 文件

        Args:
            file_path: CSV 文件路径

        Returns:
            解析后的数据列表，每行作为一个字典
        """
        rows = []
        # 尝试多种编码读取
        for encoding in cls.ENCODINGS:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                break
            except (UnicodeDecodeError, csv.Error):
                continue

        if not rows:
            raise ValueError(f"无法读取 CSV 文件: {file_path}")

        return rows

    @classmethod
    def _read_file_with_encoding(cls, file_path: str) -> str:
        """尝试多种编码读取文件

        Args:
            file_path: 文件路径

        Returns:
            文件内容字符串
        """
        for encoding in cls.ENCODINGS:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, LookupError):
                continue
            except FileNotFoundError:
                raise FileNotFoundError(f"文件不存在: {file_path}")

        raise ValueError(f"无法识别文件编码: {file_path}")

    @classmethod
    def load(cls, file_path: str) -> List[Dict[str, Any]]:
        """根据文件扩展名自动加载数据

        Args:
            file_path: 数据文件路径，支持 .yaml, .yml, .json, .csv

        Returns:
            解析后的数据列表

        Raises:
            ValueError: 不支持的文件类型
        """
        ext = Path(file_path).suffix.lower()

        if ext in ['.yaml', '.yml']:
            return cls.load_yaml(file_path)
        elif ext == '.json':
            return cls.load_json(file_path)
        elif ext == '.csv':
            return cls.load_csv(file_path)
        else:
            raise ValueError(f"不支持的文件类型: {ext}")


class VariableReplacer:
    """变量替换器，支持多种变量源"""

    # 延迟导入数据生成工具（避免类定义时的作用域问题）
    _cached_functions = {}

    @classmethod
    def _get_functions(cls):
        """延迟加载数据生成函数"""
        if not cls._cached_functions:
            try:
                from utils.auto_generate.generate_phone import create_phone_no
                from utils.auto_generate.generate_idcardno import create_identity_card
                from utils.auto_generate.generate_address import generate_address
                from utils.auto_generate.generate_cardNo import create_card_number
                from utils.auto_generate.generate_customer import (
                    create_name,
                    creare_company_name,
                    create_email,
                )
                cls._cached_functions = {
                    'phone': create_phone_no,
                    'idcard': create_identity_card,
                    'idcardno': create_identity_card,
                    'address': generate_address,
                    'cardno': create_card_number,
                    'cardNo': create_card_number,
                    'name': create_name,
                    'company_name': creare_company_name,
                    'email': create_email,
                }
            except ImportError:
                cls._cached_functions = {}
        return cls._cached_functions

    BUILTIN_FUNCTIONS = None  # 动态生成

    def __init__(self):
        self.environment_vars: Dict[str, Any] = {}
        self.global_vars: Dict[str, Any] = {}

    def _get_builtin_functions(self) -> Dict[str, Any]:
        """获取内置函数（动态生成）"""
        if VariableReplacer.BUILTIN_FUNCTIONS is None:
            # 直接在这里导入并调用
            funcs = {}
            try:
                from utils.auto_generate.generate_phone import create_phone_no as phone_func
                funcs['phone'] = phone_func
            except ImportError:
                pass
            try:
                from utils.auto_generate.generate_idcardno import create_identity_card as idcard_func
                funcs['idcard'] = idcard_func
                funcs['idcardno'] = idcard_func
            except ImportError:
                pass
            try:
                from utils.auto_generate.generate_address import generate_address as address_func
                funcs['address'] = address_func
            except ImportError:
                pass
            try:
                from utils.auto_generate.generate_cardNo import create_card_number as cardno_func
                funcs['cardno'] = cardno_func
                funcs['cardNo'] = cardno_func
            except ImportError:
                pass
            try:
                from utils.auto_generate.generate_customer import create_name as name_func
                funcs['name'] = name_func
            except ImportError:
                pass
            try:
                from utils.auto_generate.generate_customer import creare_company_name as company_func
                funcs['company_name'] = company_func
            except ImportError:
                pass
            try:
                from utils.auto_generate.generate_customer import create_email as email_func
                funcs['email'] = email_func
            except ImportError:
                pass

            VariableReplacer.BUILTIN_FUNCTIONS = {
                'phone': lambda: str(funcs.get('phone')()) if 'phone' in funcs else '',
                'idcard': lambda: str(funcs.get('idcard')()) if 'idcard' in funcs else '',
                'idcardno': lambda: str(funcs.get('idcardno')()) if 'idcardno' in funcs else '',
                'address': lambda: str(funcs.get('address')()) if 'address' in funcs else '',
                'cardno': lambda: str(funcs.get('cardno')()) if 'cardno' in funcs else '',
                'cardNo': lambda: str(funcs.get('cardNo')()) if 'cardNo' in funcs else '',
                'name': lambda: str(funcs.get('name')()) if 'name' in funcs else '',
                'company_name': lambda: str(funcs.get('company_name')()) if 'company_name' in funcs else '',
                'email': lambda: str(funcs.get('email')()) if 'email' in funcs else '',
                'timestamp': lambda: str(int(__import__('time').time())),
                'random': lambda n=10: str(__import__('random').randint(100000, 999999))[:n] if isinstance(n, int) else str(__import__('random').randint(100000, 999999)),
                'date': lambda: __import__('datetime').datetime.now().strftime('%Y-%m-%d'),
                'datetime': lambda: __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            # 缓存实际可用的函数引用
            VariableReplacer._cached_funcs = funcs
        return VariableReplacer.BUILTIN_FUNCTIONS

    def set_environment_vars(self, vars_dict: Dict[str, Any]) -> None:
        """设置环境变量

        Args:
            vars_dict: 环境变量字典
        """
        self.environment_vars = vars_dict or {}

    def set_global_vars(self, vars_dict: Dict[str, Any]) -> None:
        """设置全局变量

        Args:
            vars_dict: 全局变量字典
        """
        self.global_vars = vars_dict or {}

    def replace(self, data: Union[str, Dict, List, Any]) -> Any:
        """递归替换数据中的变量

        Args:
            data: 待替换的数据

        Returns:
            替换后的数据
        """
        if isinstance(data, str):
            return self._replace_string(data)
        elif isinstance(data, dict):
            return {k: self.replace(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.replace(item) for item in data]
        return data

    def _replace_string(self, text: str) -> str:
        """替换字符串中的变量

        支持格式:
        - {{var_name}} - 普通变量
        - {{env:var_name}} - 环境变量
        - {{global:var_name}} - 全局变量
        - {{func:func_name}} - 内置函数
        - {{func:func_name(arg1, arg2)}} - 带参数的内置函数

        Args:
            text: 包含变量的字符串

        Returns:
            替换后的字符串
        """
        if not isinstance(text, str):
            return text

        # 匹配 {{...}} 格式的变量
        pattern = r'\{\{([^}]+)\}\}'
        matches = re.findall(pattern, text)

        for match in matches:
            replacement = self._resolve_variable(match)
            text = text.replace('{{' + match + '}}', str(replacement))

        return text

    def _resolve_variable(self, var_expr: str) -> Any:
        """解析变量表达式

        Args:
            var_expr: 变量表达式

        Returns:
            解析后的值
        """
        var_expr = var_expr.strip()

        # 检查是否是内置函数调用（支持带func:前缀或不带前缀）
        if var_expr.startswith('func:'):
            return self._resolve_function(var_expr[5:])

        # 检查是否是内置函数（不带前缀时直接查找）
        builtin_funcs = self._get_builtin_functions()
        if var_expr in builtin_funcs:
            try:
                return str(builtin_funcs[var_expr]())
            except Exception:
                return f'{{{{{var_expr}}}}}'

        # 检查是否是环境变量
        if var_expr.startswith('env:'):
            var_name = var_expr[4:]
            return self.environment_vars.get(var_name, f'{{{{env:{var_name}}}}}')

        # 检查是否是全局变量
        if var_expr.startswith('global:'):
            var_name = var_expr[7:]
            return self.global_vars.get(var_name, f'{{{{global:{var_name}}}}}')

        # 尝试从环境变量查找
        if var_expr in self.environment_vars:
            return self.environment_vars[var_expr]

        # 尝试从全局变量查找
        if var_expr in self.global_vars:
            return self.global_vars[var_expr]

        # 返回原表达式
        return f'{{{{{var_expr}}}}}'

    def _resolve_function(self, func_expr: str) -> str:
        """解析内置函数表达式

        Args:
            func_expr: 函数表达式，如 "phone()" 或 "random(6)"

        Returns:
            函数执行结果
        """
        # 匹配函数名和参数
        match = re.match(r'^(\w+)\((.*)\)$', func_expr.strip())
        if match:
            func_name = match.group(1)
            args_str = match.group(2)

            builtin_funcs = self._get_builtin_functions()
            if func_name in builtin_funcs:
                func = builtin_funcs[func_name]
                if args_str:
                    # 简单参数处理，仅支持字符串和数字
                    args = []
                    for arg in args_str.split(','):
                        arg = arg.strip().strip('"\'')
                        if arg.isdigit():
                            args.append(int(arg))
                        else:
                            args.append(arg)
                    try:
                        return func(*args)
                    except TypeError:
                        return str(func())
                return str(func())

        return f'{{{{func:{func_expr}}}}}'


def parametrize_data(
    data_file: str,
    env_vars: Optional[Dict[str, Any]] = None,
    global_vars: Optional[Dict[str, Any]] = None,
    encoding: Optional[str] = None,
) -> pytest.MarkDecorator:
    """参数化装饰器

    从数据文件加载测试数据，并创建 pytest.mark.parametrize 装饰器。
    支持变量替换功能。

    Args:
        data_file: 数据文件路径，支持 .yaml, .yml, .json, .csv 格式
        env_vars: 可选的环境变量字典
        global_vars: 可选的全局变量字典
        encoding: 可选的编码，默认自动检测

    Returns:
        pytest.mark.parametrize 装饰器

    Example:
        # data/params/login_data.yaml
        # - description: 正常登录
        #   username: testuser
        #   password: Test123456
        #   expected_code: 200

        @parametrize_data("data/params/login_data.yaml")
        def test_login(username, password, expected_code):
            assert response.status_code == expected_code

        # 使用变量替换
        # - description: 生成手机号登录
        #   username: {{phone}}
        #   expected_code: 200
    """
    # 解析文件路径（相对于项目根目录）
    project_root = Path(__file__).parent.parent
    file_path = project_root / data_file

    # 加载数据
    if not file_path.exists():
        raise FileNotFoundError(f"数据文件不存在: {file_path}")

    raw_data = DataLoader.load(str(file_path))

    # 初始化变量替换器
    replacer = VariableReplacer()

    # 设置环境变量
    if env_vars:
        replacer.set_environment_vars(env_vars)
    else:
        # 尝试从环境配置加载
        replacer.set_environment_vars({})

    # 设置全局变量
    if global_vars:
        replacer.set_global_vars(global_vars)
    else:
        # 尝试从全局变量加载
        replacer.set_global_vars({})

    # 替换变量
    processed_data = [replacer.replace(item) for item in raw_data]

    # 构建参数化数据
    if not processed_data:
        raise ValueError(f"数据文件为空: {data_file}")

    # 获取所有参数键
    param_keys = list(processed_data[0].keys())

    # 构建参数化数据列表
    param_values = []
    for item in processed_data:
        param_tuple = tuple(item.get(key) for key in param_keys)
        param_values.append(param_tuple)

    # 返回 pytest.mark.parametrize 装饰器
    return pytest.mark.parametrize(
        argnames=','.join(param_keys),
        argvalues=param_values,
    )


def load_data(
    data_file: str,
    env_vars: Optional[Dict[str, Any]] = None,
    global_vars: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """加载并处理测试数据

    与 parametrize_data 不同，此函数返回处理后的数据列表，
    不会自动创建 parametrize 装饰器。

    Args:
        data_file: 数据文件路径
        env_vars: 可选的环境变量字典
        global_vars: 可选的全局变量字典

    Returns:
        处理后的数据列表

    Example:
        data = load_data("data/params/login_data.yaml")
        for item in data:
            print(item['username'])
    """
    project_root = Path(__file__).parent.parent
    file_path = project_root / data_file

    if not file_path.exists():
        raise FileNotFoundError(f"数据文件不存在: {file_path}")

    raw_data = DataLoader.load(str(file_path))

    replacer = VariableReplacer()
    replacer.set_environment_vars(env_vars or {})
    replacer.set_global_vars(global_vars or {})

    return [replacer.replace(item) for item in raw_data]


def get_builtin_functions() -> Dict[str, Any]:
    """获取内置函数列表

    Returns:
        内置函数名称到函数的映射字典
    """
    replacer = VariableReplacer()
    return replacer._get_builtin_functions().copy()
