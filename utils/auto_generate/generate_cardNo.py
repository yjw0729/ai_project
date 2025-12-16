import random
from random import choice


def create_card_no(bank_name = '')->str:
    '''
    随机生成银行卡号,入参中
    :param bank:
    :return:
    '''
    if bank_name == '' or len(bank_name) < 6:
        title = '621226'
    else:
        title = bank_name

    random_digits = ''.join(random.choices('0123456789', k = 10))
    return title + random_digits


