"""
测试报告生成器。

负责将测试执行结果生成为 HTML 和 JSON 格式的报告文件。
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional


class ReportGenerator:
    """
    测试报告生成器。

    将 APITestRunner 的执行结果转换为可读的报告文件。
    """

    def __init__(self, output_dir: str = "outputs/reports"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_html_report(
        self,
        results: List[Any],
        summary: Dict[str, Any],
        execution_id: str,
    ) -> str:
        """
        生成 HTML 格式的测试报告。

        Args:
            results: 测试结果列表
            summary: 测试汇总信息
            execution_id: 执行 ID

        Returns:
            报告文件路径
        """
        html_path = os.path.join(self.output_dir, f"{execution_id}.html")

        rows = []
        for r in results:
            status_cls = "passed" if getattr(r, "status", "") == "passed" else "failed"
            rows.append(
                f"<tr class='{status_cls}'>"
                f"<td>{getattr(r, 'case_id', '-')}</td>"
                f"<td>{getattr(r, 'case_name', '-')}</td>"
                f"<td>{getattr(r, 'status', '-')}</td>"
                f"<td>{getattr(r, 'duration_ms', 0):.1f}ms</td>"
                f"<td>{getattr(r, 'error_message', '') or ''}</td>"
                f"</tr>"
            )

        html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>测试报告 - {execution_id}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background: #4CAF50; color: white; }}
tr.passed {{ background: #e8f5e9; }}
tr.failed {{ background: #ffebee; }}
.summary {{ margin-bottom: 20px; padding: 15px; background: #f5f5f5; border-radius: 5px; }}
</style>
</head>
<body>
<h1>测试执行报告</h1>
<div class="summary">
  <strong>执行ID:</strong> {execution_id}<br>
  <strong>生成时间:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
  <strong>总数:</strong> {summary.get('total', 0)}&nbsp;
  <strong>通过:</strong> {summary.get('passed', 0)}&nbsp;
  <strong>失败:</strong> {summary.get('failed', 0)}&nbsp;
  <strong>错误:</strong> {summary.get('error', 0)}
</div>
<table>
  <tr><th>用例ID</th><th>用例名称</th><th>状态</th><th>耗时</th><th>错误信息</th></tr>
  {''.join(rows)}
</table>
</body>
</html>"""
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)
        return html_path

    def generate_json_report(
        self,
        results: List[Any],
        summary: Dict[str, Any],
        execution_id: str,
    ) -> str:
        """
        生成 JSON 格式的测试报告。

        Args:
            results: 测试结果列表
            summary: 测试汇总信息
            execution_id: 执行 ID

        Returns:
            报告文件路径
        """
        json_path = os.path.join(self.output_dir, f"{execution_id}.json")
        data = {
            "execution_id": execution_id,
            "generated_at": datetime.now().isoformat(),
            "summary": summary,
            "results": [
                {
                    "case_id": getattr(r, "case_id", "-"),
                    "case_name": getattr(r, "case_name", "-"),
                    "status": getattr(r, "status", "-"),
                    "duration_ms": getattr(r, "duration_ms", 0),
                    "error_message": getattr(r, "error_message", "") or "",
                }
                for r in results
            ],
        }
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return json_path
