"""
VisionClick Agent - Task Parser.

Extracts structured task data from DOM: task_id, video source, statements.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

try:
    from playwright.async_api import Page
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    Page = Any

from app.browser.page_detector import PageDetector
from app.utils.logging import get_logger


class TaskStatement(BaseModel):
    """A parsed task statement from the DOM."""
    id: int
    text: str
    index: int = 0


class ParsedTask(BaseModel):
    """Complete parsed task from the DOM."""
    task_id: str = ""
    video_src: str = ""
    statements: List[TaskStatement] = Field(default_factory=list)
    has_submit: bool = False


class TaskParser:
    """Parse annotation tasks from the browser DOM."""

    def __init__(self):
        self.detector = PageDetector()

    async def parse_task(self, page: Page) -> ParsedTask:
        """Parse the current task from the page DOM."""
        logger = get_logger()
        logger.info("Parsing task from DOM", extra={"stage": "parsing"})

        task = ParsedTask()

        # Detect task container
        container = await self.detector.detect_task_container(page)
        if not container:
            logger.warning("Task container not found")
            return task

        # Extract task ID
        task_id = await self._extract_task_id(page)
        task.task_id = task_id or ""

        # Detect and extract video source
        video_info = await self.detector.detect_video(page)
        if video_info:
            task.video_src = video_info.get("src", "") or ""
            logger.info(f"Video source: {task.video_src}",
                        extra={"task_id": task.task_id, "stage": "parsing"})

        # Detect statements
        stmt_elements = await self.detector.detect_statements(page)
        for elem_info in stmt_elements:
            stmt = TaskStatement(
                id=elem_info["id"],
                text=elem_info["text"],
                index=elem_info["index"],
            )
            task.statements.append(stmt)

        logger.info(
            f"Parsed task {task.task_id}: {len(task.statements)} statements",
            extra={"task_id": task.task_id, "stage": "parsing"}
        )

        # Check for submit button
        submit = await self.detector.detect_submit_button(page)
        task.has_submit = submit is not None

        return task

    async def _extract_task_id(self, page: Page) -> Optional[str]:
        """Extract task ID from page."""
        # Try data attribute
        selectors = [
            '[data-task-id]',
            '[data-testid="task-id"]',
            '#task-id',
        ]
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    task_id = await el.get_attribute("data-task-id")
                    if task_id and task_id.strip():
                        return task_id.strip()
                    text = await el.inner_text()
                    if text and text.strip():
                        clean = text.replace("Task:", "").strip()
                        if clean:
                            return clean
            except Exception:
                continue


        # Try URL parameter
        url = page.url
        if "task=" in url:
            import re
            match = re.search(r"task=([^&]+)", url)
            if match:
                return match.group(1)

        return None
