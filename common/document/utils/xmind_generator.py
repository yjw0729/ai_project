#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XMind文件生成器
根据测试案例生成XMind格式的思维导图文件
"""

import json
import zipfile
import os
import uuid
import logging
from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path


class XMindGenerator:
    """XMind文件生成器"""
    
    def __init__(self, output_dir: str = "outputs/test_cases"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_test_cases_xmind(
        self, 
        document_title: str, 
        test_cases: List[Dict[str, Any]],
        business_module: str = ""
    ) -> str:
        """
        生成XMind文件
        
        Args:
            document_title: 文档标题
            test_cases: 测试案例列表
            business_module: 业务模块
            
        Returns:
            生成的文件路径
        """
        # 生成唯一ID
        file_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 构建XMind内容结构
        xmind_content = self._build_xmind_content(document_title, test_cases, business_module)
        
        # 验证content是有效的JSON数组
        if not isinstance(xmind_content, list):
            raise ValueError("XMind content must be a JSON array")
        if len(xmind_content) == 0:
            raise ValueError("XMind content cannot be empty")
        
        # 将content转为JSON字符串并验证
        content_json = json.dumps(xmind_content, ensure_ascii=False, indent=2)
        
        # 验证JSON可以被解析
        try:
            parsed = json.loads(content_json)
            if not isinstance(parsed, list):
                raise ValueError("JSON must decode to a list")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON generated: {e}")
        
        # 创建ZIP文件（XMind格式）
        xmind_path = self.output_dir / f"{document_title}_测试案例_{timestamp}.xmind"
        
        with zipfile.ZipFile(xmind_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 添加content.json - XMind Zen格式使用JSON数组
            zf.writestr('content.json', content_json)
            
            # 添加manifest.json - XMind Zen格式必需的文件清单
            manifest_json = {
                "version": "1.0",
                "media": {
                    "content/json": {
                        "path": "content.json"
                    }
                }
            }
            zf.writestr('manifest.json', json.dumps(manifest_json, ensure_ascii=False, indent=2))
            
            # 添加meta.xml - XMind需要XML格式的元数据
            meta_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<meta>
    <app name="XMind" version="3.7.9"/>
    <created>{datetime.now().isoformat()}</created>
    <creator>AI Test Case Generator</creator>
    <description>{document_title}</description>
</meta>'''
            zf.writestr('meta.xml', meta_xml)
        
        # 验证生成的文件
        self._verify_xmind_file(xmind_path)
        
        return str(xmind_path)
    
    def _verify_xmind_file(self, xmind_path: Path):
        """
        验证生成的XMind文件是否有效
        """
        try:
            with zipfile.ZipFile(xmind_path, 'r') as zf:
                # 检查必要文件存在
                file_list = zf.namelist()
                if 'content.json' not in file_list:
                    raise ValueError("content.json not found in XMind file")
                
                # 验证content.json是有效的JSON数组
                content = zf.read('content.json').decode('utf-8')
                if not content.strip().startswith('['):
                    raise ValueError(f"content.json must start with '[' but got: {content[:50]}")
                
                parsed = json.loads(content)
                if not isinstance(parsed, list):
                    raise ValueError("content.json must be a JSON array")
        except Exception as e:
            raise ValueError(f"XMind file verification failed: {e}")
    
    def _build_xmind_content(
        self,
        title: str,
        test_cases: List[Dict[str, Any]],
        business_module: str
    ) -> List[Dict[str, Any]]:
        """
        构建XMind内容结构 - 支持页面维度

        如果测试用例包含 page_index 或 page_name 字段，则按页面维度组织；
        否则按原有逻辑按模块/接口分组。

        Returns:
            JSON数组格式，符合XMind Zen模式要求
        """

        # 检查是否包含页面维度信息
        has_page_info = any(tc.get("page_index") or tc.get("page_name") for tc in test_cases)

        if has_page_info:
            return self._build_xmind_content_by_page(title, test_cases, business_module)
        else:
            return self._build_xmind_content_by_module(title, test_cases, business_module)

    def _build_xmind_content_by_page(
        self,
        title: str,
        test_cases: List[Dict[str, Any]],
        business_module: str
    ) -> List[Dict[str, Any]]:
        """按页面维度构建XMind内容"""

        # 根节点
        root = {
            "id": "root",
            "title": f"{title} - 页面测试用例",
            "children": {
                "attached": []
            }
        }

        # 按页面分组
        page_groups = {}
        for tc in test_cases:
            page_name = tc.get("page_name", f"页面{tc.get('page_index', 1)}")
            if page_name not in page_groups:
                page_groups[page_name] = []
            page_groups[page_name].append(tc)

        # 添加页面统计
        stats_node = {
            "id": self._generate_id(),
            "title": f"共 {len(page_groups)} 个页面，{len(test_cases)} 个测试用例",
            "children": {"attached": []}
        }
        root["children"]["attached"].append(stats_node)

        # 测试类型映射（不使用图标）
        test_type_map = {
            "字段验证": "[字段验证]",
            "交互测试": "[交互测试]",
            "边界测试": "[边界测试]",
            "异常测试": "[异常测试]",
            "功能测试": "[功能测试]"
        }

        # 按页面添加节点
        for page_name, cases in page_groups.items():
            page_node = {
                "id": self._generate_id(),
                "title": f"{page_name} ({len(cases)}条)",
                "children": {"attached": []}
            }

            # 按测试类型分组
            type_groups = {}
            for tc in cases:
                test_type = tc.get("test_type", "功能测试")
                if test_type not in type_groups:
                    type_groups[test_type] = []
                type_groups[test_type].append(tc)

            # 添加测试类型节点
            for test_type, type_cases in type_groups.items():
                type_prefix = test_type_map.get(test_type, "[其他]")
                type_node = {
                    "id": self._generate_id(),
                    "title": f"{type_prefix} ({len(type_cases)}条)",
                    "children": {"attached": []}
                }

                for tc in type_cases:
                    scene = tc.get("scene", "未命名测试")
                    expected = tc.get("expected", "")
                    priority = tc.get("priority", "")
                    field_name = tc.get("field_name", "")
                    validation_point = tc.get("validation_point", "")

                    # 案例标题（不使用图标）
                    if field_name:
                        case_title = f"[{priority}] {field_name}: {scene}".strip() if priority else f"{field_name}: {scene}"
                    else:
                        case_title = f"[{priority}] {scene}".strip() if priority else scene

                    case_node = {
                        "id": self._generate_id(),
                        "title": case_title,
                        "children": {"attached": []}
                    }

                    # 添加字段名和验证点
                    if validation_point:
                        validation_node = {
                            "id": self._generate_id(),
                            "title": f"验证点: {validation_point}",
                            "children": {"attached": []}
                        }
                        case_node["children"]["attached"].append(validation_node)

                    # 添加预期结果
                    if expected:
                        expected_node = {
                            "id": self._generate_id(),
                            "title": f"预期: {expected}",
                            "children": {"attached": []}
                        }
                        case_node["children"]["attached"].append(expected_node)

                    # 添加测试步骤
                    test_steps = tc.get("test_steps", [])
                    if test_steps:
                        steps_node = {
                            "id": self._generate_id(),
                            "title": f"步骤 ({len(test_steps)}步)",
                            "children": {"attached": []}
                        }
                        for i, step in enumerate(test_steps, 1):
                            step_node = {
                                "id": self._generate_id(),
                                "title": f"{i}. {step}",
                                "children": {"attached": []}
                            }
                            steps_node["children"]["attached"].append(step_node)
                        case_node["children"]["attached"].append(steps_node)

                    type_node["children"]["attached"].append(case_node)

                page_node["children"]["attached"].append(type_node)

            root["children"]["attached"].append(page_node)

        return [{
            "rootTopic": root,
            "topicSelected": 0,
            "view": {
                "zoomLevel": 100,
                "showTheme": True
            },
            "selection": [],
            "lastModified": datetime.now().isoformat()
        }]

    def _build_xmind_content_by_module(
        self,
        title: str,
        test_cases: List[Dict[str, Any]],
        business_module: str
    ) -> List[Dict[str, Any]]:
        """按模块/接口维度构建XMind内容"""

        # 根节点
        root = {
            "id": "root",
            "title": f"{title} - 测试案例",
            "children": {
                "attached": []
            }
        }

        # 模块概览
        if business_module:
            overview_node = {
                "id": self._generate_id(),
                "title": f"业务模块: {business_module}",
                "children": {"attached": []}
            }
            root["children"]["attached"].append(overview_node)

        # 测试统计
        stats_node = {
            "id": self._generate_id(),
            "title": f"测试案例统计: 共{len(test_cases)}个",
            "children": {"attached": []}
        }
        root["children"]["attached"].append(stats_node)

        # 按接口分组（优先）或按模块分组
        interface_groups = {}
        module_groups = {}

        has_interface = any(tc.get("interface") for tc in test_cases)

        for tc in test_cases:
            module = tc.get("module", "其他")
            if module not in module_groups:
                module_groups[module] = []
            module_groups[module].append(tc)

            if has_interface:
                interface = tc.get("interface", "其他接口")
                if interface not in interface_groups:
                    interface_groups[interface] = []
                interface_groups[interface].append(tc)

        if has_interface:
            groups = interface_groups
            group_title_prefix = "[接口]"
        else:
            groups = module_groups
            group_title_prefix = "[模块]"

        # 测试类型映射（不使用图标）
        test_type_map = {
            "接口参数测试": "[参数测试]",
            "场景测试": "[场景测试]",
            "流程测试": "[流程测试]",
        }
        default_test_type = "[其他]"

        # 添加分组节点
        for group_name, cases in groups.items():
            group_node = {
                "id": self._generate_id(),
                "title": f"{group_title_prefix} {group_name}",
                "children": {"attached": []}
            }

            # 按测试类型分组
            type_groups = {}
            for tc in cases:
                test_type = tc.get("test_type", "接口参数测试")
                if test_type not in type_groups:
                    type_groups[test_type] = []
                type_groups[test_type].append(tc)

            # 添加测试类型节点
            for test_type, type_cases in type_groups.items():
                type_prefix = test_type_map.get(test_type, default_test_type)
                type_node = {
                    "id": self._generate_id(),
                    "title": f"{type_prefix} {test_type} ({len(type_cases)}条)",
                    "children": {"attached": []}
                }

                for tc in type_cases:
                    scene = tc.get("scene") or tc.get("title") or tc.get("description") or "未命名测试"
                    expected = tc.get("expected") or tc.get("expected_result") or ""
                    priority = tc.get("priority", "")

                    # 案例标题（不使用图标）
                    case_title = f"[{priority}] {scene}".strip() if priority else scene

                    case_node = {
                        "id": self._generate_id(),
                        "title": case_title,
                        "children": {"attached": []}
                    }

                    # 添加预期结果
                    if expected:
                        expected_node = {
                            "id": self._generate_id(),
                            "title": f"预期: {expected}",
                            "children": {"attached": []}
                        }
                        case_node["children"]["attached"].append(expected_node)

                    # 添加前置条件
                    if tc.get("precondition"):
                        precondition_node = {
                            "id": self._generate_id(),
                            "title": f"前置: {tc['precondition']}",
                            "children": {"attached": []}
                        }
                        case_node["children"]["attached"].append(precondition_node)

                    type_node["children"]["attached"].append(case_node)

                group_node["children"]["attached"].append(type_node)

            root["children"]["attached"].append(group_node)

        return [{
            "rootTopic": root,
            "topicSelected": 0,
            "view": {
                "zoomLevel": 100,
                "showTheme": True
            },
            "selection": [],
            "lastModified": datetime.now().isoformat()
        }]

    def _format_test_case_title(self, tc: Dict[str, Any]) -> str:
        """格式化测试案例标题"""
        title = tc.get("title", "未命名测试")
        priority = tc.get("priority", "")
        return f"[{priority}] {title}".strip() if priority else title
    
    def _generate_id(self) -> str:
        """生成唯一ID"""
        return f"id_{uuid.uuid4().hex[:8]}"


def parse_llm_response_to_test_cases(llm_response: str) -> List[Dict[str, Any]]:
    """
    解析LLM响应为测试案例列表
    增强版：处理截断、不完整JSON
    
    Args:
        llm_response: LLM返回的JSON格式响应
        
    Returns:
        测试案例列表
    """
    import re
    
    # 策略1: 尝试直接解析
    try:
        result = json.loads(llm_response)
        if isinstance(result, list):
            return result
    except:
        pass
    
    # 策略2: 尝试提取JSON数组
    json_match = re.search(r'\[.*\]', llm_response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except:
            pass
    
    # 策略3: 尝试解析markdown代码块
    code_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', llm_response, re.DOTALL)
    if code_match:
        try:
            return json.loads(code_match.group(1))
        except:
            pass
    
    # 策略4: 尝试修复截断的JSON（常见于输出被截断的情况）
    # 尝试补全未闭合的数组
    try:
        # 找到第一个 [ 和最后一个 ]
        start_idx = llm_response.find('[')
        end_idx = llm_response.rfind(']')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            truncated = llm_response[start_idx:end_idx+1]
            # 尝试补全可能的未闭合引号
            # 统计括号平衡
            open_braces = truncated.count('{')
            close_braces = truncated.count('}')
            open_brackets = truncated.count('[')
            close_brackets = truncated.count(']')
            
            # 如果括号不平衡，尝试修复
            if open_braces != close_braces or open_brackets != close_brackets:
                # 简单修复：补全到最后一个完整的对象
                result = []
                # 尝试找到所有完整的JSON对象
                obj_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', truncated)
                for obj in obj_matches:
                    try:
                        result.append(json.loads(obj))
                    except:
                        continue
                if result:
                    return result
    except:
        pass
    
    # 策略5: 尝试逐行解析，提取有效的JSON对象
    try:
        lines = llm_response.split('\n')
        objects = []
        current_obj = ""
        in_object = False
        brace_count = 0
        
        for line in lines:
            if '{' in line:
                in_object = True
            if in_object:
                current_obj += line + "\n"
                brace_count += line.count('{') - line.count('}')
                if brace_count == 0 and '}' in line:
                    # 一个完整的对象结束
                    try:
                        objects.append(json.loads(current_obj))
                    except:
                        pass
                    current_obj = ""
                    in_object = False
        
        if objects:
            return objects
    except:
        pass
    
    # 返回空列表
    logger = logging.getLogger(__name__)
    logger.warning(f"无法解析LLM响应为测试用例: {llm_response[:200]}...")
    return []



