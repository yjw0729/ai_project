import os
import uuid
import json
import logging
from flask import Blueprint, request, make_response, current_app

from common.db_mapper.test_case_mapper import TestCaseMapper

test_case_import_opt = Blueprint("test_case_import_opt", __name__)


def json_response(body, status=200):
    resp = make_response(jsonify(body), status)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


def jsonify(body):
    """兼容旧版 Flask（无jsonify参数的make_response）"""
    try:
        from flask import jsonify as _flask_jsonify
        return _flask_jsonify(body)
    except Exception:
        return json.dumps(body, ensure_ascii=False)


def _build_csv_error(msg, row=None, field=None):
    detail = {}
    if row is not None:
        detail['row'] = row
    if field is not None:
        detail['field'] = field
    return {'msg': msg, 'detail': detail}


@test_case_import_opt.route("/import", methods=["POST"])
def import_test_cases_from_csv():
    """
    批量导入测试用例接口

    上传 CSV 文件，将其中的案例存入 crosstest_test_case 表。

    请求方式：multipart/form-data
        - file: CSV 文件（必填）
        - creator: 创建人（必填）
        - db_key: 数据库标识（可选，默认 "default"）
        - overwrite: 是否覆盖已存在的同名案例（可选，默认 true）

    CSV 列格式（中文表头，仅"测试步骤"为必填列，其余均可选）：
        用例名称, 所属模块, 所属系统, 优先级, 案例描述, 前置条件,
        测试步骤, 期望结果, 测试数据, 标签,
        最大重试次数, 超时时间(秒), 状态, 创建人

    字段说明：
        - 测试步骤（必填）：JSON数组字符串，如 [{"step_number": 1, "description": "xxx"}]
        - 用例名称（可选）：空值时自动生成为 "未命名用例_行号"
        - 所属模块（可选）：空值时默认为 "默认模块"
        - 其他字段均为可选

    返回示例：
        {
            "code": 200,
            "msg": "导入完成",
            "data": {
                "success_count": 3,
                "fail_count": 1,
                "total_count": 4,
                "created_ids": [1, 2, 3],
                "updated_ids": [],
                "errors": [
                    {"row": 5, "name": "测试用例A", "error": "所属模块不能为空"}
                ]
            }
        }
    """
    logger = current_app.logger or logging.getLogger(__name__)

    try:
        # 参数校验
        creator = request.form.get('creator', '').strip()
        if not creator:
            return json_response({"code": 400, "msg": "缺少必填参数: creator", "data": None}, status=400)

        if 'file' not in request.files:
            return json_response({"code": 400, "msg": "请求中未包含文件，请使用 multipart/form-data 格式上传 CSV 文件", "data": None}, status=400)

        file = request.files['file']
        if file.filename == '':
            return json_response({"code": 400, "msg": "文件名为空", "data": None}, status=400)

        # 只允许上传 CSV 文件
        if not file.filename.lower().endswith('.csv'):
            return json_response({"code": 400, "msg": "仅支持 CSV 格式文件", "data": None}, status=400)

        db_key = (request.form.get('db_key') or 'default').strip()
        logger.info("【导入测试用例】creator=%s, filename=%s, db_key=%s", creator, file.filename, db_key)

        # 保存上传文件到临时目录
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'test_case_imports')
        os.makedirs(upload_dir, exist_ok=True)
        temp_file_name = f"{uuid.uuid4().hex}_{file.filename}"
        temp_file_path = os.path.join(upload_dir, temp_file_name)

        try:
            file.save(temp_file_path)
            logger.info("【导入测试用例】文件已保存至: %s", temp_file_path)

            # 调用 Mapper 进行批量导入
            mapper = TestCaseMapper(db_key=db_key)
            result = mapper.import_cases_from_csv(temp_file_path, creator)

            success_count = result.get('success_count', 0)
            fail_count = result.get('fail_count', 0)
            total_count = result.get('total_count', 0)
            created_ids = result.get('created_ids', [])
            updated_ids = result.get('updated_ids', [])
            errors = result.get('errors', [])

            if fail_count > 0:
                logger.warning("【导入测试用例】部分失败: success=%s, fail=%s, errors=%s",
                               success_count, fail_count, errors)

            msg = f"导入完成：成功 {success_count} 条，失败 {fail_count} 条，共 {total_count} 条"
            return json_response({
                "code": 200,
                "msg": msg,
                "data": {
                    "success_count": success_count,
                    "fail_count": fail_count,
                    "total_count": total_count,
                    "created_ids": created_ids,
                    "updated_ids": updated_ids,
                    "errors": errors,
                }
            }, status=200)

        finally:
            # 清理临时文件
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    logger.info("【导入测试用例】临时文件已清理: %s", temp_file_path)
                except Exception as cleanup_err:
                    logger.warning("【导入测试用例】临时文件清理失败: %s", cleanup_err)

    except ValueError as ve:
        logger.warning("【导入测试用例】CSV格式校验失败: %s", ve)
        return json_response({"code": 400, "msg": f"CSV格式错误: {ve}", "data": None}, status=400)

    except Exception as e:
        logger.exception("【导入测试用例】服务器内部错误")
        return json_response({"code": 500, "msg": f"导入失败: {e}", "data": None}, status=500)


@test_case_import_opt.route("/template", methods=["GET"])
def download_csv_template():
    """
    下载 CSV 导入模板文件

    直接读取预定义的模板文件并返回，确保格式正确。

    完整路径（与列表/执行接口同域同前缀，避免请求落到前端 SPA 得到 HTML）：
    GET /data_service/testcase/template
    兼容：GET /testcase/template
    """
    logger = current_app.logger or logging.getLogger(__name__)

    try:
        # 模板文件路径 (从 api/http_test_case_import.py 往上一级到项目根目录)
        template_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'templates'
        )
        template_path = os.path.join(template_dir, 'test_case_import_template.csv')

        # 检查模板文件是否存在
        if not os.path.exists(template_path):
            logger.error(f"【下载CSV模板】模板文件不存在: {template_path}")
            return json_response({
                "code": 404,
                "msg": f"模板文件不存在: {template_path}",
                "data": None
            }, status=404)

        # 读取模板文件内容，并添加 UTF-8 BOM (确保 Excel 正确识别中文)
        with open(template_path, 'r', encoding='utf-8-sig') as f:
            csv_content = '\ufeff' + f.read()

        logger.info(f"【下载CSV模板】成功，文件大小: {len(csv_content)} bytes")

        # 返回文件下载响应
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
        response.headers['Content-Disposition'] = 'attachment; filename=test_case_import_template.csv'
        return response

    except Exception as e:
        logger.exception("【下载CSV模板】失败")
        return json_response({"code": 500, "msg": f"下载模板失败: {e}", "data": None}, status=500)
