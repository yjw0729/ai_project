from flask import request, Blueprint
from utils.auto_generate.generate_address import generate_address
from utils.read_config_path.read_app_dir import get_xml_path, read_xml

#设置文件路由
generate_address_opt = Blueprint('generate_address_opt', __name__)
root_path = read_xml(get_xml_path(), 'root_path')

@generate_address_opt.route('/create_address', methods = ['POST'])
def create_address():
    address = generate_address()
    response = {
        'code': 200,
        'message': '地址生成完成',
        'data': {
            'bankcard_no': address
        }
    }


    return response

