from flask import request, Blueprint
from utils.read_config_path.read_app_dir import read_xml, get_xml_path
from utils.auto_generate.generate_picture import cv2_pil_add_text

#设置文件路由
draw_picture_opt =Blueprint('draw_picture_opt', __name__)
# 从XML配置文件中读取名为'root_path'的配置项的值
root_path = read_xml(get_xml_path(), 'root_path')


@draw_picture_opt.route("/draw_picture", methods = ['POST'])
def create_bankcard_no():
    get_json = request.get_json()
    card_name = get_json['card_name']
    card_number = get_json['card_number']
    img_type = get_json['img_type']
    picture = cv2_pil_add_text(card_name=card_name, card_number=card_number, img_type=img_type)
    response = {
        'code': 200,
        'message': '图片生成完成',
        'data': {
            'bankcard_no': picture
        }
    }
    return response




