"""Structured JSON logging for health-engine gateway.

Replaces Python's default text log format with a single JSON object per line
on stdout. Every logger in the process (app loggers, gunicorn, uvicorn) emits
the same schema:

    {"ts": "...", "level": "info", "logger": "health-engine.api", "message": "..."}

Optional fields: exception (traceback string), plus any extras passed via
logging's `extra` dict.
"""

import json
import logging
import sys
import traceback
from datetime import datetime, timezone

# Fields that belong to the core schema and can't be overwritten by extras.
_CORE_FIELDS = frozenset({"ts", "level", "logger", "message", "exception"})

# Standard LogRecord attributes we skip when collecting extras.
_LOG_RECORD_ATTRS = frozenset({
    "name", "msg", "args", "created", "relativeCreated", "exc_info",
    "exc_text", "stack_info", "lineno", "funcName", "pathname", "filename",
    "module", "thread", "threadName", "process", "processName", "levelname",
    "levelno", "msecs", "message", "taskName",
})


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        # Build core entry
        entry: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc)
                        .astimezone().isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Exception traceback
        if record.exc_info and record.exc_info[0] is not None:
            entry["exception"] = "".join(
                traceback.format_exception(*record.exc_info)
            ).rstrip()

        # Merge extra fields (skip standard attrs and core schema keys)
        for key, value in record.__dict__.items():
            if key in _LOG_RECORD_ATTRS or key in _CORE_FIELDS:
                continue
            entry[key] = value

        return json.dumps(entry, default=str)


def configure_logging(stream=None, level: int = logging.INFO):
    """Set up root logger with JSON formatter on stdout.

    Args:
        stream: Output stream (default: sys.stdout). Accept a param
                so tests can capture output.
        level: Root log level (default: INFO).
    """
    root = logging.getLogger()

    # Idempotent: remove any existing JsonFormatter handler
    root.handlers = [
        h for h in root.handlers
        if not isinstance(h.formatter, JsonFormatter)
    ]

    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)
