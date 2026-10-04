import uuid
from enum import Enum
from datetime import timezone, datetime

from shared.trading_shared.serialization import to_jsonable


class AuditEventType(str, Enum):
    BOOK_CREATED = "BOOK_CREATED"
    BOOK_UPDATED = "BOOK_UPDATED"
    BOOK_DELETED = "BOOK_DELETED"
    BOOK_DEACTIVATED = "BOOK_DEACTIVATED"

    TRADE_OPENED = "TRADE_OPENED"
    TRADE_CLOSED = "TRADE_CLOSED"
    TRADE_REJECTED = "TRADE_REJECTED"

    SNAPSHOT_TAKEN = "SNAPSHOT_TAKEN"

    DB_PUSH_ERROR = "DB_PUSH_ERROR"

    STREAM_ERROR = "STREAM_ERROR"
    STREAM_RECONNECTED = "STREAM_RECONNECTED"


class AuditSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


def build_audit_log(service_name, event_type, entity_id, message, entity_type=None,
                       severity=AuditSeverity.INFO, payload=None, correlation_id=None):
    """Build a dict matching the AuditLogs columns, ready for push_audit_logs"""
    return {
        "audit_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "service_name": service_name,
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id is not None else None,
        "correlation_id": correlation_id,
        "severity": severity,
        "message": message,
        "payload": to_jsonable(payload),
    }
