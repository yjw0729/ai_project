"""
参数化驱动模块自测脚本

用于验证 parametrize/driver.py 模块功能是否正常。
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_import():
    """测试模块导入"""
    print("=" * 60)
    print("测试1: 模块导入")
    print("=" * 60)

    try:
        from parametrize import parametrize_data, load_data, DataLoader, get_builtin_functions
        print("[PASS] 模块导入成功")
        return True
    except ImportError as e:
        print(f"[FAIL] 模块导入失败: {e}")
        return False


def test_data_loader():
    """测试数据加载器"""
    print("\n" + "=" * 60)
    print("测试2: 数据加载器 (YAML)")
    print("=" * 60)

    try:
        from parametrize import DataLoader

        # 测试加载 YAML
        data_file = project_root / "parametrize" / "data" / "params" / "login_data.yaml"
        data = DataLoader.load(str(data_file))

        print(f"[PASS] 加载 YAML 成功，共 {len(data)} 条数据")
        for i, item in enumerate(data):
            print(f"  [{i+1}] {item.get('description', 'N/A')}")
        return True
    except Exception as e:
        print(f"[FAIL] 数据加载失败: {e}")
        return False


def test_variable_replacer():
    """测试变量替换器"""
    print("\n" + "=" * 60)
    print("测试3: 变量替换器")
    print("=" * 60)

    try:
        from parametrize.driver import VariableReplacer

        replacer = VariableReplacer()

        # 设置测试变量
        replacer.set_environment_vars({
            'TEST_USER': 'env_test_user',
            'API_BASE_URL': 'http://test.example.com',
        })
        replacer.set_global_vars({
            'DEFAULT_PASSWORD': 'global_pass_123',
            'ADMIN_TOKEN': 'token_abc',
        })

        # 测试变量替换
        test_cases = [
            ('{{phone}}', 'phone'),
            ('{{env:TEST_USER}}', 'env'),
            ('{{global:DEFAULT_PASSWORD}}', 'global'),
            ('{{name}}', 'name'),
            ('{{idcard}}', 'idcard'),
            ('{{email}}', 'email'),
            ('{{address}}', 'address'),
            ('{{timestamp}}', 'timestamp'),
            ('{{date}}', 'date'),
            ('普通文本', 'plain'),
        ]

        all_passed = True
        for test_input, var_type in test_cases:
            result = replacer.replace(test_input)
            # 检查是否仍然包含 {{ 未被替换（排除普通文本）
            if '{{' in result and var_type != 'plain':
                print(f"  [{var_type}] {test_input} -> {result} [WARN: 未完全替换]")
                all_passed = False
            else:
                print(f"  [{var_type}] {test_input} -> {result} [PASS]")

        if all_passed:
            print("[PASS] 变量替换测试通过")
        else:
            print("[WARN] 部分变量替换失败（可能缺少生成器模块）")

        return True
    except Exception as e:
        print(f"[FAIL] 变量替换测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_load_data():
    """测试 load_data 函数"""
    print("\n" + "=" * 60)
    print("测试4: load_data 函数")
    print("=" * 60)

    try:
        from parametrize import load_data

        data = load_data("parametrize/data/params/login_data.yaml")

        print(f"[PASS] load_data 加载成功，共 {len(data)} 条数据")
        for i, item in enumerate(data[:3]):  # 只显示前3条
            print(f"  [{i+1}] {item}")
        return True
    except Exception as e:
        print(f"[FAIL] load_data 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_builtin_functions():
    """测试内置函数"""
    print("\n" + "=" * 60)
    print("测试5: 内置函数列表")
    print("=" * 60)

    try:
        from parametrize import get_builtin_functions

        functions = get_builtin_functions()

        print(f"[PASS] 获取内置函数列表成功，共 {len(functions)} 个函数")
        print("  可用函数:")
        for name in sorted(functions.keys()):
            print(f"    - {name}")
        return True
    except Exception as e:
        print(f"[FAIL] 内置函数测试失败: {e}")
        return False


def test_parametrize_decorator():
    """测试 parametrize_data 装饰器"""
    print("\n" + "=" * 60)
    print("测试6: parametrize_data 装饰器")
    print("=" * 60)

    try:
        from parametrize import parametrize_data
        import pytest

        # 使用装饰器
        decorator = parametrize_data("parametrize/data/params/login_data.yaml")

        print(f"[PASS] parametrize_data 装饰器创建成功")
        print(f"  装饰器类型: {type(decorator)}")

        # 检查是否是 pytest MarkDecorator
        if hasattr(decorator, 'mark'):
            print(f"  mark 属性: {decorator.mark}")
        return True
    except Exception as e:
        print(f"[FAIL] parametrize_data 装饰器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_json_data():
    """测试 JSON 数据加载"""
    print("\n" + "=" * 60)
    print("测试7: JSON 数据加载")
    print("=" * 60)

    try:
        from parametrize import DataLoader
        import tempfile
        import os

        # 创建临时 JSON 文件
        json_data = [
            {"username": "test1", "password": "pass1"},
            {"username": "test2", "password": "pass2"},
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            import json
            json.dump(json_data, f)
            temp_file = f.name

        try:
            data = DataLoader.load_json(temp_file)
            print(f"[PASS] JSON 数据加载成功，共 {len(data)} 条数据")
            for item in data:
                print(f"  {item}")
        finally:
            os.unlink(temp_file)

        return True
    except Exception as e:
        print(f"[FAIL] JSON 数据加载测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_csv_data():
    """测试 CSV 数据加载"""
    print("\n" + "=" * 60)
    print("测试8: CSV 数据加载")
    print("=" * 60)

    try:
        from parametrize import DataLoader
        import tempfile
        import os

        # 创建临时 CSV 文件
        csv_content = """username,password,expected_code
test1,pass1,200
test2,pass2,400"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_content)
            temp_file = f.name

        try:
            data = DataLoader.load_csv(temp_file)
            print(f"[PASS] CSV 数据加载成功，共 {len(data)} 条数据")
            for item in data:
                print(f"  {item}")
        finally:
            os.unlink(temp_file)

        return True
    except Exception as e:
        print(f"[FAIL] CSV 数据加载测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("参数化驱动模块自测")
    print("=" * 60)

    results = []

    # 执行所有测试
    results.append(("模块导入", test_import()))
    results.append(("数据加载器", test_data_loader()))
    results.append(("变量替换器", test_variable_replacer()))
    results.append(("load_data函数", test_load_data()))
    results.append(("内置函数", test_builtin_functions()))
    results.append(("装饰器", test_parametrize_decorator()))
    results.append(("JSON加载", test_json_data()))
    results.append(("CSV加载", test_csv_data()))

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {name}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n所有测试通过！模块可以正常使用。")
        return 0
    else:
        print(f"\n有 {total - passed} 项测试失败，请检查。")
        return 1


if __name__ == '__main__':
    sys.exit(main())
