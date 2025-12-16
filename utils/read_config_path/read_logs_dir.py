from os import getcwd as os_pwd, path as os_path, makedirs as os_mks
from platform import system as pl_system

# xml 读取工具
try:
    import xml.etree.cElementTree as XMLTree
except ImportError:
    import xml.etree.ElementTree as XMLTree


def get_xml_path(filename='eqlog.xml'):
    """
    配置文件读取
    :return: 配置文件地址
    """
    xml_path = os_pwd() + '/' + filename
    if os_path.exists(xml_path):
        pass
    else:
        xml_path = os_pwd() + '/eqconfig/' + filename
        if os_path.exists(xml_path):
            pass
        else:
            xml_path = os_path.abspath(os_path.join(os_pwd(), "..")) + '/' + filename
            if os_path.exists(xml_path):
                pass
            else:
                xml_path = os_path.abspath(os_path.join(os_pwd(), "..")) + '/eqconfig/' + filename
                if os_path.exists(xml_path):
                    pass
                else:
                    xml_path = os_path.abspath(os_path.join(os_pwd(), "../..")) + '/' + filename
                    if os_path.exists(xml_path):
                        pass
                    else:
                        xml_path = os_path.abspath(os_path.join(os_pwd(), "../..")) + '/eqconfig/' + filename
                        if os_path.exists(xml_path):
                            pass
                        else:
                            xml_path = ''
    # 返回 xml 文件路径
    return xml_path


def read_xml(xml_path):
    """
    配置文件信息读取
    :param xml_path: 配置文件路径
    :return: 初期只有路径地址
    """
    result = ''
    if xml_path != '':
        try:
            xml_tree = XMLTree.parse(xml_path)  # 打开xml文档
            xml_root = xml_tree.getroot()  # 获得root节点
            if pl_system().lower() == 'windows':  # windows
                result = xml_root.find('file_path').find('win_path').text
            elif pl_system().lower() == 'linux':  # linux
                result = xml_root.find('file_path').find('linux_path').text
            else:  # other
                result = xml_root.find('file_path').find('linux_path').text
        except Exception as e:
            print(str(e))
    # 返回日志文件解析结果
    return result


def create_log_file(modules='app_flask'):
    """
    创建日志文件
    :param modules: 日志模块名称
    :return: None
    """
    file_name = read_xml(get_xml_path()) + modules + '.log'
    print(file_name)
    # 判断日志路径是否存在
    if not os_path.exists(os_path.dirname(file_name)):
        try:
            os_mks(os_path.dirname(file_name))
        except FileExistsError as e:
            print(str(e))

    # 判断日志文件是否存在
    if not os_path.exists(file_name):
        try:
            f = open(file_name, 'w')
            f.close()
        except AttributeError as e:
            print(str(e))
    return file_name
