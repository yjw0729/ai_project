from random import choice
import random
from utils.auto_generate import areas
from datetime import datetime, timedelta
import string


def create_identity_card(type='') -> str:
    '''
    生成随机身份证号
    :param type:->0:居民身份证  类型 1 (台湾居住证(中国台湾居民)): 58392617
类型 2 (来往大陆通行证(中国台湾居民)): 74018235
类型 3 (港澳居住证(中国港澳居民)): 820000198504152815
类型 4 (来往内地通行证(中国港澳居民)): H92647381
类型 5 (护照(其他国家或地区居民)): AB740628
类型 6 (外国人永久居留身份证(其他国家或地区居民)): J62847501928374651
类型 7 (来往内地通行证(非中国籍)): XD5928374
    :return:
    '''
    # eqlogger.info('[传入参数：' + birthday + ']---显示输出')
    if type == '' or type =='0':
        area_num = choice(areas.area_num)
        year = ['1975', '1976', '1977', '1978', '1979', '1980', '1981', '1982', '1983', '1984',
                '1985', '1986', '1987', '1988', '1989', '1990', '1991', '1992', '1993', '1994'
                ]
        year_number = choice(year)
        month = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
        day = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17',
               '18', '19',
               '20', '21', '22', '23', '24', '25', '26', '27', '28']
        month_number = choice(month)
        day_number = choice(day)
        # 出生的年月日
        medile = year_number + month_number + day_number
        shunxuma = str(random.randint(100, 999))

        code = str((int(area_num[0:1]) * 7 + int(area_num[1:2]) * 9 + int(
            area_num[2:3]) * 10 + int(area_num[3:4]) * 5 +
                    int(area_num[4:5]) * 8 + int(area_num[5:6]) * 4 + int(year_number[0:1]) * 2 + int(
                    year_number[1:2]) * 1 + int(year_number[2:3]) * 6 +
                    int(year_number[3:4]) * 3 + int(month_number[0:1]) * 7 + int(month_number[1:2]) * 9 + int(
                    day_number[0:1]) * 10 + int(day_number[1:2]) * 5 +
                    int(shunxuma[0:1]) * 8 + int(shunxuma[1:2]) * 4 + int(shunxuma[2:3]) * 2) % 11)
        if code == "0":
            code_number = "1"
        elif code == "1":
            code_number = "0"
        elif code == "2":
            code_number = "X"
        elif code == "3":
            code_number = "9"
        elif code == "4":
            code_number = "8"
        elif code == "5":
            code_number = "7"
        elif code == "6":
            code_number = "6"
        elif code == "7":
            code_number = "5"
        elif code == "8":
            code_number = "4"
        elif code == "9":
            code_number = "3"
        elif code == "10":
            code_number = "2"
        ID_number = area_num + medile + shunxuma + code_number
        return ID_number
    elif type == '1' or type == '2':
        return ''.join(random.choices('0123456789', k=8))
    elif type == '3':
        region = random.choice(['810000', '820000'])
        # 出生日期(1950-2010)
        birth_date = datetime.now() - timedelta(days=random.randint(365 * 20, 365 * 70))
        birth_str = birth_date.strftime('%Y%m%d')
        # 顺序码(3位) + 性别码(1位)
        sequence = ''.join(random.choices('0123456789', k=3))
        gender = random.choice(['1', '2'])  # 1男, 2女
        # 校验码(1位)
        check_code = random.choice('0123456789X')
        return region + birth_str + sequence + gender + check_code
    elif type == '4':
        prefix = random.choice(['H', 'M'])  # H:香港, M:澳门
        return prefix + ''.join(random.choices('0123456789', k=8))
    elif type == '5':
        prefix = ''.join(random.choices(string.ascii_uppercase, k=random.randint(1, 2)))
        digits = ''.join(random.choices('0123456789', k=random.randint(5, 7)))
        return prefix + digits
    elif type == '6':
        return 'J' + ''.join(random.choices('0123456789', k=17))
    elif type == '7':
        prefix = ''.join(random.choices(string.ascii_uppercase, k=random.randint(1, 2)))
        digits = ''.join(random.choices('0123456789', k=random.randint(5, 7)))
        return prefix + digits
    else:
        raise ValueError("无效的证件类型")

