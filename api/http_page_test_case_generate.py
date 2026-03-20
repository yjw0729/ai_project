#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
页面测试用例生成API
根据页面截图和字段规则生成完整的XMind格式测试用例

接口说明：
- 请求地址：POST /page_test_case/generate
- 请求格式：multipart/form-data
- 功能：根据上传的页面图片和字段规则文本，生成完整的页面测试用例XMind文件
"""

import os
import uuid
import json
import base64
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename

# 设置日志
logger = logging.getLogger(__name__)

# 创建Blueprint
page_test_case_bp = Blueprint('page_test_case', __name__)

# 配置
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'outputs', 'page_test_cases')
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
ALLOWED_TEXT_EXTENSIONS = {'txt', 'md', 'json'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename, allowed_extensions):
    """检查文件类型是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def json_response(data, status=200):
    """统一JSON响应格式"""
    response = {
        "code": status if status < 400 else 500,
        "message": "success" if status < 400 else "error",
        "data": data
    }
    return jsonify(response), status


# ==================== AI 生成相关函数 ====================

def generate_page_test_cases_with_ai(images_info: list, field_rules_text: str, page_name: str = "") -> dict:
    """
    使用AI生成页面测试用例
    
    参数：
    - images_info: 图片信息列表，每个元素包含 {base64, filename, description}
    - field_rules_text: 字段规则文本
    - page_name: 页面名称
    
    返回：
    - dict: 生成的测试用例
    """
    try:
        from common.llm.llm_client import LLMClient
        
        llm_client = LLMClient()
        
        # 构建提示词
        prompt = build_page_test_case_prompt(images_info, field_rules_text, page_name)
        
        # 调用AI生成
        content, raw_response = llm_client.chat_with_prompt(
            prompt=prompt,
            system_prompt="你是一个专业的测试用例设计专家，擅长根据页面截图和字段规则生成全面的测试用例。"
        )

        # 解析AI返回的测试用例
        test_cases = parse_ai_response(content)

        return {
            "success": True,
            "test_cases": test_cases,
            "raw_response": raw_response
        }
        
    except Exception as e:
        logger.error(f"AI生成测试用例失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


def build_page_test_case_prompt(images_info: list, field_rules_text: str, page_name: str) -> str:
    """构建生成测试用例的提示词"""

    prompt = f"""你是一个专业的测试用例设计专家。请根据以下页面截图和字段规则，为每个页面生成完整的、独立的测试用例。

## 页面维度说明
你收到的{len(images_info)}张截图代表{len(images_info)}个不同的页面，每个页面是独立的测试维度。

## 页面列表（共{len(images_info)}个页面）

"""
    # 按页面组织图片信息
    for i, img_info in enumerate(images_info, 1):
        prompt += f"""
### 页面 {i}: {img_info.get('filename', '未命名')}
页面描述：{img_info.get('description', '无描述')}
"""

    prompt += f"""
## 字段规则和取值要求
{field_rules_text}

## 测试用例编写要求

### 按页面维度组织
为每个页面独立编写测试用例，测试用例结构如下：

```
一级：页面维度（每个页面一个根节点）
  二级：字段验证（每个字段的规则验证）
    - 必填项验证（为空时的提示）
    - 格式验证（格式错误的提示）
    - 长度验证（超出限制的提示）
    - 取值范围验证（非法值的提示）
    - 默认值验证
  二级：交互验证
    - 按钮点击（提交/重置/查询等）
    - 下拉框选择
    - 复选框/单选框
    - 输入框输入
    - 字段联动（级联选择、联动显示隐藏）
  二级：边界值测试
    - 最大/最小长度边界
    - 特殊字符处理
    - 边界数值
  二级：异常测试
    - 并发提交
    - 重复提交
    - 网络异常
```

### 每个字段需要覆盖的验证点

#### 1. 字段规则验证
- **必填验证**：不填写时应有明确错误提示
- **格式验证**：不符合格式时的错误提示（如邮箱、手机号、身份证等）
- **长度验证**：超出最大长度、不足最小长度的提示
- **取值范围**：不在允许范围内的错误提示
- **默认值**：默认值是否正确显示和应用

#### 2. 页面交互验证
- **按钮操作**：提交、取消、重置、查询、导出等按钮
- **下拉选择**：选项切换、级联关系
- **输入交互**：实时校验、模糊搜索
- **联动关系**：字段间依赖、显示/隐藏逻辑
- **状态变化**：禁用/启用、只读/可编辑

#### 3. 边界值和异常
- 边界数值（最大、最小、临界值）
- 特殊字符（<>&\等HTML转义字符）
- 全角/半角混合
- 空格处理（前导、尾随、连续空格）
- 并发/重复操作

## 输出格式要求

请以JSON格式返回测试用例，必须按页面维度组织：
```json
{{
    "pages": [
        {{
            "page_index": 1,
            "page_name": "页面1名称",
            "page_description": "页面功能描述",
            "test_cases": [
                {{
                    "id": "P1_001",
                    "scene": "测试场景描述",
                    "precondition": "前置条件",
                    "test_steps": ["步骤1", "步骤2", "步骤3"],
                    "expected": "预期结果",
                    "priority": "P0/P1/P2/P3",
                    "test_type": "字段验证/交互测试/边界测试/异常测试",
                    "field_name": "涉及的字段名",
                    "validation_point": "具体验证点（必填/格式/长度/取值/按钮/联动等）"
                }}
            ]
        }}
    ]
}}
```

## 重要提醒

1. **每个页面独立**：确保每个页面的测试用例完整、独立
2. **字段全覆盖**：字段规则中提到的每个字段都需要有对应测试用例
3. **交互全覆盖**：页面上的每个可交互元素（按钮、下拉框、输入框等）都需要测试
4. **错误提示验证**：每个验证失败场景都需要检查错误提示是否正确
5. **优先级分配**：
   - P0：核心功能，提交/保存等主要操作
   - P1：重要功能，必填项、格式校验
   - P2：一般功能，非必填项、边界值
   - P3：边缘功能，特殊字符、异常情况

请直接返回JSON，不要包含其他解释性文字。
"""

    return prompt


def parse_ai_response(response: str) -> dict:
    """解析AI返回的测试用例JSON"""
    try:
        # 尝试提取JSON部分
        json_str = response
        if '```json' in response:
            json_str = response.split('```json')[1].split('```')[0]
        elif '```' in response:
            json_str = response.split('```')[1].split('```')[0]

        # 解析JSON
        data = json.loads(json_str.strip())

        # 新格式：按页面维度组织
        if isinstance(data, dict) and 'pages' in data:
            return data

        # 兼容旧格式
        if isinstance(data, dict):
            # 如果是旧格式，包装成新格式
            return {
                "pages": [{
                    "page_index": 1,
                    "page_name": "页面测试",
                    "test_cases": data.get('test_cases', [])
                }]
            }
        elif isinstance(data, list):
            return {
                "pages": [{
                    "page_index": 1,
                    "page_name": "页面测试",
                    "test_cases": data
                }]
            }
        else:
            return {"pages": []}

    except Exception as e:
        logger.error(f"解析AI响应失败: {e}")
        return {"pages": []}


def analyze_page_image(image_bytes: bytes, image_filename: str) -> dict:
    """
    使用多模态AI分析页面截图
    
    参数：
    - image_bytes: 图片二进制数据
    - image_filename: 图片文件名
    
    返回：
    - dict: 页面元素分析结果
    """
    try:
        import dashscope
        from dashscope import MultiModalConversation
        
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            return {
                "success": False,
                "error": "未设置DASHSCOPE_API_KEY"
            }
        
        dashscope.api_key = api_key
        
        # 图片转base64
        img_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # 构建消息
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "image": f"data:image/jpeg;base64,{img_base64}"
                    },
                    {
                        "text": "请详细描述这个页面的布局和元素，包括：1.页面整体结构 2.包含的字段（输入框、下拉框、按钮等）3.字段的排列顺序 4.是否有必填标识 5.字段的默认值或预设内容"
                    }
                ]
            }
        ]
        
        # 调用模型
        response = MultiModalConversation.call(
            model='qwen-vl-plus',
            messages=messages
        )
        
        if response.status_code == 200:
            analysis = response.output.choices[0].message.content[0]['text']
            return {
                "success": True,
                "filename": image_filename,
                "analysis": analysis
            }
        else:
            return {
                "success": False,
                "error": f"API调用失败: {response.message}"
            }
            
    except Exception as e:
        logger.error(f"分析页面图片失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ==================== XMind 生成 ====================

def generate_xmind_from_test_cases(pages: list, page_name: str) -> str:
    """
    根据测试用例生成XMind文件（支持页面维度）

    参数：
    - pages: 页面列表，每个页面包含 {page_index, page_name, test_cases}
    - page_name: 页面名称

    返回：
    - str: 生成的文件路径
    """
    from common.rag.utils.xmind_generator import XMindGenerator

    generator = XMindGenerator(output_dir=UPLOAD_FOLDER)

    # 转换为XMind格式（按页面维度组织）
    xmind_cases = []
    for page in pages:
        page_index = page.get('page_index', 1)
        page_title = page.get('page_name', f'页面{page_index}')
        test_cases = page.get('test_cases', [])

        for tc in test_cases:
            # 使用页面名称作为业务模块
            xmind_case = {
                "scene": tc.get("scene", ""),
                "expected": tc.get("expected", ""),
                "priority": tc.get("priority", "P2"),
                "test_type": tc.get("test_type", "功能测试"),
                "field_name": tc.get("field_name", ""),
                "precondition": tc.get("precondition", ""),
                "test_steps": tc.get("test_steps", []),
                "page_index": page_index,
                "page_name": page_title,
                "validation_point": tc.get("validation_point", "")
            }
            xmind_cases.append(xmind_case)

    # 生成文件
    file_path = generator.generate_test_cases_xmind(
        document_title=page_name or "页面测试用例",
        test_cases=xmind_cases,
        business_module=""
    )

    return file_path


# ==================== API 接口 ====================

@page_test_case_bp.route('/generate', methods=['POST'])
def generate_page_test_case():
    """
    生成页面测试用例接口
    
    请求参数（multipart/form-data）：
    - images: 页面截图文件（支持多文件上传）
    - field_rules: 字段规则文本文件（可选，与field_rules_text二选一）
    - field_rules_text: 字段规则文本内容（可选）
    - page_name: 页面名称（可选）
    - generate_xmind: 是否生成XMind文件（true/false，默认true）
    """
    try:
        # 检查是否有文件
        if 'images' not in request.files:
            return json_response({"code": 400, "message": "未找到页面截图文件"}, 400)
        
        images_files = request.files.getlist('images')
        if not images_files or all(f.filename == '' for f in images_files):
            return json_response({"code": 400, "message": "未选择页面截图文件"}, 400)
        
        # 获取其他参数
        page_name = request.form.get('page_name', '')
        field_rules_text = request.form.get('field_rules_text', '')
        generate_xmind = request.form.get('generate_xmind', 'true').lower() == 'true'
        
        # 处理字段规则文本
        if 'field_rules' in request.files and request.files['field_rules'].filename:
            field_rules_file = request.files['field_rules']
            if allowed_file(field_rules_file.filename, ALLOWED_TEXT_EXTENSIONS):
                field_rules_text = field_rules_file.read().decode('utf-8')
        
        if not field_rules_text:
            return json_response({"code": 400, "message": "字段规则文本不能为空"}, 400)
        
        logger.info(f"开始生成页面测试用例，页面名称: {page_name}")
        logger.info(f"上传图片数量: {len(images_files)}")
        
        # 处理上传的图片
        images_info = []
        for img_file in images_files:
            if img_file.filename and allowed_file(img_file.filename, ALLOWED_IMAGE_EXTENSIONS):
                # 保存图片
                img_id = str(uuid.uuid4())[:8]
                ext = img_file.filename.rsplit('.', 1)[1].lower()
                img_filename = f"{img_id}_{secure_filename(img_file.filename)}"
                img_path = os.path.join(UPLOAD_FOLDER, img_filename)
                img_file.save(img_path)
                
                # 读取图片bytes
                with open(img_path, 'rb') as f:
                    img_bytes = f.read()
                
                # 分析图片（可选，如果需要AI理解页面内容）
                analysis_result = analyze_page_image(img_bytes, img_file.filename)
                
                images_info.append({
                    "filename": img_file.filename,
                    "path": img_path,
                    "base64": base64.b64encode(img_bytes).decode('utf-8'),
                    "description": analysis_result.get('analysis', '') if analysis_result.get('success') else ''
                })
        
        logger.info(f"处理完成 {len(images_info)} 张图片")
        
        # 调用AI生成测试用例
        logger.info("开始调用AI生成测试用例...")
        ai_result = generate_page_test_cases_with_ai(
            images_info=images_info,
            field_rules_text=field_rules_text,
            page_name=page_name
        )
        
        if not ai_result.get('success'):
            return json_response({
                "code": 500,
                "message": f"AI生成失败: {ai_result.get('error')}"
            }, 500)

        # 解析新的页面维度格式
        pages_data = ai_result.get('test_cases', {})
        if isinstance(pages_data, dict) and 'pages' in pages_data:
            pages = pages_data['pages']
        elif isinstance(pages_data, list):
            # 兼容旧格式
            pages = [{"page_index": 1, "page_name": page_name or "页面测试", "test_cases": pages_data}]
        else:
            pages = []

        # 计算总测试用例数
        total_test_cases = sum(len(p.get('test_cases', [])) for p in pages)

        if total_test_cases == 0:
            return json_response({
                "code": 400,
                "message": "未生成任何测试用例"
            }, 400)

        logger.info(f"AI生成完成，共 {len(pages)} 个页面，{total_test_cases} 个测试用例")

        # 生成XMind文件
        xmind_path = ""
        if generate_xmind:
            logger.info("开始生成XMind文件...")
            xmind_path = generate_xmind_from_test_cases(pages, page_name or "页面测试用例")
            logger.info(f"XMind文件生成完成: {xmind_path}")

        # 返回结果
        result = {
            "page_name": page_name,
            "pages_count": len(pages),
            "test_cases_count": total_test_cases,
            "pages": [
                {
                    "page_index": p.get('page_index', i+1),
                    "page_name": p.get('page_name', f'页面{i+1}'),
                    "test_cases_count": len(p.get('test_cases', []))
                }
                for i, p in enumerate(pages)
            ],
            "images_count": len(images_info)
        }

        if xmind_path:
            result["xmind_file"] = xmind_path
            result["xmind_filename"] = os.path.basename(xmind_path)

        return json_response(result)
        
    except Exception as e:
        logger.error(f"生成页面测试用例失败: {e}", exc_info=True)
        return json_response({
            "code": 500,
            "message": f"服务器错误: {str(e)}"
        }, 500)


@page_test_case_bp.route('/download/<filename>', methods=['GET'])
def download_xmind(filename):
    """
    下载生成的XMind文件
    """
    try:
        file_path = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
        if not os.path.exists(file_path):
            return json_response({"code": 404, "message": "文件不存在"}, 404)
        
        return send_file(
            file_path,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"下载文件失败: {e}")
        return json_response({"code": 500, "message": str(e)}, 500)


@page_test_case_bp.route('/templates', methods=['GET'])
def get_field_rules_template():
    """
    获取字段规则的填写模板
    """
    template = """# 字段规则填写示例

## 页面基本信息
- 页面名称：用户注册页面
- 所属模块：用户管理

## 字段列表

### 1. 用户名 (username)
- 类型：输入框
- 是否必填：是
- 最大长度：20
- 格式要求：字母数字下划线组合
- 取值范围：a-z, A-Z, 0-9, _
- 默认值：无
- 错误提示：
  - 为空："用户名不能为空"
  - 格式错误："用户名只能包含字母、数字和下划线"
  - 长度超出："用户名不能超过20个字符"

### 2. 密码 (password)
- 类型：输入框（密文）
- 是否必填：是
- 最大长度：16
- 最小长度：8
- 格式要求：字母数字特殊字符组合
- 取值范围：至少包含大写字母、小写字母、数字各一个
- 默认值：无
- 错误提示：
  - 为空："密码不能为空"
  - 长度不足："密码长度不能少于8位"
  - 格式错误："密码必须包含大写字母、小写字母和数字"

### 3. 确认密码 (confirm_password)
- 类型：输入框（密文）
- 是否必填：是
- 最大长度：16
- 格式要求：与密码一致
- 取值范围：与password字段一致
- 默认值：无
- 错误提示：
  - 为空："请再次输入密码"
  - 不一致："两次输入的密码不一致"

### 4. 邮箱 (email)
- 类型：输入框
- 是否必填：是
- 最大长度：50
- 格式要求：邮箱格式
- 取值范围：符合RFC 5322标准
- 默认值：无
- 错误提示：
  - 为空："邮箱不能为空"
  - 格式错误："请输入有效的邮箱地址"

### 5. 手机号 (phone)
- 类型：输入框
- 是否必填：否
- 最大长度：11
- 格式要求：11位数字
- 取值范围：1开头，第二位3-9
- 默认值：无
- 错误提示：
  - 格式错误："请输入有效的手机号码"

### 6. 验证码 (verify_code)
- 类型：输入框
- 是否必填：是
- 最大长度：6
- 格式要求：6位数字
- 取值范围：000000-999999
- 默认值：无
- 错误提示：
  - 为空："请输入验证码"
  - 错误："验证码错误"
  - 过期："验证码已过期"

### 7. 用户协议 (agreement)
- 类型：复选框
- 是否必填：是
- 取值范围：勾选/不勾选
- 默认值：未勾选
- 错误提示：
  - 未勾选："请阅读并同意用户协议"

### 8. 注册按钮
- 类型：按钮
- 文字：注册
- 状态：默认可用

## 页面交互规则
1. 用户名输入后立即校验格式
2. 密码强度实时提示
3. 两次密码输入时实时比对
4. 所有必填项填写后才能点击注册按钮
5. 点击注册后统一验证所有字段

## 特殊场景
1. 用户名重复检查（异步）
2. 邮箱格式实时校验（异步）
3. 发送验证码后60秒倒计时
"""
    
    return json_response({
        "template": template,
        "format": "markdown"
    })
