"""
API自动化测试 - 报告生成器
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from common.test_executor.api_test_runner import TestResult

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    测试报告生成器。
    支持生成JSON、HTML和Allure格式报告。
    """

    def __init__(self, output_dir: str = "outputs/reports"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_json_report(
        self,
        results: List[TestResult],
        summary: Dict[str, Any],
        execution_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        生成JSON格式报告。
        返回报告文件路径。
        """
        report = {
            "execution_id": execution_id,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": summary,
            "metadata": metadata or {},
            "results": [r.to_dict() for r in results],
        }

        file_name = f"{execution_id}.json"
        file_path = os.path.join(self.output_dir, file_name)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info("【ReportGenerator】JSON报告已生成: %s", file_path)
        return file_path

    def generate_html_report(
        self,
        results: List[TestResult],
        summary: Dict[str, Any],
        execution_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        生成HTML格式报告。
        返回报告文件路径。
        """
        passed = [r for r in results if r.status == "passed"]
        failed = [r for r in results if r.status == "failed"]
        errors = [r for r in results if r.status == "error"]

        html_content = self._build_html(
            execution_id, summary, results, passed, failed, errors, metadata
        )

        file_name = f"{execution_id}.html"
        file_path = os.path.join(self.output_dir, file_name)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info("【ReportGenerator】HTML报告已生成: %s", file_path)
        return file_path

    def _build_html(
        self,
        execution_id: str,
        summary: Dict[str, Any],
        results: List[TestResult],
        passed: List[TestResult],
        failed: List[TestResult],
        errors: List[TestResult],
        metadata: Optional[Dict[str, Any]],
    ) -> str:
        """构建HTML报告内容"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        success_rate = summary.get("success_rate", 0)

        # 状态颜色
        def status_color(status: str) -> str:
            return {"passed": "#28a745", "failed": "#dc3545", "error": "#ffc107", "skipped": "#6c757d"}.get(status, "#6c757d")

        # 结果行HTML
        def result_row(r: TestResult) -> str:
            color = status_color(r.status)
            assertions_html = ""
            for a in r.assertions:
                a_color = "#28a745" if a.get("passed") else "#dc3545"
                assertions_html += f'<div class="assertion-item" style="color:{a_color}">{"✓" if a.get("passed") else "✗"} {a.get("name","")}: {a.get("message","")}</div>'
            error_html = f'<div class="error-msg">{r.error or ""}</div>' if r.error else ""
            resp_preview = json.dumps(r.response_body, ensure_ascii=False)[:200] if r.response_body else ""
            return f"""
            <tr>
                <td>{r.case_name}</td>
                <td style="color:{color};font-weight:bold">{r.status.upper()}</td>
                <td>{r.duration_ms:.1f}ms</td>
                <td>{r.response_time_ms}ms</td>
                <td>{r.status_code or "-"}</td>
                <td class="assertions-cell">{assertions_html}</td>
                <td class="response-cell">{resp_preview}</td>
                <td>{error_html}</td>
            </tr>"""

        passed_rows = "\n".join(result_row(r) for r in passed)
        failed_rows = "\n".join(result_row(r) for r in failed)
        error_rows = "\n".join(result_row(r) for r in errors)

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>API测试报告 - {execution_id}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
  .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; }}
  .header h1 {{ font-size: 24px; margin-bottom: 10px; }}
  .header .meta {{ opacity: 0.9; font-size: 14px; }}
  .summary-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }}
  .card {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
  .card .label {{ color: #666; font-size: 13px; text-transform: uppercase; }}
  .card .value {{ font-size: 28px; font-weight: bold; margin-top: 5px; }}
  .card.total {{ border-left: 4px solid #667eea; }}
  .card.passed {{ border-left: 4px solid #28a745; }}
  .card.failed {{ border-left: 4px solid #dc3545; }}
  .card.error {{ border-left: 4px solid #ffc107; }}
  .card.rate {{ border-left: 4px solid #17a2b8; }}
  .card.rate .value {{ color: {'#28a745' if success_rate >= 80 else '#ffc107' if success_rate >= 60 else '#dc3545'}; }}
  .section {{ background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; overflow: hidden; }}
  .section-header {{ padding: 15px 20px; font-weight: bold; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }}
  .section-header .badge {{ padding: 3px 10px; border-radius: 12px; font-size: 12px; color: white; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: #f8f9fa; padding: 12px 10px; text-align: left; font-weight: 600; border-bottom: 2px solid #dee2e6; position: sticky; top: 0; }}
  td {{ padding: 10px; border-bottom: 1px solid #eee; vertical-align: top; }}
  .assertions-cell {{ max-width: 300px; }}
  .assertion-item {{ font-size: 12px; padding: 2px 0; }}
  .response-cell {{ max-width: 200px; word-break: break-all; font-size: 12px; color: #666; }}
  .error-msg {{ color: #dc3545; font-size: 12px; margin-top: 5px; }}
  .status-passed {{ color: #28a745; }}
  .status-failed {{ color: #dc3545; }}
  .status-error {{ color: #ffc107; }}
  .empty-section {{ padding: 40px; text-align: center; color: #999; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>API自动化测试报告</h1>
    <div class="meta">
      <div>执行ID: {execution_id}</div>
      <div>生成时间: {now_str}</div>
    </div>
  </div>

  <div class="summary-cards">
    <div class="card total">
      <div class="label">总用例数</div>
      <div class="value">{summary.get('total', 0)}</div>
    </div>
    <div class="card passed">
      <div class="label">通过</div>
      <div class="value">{len(passed)}</div>
    </div>
    <div class="card failed">
      <div class="label">失败</div>
      <div class="value">{len(failed)}</div>
    </div>
    <div class="card error">
      <div class="label">异常</div>
      <div class="value">{len(errors)}</div>
    </div>
    <div class="card rate">
      <div class="label">成功率</div>
      <div class="value">{success_rate}%</div>
    </div>
    <div class="card">
      <div class="label">总耗时</div>
      <div class="value">{summary.get('total_duration_ms', 0):.0f}ms</div>
    </div>
  </div>

  {"<div class='section'>" if failed else ""}
  {"<div class='section-header'>" + f"<span>失败用例 ({len(failed)})</span>" + "</div><table><thead><tr><th>用例名称</th><th>状态</th><th>耗时</th><th>响应时间</th><th>状态码</th><th>断言结果</th><th>响应预览</th><th>错误信息</th></tr></thead><tbody>{failed_rows}</tbody></table></div>" if failed else "</div>"}
  {"<div class='section'>" if errors else ""}
  {"<div class='section-header'>" + f"<span>异常用例 ({len(errors)})</span>" + "</div><table><thead><tr><th>用例名称</th><th>状态</th><th>耗时</th><th>响应时间</th><th>状态码</th><th>断言结果</th><th>响应预览</th><th>错误信息</th></tr></thead><tbody>{error_rows}</tbody></table></div>" if errors else "</div>"}

  <div class="section">
    <div class="section-header">
      <span>全部用例 ({len(results)})</span>
    </div>
    <table>
      <thead>
        <tr>
          <th>用例名称</th>
          <th>状态</th>
          <th>耗时</th>
          <th>响应时间</th>
          <th>状态码</th>
          <th>断言结果</th>
          <th>响应预览</th>
          <th>错误信息</th>
        </tr>
      </thead>
      <tbody>
        {passed_rows}{failed_rows}{error_rows}
      </tbody>
    </table>
  </div>
</div>
</body>
</html>"""

    def generate_allure_report(
        self,
        results: List[TestResult],
        execution_id: str,
        output_dir: Optional[str] = None
    ) -> str:
        """
        生成Allure兼容的JSON报告。
        返回报告目录路径。
        """
        allure_dir = os.path.join(output_dir or self.output_dir, f"{execution_id}-allure")
        os.makedirs(allure_dir, exist_ok=True)

        # 生成allure的 suites.json
        suite_data = {
            "name": f"API Auto Test - {execution_id}",
            "children": [],
            "suites": [],
        }

        for i, r in enumerate(results):
            test_uuid = f"{execution_id}-{i}"
            case_data = {
                "name": r.case_name,
                "status": r.status,
                "time": {"start": 0, "stop": int(r.duration_ms), "duration": int(r.duration_ms)},
                "statusMessage": r.error or "",
                "description": "",
                "testCaseId": str(r.case_id),
                "steps": [],
            }

            # 添加步骤
            case_data["steps"].append({
                "name": "Send Request",
                "status": "passed",
                "time": {"start": 0, "stop": int(r.response_time_ms)},
                "attachments": [
                    {
                        "name": "Response",
                        "type": "text/plain",
                        "source": f"{test_uuid}-response.txt",
                    }
                ],
            })

            # 断言步骤
            for a in r.assertions:
                case_data["steps"].append({
                    "name": f"Assert: {a.get('name', '')}",
                    "status": "passed" if a.get("passed") else "failed",
                    "time": {"start": 0, "stop": 0},
                })

            # 保存响应附件
            resp_file = os.path.join(allure_dir, f"{test_uuid}-response.txt")
            with open(resp_file, 'w', encoding='utf-8') as f:
                f.write(json.dumps(r.response_body, ensure_ascii=False, indent=2) if r.response_body else "")

            suite_data["children"].append(case_data)

        # 保存 suites.json
        with open(os.path.join(allure_dir, "suites.json"), 'w', encoding='utf-8') as f:
            json.dump(suite_data, f, ensure_ascii=False, indent=2)

        logger.info("【ReportGenerator】Allure报告已生成: %s", allure_dir)
        return allure_dir
