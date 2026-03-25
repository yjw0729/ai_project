"""
回填缺失的汇总记录

执行方式：
    python check_tasks_result.py

此脚本将 doc_id=46710f28-387a-4c42-a433-374ccbebc9d3 的记录从明细表回填到汇总表。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.db_mapper.review_summary_mapper import ReviewSummaryMapper
from common.db_mapper.review_record_mapper import ReviewRecordMapper

DOC_ID = "46710f28-387a-4c42-a433-374ccbebc9d3"


def main():
    print(f"[回填脚本] 开始回填汇总记录, doc_id={DOC_ID}")

    # 1. 从明细表查询该文档的统计信息
    try:
        record_mapper = ReviewRecordMapper()
        detail = record_mapper.get_review_detail(DOC_ID)
    except Exception as e:
        print(f"[回填脚本] 查询明细记录失败: {e}")
        detail = None

    if detail:
        document_title = detail.get('document_title', '基于SCA的用户授权服务')
        business_module = detail.get('business_module', '')
        document_type = detail.get('document_type', 'api_doc')
        interface_count = detail.get('interface_count', 0)
        image_count = detail.get('image_count', 0)
        print(f"[回填脚本] 从明细表获取: title={document_title}, interfaces={interface_count}, images={image_count}")
    else:
        # 兜底：从日志已知的信息
        document_title = "基于SCA的用户授权服务"
        business_module = ""
        document_type = "api_doc"
        interface_count = 8
        image_count = 10
        print(f"[回填脚本] 使用默认数据: interfaces={interface_count}, images={image_count}")

    # 2. 检查汇总表是否已有该记录
    summary_mapper = ReviewSummaryMapper()
    existing = summary_mapper.get_by_doc_id(DOC_ID)

    if existing:
        print(f"[回填脚本] 汇总表已存在该记录 (id={existing.get('id')})，更新...")
        result = summary_mapper.upsert(
            doc_id=DOC_ID,
            document_title=document_title,
            business_module=business_module,
            document_type=document_type,
            interface_count=interface_count,
            image_count=image_count,
            general_image_count=image_count,  # 不区分流程图，统一算知识类图片
            test_case_count=0,
            status='pending',
        )
        print(f"[回填脚本] 更新成功: {result}")
    else:
        print(f"[回填脚本] 汇总表无该记录，执行插入...")
        result = summary_mapper.upsert(
            doc_id=DOC_ID,
            document_title=document_title,
            business_module=business_module,
            document_type=document_type,
            interface_count=interface_count,
            image_count=image_count,
            general_image_count=image_count,
            test_case_count=0,
            status='pending',
        )
        print(f"[回填脚本] 插入成功: {result}")

    # 3. 验证
    final = summary_mapper.get_by_doc_id(DOC_ID)
    print(f"[回填脚本] 验证结果: {final}")

    if final:
        print("[回填脚本] 成功！该文档现已出现在 list_reviews 列表中。")
    else:
        print("[回填脚本] 失败：汇总表写入后查询无结果，请检查数据库连接。")


if __name__ == "__main__":
    main()
