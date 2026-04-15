"""
Worker模块单元测试

测试任务轮询器、工作池、任务处理器的基本功能。
与实际实现的 API 保持一致。
"""

import time
import unittest
import tempfile
import sqlite3
import pathlib
import shutil
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor, as_completed

import sys
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from app.models.task import Task, TaskStatus, TaskType
from app.worker.task_poller import TaskPoller
from app.worker.worker_pool import WorkerPool
from app.worker.task_processor import TaskProcessor


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

class TestDB:
    """每个测试用例使用独立的临时数据库"""

    def __init__(self):
        self.tmp_dir = tempfile.mkdtemp(prefix='pytest_taskdb_')
        self.db_path = pathlib.Path(self.tmp_dir) / 'task.db'

    def init_schema(self):
        project_root = pathlib.Path(__file__).parent.parent.parent
        schema_path = project_root / 'db' / 'schema.sql'
        conn = sqlite3.connect(str(self.db_path))
        with open(schema_path, encoding='utf-8') as f:
            conn.executescript(f.read())
        conn.commit()
        conn.close()
        return str(self.db_path)

    def close(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Tests: Task model
# ---------------------------------------------------------------------------

class TestTaskModel(unittest.TestCase):
    """Task 数据模型测试"""

    def test_task_creation_default(self):
        """测试默认任务创建"""
        task = Task(task_id='t-001', task_type=TaskType.DOCUMENT_PARSE)
        self.assertEqual(task.task_id, 't-001')
        self.assertEqual(task.task_type, TaskType.DOCUMENT_PARSE)
        self.assertEqual(task.status, TaskStatus.PENDING)
        self.assertEqual(task.progress, 0)
        self.assertIsNone(task.error_message)
        self.assertIsNotNone(task.created_at)
        self.assertIsNotNone(task.updated_at)

    def test_task_from_dict(self):
        """测试从字典创建任务"""
        data = {
            'task_id': 't-002',
            'task_type': 'case_generate',
            'status': 'pending',
            'params': '{"interface_id": 123}',
            'document_id': 10,
            'interface_ids': '[1, 2, 3]',
            'progress': 50,
            'result': None,
            'error_message': None,
        }
        task = Task.from_dict(data)
        self.assertEqual(task.task_id, 't-002')
        self.assertEqual(task.task_type, TaskType.CASE_GENERATE)
        self.assertEqual(task.params, {'interface_id': 123})
        self.assertEqual(task.interface_ids, [1, 2, 3])
        self.assertEqual(task.progress, 50)

    def test_task_to_dict(self):
        """测试任务转字典"""
        task = Task(
            task_id='t-003',
            task_type=TaskType.ASSERTION_GENERATE,
            params={'mode': 'auto'},
            progress=75,
        )
        d = task.to_dict()
        self.assertEqual(d['task_id'], 't-003')
        self.assertEqual(d['task_type'], 'assertion_generate')
        self.assertEqual(d['params'], '{"mode": "auto"}')
        self.assertEqual(d['progress'], 75)

    def test_task_from_row(self):
        """测试从数据库行创建任务"""
        columns = ['task_id', 'task_type', 'status', 'params',
                   'document_id', 'interface_ids', 'result',
                   'error_message', 'progress', 'created_at', 'updated_at', 'completed_at']
        row = ('row-001', 'document_parse', 'pending', None,
               None, None, None, None, 0, '2026-03-23 10:00:00',
               '2026-03-23 10:00:00', None)
        task = Task.from_row(row, columns)
        self.assertEqual(task.task_id, 'row-001')
        self.assertEqual(task.task_type, TaskType.DOCUMENT_PARSE)
        self.assertEqual(task.status, TaskStatus.PENDING)

    def test_task_update_progress(self):
        """测试进度更新"""
        task = Task(task_id='t-004', task_type=TaskType.DOCUMENT_PARSE)
        task.update_progress(50)
        self.assertEqual(task.progress, 50)
        # Note: updated_at and created_at may be equal if update happens within same microsecond
        # This is acceptable for practical purposes

        task.update_progress(100)
        self.assertEqual(task.progress, 100)
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertIsNotNone(task.completed_at)

    def test_task_progress_clamps_to_0_100(self):
        """测试进度值被限制在 0-100"""
        task = Task(task_id='t-005', task_type=TaskType.DOCUMENT_PARSE)
        task.update_progress(-10)
        self.assertEqual(task.progress, 0)
        task.update_progress(200)
        self.assertEqual(task.progress, 100)

    def test_task_mark_failed(self):
        """测试标记失败"""
        task = Task(task_id='t-006', task_type=TaskType.DOCUMENT_PARSE)
        task.mark_failed('network error')
        self.assertEqual(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, 'network error')
        self.assertIsNotNone(task.completed_at)

    def test_task_string_to_enum(self):
        """测试字符串到枚举的自动转换"""
        task = Task(task_id='t-007', task_type='page_case_generate',
                    status='running')
        self.assertEqual(task.task_type, TaskType.PAGE_CASE_GENERATE)
        self.assertEqual(task.status, TaskStatus.RUNNING)

    def test_task_status_processing_in_enum(self):
        """验证 PROCESSING 状态存在于枚举中"""
        self.assertTrue(hasattr(TaskStatus, 'PROCESSING'))
        self.assertEqual(TaskStatus.PROCESSING.value, 'processing')


# ---------------------------------------------------------------------------
# Tests: TaskPoller (with real SQLite)
# ---------------------------------------------------------------------------

class TestTaskPoller(unittest.TestCase):
    """TaskPoller 任务轮询器测试"""

    def setUp(self):
        self._tdb = TestDB()
        self.db_path = self._tdb.init_schema()
        self.poller = TaskPoller(db_path=self.db_path, poll_interval=0.1)

    def tearDown(self):
        self._tdb.close()

    def test_create_task(self):
        """测试创建任务"""
        task_id = self.poller.create_task(
            task_type='document_parse',
            params={'doc_id': 1},
            document_id=1,
        )
        self.assertIsNotNone(task_id)
        self.assertEqual(len(task_id), 36)  # UUID length

    def test_get_task(self):
        """测试获取单个任务"""
        task_id = self.poller.create_task(
            task_type='case_generate',
            params={'interface_id': 5},
            interface_ids=[1, 2],
        )
        task = self.poller.get_task(task_id)
        self.assertIsNotNone(task)
        self.assertEqual(task.task_id, task_id)
        self.assertEqual(task.task_type, TaskType.CASE_GENERATE)
        self.assertEqual(task.params, {'interface_id': 5})

    def test_get_task_not_found(self):
        """测试获取不存在的任务"""
        task = self.poller.get_task('not-exist-id')
        self.assertIsNone(task)

    def test_get_task_list(self):
        """测试分页获取任务列表"""
        for i in range(5):
            self.poller.create_task(task_type='document_parse',
                                    params={'index': i})
        result = self.poller.get_task_list(page=1, page_size=3)
        self.assertEqual(result['total'], 5)
        self.assertEqual(len(result['tasks']), 3)
        self.assertEqual(result['total_pages'], 2)

    def test_get_task_list_filter_by_status(self):
        """测试按状态筛选"""
        tid = self.poller.create_task(task_type='document_parse')
        self.poller.update_task_status(tid, TaskStatus.COMPLETED.value)
        self.poller.create_task(task_type='document_parse')  # still pending

        result = self.poller.get_task_list(status='completed')
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['tasks'][0]['task_id'], tid)

    def test_poll_pending_task(self):
        """测试轮询获取待处理任务"""
        task_id = self.poller.create_task(task_type='document_parse')
        polled = self.poller.poll_pending_task()
        self.assertIsNotNone(polled)
        self.assertEqual(polled.task_id, task_id)
        self.assertEqual(polled.status, TaskStatus.PROCESSING)

    def test_poll_pending_task_no_pending(self):
        """测试没有待处理任务时返回 None"""
        polled = self.poller.poll_pending_task()
        self.assertIsNone(polled)

    def test_poll_pending_task_idempotent(self):
        """测试同一任务不会被多个轮询器重复获取（单连接）"""
        task_id = self.poller.create_task(task_type='document_parse')
        polled1 = self.poller.poll_pending_task()
        polled2 = self.poller.poll_pending_task()
        self.assertEqual(polled1.task_id, task_id)
        self.assertIsNone(polled2)  # 已变为 PROCESSING，不再被拾取

    def test_poll_concurrent(self):
        """测试多线程并发轮询不会重复获取"""
        task_ids = [self.poller.create_task(task_type='document_parse')
                    for _ in range(5)]
        polled_ids = []
        lock = __import__('threading').Lock()

        def poll_once():
            p = TaskPoller(db_path=self.db_path, poll_interval=0.01)
            result = p.poll_pending_task()
            if result:
                with lock:
                    polled_ids.append(result.task_id)

        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = [ex.submit(poll_once) for _ in range(5)]
            for f in futures:
                f.result()

        # 应该拾取了 5 个不同的任务
        self.assertEqual(len(polled_ids), 5)
        self.assertEqual(set(polled_ids), set(task_ids))

    def test_update_task_status_completed(self):
        """测试更新任务为完成状态"""
        task_id = self.poller.create_task(task_type='document_parse')
        success = self.poller.update_task_status(
            task_id, TaskStatus.COMPLETED.value,
            progress=100, result={'interfaces': 3}
        )
        self.assertTrue(success)
        task = self.poller.get_task(task_id)
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(task.progress, 100)
        self.assertIsNotNone(task.completed_at)

    def test_update_task_status_failed(self):
        """测试更新任务为失败状态"""
        task_id = self.poller.create_task(task_type='document_parse')
        success = self.poller.update_task_status(
            task_id, TaskStatus.FAILED.value,
            error_message='parsing error'
        )
        self.assertTrue(success)
        task = self.poller.get_task(task_id)
        self.assertEqual(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, 'parsing error')

    def test_poller_start_stop(self):
        """测试轮询器启动和停止"""
        self.assertFalse(self.poller.is_running())
        self.poller.start()
        self.assertTrue(self.poller.is_running())
        self.poller.stop()
        self.assertFalse(self.poller.is_running())

    def test_poller_callback(self):
        """测试轮询回调函数被正确调用"""
        received = []

        def callback(task):
            received.append(task.task_id)

        poller = TaskPoller(db_path=self.db_path, poll_interval=0.05,
                            on_task_callback=callback)
        task_id = self.poller.create_task(task_type='document_parse')
        poller.start()
        time.sleep(0.3)  # 等待轮询周期
        poller.stop()
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], task_id)


