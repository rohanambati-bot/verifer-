"""VisionClick Agent - Timing utilities for performance measurement."""
import time
import functools
from typing import Optional, Dict
from contextlib import contextmanager
from app.utils.logging import get_logger


class PerformanceTimer:
    """Track and report performance metrics."""

    def __init__(self):
        self.metrics: Dict[str, list] = {}

    def record(self, name: str, duration_ms: float):
        """Record a timing metric."""
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(duration_ms)

    @contextmanager
    def measure(self, name: str, task_id: Optional[str] = None):
        """Context manager to measure execution time."""
        start = time.monotonic()
        try:
            yield
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            self.record(name, duration_ms)
            logger = get_logger()
            extra = {"latency_ms": duration_ms, "stage": name}
            if task_id:
                extra["task_id"] = task_id
            logger.debug(f"{name} completed in {duration_ms}ms", extra=extra)

    def get_average(self, name: str) -> float:
        """Get average time for a metric."""
        values = self.metrics.get(name, [])
        return sum(values) / len(values) if values else 0.0

    def get_p95(self, name: str) -> float:
        """Get P95 time for a metric."""
        values = sorted(self.metrics.get(name, []))
        if not values:
            return 0.0
        idx = int(len(values) * 0.95)
        return values[min(idx, len(values) - 1)]

    def get_median(self, name: str) -> float:
        """Get median time for a metric."""
        values = sorted(self.metrics.get(name, []))
        if not values:
            return 0.0
        mid = len(values) // 2
        if len(values) % 2 == 0:
            return (values[mid - 1] + values[mid]) / 2
        return values[mid]

    def get_summary(self) -> Dict[str, Dict[str, float]]:
        """Get summary of all metrics."""
        summary = {}
        for name in self.metrics:
            values = self.metrics[name]
            summary[name] = {
                "count": len(values),
                "avg_ms": self.get_average(name),
                "median_ms": self.get_median(name),
                "p95_ms": self.get_p95(name),
                "min_ms": min(values) if values else 0,
                "max_ms": max(values) if values else 0,
            }
        return summary


# Global timer instance
_timer = PerformanceTimer()


def get_timer() -> PerformanceTimer:
    """Get the global performance timer."""
    return _timer
