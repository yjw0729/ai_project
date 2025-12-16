import random
from random import choices,choice


def create_phone_no()->str:
    '''
    随机生成手机号信息
    :return:
    '''
    title_list = ['134', '135', '136', '137', '138', '139', '147', '148', '150', '151', '152', '157', '158', '159',
                  '172', '178', '182', '183', '184', '187', '188', '198', '130', '131', '132', '145', '146', '155',
                  '156', '166', '171', '175', '176', '185', '186']
    phone = choice(title_list) + ''.join(choices('0123456789', k=8))

    return phone