# ---------------------------------------------------------------------------
# Tests: WorkerPool
# ---------------------------------------------------------------------------

class TestWorkerPool(unittest.TestCase):
    """WorkerPool 工作池测试"""

    def setUp(self):
        self.pool = WorkerPool(max_workers=2)

    def tearDown(self):
        if self.pool.is_running():
            self.pool.stop(wait=True)

    def test_pool_start_stop(self):
        """测试工作池启动和停止"""
        self.assertFalse(self.pool.is_running())
        self.pool.start()
        self.assertTrue(self.pool.is_running())
        stats = self.pool.get_stats()
        self.assertEqual(stats['max_workers'], 2)
        self.pool.stop()
        self.assertFalse(self.pool.is_running())

    def test_pool_submit_success(self):
        """测试提交并成功执行任务"""
        self.pool.start()

        def double(x):
            return x * 2

        future = self.pool.submit('task-1', double, 5)
        self.assertIsNotNone(future)
        result = future.result(timeout=5.0)
        self.assertTrue(result['success'])
        self.assertEqual(result['result'], 10)

    def test_pool_submit_failure(self):
        """测试提交失败的任务"""
        self.pool.start()

        def bad_task():
            raise ValueError('test error')

        future = self.pool.submit('task-bad', bad_task)
        result = future.result(timeout=5.0)
        self.assertFalse(result['success'])
        self.assertIn('test error', result['error'])

    def test_pool_map(self):
        """测试并行映射"""
        self.pool.start()

        def double(x):
            return x * 2

        results = self.pool.map(double, [1, 2, 3, 4, 5])
        self.assertEqual(len(results), 5)
        for r in results:
            self.assertTrue(r['success'])
            self.assertIn(r['result'], [2, 4, 6, 8, 10])

    def test_pool_stats(self):
        """测试统计信息"""
        self.pool.start()

        def slow():
            time.sleep(0.05)
            return True

        for i in range(3):
            self.pool.submit(f'task-{i}', slow)

        time.sleep(0.2)
        stats = self.pool.get_stats()
        self.assertEqual(stats['submitted'], 3)
        self.assertGreaterEqual(stats['completed'], 1)

    def test_pool_result_retrieval(self):
        """测试获取任务结果"""
        self.pool.start()

        def add(a, b):
            return a + b

        self.pool.submit('add-task', add, 3, 7)
        time.sleep(0.2)
        result = self.pool.get_result('add-task')
        self.assertIsNotNone(result)
        self.assertTrue(result['success'])
        self.assertEqual(result['result'], 10)


