"""
VisionClick Agent - Data Repository.
CRUD operations and query methods for all tables.
"""
import json
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.database.database import Database
from app.database.models import (
    TaskRecord, StatementRecord, FrameRecord, EvidenceRecord,
    DecisionRecord, ActionRecord, RunRecord, ErrorRecord, MetricRecord
)


class Repository:
    """Data access layer for all database tables."""

    def __init__(self, db: Database):
        self.db = db

    # ─── Tasks ────────────────────────────────────────────────────────────

    async def save_task(self, record: TaskRecord) -> Optional[int]:
        return await self.db.execute(
            "INSERT OR REPLACE INTO tasks (task_id, video_src, statement_count, status, created_at, completed_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (record.task_id, record.video_src, record.statement_count,
             record.status, record.created_at, record.completed_at)
        )

    async def update_task_status(self, task_id: str, status: str):
        await self.db.execute(
            "UPDATE tasks SET status=?, completed_at=? WHERE task_id=?",
            (status, datetime.utcnow().isoformat(), task_id)
        )

    async def get_task(self, task_id: str) -> Optional[dict]:
        return await self.db.fetch_one(
            "SELECT * FROM tasks WHERE task_id=?", (task_id,)
        )

    async def get_all_tasks(self) -> List[dict]:
        return await self.db.fetch_all("SELECT * FROM tasks ORDER BY created_at DESC")

    # ─── Statements ───────────────────────────────────────────────────────

    async def save_statement(self, record: StatementRecord) -> Optional[int]:
        return await self.db.execute(
            "INSERT INTO statements (task_id, statement_id, text, created_at) VALUES (?, ?, ?, ?)",
            (record.task_id, record.statement_id, record.text, record.created_at)
        )

    # ─── Frames ───────────────────────────────────────────────────────────

    async def save_frame(self, record: FrameRecord) -> Optional[int]:
        return await self.db.execute(
            "INSERT INTO frames (task_id, frame_number, timestamp, motion_score, objects, hands, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (record.task_id, record.frame_number, record.timestamp,
             record.motion_score, record.objects, record.hands, record.created_at)
        )

    async def get_frames_count(self, task_id: str) -> int:
        result = await self.db.fetch_one(
            "SELECT COUNT(*) as cnt FROM frames WHERE task_id=?", (task_id,)
        )
        return result["cnt"] if result else 0

    # ─── Evidence ─────────────────────────────────────────────────────────

    async def save_evidence(self, record: EvidenceRecord) -> Optional[int]:
        return await self.db.execute(
            "INSERT INTO evidence (task_id, statement_id, start_time, end_time, reason, score, evidence_type, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (record.task_id, record.statement_id, record.start_time,
             record.end_time, record.reason, record.score,
             record.evidence_type, record.created_at)
        )

    # ─── Decisions ────────────────────────────────────────────────────────

    async def save_decision(self, record: DecisionRecord) -> Optional[int]:
        return await self.db.execute(
            "INSERT INTO decisions (task_id, statement_id, statement_text, answer, confidence, "
            "confidence_level, is_second_pass, first_pass_answer, first_pass_confidence, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (record.task_id, record.statement_id, record.statement_text,
             record.answer, record.confidence, record.confidence_level,
             record.is_second_pass, record.first_pass_answer,
             record.first_pass_confidence, record.created_at)
        )

    async def get_decisions(self, task_id: str) -> List[dict]:
        return await self.db.fetch_all(
            "SELECT * FROM decisions WHERE task_id=? ORDER BY statement_id",
            (task_id,)
        )

    async def get_all_decisions(self) -> List[dict]:
        return await self.db.fetch_all(
            "SELECT task_id, statement_id, statement_text, answer, confidence, "
            "confidence_level, created_at FROM decisions ORDER BY created_at"
        )

    # ─── Actions ──────────────────────────────────────────────────────────

    async def save_action(self, record: ActionRecord) -> Optional[int]:
        return await self.db.execute(
            "INSERT INTO actions (task_id, statement_id, action_type, success, verified, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (record.task_id, record.statement_id, record.action_type,
             record.success, record.verified, record.created_at)
        )

    # ─── Runs ─────────────────────────────────────────────────────────────

    async def save_run(self, record: RunRecord) -> Optional[int]:
        return await self.db.execute(
            "INSERT INTO runs (run_id, started_at, completed_at, tasks_processed, "
            "tasks_succeeded, tasks_failed, dry_run, config) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (record.run_id, record.started_at, record.completed_at,
             record.tasks_processed, record.tasks_succeeded,
             record.tasks_failed, record.dry_run, record.config)
        )

    async def update_run(self, run_id: str, **kwargs):
        sets = ", ".join(f"{k}=?" for k in kwargs.keys())
        vals = list(kwargs.values()) + [run_id]
        await self.db.execute(
            f"UPDATE runs SET {sets} WHERE run_id=?", tuple(vals)
        )

    # ─── Errors ───────────────────────────────────────────────────────────

    async def save_error(self, record: ErrorRecord) -> Optional[int]:
        return await self.db.execute(
            "INSERT INTO errors (task_id, stage, error_type, error_message, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (record.task_id, record.stage, record.error_type,
             record.error_message, record.created_at)
        )

    async def get_error_count(self) -> int:
        result = await self.db.fetch_one("SELECT COUNT(*) as cnt FROM errors")
        return result["cnt"] if result else 0

    # ─── Metrics ──────────────────────────────────────────────────────────

    async def save_metric(self, record: MetricRecord) -> Optional[int]:
        return await self.db.execute(
            "INSERT INTO metrics (task_id, metric_name, metric_value, unit, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (record.task_id, record.metric_name, record.metric_value,
             record.unit, record.created_at)
        )

    # ─── Aggregations ────────────────────────────────────────────────────

    async def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get aggregated stats for the dashboard."""
        stats = {
            "tasks_completed": 0,
            "total_statements": 0,
            "correct_decisions": 0,
            "incorrect_decisions": 0,
            "avg_confidence": 0.0,
            "avg_latency_ms": 0.0,
            "error_count": 0,
        }

        result = await self.db.fetch_one(
            "SELECT COUNT(*) as cnt FROM tasks WHERE status='completed'"
        )
        if result:
            stats["tasks_completed"] = result["cnt"]

        result = await self.db.fetch_one(
            "SELECT COUNT(*) as cnt, AVG(confidence) as avg_conf FROM decisions"
        )
        if result:
            stats["total_statements"] = result["cnt"]
            stats["avg_confidence"] = result["avg_conf"] or 0.0

        stats["error_count"] = await self.get_error_count()

        result = await self.db.fetch_one(
            "SELECT AVG(metric_value) as avg_val FROM metrics WHERE metric_name='total_task_ms'"
        )
        if result:
            stats["avg_latency_ms"] = result["avg_val"] or 0.0

        return stats
