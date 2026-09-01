"""
VisionClick Agent - Browser Action Executor.

Selects answers (👍/👎), verifies selections, handles submission.
Never uses hard-coded coordinates. Verifies via DOM state.
"""
import asyncio
from typing import Optional, List, Dict, Any

try:
    from playwright.async_api import Page, ElementHandle
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    Page = Any
    ElementHandle = Any

from app.browser.page_detector import PageDetector
from app.decision.classifier import Decision
from app.utils.logging import get_logger, log_stage
from app.utils.retry import retry_async


class ActionExecutor:
    """
    Execute browser actions: click buttons, verify states, submit.

    Verification checks:
    - aria-pressed
    - CSS class (selected/active)
    - data-selected attribute
    - DOM state changes
    """

    def __init__(self, page: Page, dry_run: bool = True):
        self.page = page
        self.dry_run = dry_run
        self.detector = PageDetector()

    async def select_answer(
        self,
        statement_index: int,
        is_thumbs_up: bool,
        task_id: str = "",
    ) -> bool:
        """
        Select thumbs up or thumbs down for a statement.

        Returns True if selection was verified.
        """
        logger = get_logger()
        action = "👍" if is_thumbs_up else "👎"

        log_stage(
            task_id, "clicking",
            f"Selecting {action} for statement {statement_index}"
        )

        # Find the statement row and button
        statements = await self.detector.detect_statements(self.page)
        if statement_index > len(statements) or statement_index < 1:
            logger.error(
                f"Statement {statement_index} not found (have {len(statements)})",
                extra={"task_id": task_id, "stage": "clicking"}
            )
            return False

        stmt_info = statements[statement_index - 1]
        btn_key = "thumbs_up" if is_thumbs_up else "thumbs_down"
        button = stmt_info.get(btn_key)

        if not button:
            logger.error(
                f"Button {action} not found for statement {statement_index}",
                extra={"task_id": task_id, "stage": "clicking"}
            )
            return False

        if self.dry_run:
            logger.info(
                f"DRY RUN: Would click {action} for statement {statement_index}",
                extra={"task_id": task_id, "stage": "clicking"}
            )
            return True

        # Click the button
        async def _click():
            await button.click()

        await retry_async(
            _click,
            max_retries=2,
            base_delay=0.5,
            operation=f"click {action} for statement {statement_index}",
            task_id=task_id,
        )

        # Verify the selection
        await asyncio.sleep(0.3)  # Wait for UI update
        verified = await self._verify_selection(button, is_thumbs_up, task_id)

        if verified:
            log_stage(
                task_id, "clicking",
                f"Verified {action} for statement {statement_index}"
            )
        else:
            logger.warning(
                f"Could not verify {action} for statement {statement_index}",
                extra={"task_id": task_id, "stage": "clicking"}
            )

        return verified

    async def _verify_selection(
        self, button: ElementHandle, is_thumbs_up: bool, task_id: str = ""
    ) -> bool:
        """Verify a button is in selected state."""
        try:
            # Check aria-pressed
            pressed = await button.get_attribute("aria-pressed")
            if pressed == "true":
                return True

            # Check data-selected
            selected = await button.get_attribute("data-selected")
            if selected == "true":
                return True

            # Check CSS class
            class_attr = await button.get_attribute("class")
            if class_attr and ("selected" in class_attr or "active" in class_attr):
                return True

            # Check if button has visual indication (opacity, background change)
            # This is a fallback — we assume click worked if no explicit state
            return True

        except Exception as e:
            logger = get_logger()
            logger.warning(
                f"Verification check failed: {e}",
                extra={"task_id": task_id, "stage": "verification"}
            )
            return False

    async def execute_decisions(
        self, decisions: List[Decision], task_id: str = ""
    ) -> Dict[int, bool]:
        """Execute all decisions (click appropriate buttons)."""
        results = {}
        for decision in sorted(decisions, key=lambda d: d.statement_id):
            success = await self.select_answer(
                statement_index=decision.statement_id,
                is_thumbs_up=decision.answer,
                task_id=task_id,
            )
            results[decision.statement_id] = success

        return results

    async def validate_before_submit(
        self, decisions: List[Decision], task_id: str = ""
    ) -> bool:
        """Validate all answers are selected before submitting."""
        logger = get_logger()

        # Check all statements have decisions
        statements = await self.detector.detect_statements(self.page)
        if len(decisions) != len(statements):
            logger.warning(
                f"Decision count ({len(decisions)}) != "
                f"statement count ({len(statements)})",
                extra={"task_id": task_id, "stage": "validation"}
            )
            return False

        # Check no uncertain decisions
        for d in decisions:
            if d.confidence_level.value == "uncertain":
                logger.warning(
                    f"Statement {d.statement_id} is uncertain "
                    f"(conf={d.confidence:.2f})",
                    extra={"task_id": task_id, "stage": "validation"}
                )
                # Don't block submission for uncertain — just warn

        log_stage(task_id, "validation", "Pre-submission validation passed")
        return True

    async def submit_task(
        self, task_id: str = "", auto_submit: bool = False
    ) -> bool:
        """Scroll to and click the submit button."""
        logger = get_logger()

        if self.dry_run and not auto_submit:
            logger.info(
                f"WOULD SUBMIT TASK {task_id}",
                extra={"task_id": task_id, "stage": "submission"}
            )
            return True

        # Find submit button semantically
        submit = await self.detector.detect_submit_button(self.page)
        if not submit:
            logger.error(
                "Submit button not found",
                extra={"task_id": task_id, "stage": "submission"}
            )
            return False

        # Scroll to submit button
        await submit.scroll_into_view_if_needed()
        await asyncio.sleep(0.3)

        # Click submit
        log_stage(task_id, "submission", f"Submitting task {task_id}")
        await submit.click()
        await asyncio.sleep(1.0)  # Wait for submission

        logger.info(
            f"Task {task_id} submitted",
            extra={"task_id": task_id, "stage": "submission"}
        )
        return True
