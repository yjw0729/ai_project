import os
from PIL import Image, ImageDraw, ImageFont
from utils.read_config_path.read_app_dir import read_xml, get_xml_path


def check_card_number(card_name:str)->bool:
    '''
    输入的证件名称校验
    :param card_name:
    :return:
    '''
    if len(card_name) == 0 or len(card_name) < 2:
        return False
    return True


def check_user_card_input(card_number:str)->bool:
    '''
    输入的证件号码校验
    :param card_number:
    :return:
    '''
    if len(card_number) == 0 or len(card_number) < 18:
        return False
    return True


def cv2_pil_add_text(card_name:str, card_number:str, img_type:str):
    '''
    图片绘制，预期是根据传入的img_type进行绘制不同类型的图片信息
    :param card_name:
    :param card_number:
    :param img_type:shenfenzheng
    :return:
    '''
    root_path = read_xml(get_xml_path(), 'root_path').rstrip('/')
    deno_front_path = read_xml(get_xml_path(), 'identity_card_img') + img_type
    print(deno_front_path)
    im = Image.open(deno_front_path + '/demo-front.png')
    draw = ImageDraw.Draw(im)
    song_ttf = root_path + '/docs/ttf/song.ttf'
    cu_ttf = root_path + '/docs/ttf/cu.otf'
    fnt_song = ImageFont.truetype(song_ttf, 26)
    fnt_hei = ImageFont.truetype(cu_ttf, 25)

  # 绘制姓名
    # 起始位置
    name_left, name_top = 140, 56
    # 逐个字绘制
    for n in card_name:
        # 绘制
        draw.text((name_left, name_top), n, fill='black', font=fnt_song)
        # 增加字间距
        name_left = name_left + 28

    # 绘制号码
    # 起始位置
    num_left, num_top = 200, 346
    # 逐个字绘制
    for s in card_number:
        # 绘制
        draw.text((num_left, num_top), s, fill='black', font=fnt_hei)
        # 增加字间距
        num_left = num_left + 19

    save_path = root_path + '/docs/static/out_identity_img/'
    if not os.path.exists(save_path):
        os.makedirs(save_path)
    # 保存绘制的图片
    im_rgb = im.convert('RGB')
    im_rgb.save(save_path + card_number + '.jpg')
    return save_path + card_number + '.jpg'


if __name__ == '__main__':
    cv2_pil_add_text('呵呵', '11000520221225152X', 'shenfenzheng')