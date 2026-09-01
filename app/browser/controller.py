"""
VisionClick Agent - Browser Controller.

Manages Playwright Chromium lifecycle: launch, navigate, wait, close.
All async for optimal performance.
"""
import asyncio
from typing import Optional
from app.config import BrowserConfig
from app.utils.logging import get_logger
from app.utils.retry import retry_async

try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    Browser = None
    Page = None
    BrowserContext = None


class BrowserController:
    """Manage Playwright Chromium browser lifecycle."""

    def __init__(self, config: Optional[BrowserConfig] = None):
        self.config = config or BrowserConfig()
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def launch(self):
        """Launch Chromium browser."""
        if not HAS_PLAYWRIGHT:
            raise RuntimeError(
                "Playwright not installed. Run: pip install playwright && "
                "python -m playwright install chromium"
            )

        logger = get_logger()
        logger.info("Launching Chromium browser", extra={"stage": "browser"})

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.config.headless,
            slow_mo=self.config.slow_mo,
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
        )
        self._page = await self._context.new_page()
        logger.info("Browser launched successfully", extra={"stage": "browser"})

    async def navigate(self, url: str, wait_until: str = "networkidle"):
        """Navigate to URL and wait for page to load."""
        logger = get_logger()
        logger.info(f"Navigating to {url}", extra={"stage": "browser"})

        async def _nav():
            await self._page.goto(url, wait_until=wait_until, timeout=30000)

        await retry_async(
            _nav,
            max_retries=3,
            base_delay=2.0,
            operation=f"navigate to {url}",
        )

    async def wait_for_selector(self, selector: str, timeout: int = 10000):
        """Wait for a CSS selector to appear."""
        await self._page.wait_for_selector(selector, timeout=timeout)

    async def wait_for_load(self):
        """Wait for page to finish loading."""
        await self._page.wait_for_load_state("networkidle")

    @property
    def page(self) -> Optional[Page]:
        """Get the current page."""
        return self._page

    async def close(self):
        """Close browser and cleanup."""
        logger = get_logger()
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            logger.info("Browser closed", extra={"stage": "browser"})
        except Exception as e:
            logger.error(f"Error closing browser: {e}", extra={"stage": "browser"})

    async def screenshot(self, path: str = "screenshot.png"):
        """Take a screenshot."""
        if self._page:
            await self._page.screenshot(path=path)
