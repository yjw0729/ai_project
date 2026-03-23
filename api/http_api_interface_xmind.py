#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
接口出入参 XMind 测试用例生成 API
根据接口说明 Word 文档生成 XMind：接口名 -> 请求参数/响应参数 -> 字段名 -> 必填、枚举、说明
"""

import os
import logging
from flask import Blueprint, request, jsonify, send_file, make_response
from werkzeug.utils import secure_filename

from common.rag.utils.api_doc_parser import (
    parse_api_doc_from_docx,
    generate_api_params_xmind,
)

logger = logging.getLogger(__name__)

api_interface_xmind_bp = Blueprint("api_interface_xmind", __name__)

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "api_interface_xmind"
)
os.makedirs(OUTPUT_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"docx", "doc"}


def json_response(body, status=200):
    """返回JSON响应"""
    resp = make_response(jsonify(body), status)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    # 禁用缓存，确保前端总能获取最新数据
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def json_response(data, status=200):
    """返回JSON响应"""
    resp = make_response(jsonify({
        "code": status if status < 400 else 500,
        "message": "success" if status < 400 else "error",
        "data": data,
    }), status)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    # 禁用缓存，确保前端总能获取最新数据
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@api_interface_xmind_bp.route("/generate", methods=["POST"])
def generate_api_interface_xmind():
    """
    根据接口说明 Word 文档生成接口出入参 XMind 测试用例。

    请求方式：POST multipart/form-data 或 application/json
    - file: 接口文档 .docx 文件（与 doc_path 二选一）
    - doc_path: 服务器上的文档路径，如 word/交易下单接口修改和传参说明.docx（与 file 二选一）
    - root_title: 可选，XMind 根节点标题，不传则从文档中推断
    - download: 可选，传入 "true" 则直接返回 XMind 文件（默认返回 JSON）

    返回：
    - 默认：JSON 包含文件路径和信息
    - download=true：直接返回 XMind 文件供下载
    """
    # 是否直接下载（支持 form、json、query 参数）
    download = False
    if request.is_json and request.get_json():
        download = request.get_json().get("download", False) in (True, "true", "True", "1", "yes")
    if not download:
        download = request.form.get("download", "").lower() in ("true", "1", "yes")
    if not download:
        download = request.args.get("download", "").lower() in ("true", "1", "yes")

    try:
        doc_path = None
        root_title = (request.form.get("root_title") or request.args.get("root_title") or "").strip()

        if "file" in request.files and request.files["file"].filename:
            f = request.files["file"]
            if not allowed_file(f.filename):
                return json_response(
                    {"message": "仅支持 .docx / .doc 文件"},
                    400,
                )
            save_path = os.path.join(OUTPUT_DIR, secure_filename(f.filename))
            f.save(save_path)
            doc_path = save_path
        elif request.form.get("doc_path"):
            doc_path = request.form.get("doc_path").strip()
        elif request.is_json and request.get_json():
            doc_path = request.get_json().get("doc_path", "").strip()
            root_title = (request.get_json().get("root_title") or root_title).strip()

        if not doc_path:
            return json_response(
                {"message": "请上传 file 或提供 doc_path"},
                400,
            )

        # 若 doc_path 为相对路径，则相对于项目根
        if not os.path.isabs(doc_path):
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            doc_path = os.path.normpath(os.path.join(project_root, doc_path))

        if not os.path.isfile(doc_path):
            return json_response(
                {"message": f"文件不存在: {doc_path}"},
                404,
            )

        root_title_parsed, interfaces = parse_api_doc_from_docx(
            doc_path,
            root_title=root_title or None,
        )
        title = root_title or root_title_parsed

        if not interfaces:
            return json_response(
                {"message": "未能从文档中解析出接口或参数，请检查文档是否包含请求/响应参数表格"},
                400,
            )

        xmind_path = generate_api_params_xmind(
            root_title=title,
            interfaces=interfaces,
            output_dir=OUTPUT_DIR,
            filename_prefix="接口参数",
        )

        # 统计
        total_request = sum(len(i.request_params) for i in interfaces)
        total_response = sum(len(i.response_params) for i in interfaces)

        # 如果请求直接下载，返回文件
        if download:
            return send_file(
                xmind_path,
                mimetype="application/octet-stream",
                as_attachment=True,
                download_name=os.path.basename(xmind_path),
            )

        return json_response({
            "xmind_file": xmind_path,
            "xmind_filename": os.path.basename(xmind_path),
            "root_title": title,
            "interfaces_count": len(interfaces),
            "request_params_count": total_request,
            "response_params_count": total_response,
            "interfaces": [
                {
                    "name": i.name,
                    "request_params_count": len(i.request_params),
                    "response_params_count": len(i.response_params),
                }
                for i in interfaces
            ],
        })
    except Exception as e:
        logger.exception("生成接口 XMind 失败")
        return json_response(
            {"message": f"生成失败: {str(e)}"},
            500,
        )


@api_interface_xmind_bp.route("/download/<filename>", methods=["GET"])
def download_xmind(filename):
    """下载生成的 XMind 文件"""
    try:
        path = os.path.join(OUTPUT_DIR, secure_filename(filename))
        if not os.path.isfile(path):
            return json_response({"message": "文件不存在"}, 404)
        return send_file(
            path,
            mimetype="application/octet-stream",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        logger.exception("下载 XMind 失败")
        return json_response({"message": str(e)}, 500)
