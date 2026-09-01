"""
VisionClick Agent - SQLite Database Manager.

Async SQLite with aiosqlite: schema creation, connection management.
All 9 tables: tasks, statements, frames, evidence, decisions, actions, runs, errors, metrics.
"""
import os
import json
from typing import Optional

try:
    import aiosqlite
    HAS_AIOSQLITE = True
except ImportError:
    HAS_AIOSQLITE = False

from app.utils.logging import get_logger

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT UNIQUE NOT NULL,
    video_src TEXT DEFAULT '',
    statement_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    statement_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

CREATE TABLE IF NOT EXISTS frames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    frame_number INTEGER NOT NULL,
    timestamp REAL DEFAULT 0.0,
    motion_score REAL DEFAULT 0.0,
    objects TEXT DEFAULT '',
    hands TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    statement_id INTEGER NOT NULL,
    start_time REAL DEFAULT 0.0,
    end_time REAL DEFAULT 0.0,
    reason TEXT DEFAULT '',
    score REAL DEFAULT 0.0,
    evidence_type TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    statement_id INTEGER NOT NULL,
    statement_text TEXT DEFAULT '',
    answer BOOLEAN NOT NULL,
    confidence REAL NOT NULL,
    confidence_level TEXT DEFAULT '',
    is_second_pass BOOLEAN DEFAULT 0,
    first_pass_answer BOOLEAN,
    first_pass_confidence REAL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    statement_id INTEGER NOT NULL,
    action_type TEXT DEFAULT '',
    success BOOLEAN DEFAULT 1,
    verified BOOLEAN DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT UNIQUE NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    tasks_processed INTEGER DEFAULT 0,
    tasks_succeeded INTEGER DEFAULT 0,
    tasks_failed INTEGER DEFAULT 0,
    dry_run BOOLEAN DEFAULT 1,
    config TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT DEFAULT '',
    stage TEXT DEFAULT '',
    error_type TEXT DEFAULT '',
    error_message TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT DEFAULT '',
    metric_name TEXT DEFAULT '',
    metric_value REAL DEFAULT 0.0,
    unit TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_decisions_task ON decisions(task_id);
CREATE INDEX IF NOT EXISTS idx_evidence_task ON evidence(task_id);
CREATE INDEX IF NOT EXISTS idx_frames_task ON frames(task_id);
CREATE INDEX IF NOT EXISTS idx_errors_task ON errors(task_id);
"""


class Database:
    """Async SQLite database manager."""

    def __init__(self, db_path: str = "./data/visionclick.db"):
        self.db_path = db_path
        self._connection = None

    async def initialize(self):
        """Initialize database and create schema."""
        if not HAS_AIOSQLITE:
            get_logger().warning("aiosqlite not installed, database disabled")
            return

        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.executescript(SCHEMA_SQL)
        await self._connection.commit()
        get_logger().info(f"Database initialized: {self.db_path}",
                          extra={"stage": "database"})

    async def execute(self, sql: str, params: tuple = ()) -> Optional[int]:
        """Execute SQL and return last row ID."""
        if not self._connection:
            return None
        cursor = await self._connection.execute(sql, params)
        await self._connection.commit()
        return cursor.lastrowid

    async def fetch_all(self, sql: str, params: tuple = ()) -> list:
        """Fetch all rows."""
        if not self._connection:
            return []
        cursor = await self._connection.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def fetch_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """Fetch one row."""
        if not self._connection:
            return None
        cursor = await self._connection.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def close(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
