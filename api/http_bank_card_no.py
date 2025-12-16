from flask import request, Blueprint
from utils.auto_generate.generate_cardNo import create_card_no
from utils.read_config_path.read_app_dir import read_xml, get_xml_path

#设置文件路由
bankcard_number_opt =Blueprint('bankcard_number_opt', __name__)
# 从XML配置文件中读取名为'root_path'的配置项的值
root_path = read_xml(get_xml_path(), 'root_path')


@bankcard_number_opt.route("/create_card_no", methods = ['POST'])
def create_bankcard_no():
    get_json = request.get_json()
    bankname = get_json['bank_name']
    bank_card_no = create_card_no(bankname)
    response = {
        'code': 200,
        'message': '银行卡号生成完成',
        'data': {
            'bankcard_no': bank_card_no
        }
    }
    return response




