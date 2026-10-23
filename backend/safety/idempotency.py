"""Idempotency guard preventing duplicate state-changing mutations."""
import time
from typing import Any, Dict, Optional


class IdempotencyGuard:
    def __init__(self, ttl_seconds: float = 300.0):
        self.ttl = ttl_seconds
        # key -> { "result": dict, "expires_at": float }
        self._records: Dict[str, Dict[str, Any]] = {}

    def get_existing(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        record = self._records.get(idempotency_key)
        if not record:
            return None
        if time.time() > record["expires_at"]:
            del self._records[idempotency_key]
            return None
        return record["result"]

    def record_execution(self, idempotency_key: str, result: Dict[str, Any]) -> None:
        self._records[idempotency_key] = {
            "result": result,
            "expires_at": time.time() + self.ttl
        }


idempotency_guard = IdempotencyGuard()
