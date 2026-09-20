"""Structured JSON audit logger for security-relevant events.

Writes one JSON line per event to ``logs/audit.jsonl``.  A singleton
``audit_logger`` instance is provided for convenience.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Severity levels
# ---------------------------------------------------------------------------
SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"

_VALID_SEVERITIES = {SEVERITY_INFO, SEVERITY_WARNING, SEVERITY_ERROR}


class AuditLogger:
    """Append-only structured JSON audit logger.

    Events are written to ``logs/audit.jsonl`` (one JSON object per line).
    The log directory is created automatically if it does not exist.
    """

    def __init__(self, log_path: str | Path | None = None) -> None:
        if log_path is None:
            # Default: logs/audit.jsonl relative to the backend package root
            base = Path(__file__).resolve().parents[2]
            log_path = base / "logs" / "audit.jsonl"
        self._log_path = Path(log_path)
        self._lock = threading.Lock()

        # Ensure directory exists
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Core write
    # ------------------------------------------------------------------

    def log_event(
        self,
        *,
        event_type: str,
        source_ip: str = "unknown",
        user_agent: str = "",
        endpoint: str = "",
        detail: dict[str, Any] | None = None,
        severity: str = SEVERITY_INFO,
    ) -> dict[str, Any]:
        """Write a single audit event and return the record dict."""
        if severity not in _VALID_SEVERITIES:
            severity = SEVERITY_INFO

        record: dict[str, Any] = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "source_ip": source_ip,
            "user_agent": user_agent,
            "endpoint": endpoint,
            "detail": detail or {},
            "severity": severity,
        }

        line = json.dumps(record, ensure_ascii=False)

        with self._lock:
            try:
                with open(self._log_path, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except OSError as exc:
                # Fallback: log the failure so it is not silently swallowed
                logger.error("Failed to write audit event: %s", exc)

        return record

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def log_security_event(
        self,
        *,
        event_type: str,
        source_ip: str = "unknown",
        user_agent: str = "",
        endpoint: str = "",
        detail: dict[str, Any] | None = None,
        severity: str = SEVERITY_WARNING,
    ) -> dict[str, Any]:
        """Shorthand for security-relevant events (default severity: warning)."""
        return self.log_event(
            event_type=event_type,
            source_ip=source_ip,
            user_agent=user_agent,
            endpoint=endpoint,
            detail=detail,
            severity=severity,
        )

    def log_api_access(
        self,
        *,
        endpoint: str,
        source_ip: str = "unknown",
        user_agent: str = "",
        detail: dict[str, Any] | None = None,
        severity: str = SEVERITY_INFO,
    ) -> dict[str, Any]:
        """Shorthand for general API access events."""
        return self.log_event(
            event_type="api_access",
            source_ip=source_ip,
            user_agent=user_agent,
            endpoint=endpoint,
            detail=detail,
            severity=severity,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
audit_logger = AuditLogger()
