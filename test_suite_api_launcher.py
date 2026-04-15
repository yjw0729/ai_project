# -*- coding: utf-8 -*-
"""
测试套件 API 启动脚本

用于测试新的 test_suite 和 test_suite_case API 接口。

使用方法:
    python test_suite_api_launcher.py

接口列表:
    TestSuite CRUD:
    - POST   /api/test-suite                    创建测试套件
    - GET    /api/test-suite/<id>              获取测试套件详情
    - PUT    /api/test-suite/<id>              更新测试套件
    - DELETE /api/test-suite/<id>              删除测试套件
    - GET    /api/test-suite/list              获取测试套件列表

    TestSuiteCase 用例管理:
    - POST   /api/test-suite/<id>/cases        向套件添加用例
    - PUT    /api/test-suite/<id>/cases/<sc_id> 更新套件用例配置
    - DELETE /api/test-suite/<id>/cases/<sc_id> 从套件移除用例
    - PUT    /api/test-suite/<id>/cases/reorder    重新排序用例
    - PUT    /api/test-suite/<id>/cases/batch-update 批量更新用例
    - DELETE /api/test-suite/<id>/cases/clear   清空套件用例
    - GET    /api/test-suite/<id>/cases/statistics  获取统计

    TestSuite 执行:
    - POST   /api/test-suite/<id>/execute      执行测试套件
    - GET    /api/test-suite/<id>/execution-history  执行历史
"""

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify
from flask_cors import CORS
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_suite_app():
    """创建并配置 Flask 应用（仅用于测试新接口）"""
    app = Flask(__name__)
    CORS(app)

    # 注册 Blueprint
    from platform_service.api.http_test_suite import test_suite_bp
    from platform_service.api.http_test_suite_case import test_suite_case_bp
    from platform_service.api.http_test_suite_execute import test_suite_execute_bp

    app.register_blueprint(test_suite_bp)
    app.register_blueprint(test_suite_case_bp)
    app.register_blueprint(test_suite_execute_bp)

    # 健康检查
    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "test-suite-api"})

    return app


def list_routes(app):
    """列出所有注册的路由"""
    print("\n" + "=" * 60)
    print("已注册的 API 端点")
    print("=" * 60)

    routes = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint != 'static':
            methods = ','.join(sorted(rule.methods - {'OPTIONS', 'HEAD'}))
            routes.append({
                'methods': methods,
                'endpoint': rule.endpoint,
                'path': rule.rule
            })

    routes.sort(key=lambda x: x['path'])

    for r in routes:
        print(f"  {r['methods']:10s} {r['path']}")

    print("=" * 60)
    print(f"共 {len(routes)} 个端点\n")


def main():
    print("=" * 60)
    print("测试套件 API 启动器")
    print("=" * 60)

    try:
        app = create_test_suite_app()
        print("[OK] Flask 应用创建成功")

        # 列出路由
        list_routes(app)

        print("\n启动服务...")
        print("  访问 http://127.0.0.1:5001 查看 API\n")

        app.run(host='0.0.0.0', port=5001, debug=True)

    except Exception as e:
        print(f"[FAIL] 启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
