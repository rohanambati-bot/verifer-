"""
VisionClick Agent - Main Orchestrator.

Autonomous perception/reasoning/action pipeline:
OBSERVE → UNDERSTAND → EXTRACT → TEMPORAL ANALYSIS → REASON →
COLLECT EVIDENCE → CLASSIFY → VERIFY → ACT → VERIFY ACTION →
SUBMIT → RECORD RESULT → NEXT TASK
"""
import os
import asyncio
import time
import uuid
from typing import Optional, List
from datetime import datetime

from app.config import AppConfig, load_config
from app.utils.logging import setup_logging, get_logger, log_stage
from app.utils.timing import get_timer
from app.vision.base import VisionProvider, create_provider
from app.reasoning.statement_parser import StatementParser
from app.reasoning.confidence import ConfidenceConfig
from app.decision.classifier import DecisionClassifier, Decision
from app.decision.verifier import Verifier
from app.video.temporal import TemporalProcessor
from app.database.database import Database
from app.database.repository import Repository
from app.database.models import (
    TaskRecord, StatementRecord, DecisionRecord,
    ActionRecord, RunRecord, ErrorRecord, MetricRecord
)

try:
    from app.browser.controller import BrowserController
    from app.browser.task_parser import TaskParser
    from app.browser.action_executor import ActionExecutor
    HAS_BROWSER = True
except ImportError:
    HAS_BROWSER = False


