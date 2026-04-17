# -*- coding: utf-8 -*-
"""
数据工厂 Blueprint

统一管理各类测试数据生成接口：
- /data_service/create_card_no         - 生成银行卡号
- /data_service/create_address          - 生成地址
- /data_service/create_customer_information - 生成商户/客户信息
- /data_service/create_idCardNo         - 生成证件号
- /data_service/create_phone            - 生成手机号
- /data_service/draw_picture            - 生成图片（身份证/银行卡等）
"""
from flask import Blueprint, request

data_generate_bp = Blueprint("data_generate", __name__)

# ---------- 银行卡号 ----------
from utils.auto_generate.generate_cardNo import create_card_no


@data_generate_bp.route("/create_card_no", methods=["POST"])
def create_bankcard_no():
    """生成银行卡号"""
    get_json = request.get_json() or {}
    bankname = get_json.get("bank_name", "")
    bank_card_no = create_card_no(bankname)
    return {
        "code": 200,
        "message": "银行卡号生成完成",
        "data": {"bankcard_no": bank_card_no},
    }


# ---------- 地址 ----------
from utils.auto_generate.generate_address import generate_address


@data_generate_bp.route("/create_address", methods=["POST"])
def create_address():
    """生成随机地址"""
    address = generate_address()
    return {
        "code": 200,
        "message": "地址生成完成",
        "data": {"address": address},
    }


# ---------- 商户/客户信息 ----------
from utils.auto_generate.generate_customer import create_customer_information as gen_customer_info


@data_generate_bp.route("/create_customer_information", methods=["POST"])
def create_customer():
    """生成商户/客户信息"""
    get_json = request.get_json() or {}
    customer_type = get_json.get("customerType", "00")
    person_type = get_json.get("personType", "0")
    customer_info = gen_customer_info(customerType=customer_type, personType=person_type)
    return {
        "code": 200,
        "message": "商户信息生成完成",
        "data": customer_info,
    }


# ---------- 证件号 ----------
from utils.auto_generate.generate_idcardno import create_identity_card


@data_generate_bp.route("/create_idCardNo", methods=["POST"])
def create_id_card_no():
    """生成身份证号"""
    get_json = request.get_json() or {}
    id_type = get_json.get("type", "0")
    id_card_no = create_identity_card(id_type)
    return {
        "code": 200,
        "message": "证件号生成完成",
        "data": {"id_card_no": id_card_no},
    }


# ---------- 手机号 ----------
from utils.auto_generate.generate_phone import create_phone_no


@data_generate_bp.route("/create_phone", methods=["POST"])
def create_phone():
    """生成手机号"""
    phone = create_phone_no()
    return {
        "code": 200,
        "message": "手机号生成完成",
        "data": {"phone": phone},
    }


# ---------- 图片生成 ----------
from utils.auto_generate.generate_picture import cv2_pil_add_text


@data_generate_bp.route("/draw_picture", methods=["POST"])
def draw_picture():
    """生成图片（身份证/银行卡等）"""
    get_json = request.get_json() or {}
    card_name = get_json.get("card_name", "测试")
    card_number = get_json.get("card_number", "1234567890")
    img_type = get_json.get("img_type", "shenfenzheng")
    picture = cv2_pil_add_text(
        card_name=card_name, card_number=card_number, img_type=img_type
    )
    return {
        "code": 200,
        "message": "图片生成完成",
        "data": {"picture": picture},
    }
