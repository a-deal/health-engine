"""Outbound message validation gate.

Checks every outbound Milo message for system internals leaking into
user-facing coaching messages. Three detection categories:

1. Machine output: JSON blobs, SQL, stack traces, log lines, HTTP errors
2. Internal vocabulary: DB columns, API paths, service names, Python identifiers
3. Structural anomalies: diagnostic dumps, system health reports

This is a deterministic filter (no LLM calls). The vocabulary list grows
over time as new leak patterns are discovered.
"""

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("health-engine.outbound_gate")

# --- Detection patterns ---

# JSON blob: { followed by "key": or 'key': within ~50 chars
_JSON_BLOB = re.compile(r'\{[\s\S]{0,50}"[a-z_]+"\s*:', re.IGNORECASE)

# Stack traces
_STACK_TRACE = re.compile(r'Traceback \(most recent call last\)|File ".*", line \d+')

# Python errors: common exception class names
_PYTHON_ERROR = re.compile(
    r'(?:ModuleNotFoundError|ImportError|AttributeError|KeyError|TypeError'
    r'|ValueError|RuntimeError|FileNotFoundError|ConnectionError'
    r'|TimeoutError|PermissionError|OSError):'
)

# SQL fragments: require SELECT/INSERT/UPDATE/DELETE as anchor, not just FROM/WHERE
_SQL_FRAGMENT = re.compile(
    r'\b(?:SELECT|INSERT INTO|UPDATE|DELETE FROM|CREATE TABLE|DROP TABLE|ALTER TABLE)\b'
    r'.*\b(?:FROM|WHERE|INTO|SET|VALUES)\b',
    re.IGNORECASE,
)

# Log lines: ISO timestamp + level
_LOG_LINE = re.compile(
    r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}.*\b(?:INFO|WARNING|ERROR|DEBUG|CRITICAL)\b'
)

# HTTP error codes in error context
_HTTP_ERROR = re.compile(
    r'\b(?:4\d{2}|5\d{2})\s+(?:Internal Server Error|Not Found|Forbidden'
    r'|Bad Request|Unauthorized|Service Unavailable|Bad Gateway'
    r'|Gateway Timeout)\b',
    re.IGNORECASE,
)

_MACHINE_OUTPUT_PATTERNS = [
    (_JSON_BLOB, "json_blob"),
    (_STACK_TRACE, "stack_trace"),
    (_PYTHON_ERROR, "python_error"),
    (_SQL_FRAGMENT, "sql_fragment"),
    (_LOG_LINE, "log_line"),
    (_HTTP_ERROR, "http_error"),
]

# Internal vocabulary that should never appear in coaching messages.
# Lowercase for case-insensitive matching. Each entry is (term, is_word_boundary).
# is_word_boundary=True means match as whole word; False means substring.
_INTERNAL_TERMS = [
    # Database internals
    ("wearable_token", True),
    ("wearable_daily", True),
    ("person_id", True),
    ("user_id", True),
    ("channel_target", True),
    ("conversation_message", True),
    ("focus_plan", True),
    ("supplement_log", True),
    ("medication_log", True),
    ("health_engine_user_id", True),
    # API paths
    ("/health/deep", False),
    ("/api/v1/", False),
    ("/api/ingest_message", False),
    # Services and infrastructure
    ("gunicorn", True),
    ("openclaw", True),
    ("launchd", True),
    ("uvicorn", True),
    ("cloudflare tunnel", True),
    # Python identifiers
    ("_get_db", False),
    ("_get_daily_snapshot", False),
    ("sync_garmin_tokens", False),
    ("_compose_message", False),
    ("_send_via_openclaw", False),
    ("init_db", False),
    # Python literals in non-code context
    (" None", False),
    (" True", False),
    (" False", False),
    # System diagnostic keywords
    ("auto-remediation", True),
    ("remediation", True),
    ("cron re-triggered", False),
    ("stale (>", False),
]

# Compile word-boundary patterns for efficiency
_INTERNAL_PATTERNS = []
for term, word_boundary in _INTERNAL_TERMS:
    if word_boundary:
        _INTERNAL_PATTERNS.append(re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE))
    else:
        _INTERNAL_PATTERNS.append(re.compile(re.escape(term), re.IGNORECASE))

# Allowed terms that look internal but are user-facing
_ALLOWLIST = re.compile(
    r'https?://dashboard\.mybaseline\.health'
    r'|https?://auth\.mybaseline\.health',
)


@dataclass
class ValidationResult:
    """Result of outbound message validation."""
    ok: bool = True
    flags: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)


def validate_outbound(message: str) -> ValidationResult:
    """Validate an outbound coaching message for system internal leaks.

    Returns a ValidationResult with ok=True if the message is clean,
    or ok=False with flags and details describing what was found.
    """
    if not message or not message.strip():
        return ValidationResult()

    result = ValidationResult()

    # Strip allowlisted content before checking
    cleaned = _ALLOWLIST.sub("", message)

    # Category 1: Machine output
    for pattern, name in _MACHINE_OUTPUT_PATTERNS:
        if pattern.search(cleaned):
            result.ok = False
            result.flags.append("machine_output")
            result.details.append(f"machine_output:{name}")
            break  # One machine output flag is enough

    # Category 2: Internal vocabulary
    for pattern in _INTERNAL_PATTERNS:
        if pattern.search(cleaned):
            match = pattern.search(cleaned)
            result.ok = False
            result.flags.append("internal_vocabulary")
            result.details.append(f"internal_vocabulary:{match.group()}")
            break  # One internal vocab flag is enough

    # Deduplicate flags
    result.flags = list(dict.fromkeys(result.flags))

    return result
