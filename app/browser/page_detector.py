"""
VisionClick Agent - Page Detector.

DOM-based detection: find task container, video element, statements, buttons.
Uses semantic selectors: ARIA, button text, labels. No hard-coded coordinates.
"""
from typing import Optional, List, Dict, Any

try:
    from playwright.async_api import Page, ElementHandle
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    Page = Any
    ElementHandle = Any

from app.utils.logging import get_logger


class PageDetector:
    """Detect task elements on the annotation page using semantic selectors."""

    # Selectors ordered by preference: semantic first, CSS last
    TASK_CONTAINER_SELECTORS = [
        '[role="main"]',
        '[data-testid="task-container"]',
        '.task-container',
        '#task-container',
        'main',
        'article',
    ]

    VIDEO_SELECTORS = [
        'video[data-testid="task-video"]',
        'video[src]',
        'video source',
        'video',
    ]

    STATEMENT_SELECTORS = [
        '[data-testid="statement-row"]',
        '.statement-row',
        '.statement',
        '.annotation-row',
        '.task-row',
        '[data-statement-id]',
        '[role="listitem"]',
    ]

    SUBMIT_SELECTORS = [
        'button:has-text("Submit and continue")',
        'button:has-text("Submit")',
        'button:has-text("Continue")',
        'button:has-text("Next")',
        '[data-testid="submit-button"]',
        'button[type="submit"]',
        '.submit-button',
    ]

    async def detect_task_container(self, page: Page) -> Optional[ElementHandle]:
        """Find the main task container."""
        for selector in self.TASK_CONTAINER_SELECTORS:
            try:
                el = await page.query_selector(selector)
                if el:
                    return el
            except Exception:
                continue
        return None

    async def detect_video(self, page: Page) -> Optional[Dict[str, Any]]:
        """Detect video element and extract source URL."""
        for selector in self.VIDEO_SELECTORS:
            try:
                el = await page.query_selector(selector)
                if el:
                    src = await el.get_attribute("src")
                    if not src:
                        # Check for <source> child
                        source_el = await el.query_selector("source")
                        if source_el:
                            src = await source_el.get_attribute("src")

                    if src and not (src.startswith("http://") or src.startswith("https://")):
                        from urllib.parse import urljoin
                        src = urljoin(page.url, src)

                    return {
                        "element": el,
                        "src": src,
                        "selector": selector,
                    }

            except Exception:
                continue
        return None

    async def detect_statements(self, page: Page) -> List[Dict[str, Any]]:
        """Detect all statement rows with their text and buttons."""
        logger = get_logger()
        statements = []

        for selector in self.STATEMENT_SELECTORS:
            try:
                elements = await page.query_selector_all(selector)
                if elements:
                    candidate_stmts = []
                    for i, el in enumerate(elements):
                        stmt = await self._parse_statement_element(
                            page, el, i + 1
                        )
                        if stmt and len(stmt.get("text", "")) > 2:
                            candidate_stmts.append(stmt)
                    if candidate_stmts:
                        return candidate_stmts
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue

        return statements

    async def _parse_statement_element(
        self, page: Page, el: ElementHandle, index: int
    ) -> Optional[Dict[str, Any]]:
        """Parse a statement element to extract text and button references."""
        try:
            # Get statement text
            text_el = await el.query_selector(
                '[data-testid="statement-text"], .statement-text'
            )
            text = ""
            if text_el:
                text = (await text_el.inner_text()).strip()

            if not text:
                # If neither class nor testid, check p or span that is not the number
                for candidate in await el.query_selector_all('p, span'):
                    cls = await candidate.get_attribute("class") or ""
                    if "number" not in cls:
                        candidate_text = (await candidate.inner_text()).strip()
                        if len(candidate_text) > len(text):
                            text = candidate_text

            if not text:
                text = (await el.inner_text()).strip()
                # Clean up: remove button text artifacts
                for remove in ["👍", "👎", "\n"]:
                    text = text.replace(remove, " ")
                text = " ".join(text.split()).strip()
                # Remove leading number
                import re
                text = re.sub(r"^\d+\.\s*", "", text).strip()


            # Find thumbs up/down buttons
            thumbs_up = await self._find_button(el, is_thumbs_up=True)
            thumbs_down = await self._find_button(el, is_thumbs_up=False)

            # Get statement ID from data attribute
            stmt_id = await el.get_attribute("data-statement-id")
            if not stmt_id:
                stmt_id = str(index)

            return {
                "id": int(stmt_id) if stmt_id.isdigit() else index,
                "text": text,
                "element": el,
                "thumbs_up": thumbs_up,
                "thumbs_down": thumbs_down,
                "index": index,
            }
        except Exception as e:
            logger = get_logger()
            logger.warning(f"Failed to parse statement {index}: {e}")
            return None

    async def _find_button(
        self, container: ElementHandle, is_thumbs_up: bool
    ) -> Optional[ElementHandle]:
        """Find thumbs up or thumbs down button within a statement row."""
        emoji = "👍" if is_thumbs_up else "👎"
        label = "thumbs up" if is_thumbs_up else "thumbs down"
        testid = "thumbs-up" if is_thumbs_up else "thumbs-down"

        # Try semantic selectors in order of preference
        selectors = [
            f'[data-testid="{testid}"]',
            f'[aria-label*="{label}"]',
            f'button:has-text("{emoji}")',
            f'.btn-{testid}',
        ]

        for selector in selectors:
            try:
                btn = await container.query_selector(selector)
                if btn:
                    return btn
            except Exception:
                continue

        # Fallback: find buttons and match by text content
        buttons = await container.query_selector_all("button")
        for btn in buttons:
            text = await btn.inner_text()
            if emoji in text:
                return btn

        return None

    async def detect_submit_button(self, page: Page) -> Optional[ElementHandle]:
        """Find the submit button."""
        for selector in self.SUBMIT_SELECTORS:
            try:
                btn = await page.query_selector(selector)
                if btn:
                    return btn
            except Exception:
                continue
        return None
