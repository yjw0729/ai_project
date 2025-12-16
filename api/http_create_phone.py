from flask import request, Blueprint
from utils.auto_generate.generate_phone import create_phone_no
from utils.read_config_path.read_app_dir import read_xml, get_xml_path

#设置文件路由
create_phone_opt =Blueprint('create_phone_opt', __name__)
# 从XML配置文件中读取名为'root_path'的配置项的值
root_path = read_xml(get_xml_path(), 'root_path')


@create_phone_opt.route('/create_phone', methods = ['POST'])
def create_phone():
    phone = create_phone_no()
    response = {
        'code': 200,
        'message': '手机号生成完成',
        'data': {
            'bankcard_no': phone
        }
    }
    return response


