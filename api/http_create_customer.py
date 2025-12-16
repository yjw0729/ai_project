from flask import request, Blueprint
from utils.read_config_path.read_app_dir import get_xml_path, read_xml
from utils.auto_generate.generate_customer import create_customer_information

#设置文件路由
generate_information_opt = Blueprint('generate_information_opt', __name__)
root_path = read_xml(get_xml_path(), 'root_path')


@generate_information_opt.route('/create_customer_information', methods= ['POST'])
def create_customer_information():
    get_json = request.get_json()
    customerType = get_json['customerType']
    personType = get_json['personType']
    customer_information = create_customer_information(customerType=customerType, personType=personType)
    response = {
        'code': 200,
        'message': '商户信息生成完成',
        'data': customer_information
    }

    return response