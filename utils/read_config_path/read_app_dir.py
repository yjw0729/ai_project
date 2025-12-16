from os import getcwd as os_pwd, path as os_path
from platform import system as pl_system

# xml 读取工具
try:
    import xml.etree.cElementTree as XMLTree
except ImportError:
    import xml.etree.ElementTree as XMLTree


def get_xml_path(file_name='application.xml'):
    '''
    xml文件的读取
    :param file_name:
    :return:
    '''
    xml_path = os_pwd() + '/' + file_name
    if os_path.exists(xml_path):
        pass
    else:
        xml_path = os_pwd() + '/app/' + file_name
        if os_path.exists(xml_path):
            pass
        else:
            xml_path = os_path.abspath(os_path.join(os_pwd(), '..')) + '/' + file_name
            if os_path.exists(xml_path):
                pass
            else:
                xml_path = os_path.abspath(os_path.join(os_pwd(), "..")) + '/app/' + file_name
                if os_path.exists(xml_path):
                    pass
                else:
                    xml_path = os_path.abspath(os_path.join(os_pwd(), "../..")) + '/' + file_name
                    if os_path.exists(xml_path):
                        pass
                    else:
                        xml_path = os_path.abspath(os_path.join(os_pwd(), "../..")) + '/app/' + file_name
                        if os_path.exists(xml_path):
                            pass
                        else:
                            xml_path = ''
    # 返回 xml 文件路径
    return xml_path


def read_xml(xml_path='', dir_type='mock_out_path'):
    """
    配置文件信息读取
    :param xml_path: 配置文件路径
    :param dir_type: 配置文件类型 mock_out_path-输出目录，mock_model_path-模板目录
    :return: 初期只有路径地址
    """
    result = ''
    if xml_path != '':
        try:
            xml_tree = XMLTree.parse(xml_path)  # 打开xml文档
            xml_root = xml_tree.getroot()  # 获得root节点
            if pl_system().lower() == 'windows':  # windows
                result = xml_root.find(dir_type).find('win_path').text
            elif pl_system().lower() == 'linux':  # linux
                result = xml_root.find(dir_type).find('linux_path').text
            else:  # other
                result = xml_root.find(dir_type).find('linux_path').text
        except Exception as e:
            print(str(e))
    # 返回日志文件解析结果
    return result
