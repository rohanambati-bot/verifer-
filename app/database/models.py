"""
VisionClick Agent - Database models.
Pydantic models for all SQLite tables.
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class TaskRecord(BaseModel):
    id: Optional[int] = None
    task_id: str
    video_src: str = ""
    statement_count: int = 0
    status: str = "pending"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None


class StatementRecord(BaseModel):
    id: Optional[int] = None
    task_id: str
    statement_id: int
    text: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class FrameRecord(BaseModel):
    id: Optional[int] = None
    task_id: str
    frame_number: int
    timestamp: float
    motion_score: float = 0.0
    objects: str = ""  # JSON string
    hands: str = ""  # JSON string
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class EvidenceRecord(BaseModel):
    id: Optional[int] = None
    task_id: str
    statement_id: int
    start_time: float = 0.0
    end_time: float = 0.0
    reason: str = ""
    score: float = 0.0
    evidence_type: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class DecisionRecord(BaseModel):
    id: Optional[int] = None
    task_id: str
    statement_id: int
    statement_text: str = ""
    answer: bool
    confidence: float
    confidence_level: str = ""
    is_second_pass: bool = False
    first_pass_answer: Optional[bool] = None
    first_pass_confidence: Optional[float] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ActionRecord(BaseModel):
    id: Optional[int] = None
    task_id: str
    statement_id: int
    action_type: str = ""  # "click_thumbs_up", "click_thumbs_down", "submit"
    success: bool = True
    verified: bool = False
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class RunRecord(BaseModel):
    id: Optional[int] = None
    run_id: str = ""
    started_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    tasks_processed: int = 0
    tasks_succeeded: int = 0
    tasks_failed: int = 0
    dry_run: bool = True
    config: str = ""  # JSON string


class ErrorRecord(BaseModel):
    id: Optional[int] = None
    task_id: str = ""
    stage: str = ""
    error_type: str = ""
    error_message: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class MetricRecord(BaseModel):
    id: Optional[int] = None
    task_id: str = ""
    metric_name: str = ""
    metric_value: float = 0.0
    unit: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
