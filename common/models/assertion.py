"""
Assertion data models.

Exports: AssertionType, AssertionSource, AssertionField, AssertionTemplate,
         AssertionConfig, AssertionResult, AssertionGroup
"""

import json
from dataclasses import dataclass, field as _field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class AssertionType(str, Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    NOT_NULL = "not_null"
    IS_NULL = "is_null"
    EXISTS = "exists"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    MATCHES = "matches"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUALS = "greater_equals"
    LESS_EQUALS = "less_equals"
    BETWEEN = "between"
    IN = "in"
    NOT_IN = "not_in"
    LENGTH = "length"


class AssertionSource(str, Enum):
    FIXED = "fixed"
    RESPONSE = "response"
    REQUEST = "request"
    VARIABLE = "variable"
    EXCEPTION_CODE = "exception_code"


@dataclass
class AssertionField:
    field: str = ""
    source: str = "fixed"
    type: str = "equals"
    expected: Any = None
    message: str = ""
    pattern: Optional[str] = None
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    exception_code: Optional[str] = None
    case_sensitive: bool = True
    enabled: bool = True
    priority: int = 1
    metadata: Dict[str, Any] = _field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'field': self.field,
            'source': self.source,
            'type': self.type,
        }
        if self.expected is not None:
            result['expected'] = self.expected
        if self.message:
            result['message'] = self.message
        if self.pattern:
            result['pattern'] = self.pattern
        if self.min_value is not None:
            result['min_value'] = self.min_value
        if self.max_value is not None:
            result['max_value'] = self.max_value
        if self.exception_code:
            result['exception_code'] = self.exception_code
        if not self.case_sensitive:
            result['case_sensitive'] = self.case_sensitive
        if not self.enabled:
            result['enabled'] = self.enabled
        if self.priority != 1:
            result['priority'] = self.priority
        if self.metadata:
            result['metadata'] = self.metadata
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssertionField':
        return cls(
            field=data.get('field', ''),
            source=data.get('source', 'fixed'),
            type=data.get('type', 'equals'),
            expected=data.get('expected'),
            message=data.get('message', ''),
            pattern=data.get('pattern'),
            min_value=data.get('min_value'),
            max_value=data.get('max_value'),
            exception_code=data.get('exception_code'),
            case_sensitive=data.get('case_sensitive', True),
            enabled=data.get('enabled', True),
            priority=data.get('priority', 1),
            metadata=data.get('metadata', {}),
        )


@dataclass
class AssertionTemplate:
    name: str = ""
    fields: List[AssertionField] = _field(default_factory=list)
    description: str = ""
    tags: List[str] = _field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'tags': self.tags,
            'fields': [f.to_dict() for f in self.fields],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssertionTemplate':
        return cls(
            name=data.get('name', ''),
            description=data.get('description', ''),
            tags=data.get('tags', []),
            fields=[AssertionField.from_dict(f) for f in data.get('fields', [])],
        )


@dataclass
class AssertionResponse:
    passed: bool
    assertion_type: str
    message: str
    expected: Any = None
    actual: Any = None
    json_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "assertion_type": self.assertion_type,
            "message": self.message,
            "expected": self.expected,
            "actual": self.actual,
            "json_path": self.json_path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssertionResponse":
        return cls(
            passed=data.get("passed", False),
            assertion_type=data.get("assertion_type", ""),
            message=data.get("message", ""),
            expected=data.get("expected"),
            actual=data.get("actual"),
            json_path=data.get("json_path"),
        )


@dataclass
class AssertionResult:
    field: str = ""
    passed: bool = False
    expected: Any = None
    actual: Any = None
    message: str = ""
    assertion_type: str = ""
    details: Dict[str, Any] = _field(default_factory=dict)
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'field': self.field,
            'passed': self.passed,
            'expected': self.expected,
            'actual': self.actual,
            'message': self.message,
        }
        if self.assertion_type:
            result['assertion_type'] = self.assertion_type
        if self.details:
            result['details'] = self.details
        if self.execution_time_ms:
            result['execution_time_ms'] = self.execution_time_ms
        return result


