from common.csv_function.read_date_from_yaml import YamlTestCaseParser


def main():
    """主函数示例"""
    # 您的YAML文件路径
    yaml_file_path = r"D:\pythonProject\pytest_sxp\data\yaml_case\XM_BATCH_PAY.yaml"

    # 创建解析器实例
    parser = YamlTestCaseParser(yaml_file_path)

    # yaml文件接口入参处理
    result = parser.strate_processing()

    # 返回结果（不保存到文件）
    return result


if __name__ == "__main__":
    # 运行演示
    result = main()

    print("\n" + "=" * 60)
    print("处理完成！结果已返回，可以直接在代码中使用")
    print("=" * 60)

'''
对于解决这个问题，我们需要做好积极发展与合理规制相结合，一方面要“鼓起劲”，积极发散正向发展思维，

'''

