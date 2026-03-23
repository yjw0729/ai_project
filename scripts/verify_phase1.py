import sys
proj_root = r"d:\pythonProject\pytest_sxp"
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

print("=== Phase 1 Verification ===\n")

# ---- shared/ package ----
print("1. Testing shared/ package...")
try:
    from shared.common_proto.schemas import TaskStatus, TaskType, APIResponse, ExecuteTestRequest
    from shared.common_proto.mq_messages import LLM_GENERATE_QUEUE, TEST_EXECUTE_QUEUE, build_llm_generate_message
    from shared.common_proto import TaskStatusResponse, MQMessage
    from shared.common_proto.trace import TraceContext
    from shared import TaskStatus, MQMessage, LLM_GENERATE_QUEUE
    print("   [OK] shared.common_proto.schemas")
    print("        TaskStatus.PENDING =", TaskStatus.PENDING)
    print("        TaskType.LLM_GENERATE =", TaskType.LLM_GENERATE)
    print("   [OK] shared.common_proto.mq_messages")
    print("        LLM queue:", LLM_GENERATE_QUEUE.queue)
    print("        Test queue:", TEST_EXECUTE_QUEUE.queue)
    print("   [OK] shared.common_proto.trace")
    ctx = TraceContext(user_id="tester")
    print("        trace_id:", ctx.trace_id[:8], "...")
    msg = build_llm_generate_message("t1", "u1", {"doc": "123"})
    print("   [OK] Message builder works, id:", msg.message_id[:8], "...")
    print("   [OK] shared package PASSED\n")
except Exception as e:
    print("   [FAIL] shared import:", e)
    import traceback; traceback.print_exc()

# ---- Step 1: directory structure ----
print("2. Testing Step 1: directory structure...")
import os
dirs_ok = True
for d in ["platform", "platform/service", "platform/api", "platform/db",
          "shared", "shared/common_proto", "shared/llm-sdk",
          "workers", "infrastructure/rabbitmq", "scripts"]:
    full = os.path.join(proj_root, d)
    exists = os.path.isdir(full)
    tag = "[OK]" if exists else "[FAIL]"
    print("  ", tag, d)
    if not exists:
        dirs_ok = False
print("   Step 1:", "PASSED" if dirs_ok else "FAILED")

# ---- Step 2: common __init__.py ----
print("\n3. Testing Step 2: common __init__.py files...")
step2_ok = True
for sub in ["llm", "rag", "test_executor", "db_mapper", "db_enitiy",
            "fixtures", "datacase_function", "csv_function", "sql"]:
    full = os.path.join(proj_root, "common", sub, "__init__.py")
    exists = os.path.isfile(full)
    tag = "[OK]" if exists else "[FAIL]"
    print("  ", tag, "common/" + sub)
    if not exists:
        step2_ok = False
print("   Step 2:", "PASSED" if step2_ok else "FAILED")

# ---- Step 3: shared package files ----
print("\n4. Testing Step 3: shared package files...")
step3_ok = True
for f in ["shared/common_proto/__init__.py", "shared/common_proto/schemas.py",
          "shared/common_proto/mq_messages.py", "shared/common_proto/trace.py",
          "shared/__init__.py", "shared/setup.py",
          "shared/llm-sdk/__init__.py", "shared/llm-sdk/llm_client.py",
          "platform/__init__.py", "platform/service/__init__.py"]:
    full = os.path.join(proj_root, f)
    exists = os.path.isfile(full)
    tag = "[OK]" if exists else "[FAIL]"
    print("  ", tag, f)
    if not exists:
        step3_ok = False
print("   Step 3:", "PASSED" if step3_ok else "FAILED")

print("\n=== Phase 1 Summary ===")
all_ok = dirs_ok and step2_ok and step3_ok
print("Overall:", "ALL PASSED" if all_ok else "SOME FAILED")
print("\nNote: The 'platform' directory name conflicts with Python stdlib 'platform'")
print("      module - this is a pre-existing project issue, NOT introduced by Phase 1.")
