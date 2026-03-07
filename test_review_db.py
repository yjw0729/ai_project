# -*- coding: utf-8 -*-
# 测试审核记录数据库功能的脚本
# 用法: python test_review_db.py

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.db_mapper.review_record_mapper import ReviewRecordMapper
from common.db_enitiy.review_record import ReviewRecord
from datetime import datetime

def test_connection():
    """测试数据库连接"""
    print("=" * 60)
    print("Testing database connection...")
    print("=" * 60)
    
    try:
        mapper = ReviewRecordMapper()
        # 尝试查询一条记录来测试连接
        result = mapper.get_all(limit=1)
        print(f"[OK] Database connection success! Current records: {len(result)}")
        return True
    except Exception as e:
        print(f"[FAIL] Database connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_insert():
    """测试插入记录"""
    print("\n" + "=" * 60)
    print("Testing insert review record...")
    print("=" * 60)
    
    try:
        mapper = ReviewRecordMapper()
        
        # 创建测试记录
        test_record = ReviewRecord(
            doc_id="test_" + datetime.now().strftime("%Y%m%d%H%M%S"),
            document_title="Test Review Record",
            business_module="Test Module",
            project_background="This is a test project background",
            business_summary="This is a test business summary",
            interface_list=[
                {"name": "Test API 1", "method": "GET", "path": "/api/test1"},
                {"name": "Test API 2", "method": "POST", "path": "/api/test2"}
            ],
            flow_chart_analysis=["Flowchart 1", "Flowchart 2"],
            image_analysis=[],
            status="pending",
            creator="test_user"
        )
        
        result = mapper.create(test_record)
        # result 现在是字典
        print(f"[OK] Insert success! ID: {result.get('id')}, doc_id: {result.get('doc_id')}")
        
        # 查询验证
        verify = mapper.get_by_doc_id(result.get('doc_id'))
        if verify:
            print(f"[OK] Query verification success: {verify.get('document_title')}")
        else:
            print("[FAIL] Query verification failed")
        
        return result.get('id')
        
    except Exception as e:
        print(f"[FAIL] Insert failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_update_status(doc_id):
    """测试更新状态"""
    if not doc_id:
        return
    
    print("\n" + "=" * 60)
    print("Testing update review status...")
    print("=" * 60)
    
    try:
        mapper = ReviewRecordMapper()
        result = mapper.update_status(
            doc_id=doc_id,
            status="approved",
            reviewer="test_reviewer",
            review_comment="Test approved"
        )
        
        if result:
            print(f"[OK] Update success! Status: {result.get('status')}")
        else:
            print("[FAIL] Update failed: Record not found")
            
    except Exception as e:
        print(f"[FAIL] Update failed: {e}")
        import traceback
        traceback.print_exc()

def test_query():
    """测试查询功能"""
    print("\n" + "=" * 60)
    print("Testing query review records...")
    print("=" * 60)
    
    try:
        mapper = ReviewRecordMapper()
        results = mapper.get_all(limit=10)
        
        print(f"[OK] Query success! Found {len(results)} records:")
        for r in results:
            print(f"  - ID: {r.get('id')}, doc_id: {r.get('doc_id')}, title: {r.get('document_title')}, status: {r.get('status')}")
            
    except Exception as e:
        print(f"[FAIL] Query failed: {e}")
        import traceback
        traceback.print_exc()

def test_delete(doc_id):
    """测试删除"""
    if not doc_id:
        return
    
    print("\n" + "=" * 60)
    print("Testing delete review record...")
    print("=" * 60)
    
    try:
        mapper = ReviewRecordMapper()
        success = mapper.delete_by_doc_id(doc_id)
        
        if success:
            print(f"[OK] Delete success! doc_id: {doc_id}")
        else:
            print("[FAIL] Delete failed")
            
    except Exception as e:
        print(f"[FAIL] Delete failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Review Record Database Function Test")
    print("=" * 60)
    
    # 测试连接
    if not test_connection():
        print("\nDatabase connection failed, please check configuration!")
        sys.exit(1)
    
    # 测试插入
    record_id = test_insert()
    
    # 测试更新
    if record_id:
        # 获取刚插入记录的doc_id
        mapper = ReviewRecordMapper()
        record = mapper.get_by_id(record_id)
        if record:
            test_update_status(record.get('doc_id'))
    
    # 测试查询
    test_query()
    
    # 清理测试数据 - 使用 doc_id
    if record_id:
        record = mapper.get_by_id(record_id)
        if record:
            test_delete(record.get('doc_id'))
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)
