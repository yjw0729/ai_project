"""
DocumentParserService 文档解析服务

负责从各种技术文档中提取接口信息。
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class DocumentParserService:
    """文档解析服务"""

    def __init__(self, llm_client=None):
        """
        初始化文档解析服务

        Args:
            llm_client: LLM客户端实例（可选），用于调用大模型辅助解析
        """
        self.llm_client = llm_client

    def parse(self, doc_content: str, doc_type: str, use_llm: bool = False) -> Dict[str, Any]:
        """
        解析文档内容，提取接口信息

        Args:
            doc_content: 文档内容
            doc_type: 文档类型 (tech_spec/api_doc/prd)
            use_llm: 是否使用LLM辅助解析

        Returns:
            {
                "interfaces": [...],
                "document_structure": {...},
                "business_rules": [...],
                "metadata": {...}
            }
        """
        try:
            logger.info(f"开始解析文档, 类型={doc_type}, use_llm={use_llm}")

            if use_llm and self.llm_client:
                return self._parse_with_llm(doc_content, doc_type)
            else:
                return self._parse_structured(doc_content, doc_type)

        except Exception as e:
            logger.error(f"文档解析失败: {e}")
            return {'interfaces': [], 'error': str(e)}

    def _parse_structured(self, doc_content: str, doc_type: str) -> Dict[str, Any]:
        """
        结构化解析（基于规则和正则）

        Args:
            doc_content: 文档内容
            doc_type: 文档类型

        Returns:
            解析结果字典
        """
        interfaces = []

        # 通用HTTP方法
        http_methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']

        # 匹配接口路径的正则: GET /api/path 或 POST /api/path/{id}
        path_pattern = re.compile(
            r'((?:' + '|'.join(http_methods) + r')\s+(/\S+))',
            re.IGNORECASE
        )

        matches = path_pattern.findall(doc_content)
        for match in matches:
            method_path = match[0].strip()
            parts = method_path.split(None, 1)
            if len(parts) == 2:
                method, path = parts
                interfaces.append({
                    'interface_name': self._infer_name_from_path(path),
                    'method': method.upper(),
                    'path': path,
                    'description': '',
                    'request_params': {},
                    'response_params': {},
                    'business_rules': [],
                })

        # 去除重复
        seen = set()
        unique_interfaces = []
        for iface in interfaces:
            key = f"{iface['method']} {iface['path']}"
            if key not in seen:
                seen.add(key)
                unique_interfaces.append(iface)

        return {
            'interfaces': unique_interfaces,
            'interface_count': len(unique_interfaces),
            'document_type': doc_type,
        }

    def _parse_with_llm(self, doc_content: str, doc_type: str) -> Dict[str, Any]:
        """
        使用LLM辅助解析文档

        Args:
            doc_content: 文档内容
            doc_type: 文档类型

        Returns:
            解析结果字典
        """
        if not self.llm_client:
            return self._parse_structured(doc_content, doc_type)

        try:
            # 构建提示词
            prompt = self._build_llm_prompt(doc_content, doc_type)

            # 调用LLM
            response = self.llm_client.generate(prompt)

            # 解析LLM返回的JSON
            result = json.loads(response)

            return result

        except json.JSONDecodeError as e:
            logger.warning(f"LLM返回格式错误，降级为结构化解析: {e}")
            return self._parse_structured(doc_content, doc_type)
        except Exception as e:
            logger.error(f"LLM解析失败: {e}")
            return self._parse_structured(doc_content, doc_type)

    def _build_llm_prompt(self, doc_content: str, doc_type: str) -> str:
        """构建LLM提示词"""
        return f"""你是资深技术文档分析师。请从以下{doc_type}类型文档中提取所有接口信息。

文档内容：
{doc_content[:8000]}

请返回JSON格式：
{{
    "interfaces": [
        {{
            "interface_name": "接口名称",
            "method": "GET/POST/PUT/DELETE",
            "path": "/api/path",
            "description": "接口描述",
            "request_params": "请求参数描述",
            "response_params": "响应参数描述",
            "business_rules": ["业务规则1", "业务规则2"]
        }}
    ],
    "document_structure": {{
        "basic_knowledge": "基础知识",
        "service_content": "服务内容",
        "api_section": "API部分"
    }}
}}
"""

    def _infer_name_from_path(self, path: str) -> str:
        """
        从路径推断接口名称

        Args:
            path: API路径，如 /api/users/{id}

        Returns:
            推断的接口名称
        """
        # 移除路径变量
        clean_path = re.sub(r'\{[^}]+\}', '', path)
        # 移除多余斜杠
        clean_path = re.sub(r'/+', '/', clean_path)
        # 移除首尾斜杠
        clean_path = clean_path.strip('/')
        # 取最后一段作为名称
        parts = clean_path.split('/')
        if parts:
            name = parts[-1]
            # 下划线转驼峰
            name = ''.join(word.capitalize() for word in name.split('_'))
            return name
        return 'UnknownInterface'

    def extract_tables(self, doc_content: str) -> List[Dict[str, str]]:
        """
        从文档中提取表格数据

        Args:
            doc_content: 文档内容

        Returns:
            表格列表，每张表格是一个字典列表
        """
        tables = []
        lines = doc_content.split('\n')

        current_table = []
        in_table = False

        for line in lines:
            stripped = line.strip()
            # 检测表格分隔符（如 |---|---|
            if re.match(r'^\|[\s\-:|]+\|$', stripped):
                in_table = True
                continue

            if in_table:
                if stripped.startswith('|'):
                    cells = [c.strip() for c in stripped.split('|')[1:-1]]
                    if cells and any(cells):
                        current_table.append(cells)
                else:
                    if current_table:
                        tables.append(current_table)
                        current_table = []
                    in_table = False

        if current_table:
            tables.append(current_table)

        return tables

    def extract_json_examples(self, doc_content: str) -> Dict[str, Any]:
        """
        从文档中提取JSON示例

        Args:
            doc_content: 文档内容

        Returns:
            JSON示例字典
        """
        json_examples = {}

        # 匹配JSON代码块
        json_pattern = re.compile(r'```(?:json)?\s*([\s\S]*?)\s*```')
        matches = json_pattern.findall(doc_content)

        for i, match in enumerate(matches):
            try:
                parsed = json.loads(match.strip())
                json_examples[f'example_{i + 1}'] = parsed
            except json.JSONDecodeError:
                continue

        return json_examples
