# -*- coding: utf-8 -*-
"""
测试图片分类功能 - 验证最终结果
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.db_mapper.review_record_mapper import ReviewRecordMapper


def test_image_classification():
    """测试图片分类功能"""
    print("=" * 60)
    print("测试图片分类功能")
    print("=" * 60)

    # 模拟8个接口
    interface_list = [
        {"name": "用户登录接口", "method": "POST", "path": "/api/user/login", "process_flow": "验证用户名密码,返回token"},
        {"name": "获取用户信息", "method": "GET", "path": "/api/user/info", "process_flow": "查询用户资料,返回用户信息"},
        {"name": "用户登出接口", "method": "POST", "path": "/api/user/logout", "process_flow": "清除token"},
        {"name": "商品查询接口", "method": "GET", "path": "/api/product/list", "process_flow": "分页查询商品"},
        {"name": "商品详情接口", "method": "GET", "path": "/api/product/detail", "process_flow": "查询商品详情"},
        {"name": "下单接口", "method": "POST", "path": "/api/order/create", "process_flow": "创建订单,扣减库存"},
        {"name": "支付接口", "method": "POST", "path": "/api/payment/pay", "process_flow": "调用支付网关"},
        {"name": "订单查询接口", "method": "GET", "path": "/api/order/list", "process_flow": "查询用户订单"},
    ]

    # 模拟11张图片分析结果
    image_analysis = [
        {"success": True, "analysis": "用户登录接口流程图：1.接收用户名密码 2.验证凭证 3.返回JWT token", "filename": "login.png", "image_index": 0},
        {"success": True, "analysis": "用户信息查询流程图：1.获取token 2.查询数据库 3.返回用户资料", "filename": "user_info.png", "image_index": 1},
        {"success": True, "analysis": "登出流程图：清除缓存的token", "filename": "logout.png", "image_index": 2},
        {"success": True, "analysis": "商品列表查询：支持分页和过滤", "filename": "product_list.png", "image_index": 3},
        {"success": True, "analysis": "商品详情：展示商品基本信息", "filename": "product_detail.png", "image_index": 4},
        {"success": True, "analysis": "下单流程：创建订单并扣减库存", "filename": "order_create.png", "image_index": 5},
        {"success": True, "analysis": "支付流程：集成第三方支付", "filename": "payment.png", "image_index": 6},
        {"success": True, "analysis": "订单查询：展示订单列表", "filename": "order_list.png", "image_index": 7},
        {"success": True, "analysis": "系统架构图：前端-后端-数据库交互", "filename": "architecture.png", "image_index": 8},
        {"success": True, "analysis": "泳道图：展示用户、商家、平台三方交互", "filename": "swimlane.png", "image_index": 9},
        {"success": True, "analysis": "错误码说明：定义各类错误码含义", "filename": "error_codes.png", "image_index": 10},
    ]

    # flow_chart_analysis包含图片分析结果
    flow_chart_analysis = []
    for img in image_analysis:
        flow_chart_analysis.append({
            "source": "image",
            "filename": img["filename"],
            "analysis": img["analysis"]
        })

    # 创建Mapper并测试
    mapper = ReviewRecordMapper()

    # 直接测试分类方法
    print("\n开始测试图片分类...")

    result = mapper._classify_image_analysis(
        interface_list=interface_list,
        image_analysis=image_analysis,
        flow_chart_list=flow_chart_analysis
    )

    print(f"\n接口图片数量: {len(result['interface_images'])}")
    print(f"知识图片数量: {len(result['general_images'])}")

    print("\n--- 匹配到接口的图片 ---")
    for item in result['interface_images']:
        print(f"  接口: {item['matched_interface_name']} <- 图片: {item['image_analysis']['filename']}")

    print("\n--- 知识图片（未匹配到接口）---")
    for img in result['general_images']:
        print(f"  {img['filename']}")

    # 验证结果
    print("\n" + "=" * 60)
    print("验证结果")
    print("=" * 60)

    # 核心知识图片必须被正确识别
    expected_general = {"architecture.png", "swimlane.png", "error_codes.png"}
    actual_general = {img['filename'] for img in result['general_images']}
    
    if expected_general.issubset(actual_general):
        print("[OK] 核心知识图片（架构图、泳道图、错误码）正确识别")
    else:
        print(f"[FAIL] 核心知识图片识别不对: 期望包含{expected_general}, 实际{actual_general}")

    # 接口图片数量至少应该有5个以上（考虑同义词差异）
    if len(result['interface_images']) >= 5:
        print(f"[OK] 接口图片数量合理: {len(result['interface_images'])} >= 5")
    else:
        print(f"[FAIL] 接口图片数量太少: {len(result['interface_images'])} < 5")

    print("\n测试完成!")


if __name__ == "__main__":
    test_image_classification()
