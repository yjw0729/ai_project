import random
from random import choice
from typing import Dict
from utils.auto_generate.generate_idcardno import create_identity_card
from utils.auto_generate.generate_address import generate_address
from utils.auto_generate.generate_bussiness_license import generate_organization_code, generate_business_license, generate_simple_15digit_license


def create_name()->str:
    '''
    生成个人姓名
    :return:
    '''
    # 常见姓氏列表
    surnames = ['李', '王', '张', '刘', '陈', '杨', '赵', '黄', '周', '吴',
                '徐', '孙', '胡', '朱', '高', '林', '何', '郭', '马', '罗',
                '梁', '宋', '郑', '谢', '韩', '唐', '冯', '于', '董', '萧']

    # 名字常用字列表
    given_name_chars = ['伟', '芳', '娜', '秀英', '敏', '静', '丽', '强', '磊', '军',
                        '洋', '勇', '艳', '杰', '娟', '涛', '明', '超', '秀兰', '霞',
                        '平', '刚', '桂英', '文', '华', '建', '红', '梅', '鹏', '金']
    surname = choice(surnames)
    name = choice(surnames)

    return surname + name


def creare_company_name()->str:
    '''
    生成公司名称
    :return:
    '''
    # 地域部分
    regions = ['北京', '上海', '广州', '深圳', '杭州', '南京', '成都', '重庆', '武汉', '西安',
               '天津', '苏州', '郑州', '长沙', '青岛', '厦门', '宁波', '无锡', '佛山', '东莞']

    # 字号部分（2-3个字）
    prefixes = ['华', '创', '联', '智', '云', '腾', '博', '宏', '鑫', '信',
                '恒', '达', '通', '盛', '嘉', '天', '宇', '海', '瑞', '新',
                '中', '国', '东', '方', '金', '银', '科', '技', '数', '字',
                '易', '优', '聚', '众', '星', '光', '顶', '峰', '领', '航']

    # 行业部分
    industries = ['科技', '信息', '网络', '数据', '软件', '智能', '电子', '通信', '互联网',
                  '数字', '云计算', '人工智能', '物联网', '区块链', '生物', '医药', '健康',
                  '环保', '能源', '材料', '制造', '机械', '工程', '建筑', '设计', '咨询',
                  '管理', '金融', '投资', '证券', '保险', '银行', '信托', '租赁', '商贸',
                  '物流', '供应链', '零售', '电商', '文化', '传媒', '教育', '培训', '旅游',
                  '餐饮', '食品', '农业', '地产', '物业', '服务', '广告', '创意']

    # 组织形式
    structures = ['有限公司', '有限责任公司', '股份有限公司', '集团有限公司',
                  '科技发展有限公司', '信息技术有限公司', '控股有限公司']

    # 随机组合
    region = random.choice(regions) if random.random() > 0.3 else ""  # 70%概率包含地域
    prefix = ''.join(random.sample(prefixes, random.randint(2, 3)))  # 2-3个字
    industry = random.choice(industries)
    structure = random.choice(structures)

    return f"{region}{prefix}{industry}{structure}"


def create_time(type:str)->str:
    '''
    随机生成时间
    :param type: 1-开始时间，2-结束时间 3-长期
    :return: 时间格式yyyy-mm-dd
    '''
    if type == '1' or type == '2':
        year = ['1990', '1991', '1992', '1993', '1994', '1995', '2000', '2001', '2002', '2003']
        month = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
        data = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28']
        return choice(year) + choice(month) +choice(data)
    elif type == '3':
        return '长期'


def create_email():
    '''
    生成email邮箱号
    :return:
    '''
    return ''.join(random.choices('0123456789', k=8)) + '@163.com'


