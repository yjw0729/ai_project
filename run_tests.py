"""Run worker unit tests directly."""
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import unittest
from tests.unit.test_worker import (
    TestTaskModel,
    TestTaskPoller,
    TestWorkerPool,
    TestTaskProcessor,
    TestIntegration,
)

loader = unittest.TestLoader()
suite = unittest.TestSuite()

suite.addTests(loader.loadTestsFromTestCase(TestTaskModel))
suite.addTests(loader.loadTestsFromTestCase(TestTaskPoller))
suite.addTests(loader.loadTestsFromTestCase(TestWorkerPool))
suite.addTests(loader.loadTestsFromTestCase(TestTaskProcessor))
suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

sys.exit(0 if result.wasSuccessful() else 1)
