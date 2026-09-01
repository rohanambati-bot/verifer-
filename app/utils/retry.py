"""VisionClick Agent - Retry utilities with exponential backoff."""
import asyncio
import functools
from typing import Optional, Callable, Type, Tuple
from app.utils.logging import get_logger


class RetryError(Exception):
    """Raised when all retry attempts are exhausted."""
    def __init__(self, message: str, last_error: Optional[Exception] = None):
        super().__init__(message)
        self.last_error = last_error


async def retry_async(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    task_id: Optional[str] = None,
    operation: str = "operation",
):
    """Execute an async function with exponential backoff retry."""
    logger = get_logger()
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except exceptions as e:
            last_error = e
            if attempt == max_retries:
                logger.error(
                    f"All {max_retries} retries exhausted for {operation}: {e}",
                    extra={"task_id": task_id or "", "stage": "retry"}
                )
                raise RetryError(
                    f"Failed after {max_retries} retries: {operation}",
                    last_error=e
                )

            delay = min(base_delay * (backoff_factor ** attempt), max_delay)
            logger.warning(
                f"Retry {attempt + 1}/{max_retries} for {operation} "
                f"after {delay:.1f}s: {e}",
                extra={"task_id": task_id or "", "stage": "retry"}
            )
            await asyncio.sleep(delay)

    raise RetryError(f"Failed: {operation}", last_error=last_error)


def retry_sync(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """Execute a sync function with retry."""
    import time
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            return func()
        except exceptions as e:
            last_error = e
            if attempt == max_retries:
                raise RetryError(
                    f"Failed after {max_retries} retries",
                    last_error=e
                )
            delay = min(base_delay * (2 ** attempt), 30.0)
            time.sleep(delay)

    raise RetryError("Failed", last_error=last_error)
