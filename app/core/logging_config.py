import logging
import sys
import json
from app.config import settings

# Fields already on every LogRecord by default — we skip these when flattening
# `extra={...}` kwargs into the JSON payload so we don't duplicate them.
_STANDARD_FIELDS = {
    "args", "msg", "levelname", "levelno", "name", "pathname", "filename", "module",
    "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs",
    "relativeCreated", "thread", "threadName", "processName", "process", "message",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_FIELDS:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("notification_service")
    root.handlers = [handler]
    root.setLevel(settings.log_level)
    root.propagate = False