# ---------------------------------------------------------------------------
# Tests: TaskProcessor
# ---------------------------------------------------------------------------

class TestTaskProcessor(unittest.TestCase):
    """TaskProcessor 任务处理器测试"""

    def test_register_handler(self):
        """测试注册自定义处理器"""
        processor = TaskProcessor()
        self.assertIn('document_parse', processor._handlers)

        def custom(task):
            return {'result': 'custom'}
        processor.register_handler('custom_type', custom)
        self.assertIn('custom_type', processor._handlers)

    def test_process_document_parse(self):
        """测试文档解析任务处理"""
        mock_parser = Mock()
        mock_parser.parse.return_value = {
            'interfaces': [{'name': 'test-api'}],
            'interface_count': 1
        }
        processor = TaskProcessor(services={'document_parser': mock_parser})
        task = {
            'task_id': 'doc-1',
            'task_type': 'document_parse',
            'params': {'doc_content': 'test content',
                       'doc_type': 'api_doc', 'use_llm': False}
        }
        result = processor.process(task)
        self.assertTrue(result['success'])
        self.assertEqual(result['task_id'], 'doc-1')
        self.assertIn('interfaces', result['result'])

    def test_process_case_generate(self):
        """测试用例生成任务处理"""
        mock_gen = Mock()
        mock_gen.generate.return_value = [
            {'scene': 'normal', 'expected': 'HTTP 200', 'priority': 'P0'}
        ]
        processor = TaskProcessor(services={'case_generator': mock_gen})
        task = {
            'task_id': 'case-1',
            'task_type': 'case_generate',
            'params': {
                'interface_info': {'name': 'test-api'},
                'options': {'min_cases': 5}
            }
        }
        result = processor.process(task)
        self.assertTrue(result['success'])
        self.assertIn('test_cases', result['result'])
        self.assertEqual(result['result']['count'], 1)

    def test_process_unknown_type(self):
        """测试未知任务类型报错"""
        processor = TaskProcessor()
        task = {'task_id': 'unknown-1', 'task_type': 'unknown_type',
                'params': {}}
        result = processor.process(task)
        self.assertFalse(result['success'])
        self.assertIn('未注册', result['error'])

    def test_processing_task_tracking(self):
        """测试任务处理中状态追踪"""
        processor = TaskProcessor()
        self.assertFalse(processor.is_processing('task-1'))
        processor._processing_tasks['task-1'] = __import__('datetime').datetime.now()
        self.assertTrue(processor.is_processing('task-1'))

    def test_iteration_parse_handler(self):
        """测试迭代文档解析处理器"""
        processor = TaskProcessor()
        task = {
            'task_id': 'iter-1',
            'task_type': 'iteration_parse',
            'params': {}
        }
        result = processor.process(task)
        self.assertTrue(result['success'])
        self.assertIn('increment_content', result['result'])

    def test_page_case_generate_handler(self):
        """测试页面用例生成处理器"""
        processor = TaskProcessor()
        task = {
            'task_id': 'page-1',
            'task_type': 'page_case_generate',
            'params': {'page_name': '收款人选择', 'page_content': '...'}
        }
        result = processor.process(task)
        self.assertTrue(result['success'])
        self.assertEqual(result['result']['page_name'], '收款人选择')


