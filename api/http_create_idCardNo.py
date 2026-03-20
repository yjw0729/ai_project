from flask import request, Blueprint
from utils.read_config_path.read_app_dir import get_xml_path, read_xml
from utils.auto_generate.generate_idcardno import create_identity_card


#设置文件路由
generate_idCardNo_opt = Blueprint('generate_idCardNo_opt', __name__)
root_path = read_xml(get_xml_path(), 'root_path')


@generate_idCardNo_opt.route('/create_idCardNo', methods = ['POST'])
def created_idCardNo():
    get_json = request.get_json() or {}
    type = get_json.get('type', '0')
    id_cardNo = create_identity_card(type)
    response = {
        'code': 200,
        'message': '证件号生成完成',
        'data': {
            'id_card_no': id_cardNo
        }
    }

    return response
