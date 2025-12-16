import random
import string


def generate_business_license():
    """
    随机生成营业执照号（18位统一社会信用代码）
    格式：登记管理部门代码(1位) + 机构类别代码(1位) + 登记管理机关行政区划码(6位) +
          主体标识码(9位) + 校验码(1位)
    """
    # 1. 登记管理部门代码（工商部门为9）
    dept_code = "9"

    # 2. 机构类别代码（1-企业，2-个体工商户，3-农民专业合作社）
    org_type = random.choice(["1", "2", "3"])

    # 3. 登记管理机关行政区划码（6位数字）
    # 使用常见的行政区划代码前缀
    region_codes = [
        "110000",  # 北京市
        "120000",  # 天津市
        "130000",  # 河北省
        "140000",  # 山西省
        "150000",  # 内蒙古自治区
        "210000",  # 辽宁省
        "220000",  # 吉林省
        "230000",  # 黑龙江省
        "310000",  # 上海市
        "320000",  # 江苏省
        "330000",  # 浙江省
        "340000",  # 安徽省
        "350000",  # 福建省
        "360000",  # 江西省
        "370000",  # 山东省
        "410000",  # 河南省
        "420000",  # 湖北省
        "430000",  # 湖南省
        "440000",  # 广东省
        "450000",  # 广西壮族自治区
        "460000",  # 海南省
        "500000",  # 重庆市
        "510000",  # 四川省
        "520000",  # 贵州省
        "530000",  # 云南省
        "540000",  # 西藏自治区
        "610000",  # 陕西省
        "620000",  # 甘肃省
        "630000",  # 青海省
        "640000",  # 宁夏回族自治区
        "650000",  # 新疆维吾尔自治区
        "810000",  # 香港特别行政区
        "820000",  # 澳门特别行政区
    ]
    region_code = random.choice(region_codes)

    # 4. 主体标识码（9位，通常是组织机构代码）
    # 组织机构代码格式：8位数字/字母 + 1位校验码
    org_code = generate_organization_code()

    # 5. 校验码（1位，根据前17位计算得出）
    first_17 = dept_code + org_type + region_code + org_code
    check_code = calculate_check_code(first_17)

    # 组合成完整的18位统一社会信用代码
    business_license = first_17 + check_code

    return business_license


def generate_organization_code():
    """
    生成9位组织机构代码（8位主体代码 + 1位校验码）
    """
    # 前8位：3位字母/数字 + 5位数字（常见格式）
    chars = string.ascii_uppercase + string.digits

    # 第1-3位：字母或数字
    part1 = ''.join(random.choices(chars, k=3))

    # 第4-8位：数字
    part2 = ''.join(random.choices(string.digits, k=5))

    first_8 = part1 + part2

    # 计算第9位校验码
    check_code = calculate_org_check_code(first_8)

    return first_8 + check_code


def calculate_org_check_code(first_8):
    """
    计算组织机构代码的校验码
    权重因子：3, 7, 9, 10, 5, 8, 4, 2
    """
    weights = [3, 7, 9, 10, 5, 8, 4, 2]
    check_chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    total = 0
    for i, char in enumerate(first_8):
        # 将字符转换为对应的数值（A=10, B=11, ..., Z=35）
        if char.isdigit():
            value = int(char)
        else:
            value = 10 + (ord(char) - ord('A'))

        total += value * weights[i]

    remainder = total % 11
    check_index = (12 - remainder) % 11

    if check_index == 10:
        return 'X'
    elif check_index == 11:
        return '0'
    else:
        return str(check_index)


def calculate_check_code(first_17):
    """
    计算统一社会信用代码的校验码（第18位）
    权重因子：[1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28]
    """
    weights = [1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28]
    check_chars = "0123456789ABCDEFGHJKLMNPQRTUWXY"

    total = 0
    for i, char in enumerate(first_17):
        # 将字符转换为对应的数值
        if char.isdigit():
            value = int(char)
        else:
            # A=10, B=11, ..., Z=35
            value = 10 + (ord(char) - ord('A'))

        total += value * weights[i]

    remainder = total % 31
    check_index = (31 - remainder) % 31

    return check_chars[check_index]


def generate_multiple_licenses(count=5):
    """
    生成多个营业执照号并显示详细信息
    """
    licenses = []

    org_type_names = {
        "1": "企业",
        "2": "个体工商户",
        "3": "农民专业合作社"
    }

    for _ in range(count):
        license_num = generate_business_license()

        # 解析营业执照号各部分
        dept_code = license_num[0]  # 登记管理部门代码
        org_type = license_num[1]  # 机构类别代码
        region_code = license_num[2:8]  # 行政区划码
        org_code = license_num[8:17]  # 组织机构代码
        check_code = license_num[17]  # 校验码

        licenses.append({
            "license_number": license_num,
            "department_code": dept_code,
            "organization_type": org_type,
            "organization_type_name": org_type_names[org_type],
            "region_code": region_code,
            "organization_code": org_code,
            "check_code": check_code
        })

    return licenses


def generate_simple_15digit_license():
    """
    简化版：随机生成15位营业执照号
    格式：6位行政区划代码 + 1位企业类型 + 8位随机数字
    """
    # 常见行政区划代码（前6位）
    region_codes = [
        "110000", "120000", "130000", "140000", "150000",  # 北京、天津、河北、山西、内蒙古
        "210000", "220000", "230000",  # 辽宁、吉林、黑龙江
        "310000", "320000", "330000", "340000", "350000",  # 上海、江苏、浙江、安徽、福建
        "360000", "370000",  # 江西、山东
        "410000", "420000", "430000", "440000", "450000", "460000",  # 河南、湖北、湖南、广东、广西、海南
        "500000", "510000", "520000", "530000", "540000",  # 重庆、四川、贵州、云南、西藏
        "610000", "620000", "630000", "640000", "650000",  # 陕西、甘肃、青海、宁夏、新疆
    ]

    # 随机选择行政区划代码
    region_code = random.choice(region_codes)

    # 企业类型代码（1位）
    enterprise_type = random.choice(["1", "2", "3", "4"])

    # 生成8位随机数字
    random_digits = ''.join([str(random.randint(0, 9)) for _ in range(8)])

    # 组合成15位营业执照号
    license_number = region_code + enterprise_type + random_digits

    return license_number


