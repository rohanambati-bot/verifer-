"""
VisionClick Agent - Structured logging with JSON and human-readable output.
"""
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional, Any, Dict


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
        }
        # Add extra fields
        for key in ("task_id", "stage", "statement_id", "decision",
                     "confidence", "latency_ms", "status", "error"):
            val = getattr(record, key, None)
            if val is not None:
                log_data[key] = val
        return json.dumps(log_data)


class HumanFormatter(logging.Formatter):
    """Human-readable console formatter with colors."""

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts = datetime.now().strftime("%H:%M:%S")
        prefix = ""

        task_id = getattr(record, "task_id", None)
        stage = getattr(record, "stage", None)
        if task_id:
            prefix += f" [{task_id}]"
        if stage:
            prefix += f" [{stage}]"

        msg = record.getMessage()

        confidence = getattr(record, "confidence", None)
        decision = getattr(record, "decision", None)
        latency = getattr(record, "latency_ms", None)

        extras = []
        if decision is not None:
            extras.append(f"decision={'TRUE' if decision else 'FALSE'}")
        if confidence is not None:
            extras.append(f"conf={confidence:.2f}")
        if latency is not None:
            extras.append(f"{latency}ms")

        extra_str = f" ({', '.join(extras)})" if extras else ""

        return (
            f"{color}{ts} {self.BOLD}{record.levelname:8s}{self.RESET}"
            f"{color}{prefix} {msg}{extra_str}{self.RESET}"
        )


def setup_logging(json_output: bool = False, level: str = "INFO") -> logging.Logger:
    """Configure dual logging: JSON file + human console."""
    logger = logging.getLogger("visionclick")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()

    # Console handler - human readable
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(HumanFormatter())
    logger.addHandler(console)

    return logger


def get_logger() -> logging.Logger:
    """Get the VisionClick logger."""
    return logging.getLogger("visionclick")


def log_decision(task_id: str, statement_id: int, decision: bool,
                 confidence: float, latency_ms: int, evidence: str = ""):
    """Log a decision with structured fields."""
    logger = get_logger()
    logger.info(
        f"Statement {statement_id}: {'TRUE' if decision else 'FALSE'} - {evidence}",
        extra={
            "task_id": task_id,
            "stage": "decision",
            "statement_id": statement_id,
            "decision": decision,
            "confidence": confidence,
            "latency_ms": latency_ms,
        }
    )


def log_stage(task_id: str, stage: str, message: str, **kwargs):
    """Log a pipeline stage event."""
    logger = get_logger()
    extra = {"task_id": task_id, "stage": stage}
    extra.update(kwargs)
    logger.info(message, extra=extra)
