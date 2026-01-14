# app/connectors/confluence_simple_connector.py
import os
import logging
from typing import List, Dict, Any, Optional
import requests
from base64 import b64encode

from common.rag.connectors.base_connector import BaseConnector
from common.rag.core.models import Document, DocumentType

logger = logging.getLogger(__name__)


class ConfluenceSimpleConnector(BaseConnector):
    """简化版Confluence连接器"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.base_url = self.config.get('url', '').rstrip('/')
        self.auth = None
        self._setup_auth()

    def _setup_auth(self):
        """设置认证"""
        username = self.config.get('username')
        password = self.config.get('password')

        if username and password:
            # 使用基本认证
            self.auth = (username, password)
        else:
            raise ValueError("需要提供用户名和密码")

    def _make_request(self, url: str) -> Optional[Dict]:
        """发送请求"""
        try:
            response = requests.get(
                url,
                auth=self.auth,
                headers={'Accept': 'application/json'},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"请求失败 {url}: {e}")
            return None

    def collect(self, source_config: Dict[str, Any]) -> List[Document]:
        """
        简单采集 - 只获取特定空间的页面

        Args:
            source_config: 必须包含 space_key

        Returns:
            文档列表
        """
        space_key = source_config.get('space_key')
        if not space_key:
            logger.error("需要指定space_key")
            return []

        limit = source_config.get('limit', 50)

        # 获取空间中的页面
        url = f"{self.base_url}/rest/api/content"
        params = {
            'spaceKey': space_key,
            'type': 'page',
            'expand': 'body.storage,version',
            'limit': limit
        }

        try:
            response = requests.get(
                url,
                params=params,
                auth=self.auth,
                headers={'Accept': 'application/json'},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            documents = []
            for page in data.get('results', []):
                doc = self._create_document_from_page(page)
                if doc:
                    documents.append(doc)

            logger.info(f"从空间 {space_key} 采集到 {len(documents)} 个文档")
            return documents

        except Exception as e:
            logger.error(f"采集失败: {e}")
            return []

    def _create_document_from_page(self, page: Dict) -> Optional[Document]:
        """从页面数据创建文档"""
        try:
            page_id = page.get('id')
            title = page.get('title', '')
            body_html = page.get('body', {}).get('storage', {}).get('value', '')

            if not body_html:
                return None

            # 简单清理HTML
            import re
            clean_text = re.sub(r'<[^>]+>', ' ', body_html)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()

            if not clean_text:
                return None

            metadata = {
                'page_id': page_id,
                'page_title': title,
                'space_key': page.get('space', {}).get('key', ''),
                'url': f"{self.base_url}/pages/viewpage.action?pageId={page_id}",
            }

            return self._create_document(
                content=clean_text,
                source_type='confluence_page',
                source_uri=metadata['url'],
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"创建文档失败: {e}")
            return None