class VisionClickAgent:
    """
    Autonomous agent for video annotation tasks.

    Implements the full perception/reasoning/action pipeline.
    """

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or load_config()
        self.logger = setup_logging()

        # Core components
        self.vision: Optional[VisionProvider] = None
        self.parser = StatementParser()
        self.classifier: Optional[DecisionClassifier] = None
        self.verifier: Optional[Verifier] = None
        self.temporal: Optional[TemporalProcessor] = None
        self.db: Optional[Database] = None
        self.repo: Optional[Repository] = None

        # Browser components
        self.browser: Optional[BrowserController] = None
        self.task_parser: Optional[TaskParser] = None
        self.executor: Optional[ActionExecutor] = None

        # State
        self.run_id = str(uuid.uuid4())[:8]
        self.tasks_processed = 0
        self.tasks_succeeded = 0
        self.tasks_failed = 0
        self.start_time = None
        self._status = "IDLE"

    @property
    def status(self):
        return self._status

    async def set_status(self, status: str):
        self._status = status
        # Notify dashboard if available
        try:
            from app.dashboard.server import agent_status
            await agent_status.update(status=status)
        except Exception:
            pass

    async def initialize(self):
        """Initialize all components."""
        logger = get_logger()
        logger.info("Initializing VisionClick Agent", extra={"stage": "init"})

        # Initialize vision provider
        gt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "demo", "ground_truth", "ground_truth.json"
        )
        self.vision = create_provider(
            self.config.vision.provider,
            ground_truth_path=gt_path,
        )

        # Initialize reasoning
        conf_config = ConfidenceConfig(
            high_confidence=self.config.vision.high_confidence,
            review_threshold=self.config.vision.review_threshold,
        )
        self.classifier = DecisionClassifier(confidence_config=conf_config)
        self.verifier = Verifier(self.vision)

        # Initialize video processor
        self.temporal = TemporalProcessor(
            vision_provider=self.vision,
            sample_fps=self.config.vision.sample_fps,
            adaptive_sampling=self.config.performance.adaptive_sampling,
        )

        # Initialize database
        self.db = Database(self.config.db_path)
        await self.db.initialize()
        self.repo = Repository(self.db)

        # Save run record
        await self.repo.save_run(RunRecord(
            run_id=self.run_id,
            dry_run=self.config.agent.dry_run,
        ))

        logger.info(
            f"Agent initialized (provider={self.config.vision.provider}, "
            f"dry_run={self.config.agent.dry_run})",
            extra={"stage": "init"}
        )

    async def initialize_browser(self):
        """Initialize browser components."""
        if not HAS_BROWSER:
            get_logger().warning("Playwright not available, browser disabled")
            return

        self.browser = BrowserController(self.config.browser)
        await self.browser.launch()
        self.task_parser = TaskParser()

    async def process_single_task(self, task_url: Optional[str] = None) -> bool:
        """
        Process a single annotation task through the full pipeline.

        OBSERVE → UNDERSTAND → EXTRACT → TEMPORAL ANALYSIS → REASON →
        COLLECT EVIDENCE → CLASSIFY → VERIFY → ACT → VERIFY ACTION →
        SUBMIT → RECORD RESULT
        """
        logger = get_logger()
        timer = get_timer()
        task_start = time.monotonic()

        try:
            # ── STAGE 1: OBSERVE ──────────────────────────────────────────
            await self.set_status("OBSERVING")
            url = task_url or self.config.demo.url

            if self.browser and self.browser.page:
                await self.browser.navigate(url)
                await self.browser.wait_for_selector(
                    '[data-testid="statement-row"], .statement-row, [role="listitem"]'
                )

                # ── STAGE 2: UNDERSTAND ─────────────────────────────────
                parsed_task = await self.task_parser.parse_task(self.browser.page)
                task_id = parsed_task.task_id or f"task_{self.tasks_processed}"

            else:
                # Fallback for testing without browser
                task_id = f"task_{self.tasks_processed}"
                parsed_task = None

            log_stage(task_id, "observe", f"Processing task {task_id}")

            # Set mock provider context
            if hasattr(self.vision, 'set_current_task'):
                self.vision.set_current_task(task_id)

            # Save task record
            if self.repo:
                await self.repo.save_task(TaskRecord(
                    task_id=task_id,
                    video_src=parsed_task.video_src if parsed_task else "",
                    statement_count=len(parsed_task.statements) if parsed_task else 0,
                    status="processing",
                ))

            # ── STAGE 3: EXTRACT ──────────────────────────────────────
            statements = []
            if parsed_task and parsed_task.statements:
                statements = parsed_task.statements
            else:
                logger.warning(f"No statements found for task {task_id}")
                return False

            for stmt in statements:
                log_stage(task_id, "extract", f"Statement {stmt.id}: {stmt.text}")
                if self.repo:
                    await self.repo.save_statement(StatementRecord(
                        task_id=task_id,
                        statement_id=stmt.id,
                        text=stmt.text,
                    ))

            # ── STAGE 4: TEMPORAL ANALYSIS ────────────────────────────
            await self.set_status("ANALYZING")

            # Get video for analysis
            video_path = None
            if parsed_task and parsed_task.video_src:
                video_path = await self.temporal.extractor.download_video(
                    parsed_task.video_src
                )

            if not video_path or not os.path.exists(video_path):
                # Create a placeholder for mock analysis
                import tempfile
                video_path = tempfile.mktemp(suffix=".mp4")
                self.temporal.extractor._create_placeholder_video(video_path)

            temporal_analysis = await self.temporal.process_video(
                video_path, task_id
            )

            # Update dashboard
            try:
                from app.dashboard.server import agent_status
                await agent_status.update(
                    current_task=task_id,
                    frames_analyzed=len(temporal_analysis.frame_analyses),
                )
            except Exception:
                pass

            # ── STAGE 5: REASON + CLASSIFY ────────────────────────────
            await self.set_status("REASONING")
            self.classifier.reset()
            decisions: List[Decision] = []

            for stmt in statements:
                log_stage(task_id, "reasoning", f"Analyzing: {stmt.text}")

                # Parse statement into structured predicate
                parsed = self.parser.parse(stmt.text)
                log_stage(
                    task_id, "reasoning",
                    f"Parsed: action={parsed.action}, obj={parsed.primary_object}, "
                    f"hand={parsed.hand}, tool={parsed.tool}"
                )

                # First pass classification
                with timer.measure("reasoning", task_id):
                    decision = self.classifier.classify(
                        statement_id=stmt.id,
                        statement_text=stmt.text,
                        parsed=parsed,
                        temporal=temporal_analysis,
                        task_id=task_id,
                    )

                # ── STAGE 6: SECOND-PASS VERIFICATION ────────────────
                if self.classifier.needs_second_pass(stmt.id):
                    await self.set_status("VERIFYING")
                    log_stage(
                        task_id, "verification",
                        f"Low confidence ({decision.confidence:.2f}), "
                        f"running second pass"
                    )

                    frames, timestamps = self.temporal.get_frames_for_verification(
                        video_path
                    )
                    decision = await self.verifier.verify_decision(
                        decision=decision,
                        parsed=parsed,
                        frames=frames,
                        timestamps=timestamps,
                        classifier=self.classifier,
                        task_id=task_id,
                    )

                decisions.append(decision)

                # Save decision
                if self.repo:
                    await self.repo.save_decision(DecisionRecord(
                        task_id=task_id,
                        statement_id=stmt.id,
                        statement_text=stmt.text,
                        answer=decision.answer,
                        confidence=decision.confidence,
                        confidence_level=decision.confidence_level.value,
                        is_second_pass=decision.evidence.is_second_pass,
                        first_pass_answer=decision.evidence.first_pass_answer,
                        first_pass_confidence=decision.evidence.first_pass_confidence,
                    ))

                # Save evidence
                if self.repo and decision.evidence:
                    for ev in decision.evidence.evidence:
                        from app.database.models import EvidenceRecord
                        await self.repo.save_evidence(EvidenceRecord(
                            task_id=task_id,
                            statement_id=stmt.id,
                            start_time=ev.start,
                            end_time=ev.end,
                            reason=ev.reason,
                            score=ev.score,
                            evidence_type=ev.evidence_type,
                        ))

            # ── STAGE 7: ACT ──────────────────────────────────────────
            await self.set_status("CLICKING")

            if self.browser and self.browser.page:
                self.executor = ActionExecutor(
                    self.browser.page,
                    dry_run=self.config.agent.dry_run,
                )

                # Execute clicks
                click_results = await self.executor.execute_decisions(
                    decisions, task_id
                )

                # Save actions
                if self.repo:
                    for stmt_id, success in click_results.items():
                        d = next((d for d in decisions if d.statement_id == stmt_id), None)
                        action_type = "click_thumbs_up" if d and d.answer else "click_thumbs_down"
                        await self.repo.save_action(ActionRecord(
                            task_id=task_id,
                            statement_id=stmt_id,
                            action_type=action_type,
                            success=success,
                            verified=success,
                        ))

                # ── STAGE 8: VALIDATE + SUBMIT ────────────────────────
                await self.set_status("SUBMITTING")

                valid = await self.executor.validate_before_submit(
                    decisions, task_id
                )

                if valid:
                    submitted = await self.executor.submit_task(
                        task_id=task_id,
                        auto_submit=self.config.agent.auto_submit,
                    )
                else:
                    logger.warning(
                        f"Validation failed for task {task_id}",
                        extra={"task_id": task_id, "stage": "submission"}
                    )
            else:
                # No browser - just log
                for d in decisions:
                    logger.info(
                        f"Result: Statement {d.statement_id} → "
                        f"{d.action_label} (conf={d.confidence:.2f})",
                        extra={"task_id": task_id, "stage": "decision"}
                    )
                if self.config.agent.dry_run:
                    logger.info(
                        f"WOULD SUBMIT TASK {task_id}",
                        extra={"task_id": task_id, "stage": "submission"}
                    )

            # ── STAGE 9: RECORD RESULT ────────────────────────────────
            task_ms = int((time.monotonic() - task_start) * 1000)
            if self.repo:
                await self.repo.update_task_status(task_id, "completed")
                await self.repo.save_metric(MetricRecord(
                    task_id=task_id,
                    metric_name="total_task_ms",
                    metric_value=task_ms,
                    unit="ms",
                ))

            self.tasks_processed += 1
            self.tasks_succeeded += 1

            log_stage(
                task_id, "complete",
                f"Task completed in {task_ms}ms "
                f"({len(decisions)} decisions)"
            )

            # Update dashboard
            try:
                from app.dashboard.server import agent_status
                await agent_status.update(
                    decisions=[d.to_dict() for d in decisions],
                    processing_time_ms=task_ms,
                )
            except Exception:
                pass

            await self.set_status("IDLE")
            return True

        except Exception as e:
            self.tasks_failed += 1
            logger.error(
                f"Task failed: {e}",
                extra={"task_id": task_id if 'task_id' in dir() else "", "stage": "error"}
            )
            if self.repo:
                await self.repo.save_error(ErrorRecord(
                    task_id=task_id if 'task_id' in dir() else "",
                    stage="process_task",
                    error_type=type(e).__name__,
                    error_message=str(e),
                ))
            await self.set_status("ERROR")
            return False

    async def run_continuous(self):
        """
        Continuous worker loop for the local test website.

        Respects MAX_TASKS, MAX_RUNTIME_MINUTES, and POLL_INTERVAL.
        """
        logger = get_logger()
        self.start_time = time.monotonic()
        max_runtime_s = self.config.agent.max_runtime_minutes * 60

        logger.info(
            f"Starting continuous worker (max_tasks={self.config.agent.max_tasks}, "
            f"max_runtime={self.config.agent.max_runtime_minutes}min, "
            f"dry_run={self.config.agent.dry_run})",
            extra={"stage": "worker"}
        )

        while self.tasks_processed < self.config.agent.max_tasks:
            # Check runtime limit
            elapsed = time.monotonic() - self.start_time
            if elapsed > max_runtime_s:
                logger.info("Max runtime reached, stopping", extra={"stage": "worker"})
                break

            # Process task
            success = await self.process_single_task()

            if not success:
                logger.warning("Task failed, continuing...", extra={"stage": "worker"})

            # Wait between tasks
            await self.set_status("WAITING")
            await asyncio.sleep(self.config.agent.poll_interval)

        # Finalize run
        if self.repo:
            await self.repo.update_run(
                self.run_id,
                completed_at=datetime.utcnow().isoformat(),
                tasks_processed=self.tasks_processed,
                tasks_succeeded=self.tasks_succeeded,
                tasks_failed=self.tasks_failed,
            )

        logger.info(
            f"Worker completed: {self.tasks_succeeded}/{self.tasks_processed} "
            f"tasks succeeded",
            extra={"stage": "worker"}
        )

    async def shutdown(self):
        """Clean shutdown."""
        logger = get_logger()
        logger.info("Shutting down agent", extra={"stage": "shutdown"})

        if self.browser:
            await self.browser.close()
        if self.vision:
            await self.vision.close()
        if self.db:
            await self.db.close()