# ---------------------------------------------------------------------------
# Tests: Integration
# ---------------------------------------------------------------------------

class TestIntegration(unittest.TestCase):
    """端到端集成测试"""

    def setUp(self):
        self._tdb = TestDB()
        self.db_path = self._tdb.init_schema()

    def tearDown(self):
        self._tdb.close()

    def test_full_pipeline_poller_to_processor(self):
        """测试完整流水线：轮询 -> 工作池 -> 处理器"""
        # 1. 创建并填充任务
        poller = TaskPoller(db_path=self.db_path, poll_interval=0.01)
        task_ids = []
        for i in range(3):
            tid = poller.create_task(
                task_type='document_parse',
                params={'doc_index': i}
            )
            task_ids.append(tid)

        # 2. 创建处理器
        mock_parser = Mock()
        mock_parser.parse.return_value = {
            'interfaces': [{'name': f'api-{i}'} for i in range(2)],
            'interface_count': 2
        }
        processor = TaskProcessor(services={'document_parser': mock_parser})

        # 3. 创建工作池
        pool = WorkerPool(max_workers=2)
        pool.start()

        # 4. 提交处理任务
        futures = []
        for task_id in task_ids:
            task = poller.get_task(task_id)
            future = pool.submit(task_id, processor.process, task.to_dict())
            futures.append((task_id, future))

        # 5. 验证所有任务成功
        completed = 0
        for task_id, future in futures:
            result = future.result(timeout=10.0)
            self.assertTrue(result['success'],
                            f"task {task_id} failed: {result.get('error')}")
            completed += 1

        self.assertEqual(completed, 3)
        pool.stop()

    def test_full_pipeline_with_status_update(self):
        """测试完整流水线并验证状态更新"""
        poller = TaskPoller(db_path=self.db_path, poll_interval=0.01)
        task_id = poller.create_task(task_type='document_parse',
                                    params={'use_llm': False})

        # 轮询获取 -> 变为 PROCESSING
        task = poller.poll_pending_task()
        self.assertEqual(task.status, TaskStatus.PROCESSING)

        # 模拟处理完成后更新为 COMPLETED
        poller.update_task_status(
            task_id,
            TaskStatus.COMPLETED.value,
            progress=100,
            result={'interfaces': 5}
        )

        # 验证数据库中的最终状态
        final = poller.get_task(task_id)
        self.assertEqual(final.status, TaskStatus.COMPLETED)
        self.assertEqual(final.progress, 100)
        self.assertIsNotNone(final.completed_at)


if __name__ == '__main__':
    unittest.main(verbosity=2)
