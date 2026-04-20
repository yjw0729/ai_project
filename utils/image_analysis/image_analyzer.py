# -*- coding: utf-8 -*-
"""
公共图片分析模块

提供统一的图片OCR和流程图分析功能，供全项目复用。
"""

import base64
import logging
from typing import Optional, Dict, Any, Union
from pathlib import Path

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    DEFAULT_MODEL = "qwen3.5-plus"

    FLOWCHART_ANALYSIS_PROMPT = """请分析这张系统交互流程图或泳道图，提取以下信息：
1. 涉及的系统和组件（有哪些参与方）
2. 各系统之间的交互顺序和调用关系
3. 图中所标明的的业务流程步骤包括正向流程和异常的流程，
4. 关键的数据流向
5. 是否有分支、循环、并行等特殊逻辑，如果存在那么将这些逻辑查找狐出来

使用资深产品设计工程师的角度，用结构化的方式描述这个图内的业务流程，
如果图片不包含流程图信息，请说明"未识别到流程图"。"""

    GENERAL_OCR_PROMPT = """请识别图片中的所有文字内容，保持原有格式。如果是流程图或表格，请描述其结构。"""

    def __init__(self, model: str = None, ai_type: Optional[str] = None):
        """
        Args:
            model: 直接指定模型名称（如 "qwen-vl-max"）。
                   与 ai_type 二选一，ai_type 优先。
            ai_type: 模型配置名称，对应 ai_config.json 中 models 下的 key。
                     传入时会自动从配置中解析 base_url、model、api_key。
        """
        if ai_type:
            from common.config import get_model_config
            cfg = get_model_config(ai_type)
            if cfg:
                self.model = cfg.get("model", self.DEFAULT_MODEL)
                self._config_api_key = cfg.get("api_key", "")
            else:
                self.model = model or self.DEFAULT_MODEL
                self._config_api_key = ""
        else:
            self.model = model or self.DEFAULT_MODEL
            self._config_api_key = ""

    def _get_api_key(self) -> Optional[str]:
        import os
        # 优先使用配置中的 api_key，其次环境变量
        if self._config_api_key:
            return self._config_api_key
        return os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("OPENAI_API_KEY")

    def _call_multimodal_model(
        self,
        image_bytes: bytes,
        prompt: str,
        image_format: str = "png"
    ) -> Optional[str]:
        try:
            import dashscope
            from dashscope import MultiModalConversation

            api_key = self._get_api_key()
            if not api_key:
                logger.warning("未设置 DASHSCOPE_API_KEY 环境变量")
                return None

            dashscope.api_key = api_key
            img_base64 = base64.b64encode(image_bytes).decode('utf-8')

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"image": f"data:image/{image_format};base64,{img_base64}"},
                        {"text": prompt}
                    ]
                }
            ]

            response = MultiModalConversation.call(model=self.model, messages=messages)

            if response.status_code == 200:
                result_content = response.output.choices[0].message.content
                analysis_text = ""
                for item in result_content:
                    if 'text' in item:
                        analysis_text += item['text']
                return analysis_text
            else:
                logger.warning(f"模型调用失败: {response.code} - {response.message}")
                return None

        except Exception as e:
            logger.error(f"调用多模态模型失败: {e}", exc_info=True)
            return None

    def analyze_flowchart(
        self,
        image_bytes: bytes = None,
        image_path: str = None,
        image_format: str = "png"
    ) -> Dict[str, Any]:
        if image_path:
            try:
                with open(image_path, "rb") as f:
                    image_bytes = f.read()
            except Exception as e:
                logger.error(f"读取图片文件失败: {e}")
                return {"success": False, "error": f"读取图片文件失败: {e}", "analysis": ""}

        if not image_bytes:
            return {"success": False, "error": "未提供图片数据", "analysis": ""}

        logger.info(f"开始分析流程图图片...")
        result = self._call_multimodal_model(
            image_bytes=image_bytes,
            prompt=self.FLOWCHART_ANALYSIS_PROMPT,
            image_format=image_format
        )

        if result is not None:
            logger.info(f"流程图分析完成，结果长度: {len(result)}")
            return {"success": True, "analysis": result, "error": ""}
        else:
            return {"success": False, "error": "模型调用失败", "analysis": ""}

    def extract_text(
        self,
        image_bytes: bytes = None,
        image_path: str = None,
        image_format: str = "png"
    ) -> Dict[str, Any]:
        if image_path:
            try:
                with open(image_path, "rb") as f:
                    image_bytes = f.read()
            except Exception as e:
                logger.error(f"读取图片文件失败: {e}")
                return {"success": False, "error": f"读取图片文件失败: {e}", "text": ""}

        if not image_bytes:
            return {"success": False, "error": "未提供图片数据", "text": ""}

        logger.info(f"开始识别图片文字...")
        result = self._call_multimodal_model(
            image_bytes=image_bytes,
            prompt=self.GENERAL_OCR_PROMPT,
            image_format=image_format
        )

        if result is not None:
            logger.info(f"文字识别完成，结果长度: {len(result)}")
            return {"success": True, "text": result, "error": ""}
        else:
            return {"success": False, "error": "模型调用失败", "text": ""}

    def analyze(
        self,
        image_bytes: bytes = None,
        image_path: str = None,
        mode: str = "flowchart",
        image_format: str = "png"
    ) -> Dict[str, Any]:
        if mode == "flowchart":
            return self.analyze_flowchart(image_bytes, image_path, image_format)
        elif mode == "ocr":
            return self.extract_text(image_bytes, image_path, image_format)
        else:
            return {"success": False, "error": f"未知的分析模式: {mode}", "analysis": ""}


def analyze_image(
    image_bytes: bytes = None,
    image_path: str = None,
    mode: str = "flowchart",
    image_format: str = "png"
) -> Dict[str, Any]:
    analyzer = ImageAnalyzer()
    return analyzer.analyze(image_bytes, image_path, mode, image_format)


def analyze_flowchart(
    image_bytes: bytes = None,
    image_path: str = None,
    image_format: str = "png"
) -> Dict[str, Any]:
    analyzer = ImageAnalyzer()
    return analyzer.analyze_flowchart(image_bytes, image_path, image_format)


def extract_image_text(
    image_bytes: bytes = None,
    image_path: str = None,
    image_format: str = "png"
) -> Dict[str, Any]:
    analyzer = ImageAnalyzer()
    return analyzer.extract_text(image_bytes, image_path, image_format)


def analyze_flowchart_image(image_bytes: bytes, image_index: int = 0) -> dict:
    analyzer = ImageAnalyzer()
    result = analyzer.analyze_flowchart(image_bytes=image_bytes)
    return {
        "success": result["success"],
        "analysis": result.get("analysis", ""),
        "image_index": image_index,
        "error": result.get("error", "")
    }
