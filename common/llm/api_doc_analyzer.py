"""
API文档分析器 - 解析OpenAPI/Swagger文档和接口说明文档。
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
from datetime import datetime

from common.llm.llm_client import LLMClient, MockLLMClient
from common.llm.api_test_prompts import (
    API_DOC_ANALYSIS_PROMPT,
    OPENAPI_ENHANCE_PROMPT,
    FLOWCHART_ANALYSIS_PROMPT,
)

logger = logging.getLogger(__name__)


class APIDocAnalyzer:
    """API文档分析器，支持OpenAPI和普通接口文档"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or MockLLMClient()

    def analyze_openapi(self, doc_content: str) -> List[Dict[str, Any]]:
        """
        分析OpenAPI 3.0/Swagger 2.0文档。
        doc_content: 可以是JSON字符串、文件路径或YAML内容
        """
        logger.info("【APIDocAnalyzer】开始分析OpenAPI文档")

        try:
            # 尝试解析为JSON
            if isinstance(doc_content, str):
                # 如果是文件路径，读取文件
                if os.path.isfile(doc_content):
                    with open(doc_content, 'r', encoding='utf-8') as f:
                        raw = f.read()
                else:
                    raw = doc_content

                # 尝试JSON解析
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    # 尝试YAML解析
                    try:
                        import yaml
                        data = yaml.safe_load(raw)
                    except ImportError:
                        logger.warning("【APIDocAnalyzer】YAML库未安装，尝试手动解析")
                        data = self._parse_yaml_manual(raw)
            else:
                data = doc_content

            # 判断OpenAPI版本
            if data.get("openapi", "").startswith("3."):
                return self._parse_openapi3(data)
            elif data.get("swagger") == "2.0":
                return self._parse_swagger2(data)
            else:
                # 未知格式，尝试LLM增强解析
                return self._enhance_with_llm(raw)

        except Exception as e:
            logger.error("【APIDocAnalyzer】解析OpenAPI文档失败: %s", str(e))
            return []

    def _parse_yaml_manual(self, raw: str) -> Dict[str, Any]:
        """手动解析简易YAML格式"""
        result = {}
        current_section = None
        lines = raw.split('\n')

        for line in lines:
            line = line.rstrip()
            if not line or line.strip().startswith('#'):
                continue

            # 检测section
            if line.endswith(':') and not line.endswith(':'):
                current_section = line.rstrip(':').strip()
                result[current_section] = {}
            elif ':' in line:
                key, _, value = line.partition(':')
                if current_section:
                    if isinstance(result.get(current_section), dict):
                        result[current_section][key.strip()] = value.strip().strip('"\'')
                else:
                    result[key.strip()] = value.strip().strip('"\'')

        return result

    def _parse_openapi3(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """解析OpenAPI 3.0格式"""
        interfaces = []
        paths = data.get("paths", {})

        for path, methods in paths.items():
            for method, details in methods.items():
                if method.upper() not in ("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"):
                    continue

                interface = {
                    "interface_name": details.get("summary", "") or details.get("operationId", path),
                    "description": details.get("description", ""),
                    "method": method.upper(),
                    "path": path,
                    "headers": {},
                    "request_params": [],
                    "response_params": [],
                    "scenarios": [],
                }

                # 解析parameters
                params = details.get("parameters", [])
                for p in params:
                    interface["request_params"].append({
                        "name": p.get("name", ""),
                        "type": p.get("schema", {}).get("type", "string"),
                        "required": p.get("required", False),
                        "description": p.get("description", ""),
                        "constraints": self._extract_constraints(p),
                        "example": p.get("example") or p.get("schema", {}).get("example", ""),
                        "in": p.get("in", "query"),
                    })

                # 解析requestBody
                request_body = details.get("requestBody", {})
                if request_body:
                    content = request_body.get("content", {})
                    json_content = content.get("application/json", {})
                    schema = json_content.get("schema", {})
                    interface["request_params"].extend(
                        self._parse_schema_to_params(schema, "body")
                    )

                # 解析responses
                responses = details.get("responses", {})
                for status_code, resp in responses.items():
                    if status_code == "200" or status_code.startswith("2"):
                        desc = resp.get("description", "")
                        resp_content = resp.get("content", {}).get("application/json", {}).get("schema")
                        if resp_content:
                            interface["response_params"].extend(
                                self._parse_schema_to_params(resp_content, "response")
                            )

                # 提取场景
                tags = details.get("tags", [])
                if tags:
                    interface["scenarios"] = tags

                interfaces.append(interface)

        logger.info("【APIDocAnalyzer】OpenAPI3解析完成，共 %d 个接口", len(interfaces))
        return interfaces

    def _parse_swagger2(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """解析Swagger 2.0格式"""
        interfaces = []
        paths = data.get("paths", {})
        definitions = data.get("definitions", {})

        for path, methods in paths.items():
            for method, details in methods.items():
                if method.upper() not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                    continue

                interface = {
                    "interface_name": details.get("summary", "") or details.get("operationId", path),
                    "description": details.get("description", ""),
                    "method": method.upper(),
                    "path": path,
                    "headers": {},
                    "request_params": [],
                    "response_params": [],
                    "scenarios": [],
                }

                # 解析parameters
                params = details.get("parameters", [])
                for p in params:
                    interface["request_params"].append({
                        "name": p.get("name", ""),
                        "type": p.get("type", "string"),
                        "required": p.get("required", False),
                        "description": p.get("description", ""),
                        "constraints": self._extract_constraints_swagger(p),
                        "example": p.get("x-example", ""),
                        "in": p.get("in", "query"),
                    })

                # 解析responses
                responses = details.get("responses", {})
                for status_code, resp in responses.items():
                    if status_code.startswith("2"):
                        schema = resp.get("schema", {})
                        if schema:
                            ref = schema.get("$ref", "")
                            if ref and "#/definitions/" in ref:
                                def_name = ref.split("/")[-1]
                                if def_name in definitions:
                                    interface["response_params"].extend(
                                        self._parse_definition(definitions[def_name], definitions)
                                    )

                tags = details.get("tags", [])
                if tags:
                    interface["scenarios"] = tags

                interfaces.append(interface)

        logger.info("【APIDocAnalyzer】Swagger2解析完成，共 %d 个接口", len(interfaces))
        return interfaces

    def _parse_schema_to_params(self, schema: Dict[str, Any], prefix: str = "") -> List[Dict[str, Any]]:
        """将OpenAPI schema转换为参数列表"""
        params = []
        if not schema:
            return params

        p_type = schema.get("type", "object")
        if p_type == "object":
            props = schema.get("properties", {})
            required = schema.get("required", [])
            for name, prop in props.items():
                params.append({
                    "name": name,
                    "type": prop.get("type", "string"),
                    "required": name in required,
                    "description": prop.get("description", ""),
                    "constraints": self._extract_constraints_from_schema(prop),
                    "example": prop.get("example", ""),
                    "in": prefix,
                })
                # 递归处理嵌套对象
                if prop.get("type") == "object":
                    nested = self._parse_schema_to_params(prop, f"{prefix}.{name}")
                    params.extend(nested)
        elif p_type == "array":
            items = schema.get("items", {})
            params.append({
                "name": "array_items",
                "type": "array",
                "description": f"数组项: {items.get('description', '')}",
                "constraints": "",
                "example": "",
                "in": prefix,
            })

        return params

    def _parse_definition(self, defn: Dict[str, Any], all_defs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """解析Swagger定义"""
        params = []
        props = defn.get("properties", {})
        required = defn.get("required", [])

        for name, prop in props.items():
            p_type = prop.get("type", "string")
            params.append({
                "name": name,
                "type": p_type,
                "required": name in required,
                "description": prop.get("description", ""),
                "example": prop.get("x-example", ""),
            })
            # 引用类型处理
            ref = prop.get("$ref", "")
            if ref and "#/definitions/" in ref:
                ref_name = ref.split("/")[-1]
                if ref_name in all_defs:
                    params.extend(self._parse_definition(all_defs[ref_name], all_defs))

        return params

    def _extract_constraints(self, param: Dict[str, Any]) -> str:
        """从OpenAPI参数中提取约束条件"""
        constraints = []
        schema = param.get("schema", {})

        if schema.get("minLength") is not None:
            constraints.append(f"最小长度={schema['minLength']}")
        if schema.get("maxLength") is not None:
            constraints.append(f"最大长度={schema['maxLength']}")
        if schema.get("minimum") is not None:
            constraints.append(f"最小值={schema['minimum']}")
        if schema.get("maximum") is not None:
            constraints.append(f"最大值={schema['maximum']}")
        if schema.get("pattern"):
            constraints.append(f"正则={schema['pattern']}")
        if schema.get("enum"):
            constraints.append(f"枚举={schema['enum']}")
        if schema.get("format"):
            constraints.append(f"格式={schema['format']}")

        return ", ".join(constraints)

    def _extract_constraints_swagger(self, param: Dict[str, Any]) -> str:
        """从Swagger 2.0参数中提取约束"""
        constraints = []
        if param.get("minLength") is not None:
            constraints.append(f"最小长度={param['minLength']}")
        if param.get("maxLength") is not None:
            constraints.append(f"最大长度={param['maxLength']}")
        if param.get("minimum") is not None:
            constraints.append(f"最小值={param['minimum']}")
        if param.get("maximum") is not None:
            constraints.append(f"最大值={param['maximum']}")
        if param.get("pattern"):
            constraints.append(f"正则={param['pattern']}")
        if param.get("enum"):
            constraints.append(f"枚举={param['enum']}")

        return ", ".join(constraints)

    def _extract_constraints_from_schema(self, schema: Dict[str, Any]) -> str:
        """从schema中提取约束"""
        constraints = []
        if schema.get("minLength") is not None:
            constraints.append(f"最小长度={schema['minLength']}")
        if schema.get("maxLength") is not None:
            constraints.append(f"最大长度={schema['maxLength']}")
        if schema.get("minimum") is not None:
            constraints.append(f"最小值={schema['minimum']}")
        if schema.get("maximum") is not None:
            constraints.append(f"最大值={schema['maximum']}")
        if schema.get("pattern"):
            constraints.append(f"正则={schema['pattern']}")
        if schema.get("enum"):
            constraints.append(f"枚举={schema['enum']}")

        return ", ".join(constraints)

    def _enhance_with_llm(self, raw_content: str) -> List[Dict[str, Any]]:
        """使用LLM增强解析未知格式的文档"""
        logger.info("【APIDocAnalyzer】使用LLM增强解析")

        try:
            prompt = OPENAPI_ENHANCE_PROMPT.format(openapi_content=raw_content[:80000])
            response, _ = self.llm.chat_with_prompt(prompt)

            # 提取JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                interfaces = data.get("interfaces", [])
                logger.info("【APIDocAnalyzer】LLM增强解析成功，%d 个接口", len(interfaces))
                return interfaces
        except Exception as e:
            logger.error("【APIDocAnalyzer】LLM增强解析失败: %s", str(e))

        return []

    def analyze_interface_doc(self, doc_text: str, doc_type: str = "docx") -> List[Dict[str, Any]]:
        """
        分析接口说明文档（Word等格式提取的纯文本）。
        doc_text: 从文档提取的文本内容
        doc_type: 文档类型（docx/pdf/html）
        """
        logger.info("【APIDocAnalyzer】开始分析接口文档，类型=%s", doc_type)

        try:
            prompt = API_DOC_ANALYSIS_PROMPT.format(api_doc_content=doc_text[:10000])
            response, _ = self.llm.chat_with_prompt(prompt)

            # 提取JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                if isinstance(data, dict):
                    data = [data]
                logger.info("【APIDocAnalyzer】接口文档分析完成，%d 个接口", len(data))
                return data
        except Exception as e:
            logger.error("【APIDocAnalyzer】接口文档分析失败: %s", str(e))

        return []


class FlowchartAnalyzer:
    """流程图分析器，从图片描述或文本描述中提取业务流程"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or MockLLMClient()

    @staticmethod
    def _parse_json_robust(text: str) -> Optional[Dict[str, Any]]:
        """
        健壮的 JSON 解析，尝试多种修复策略。
        1. 直接解析
        2. 智能提取 JSON 块 + 逐行修复
        3. 正则回退 + 逐行修复
        """
        import re

        def _try_parse(s: str) -> tuple:
            try:
                return json.loads(s), "直接解析"
            except json.JSONDecodeError:
                pass
            return None, ""

        def _smart_fix_json(s: str) -> str:
            """智能修复常见 JSON 格式问题"""
            lines = s.split('\n')
            fixed_lines = []
            i = 0
            while i < len(lines):
                line = lines[i]
                stripped = line.rstrip()

                # 跳过空行和注释行
                if not stripped or stripped.startswith('//') or stripped.startswith('#'):
                    i += 1
                    continue

                # 检查是否需要修复：行的末尾可能是未闭合的字符串
                # 例如: "content": "这是一个很长的
                #        内容跨越多行"
                # 通过引号计数判断
                in_string = False
                escape_next = False
                quote_count = 0
                for ch in stripped:
                    if escape_next:
                        escape_next = False
                        continue
                    if ch == '\\':
                        escape_next = True
                        continue
                    if ch == '"':
                        in_string = not in_string
                        quote_count += 1

                # 如果引号数量是奇数，说明字符串未闭合
                # 尝试从后续行找闭合引号
                if quote_count % 2 == 1:
                    merged_lines = [stripped]
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j].strip()
                        if not next_line or next_line.startswith('//') or next_line.startswith('#'):
                            j += 1
                            continue
                        merged_lines.append(next_line)
                        # 检查合并后引号是否平衡
                        merged = '\n'.join(merged_lines)
                        temp_quote = 0
                        temp_escape = False
                        for ch in merged:
                            if temp_escape:
                                temp_escape = False
                                continue
                            if ch == '\\':
                                temp_escape = True
                                continue
                            if ch == '"':
                                temp_quote += 1
                        if temp_quote % 2 == 0:
                            # 引号平衡了，修复成功
                            stripped = merged
                            i = j
                            break
                        j += 1
                    else:
                        # 找不到闭合，引号数奇数，强制闭合
                        stripped += '"'

                fixed_lines.append(stripped)
                i += 1

            return '\n'.join(fixed_lines)

        # 1. 直接解析
        data, method = _try_parse(text)
        if data is not None:
            return data

        # 2. 尝试正则提取第一个 JSON 对象 + 智能修复
        try:
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                json_str = match.group()
                fixed = _smart_fix_json(json_str)
                data, _ = _try_parse(fixed)
                if data is not None:
                    return data
        except Exception:
            pass

        # 3. 修复后再次尝试原始文本
        fixed = _smart_fix_json(text)
        data, _ = _try_parse(fixed)
        if data is not None:
            return data

        return None

    def analyze_text_description(self, description: str) -> Dict[str, Any]:
        """
        从文本描述中分析流程。
        description: 流程的文字描述
        """
        logger.info("【FlowchartAnalyzer】开始分析流程描述")

        try:
            prompt = FLOWCHART_ANALYSIS_PROMPT.format(flowchart_description=description)
            response, _ = self.llm.chat_with_prompt(prompt)

            data = self._parse_json_robust(response)
            if data is not None:
                logger.info("【FlowchartAnalyzer】流程分析完成，节点数=%d",
                            len(data.get("nodes", [])))
                return data
        except Exception as e:
            logger.error("【FlowchartAnalyzer】流程分析失败: %s", str(e))

        return {"flow_name": "", "nodes": [], "dependencies": [], "entry_point": "", "critical_paths": []}

    def analyze_image_base64(self, image_base64: str, description: str = "") -> Dict[str, Any]:
        """
        从图片（Base64编码）中分析流程图。
        需要支持多模态的LLM。
        """
        logger.info("【FlowchartAnalyzer】开始分析流程图图片")

        # 统一处理：无论传入的是纯 base64 还是有 data-URI 前缀，
        # 都只取 base64 主体部分，然后自行拼接正确的 data-URI 前缀。
        b64_body = image_base64
        if image_base64.startswith("data:"):
            # 提取 ;base64, 之后的部分
            sep = ";base64,"
            idx = image_base64.find(sep)
            if idx != -1:
                b64_body = image_base64[idx + len(sep):]
            else:
                # 有 data: 但格式不对，直接取 : 之后的内容
                b64_body = image_base64.split(":", 1)[1]
                if "," in b64_body:
                    b64_body = b64_body.split(",", 1)[1]

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"请分析以下流程图，提取业务流程信息。{description}"
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64_body}"}
                    }
                ]
            }
        ]

        try:
            response, _ = self.llm.chat(messages)

            data = self._parse_json_robust(response)
            if data is not None:
                return data
        except Exception as e:
            logger.error("【FlowchartAnalyzer】图片分析失败: %s", str(e))

        # 回退到文本分析模式
        return self.analyze_text_description(f"流程图内容：{description}")

    def build_test_chain(self, flow_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        根据流程数据构建测试链。
        返回按执行顺序排列的测试步骤列表。
        """
        nodes = flow_data.get("nodes", [])
        dependencies = flow_data.get("dependencies", [])
        entry_point = flow_data.get("entry_point", "")

        # 构建节点ID到节点的映射
        node_map = {n.get("id"): n for n in nodes}

        # 拓扑排序
        test_chain = []
        visited = set()

        def visit(node_id: str):
            if node_id in visited or node_id not in node_map:
                return
            visited.add(node_id)
            node = node_map[node_id]
            test_chain.append({
                "node_id": node_id,
                "name": node.get("name", ""),
                "type": node.get("type", "action"),
                "api_path": node.get("api_path", ""),
                "method": node.get("method", "POST"),
                "params": node.get("params", {}),
                "conditions": node.get("conditions", {}),
            })
            for next_id in node.get("next_nodes", []):
                visit(next_id)

        if entry_point:
            visit(entry_point)
        else:
            # 如果没有明确的入口点，按依赖顺序
            for dep in dependencies:
                visit(dep.get("from"))

        logger.info("【FlowchartAnalyzer】构建测试链完成，%d 个步骤", len(test_chain))
        return test_chain