def create_customer_information(customerType:str, personType:str)->Dict:
    '''
    根据输入的customerType生成指定类型的商户信息
    :param customerType: 00：个人，01-企业，02-个体工商户，03-15位营业执照号信息
    :param personType: 0:居民身份证，1：台湾居住证(中国台湾居民)，2：来往大陆通行证(中国台湾居民)，3：港澳居住证(中国港澳居民)
                    4:来往内地通行证(中国港澳居民) 5:护照(其他国家或地区居民) 6:外国人永久居留身份证(其他国家或地区居民) 7:来往内地通行证(非中国籍)
    :return:返回信息list
    企业&个体->return {
        "企业名称": company_name,
        "统一社会信用代码": credit_code,
        "法定代表人": legal_person,
        "法人身份证号"：“legal_person_number”
        “法人有效期-开始时间”：“legal_start_time”
        “法人有效期-结束时间”：“legal_end_time”
        "注册资本": f"{registered_capital}万元",
        "注册日期": established_date_str,
        "注册地址": address,
        "企业类型": company_type,
        "邮箱": email,
        "官网": website
    }
    个人->return {
        "name": "张三",
        "id_card_number": "110101199001011234",
        "id_card_start_date": "2010-01-01",
        "id_card_expiry_date": "2030-01-01",
        "address": "北京市朝阳区某某街道123号"
    }
    15位营业执照号-> return {
        "business_license_number": "123456789012345",  # 15位营业执照号
        "tax_registration_number": "987654321098765",  # 税务登记号
        "organization_info": {
            "org_code": "12345678-9",  # 组织机构代码（9位）
            "org_name": "某某科技有限公司",
            "org_type": "有限责任公司",
            "registration_authority": "北京市工商行政管理局"
        },
        "legal_representative": {
            "name": "张三",
            "id_card_number": "110101199001011234",
            "id_card_start_date": "2010-01-01",
            "id_card_expiry_date": "2030-01-01"
        },
        "registration_info": {
            "registered_capital": "1000万元人民币",
            "establishment_date": "2015-06-15",
            "business_scope": "技术开发、技术服务、技术咨询；软件开发；销售计算机软硬件及辅助设备",
            "business_address": "北京市海淀区中关村大街1号"
        }
    }
    '''
    try:
        if customerType == '00':
            name = create_name()
            id_card_number = create_identity_card(personType)
            id_card_start_date = create_time('1')
            id_card_expiry_date = create_time(choice('23'))
            address = generate_address()
            return {
                "legal_representative": {
                    "name": name,
                    "id_card_number" : id_card_number,
                    "id_card_start_date": id_card_start_date,
                    "id_card_expiry_date": id_card_expiry_date,
                    "address" : address
                }
            }
        elif customerType == '01' or customerType == '02':
            company_name = creare_company_name()
            credit_code = generate_business_license()
            legal_person = create_name()
            legal_person_number = create_identity_card(personType)
            id_card_start_date = create_time('1')
            id_card_expiry_date = create_time(choice('23'))
            registered_capital = str(random.randint(100000000, 3000000000))
            address = generate_address()
            company_type = choice((['有限公司', '有限责任公司', '股份有限公司', '集团有限公司',
                  '科技发展有限公司', '信息技术有限公司', '控股有限公司']))
            email = create_email()

            return {
                "legal_representative": {
                    "name": legal_person,
                    "id_card_number" : legal_person_number,
                    "id_card_start_date": id_card_start_date,
                    "id_card_expiry_date": id_card_expiry_date
                },
                "registration_info": {
                    "企业名称": company_name,
                    "统一社会信用代码": credit_code,  # 15位营业执照号
                    "注册日期": id_card_start_date,
                    "企业类型": company_type,
                    "邮箱": email,
                    "官网": "www.ceshi.com",
                    "registered_capital": f"{registered_capital}万元",
                    "establishment_date": id_card_start_date,
                    "business_scope": "技术开发、技术服务、技术咨询；软件开发；销售计算机软硬件及辅助设备",
                    "business_address": address
                }
            }
        elif customerType == '03':
            company_name = creare_company_name()
            credit_code = generate_simple_15digit_license()
            legal_person = create_name()
            legal_person_number = create_identity_card(personType)
            id_card_start_date = create_time('1')
            id_card_expiry_date = create_time(choice('23'))
            registered_capital = str(random.randint(100000000, 3000000000))
            address = generate_address()
            company_type = choice((['有限公司', '有限责任公司', '股份有限公司', '集团有限公司',
                                    '科技发展有限公司', '信息技术有限公司', '控股有限公司']))
            email = create_email()
            tax_registration_number = generate_organization_code()

            return {
                "tax_registration_number": credit_code,  # 税务登记号
                "organization_info": {
                    "org_code": tax_registration_number,  # 组织机构代码（9位）
                    "org_name": "某某科技有限公司",
                    "org_type": "有限责任公司",
                    "registration_authority": "北京市工商行政管理局"
                },
                "legal_representative": {
                    "name": legal_person,
                    "id_card_number" : legal_person_number,
                    "id_card_start_date": id_card_start_date,
                    "id_card_expiry_date": id_card_expiry_date
                },
                "registration_info": {
                    "企业名称": company_name,
                    "统一社会信用代码": credit_code,  # 15位营业执照号
                    "注册日期": id_card_start_date,
                    "企业类型": company_type,
                    "邮箱": email,
                    "官网": "www.ceshi.com",
                    "registered_capital": f"{registered_capital}万元",
                    "establishment_date": id_card_start_date,
                    "business_scope": "技术开发、技术服务、技术咨询；软件开发；销售计算机软硬件及辅助设备",
                    "business_address": address
                }
            }
    except:
        raise ValueError('生成资质信息时，类型有误')


if __name__ == '__main__':
    print(create_customer_information(customerType='00', personType='0'))
    print(create_name())
    print(creare_company_name())
    print(create_identity_card())
    print(create_time('1'))
    print(create_email())