@dataclass
class AssertionGroup:
    id: str = ""
    name: str = ""
    assertions: List['AssertionConfig'] = _field(default_factory=list)
    enabled: bool = True
    metadata: Dict[str, Any] = _field(default_factory=dict)


class AssertionConfig:
    """CRUD operations for assertion configurations backed by SQLite."""

    def __init__(self, db_path: str):
        import sqlite3
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assertion_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interface_id INTEGER NOT NULL,
                version VARCHAR(20) NOT NULL,
                assertions TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(interface_id, version)
            )
        """)
        conn.commit()
        conn.close()

    def create(
        self,
        interface_id: int,
        assertions: List[Dict[str, Any]],
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        import sqlite3
        if version is None:
            conn = sqlite3.connect(self.db_path)
            cur = conn.execute(
                "SELECT COUNT(*) FROM assertion_configs WHERE interface_id = ?",
                (interface_id,),
            )
            count = cur.fetchone()[0]
            version = f"v{count + 1}"
            conn.close()

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE assertion_configs SET is_active = 0 WHERE interface_id = ?",
            (interface_id,),
        )
        conn.execute(
            "INSERT INTO assertion_configs (interface_id, version, assertions, is_active) VALUES (?, ?, ?, 1)",
            (interface_id, version, json.dumps(assertions)),
        )
        conn.commit()
        cur = conn.execute(
            "SELECT id FROM assertion_configs WHERE interface_id = ? AND version = ?",
            (interface_id, version),
        )
        row = cur.fetchone()
        conn.close()
        return {'id': row[0], 'version': version, 'interface_id': interface_id}

    def get_by_interface(
        self,
        interface_id: int,
        version: Optional[str] = None,
        active_only: bool = True,
    ) -> Optional[Dict[str, Any]]:
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        if version:
            cur = conn.execute(
                "SELECT id, interface_id, version, assertions, is_active, created_at "
                "FROM assertion_configs WHERE interface_id = ? AND version = ?",
                (interface_id, version),
            )
        elif active_only:
            cur = conn.execute(
                "SELECT id, interface_id, version, assertions, is_active, created_at "
                "FROM assertion_configs WHERE interface_id = ? AND is_active = 1",
                (interface_id,),
            )
        else:
            cur = conn.execute(
                "SELECT id, interface_id, version, assertions, is_active, created_at "
                "FROM assertion_configs WHERE interface_id = ?",
                (interface_id,),
            )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return {
            'id': row[0],
            'interface_id': row[1],
            'version': row[2],
            'assertions': json.loads(row[3]),
            'is_active': bool(row[4]),
            'created_at': row[5],
        }

    def get_versions(self, interface_id: int) -> List[Dict[str, Any]]:
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cur = conn.execute(
            "SELECT id, interface_id, version, assertions, is_active, created_at "
            "FROM assertion_configs WHERE interface_id = ? ORDER BY created_at DESC",
            (interface_id,),
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                'id': r[0],
                'interface_id': r[1],
                'version': r[2],
                'assertions': json.loads(r[3]),
                'is_active': bool(r[4]),
                'created_at': r[5],
            }
            for r in rows
        ]

    def update(
        self,
        config_id: int,
        assertions: List[Dict[str, Any]],
    ) -> bool:
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE assertion_configs SET assertions = ? WHERE id = ?",
            (json.dumps(assertions), config_id),
        )
        conn.commit()
        changes = conn.total_changes
        conn.close()
        return changes > 0

    def delete(self, config_id: int) -> bool:
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE assertion_configs SET is_active = 0 WHERE id = ?",
            (config_id,),
        )
        conn.commit()
        changes = conn.total_changes
        conn.close()
        return changes > 0

    @staticmethod
    def validate_template(template: AssertionTemplate) -> Tuple[bool, List[str]]:
        errors = []
        for idx, f in enumerate(template.fields):
            if not f.field:
                errors.append(f"字段 {idx}: field不能为空")
            if f.type == 'between':
                if f.min_value is None or f.max_value is None:
                    errors.append(
                        f"字段 '{f.field}': between 类型必须同时指定 min_value 和 max_value"
                    )
        return len(errors) == 0, errors

    @staticmethod
    def export_to_json(template: AssertionTemplate) -> str:
        return json.dumps(template.to_dict(), ensure_ascii=False, indent=2)
