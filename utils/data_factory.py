"""
DataFactoryService 测试数据工厂服务

负责生成各类测试数据。
"""

import uuid
import random
import string
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class DataFactoryService:
    """测试数据工厂服务"""

    # 常用姓氏和名字
    _SURNAMES = ['张', '王', '李', '赵', '刘', '陈', '杨', '黄', '周', '吴',
                 '徐', '孙', '胡', '朱', '高', '林', '何', '郭', '马', '罗']
    _NAMES = ['伟', '芳', '娜', '秀英', '敏', '静', '丽', '强', '磊', '军',
              '洋', '勇', '艳', '杰', '涛', '明', '超', '秀兰', '霞', '平']

    # 省份简称
    _PROVINCE_CODES = ['京', '沪', '粤', '浙', '苏', '川', '鲁', '豫', '鄂', '湘']

    def __init__(self):
        """初始化数据工厂"""
        self._generators: Dict[str, callable] = {
            'uuid': self._gen_uuid,
            'name': self._gen_name,
            'chinese_name': self._gen_chinese_name,
            'email': self._gen_email,
            'phone': self._gen_phone,
            'id_card': self._gen_id_card,
            'int': self._gen_int,
            'float': self._gen_float,
            'str': self._gen_str,
            'bool': self._gen_bool,
            'date': self._gen_date,
            'datetime': self._gen_datetime,
            'enum': self._gen_enum,
            'bank_card': self._gen_bank_card,
            'address': self._gen_address,
        }

    def generate(
        self,
        data_type: str,
        count: int = 1,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        生成测试数据

        Args:
            data_type: 数据类型（user/order/payment/custom）
            count: 生成数量
            params: 额外参数

        Returns:
            生成的测试数据列表
        """
        params = params or {}
        logger.info(f"生成测试数据: type={data_type}, count={count}")

        try:
            if data_type == 'custom':
                return self._generate_custom(params, count)
            elif data_type == 'user':
                return self._generate_users(count, params)
            elif data_type == 'order':
                return self._generate_orders(count, params)
            elif data_type == 'payment':
                return self._generate_payments(count, params)
            elif data_type == 'address':
                return self._generate_addresses(count, params)
            else:
                logger.warning(f"未知数据类型: {data_type}，使用自定义生成")
                return self._generate_custom(params, count)

        except Exception as e:
            logger.error(f"数据生成失败: {e}")
            return []

    def _generate_users(self, count: int, params: Dict) -> List[Dict[str, Any]]:
        """生成用户数据"""
        users = []
        for i in range(count):
            users.append({
                'user_id': str(uuid.uuid4()),
                'username': self._gen_str(prefix='user_', length=12),
                'name': self._gen_chinese_name(),
                'email': self._gen_email(),
                'phone': self._gen_phone(),
                'id_card': self._gen_id_card(),
                'age': random.randint(18, 80),
                'status': random.choice(['active', 'inactive', 'pending']),
                'created_at': self._gen_datetime(),
            })
        return users

    def _generate_orders(self, count: int, params: Dict) -> List[Dict[str, Any]]:
        """生成订单数据"""
        orders = []
        statuses = ['pending', 'paid', 'shipped', 'completed', 'cancelled', 'refunded']
        for i in range(count):
            order_id = f"ORD{datetime.now().strftime('%Y%m%d')}{random.randint(100000, 999999)}"
            orders.append({
                'order_id': order_id,
                'user_id': str(uuid.uuid4()),
                'amount': round(random.uniform(0.01, 99999.99), 2),
                'currency': 'CNY',
                'status': random.choice(statuses),
                'created_at': self._gen_datetime(),
                'paid_at': self._gen_datetime() if random.random() > 0.3 else None,
            })
        return orders

    def _generate_payments(self, count: int, params: Dict) -> List[Dict[str, Any]]:
        """生成支付数据"""
        payments = []
        methods = ['alipay', 'wechat', 'bank_card', 'credit_card']
        statuses = ['pending', 'success', 'failed', 'refunded']
        for i in range(count):
            payments.append({
                'payment_id': str(uuid.uuid4()),
                'order_id': f"ORD{random.randint(100000000, 999999999)}",
                'amount': round(random.uniform(0.01, 99999.99), 2),
                'method': random.choice(methods),
                'status': random.choice(statuses),
                'created_at': self._gen_datetime(),
                'completed_at': self._gen_datetime() if random.random() > 0.4 else None,
            })
        return payments

    def _generate_addresses(self, count: int, params: Dict) -> List[Dict[str, Any]]:
        """生成地址数据"""
        addresses = []
        for i in range(count):
            addresses.append({
                'address_id': str(uuid.uuid4()),
                'province': random.choice(self._PROVINCE_CODES),
                'city': self._gen_chinese_name(),
                'district': self._gen_chinese_name(),
                'detail': f"{self._gen_str(length=8)}小区{random.randint(1, 50)}栋{random.randint(1, 20)}单元{random.randint(101, 2999)}室",
                'postal_code': f"{random.randint(100000, 999999)}",
                'contact_name': self._gen_chinese_name(),
                'contact_phone': self._gen_phone(),
            })
        return addresses

    def _generate_custom(self, params: Dict, count: int) -> List[Dict[str, Any]]:
        """根据参数配置生成自定义数据"""
        results = []
        param_configs = params.get('param_configs', params)

        for _ in range(count):
            item = {}
            for field_name, config in param_configs.items():
                gen_type = config.get('type', 'str') if isinstance(config, dict) else 'str'
                gen_params = config if isinstance(config, dict) else {}

                if gen_type in self._generators:
                    item[field_name] = self._generators[gen_type](**gen_params)
                else:
                    item[field_name] = self._gen_str()

            results.append(item)

        return results

    # ==================== 内置生成器 ====================

    def _gen_uuid(self, **kwargs) -> str:
        return str(uuid.uuid4())

    def _gen_chinese_name(self, **kwargs) -> str:
        return random.choice(self._SURNAMES) + random.choice(self._NAMES)

    def _gen_name(self, lang: str = 'cn', **kwargs) -> str:
        if lang == 'cn':
            return self._gen_chinese_name()
        else:
            length = kwargs.get('length', 10)
            return self._gen_str(length=length)

    def _gen_email(self, **kwargs) -> str:
        username = self._gen_str(length=random.randint(5, 12)).lower()
        domains = ['qq.com', '163.com', 'gmail.com', 'outlook.com', 'example.com']
        return f"{username}@{random.choice(domains)}"

    def _gen_phone(self, **kwargs) -> str:
        prefixes = ['130', '131', '132', '133', '134', '135', '136', '137', '138', '139',
                    '150', '151', '152', '153', '155', '156', '157', '158', '159',
                    '180', '181', '182', '183', '184', '185', '186', '187', '188', '189']
        return random.choice(prefixes) + ''.join(str(random.randint(0, 9)) for _ in range(8))

    def _gen_id_card(self, **kwargs) -> str:
        """生成模拟身份证号（格式正确但非真实）"""
        province = random.randint(110000, 659000)
        year = random.randint(1960, 2005)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        seq = random.randint(100, 999)
        # 校验位简单计算
        factors = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
        check_codes = '10X98765432'
        base = f"{province}{year:04d}{month:02d}{day:02d}{seq}"
        total = sum(int(base[i]) * factors[i] for i in range(17))
        check_code = check_codes[total % 11]
        return base + check_code

    def _gen_int(self, min_val: int = 0, max_val: int = 1000, **kwargs) -> int:
        return random.randint(min_val, max_val)

    def _gen_float(self, min_val: float = 0.0, max_val: float = 1000.0, decimal: int = 2, **kwargs) -> float:
        value = random.uniform(min_val, max_val)
        return round(value, decimal)

    def _gen_str(self, length: int = 10, prefix: str = '', chars: str = None, **kwargs) -> str:
        if chars is None:
            chars = string.ascii_lowercase + string.digits
        result = prefix + ''.join(random.choice(chars) for _ in range(length - len(prefix)))
        return result

    def _gen_bool(self, **kwargs) -> bool:
        return random.choice([True, False])

    def _gen_date(self, start_days: int = -365, end_days: int = 0, **kwargs) -> str:
        delta = random.randint(start_days, end_days)
        date = datetime.now() + timedelta(days=delta)
        return date.strftime('%Y-%m-%d')

    def _gen_datetime(self, start_days: int = -365, end_days: int = 0, **kwargs) -> str:
        delta = random.randint(start_days, end_days)
        dt = datetime.now() + timedelta(days=delta, hours=random.randint(0, 23), minutes=random.randint(0, 59))
        return dt.strftime('%Y-%m-%d %H:%M:%S')

    def _gen_enum(self, values: list = None, **kwargs) -> Any:
        if values is None:
            values = ['option1', 'option2', 'option3']
        return random.choice(values)

    def _gen_bank_card(self, **kwargs) -> str:
        """生成模拟银行卡号（格式正确但非真实Luhn校验）"""
        bank_bin = random.choice(['622202', '622848', '621700', '622700'])
        middle = ''.join(str(random.randint(0, 9)) for _ in range(10))
        return bank_bin + middle + '0'  # 简化版本

    def _gen_address(self, **kwargs) -> Dict[str, str]:
        return self._generate_addresses(1, kwargs)[0]
