# -*- coding: utf-8 -*-
"""Assertion module self-test script"""

import sys
import os
import codecs

# Ensure UTF-8 output
if sys.stdout.encoding != 'utf-8':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)

# Add project path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Import modules
from assertion.validators import (
    StatusCodeValidator,
    JsonPathValidator,
    ContainsValidator,
    SchemaValidator,
    ResponseTimeValidator,
    HeaderValidator,
    AssertionExecutor,
    AssertionResult,
)
from assertion.auto_generator import AssertionGenerator


def test_import():
    """Test module import"""
    print('=== Test Module Import ===')
    try:
        from assertion import (
            StatusCodeValidator,
            JsonPathValidator,
            ContainsValidator,
            SchemaValidator,
            ResponseTimeValidator,
            HeaderValidator,
            AssertionExecutor,
            AssertionGenerator,
        )
        print('[OK] All modules imported successfully')
        return True
    except Exception as e:
        print(f'[FAIL] Import failed: {e}')
        return False


def test_validators():
    """Test assertion validators"""
    print('\n=== Test Assertion Validators ===')
    
    # Create mock response object
    class MockResponse:
        status_code = 200
        text = '{"code": 0, "message": "success", "data": {"id": 1, "name": "test"}}'
        
        def json(self):
            return {'code': 0, 'message': 'success', 'data': {'id': 1, 'name': 'test'}}
        
        @property
        def headers(self):
            return {'Content-Type': 'application/json', 'X-Request-Id': '12345'}
    
    response = MockResponse()
    
    # Test StatusCodeValidator
    print('\n1. Test StatusCodeValidator')
    validator = StatusCodeValidator({'type': 'status_code', 'expected': 200})
    result = validator.validate(response)
    print(f'   Expected: 200, Actual: {result.actual}, Passed: {result.passed}')
    assert result.passed, "StatusCodeValidator test failed"
    
    # Test JsonPathValidator
    print('\n2. Test JsonPathValidator')
    validator = JsonPathValidator({'type': 'json_path', 'path': '$.code', 'expected': 0})
    result = validator.validate(response)
    print(f'   JSONPath: $.code, Expected: 0, Actual: {result.actual}, Passed: {result.passed}')
    assert result.passed, "JsonPathValidator test failed"
    
    # Test ContainsValidator
    print('\n3. Test ContainsValidator')
    validator = ContainsValidator({'type': 'contains', 'expected': 'success', 'case_sensitive': False})
    result = validator.validate(response)
    print(f'   Contains: success, Passed: {result.passed}')
    assert result.passed, "ContainsValidator test failed"
    
    # Test SchemaValidator
    print('\n4. Test SchemaValidator')
    schema = {
        "type": "object",
        "properties": {
            "code": {"type": "integer"},
            "message": {"type": "string"}
        },
        "required": ["code", "message"]
    }
    validator = SchemaValidator({'type': 'schema', 'schema': schema})
    result = validator.validate(response)
    print(f'   Schema validation, Passed: {result.passed}')
    assert result.passed, "SchemaValidator test failed"
    
    # Test ResponseTimeValidator
    print('\n5. Test ResponseTimeValidator')
    validator = ResponseTimeValidator({'type': 'response_time', 'max_ms': 5000, 'response_time_ms': 1500})
    result = validator.validate(response)
    print(f'   Response time: 1500ms, Threshold: 5000ms, Passed: {result.passed}')
    assert result.passed, "ResponseTimeValidator test failed"
    
    # Test HeaderValidator
    print('\n6. Test HeaderValidator')
    validator = HeaderValidator({'type': 'header', 'header': 'Content-Type', 'expected': 'application/json'})
    result = validator.validate(response)
    print(f'   Header Content-Type, Expected: application/json, Actual: {result.actual}, Passed: {result.passed}')
    assert result.passed, "HeaderValidator test failed"
    
    print('\n[OK] All validators test passed')


def test_executor():
    """Test assertion executor"""
    print('\n=== Test Assertion Executor ===')
    
    # Create mock response object
    class MockResponse:
        status_code = 200
        text = '{"code": 0, "message": "success"}'
        
        def json(self):
            return {'code': 0, 'message': 'success'}
    
    response = MockResponse()
    
    # Create executor
    executor = AssertionExecutor([
        {'type': 'status_code', 'expected': 200},
        {'type': 'json_path', 'path': '$.code', 'expected': 0},
        {'type': 'contains', 'expected': 'success'}
    ])
    
    # Execute assertions
    results = executor.execute(response)
    print(f'Executed assertions: {len(results)}')
    for r in results:
        status = 'PASS' if r.passed else 'FAIL'
        print(f'   [{status}] {r.assertion_type}: {r.message}')
    
    # Verify results
    assert len(results) == 3, "Incorrect assertion count"
    assert executor.all_passed(results), "Not all assertions passed"
    
    # Test summary
    summary = executor.get_summary(results)
    print(f'\nSummary: {summary["passed"]}/{summary["total"]} passed')
    
    print('\n[OK] Assertion executor test passed')


def test_generator():
    """Test assertion generator"""
    print('\n=== Test Assertion Generator ===')
    
    # Create mock response object
    class MockResponse:
        status_code = 200
        text = '{"code": 0, "message": "success", "data": {"id": 1}}'
        
        def json(self):
            return {'code': 0, 'message': 'success', 'data': {'id': 1}}
        
        @property
        def headers(self):
            return {'Content-Type': 'application/json'}
    
    response = MockResponse()
    
    # Create generator
    generator = AssertionGenerator({
        'include_status_code': True,
        'include_response_time': True,
        'include_json_path': True,
    })
    
    # Generate assertions
    assertions = generator.generate_from_response(response, response_time_ms=150.0)
    print(f'Generated assertions: {len(assertions)}')
    for a in assertions:
        print(f'   - {a["type"]}: {a}')
    
    # Verify generation result
    assert len(assertions) > 0, "No assertions generated"
    
    # Test generation from sample
    sample = {
        'body': {'code': 0, 'message': 'ok'},
        'headers': {'Content-Type': 'application/json'}
    }
    from_sample = generator.generate_from_sample(sample)
    print(f'\nAssertions from sample: {len(from_sample)}')
    
    print('\n[OK] Assertion generator test passed')


def test_assertion_format():
    """Test assertion format compatibility"""
    print('\n=== Test Assertion Format Compatibility ===')
    
    # Test standard format from documentation
    expected_results = [
        {"type": "status_code", "expected": 200},
        {"type": "json_path", "path": "$.code", "expected": 0},
        {"type": "contains", "expected": "success"}
    ]
    
    class MockResponse:
        status_code = 200
        def json(self):
            return {'code': 0, 'message': 'success'}
    
    executor = AssertionExecutor(expected_results)
    results = executor.execute(MockResponse())
    
    print(f'Standard format assertions: {len(results)}')
    for r in results:
        status = 'PASS' if r.passed else 'FAIL'
        print(f'   [{status}] {r.assertion_type}')
    
    assert executor.all_passed(results), "Standard format assertions not all passed"
    print('\n[OK] Assertion format compatibility test passed')


def main():
    """Main function"""
    print('=' * 50)
    print('Assertion Module Self-Test')
    print('=' * 50)
    
    if not test_import():
        sys.exit(1)
    
    test_validators()
    test_executor()
    test_generator()
    test_assertion_format()
    
    print('\n' + '=' * 50)
    print('[SUCCESS] All tests passed!')
    print('=' * 50)


if __name__ == '__main__':
    main()