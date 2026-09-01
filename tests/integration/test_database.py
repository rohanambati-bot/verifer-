"""
Integration tests for Database and Repository operations.
"""
import pytest
from app.database.models import (
    TaskRecord, StatementRecord, DecisionRecord, ActionRecord, RunRecord, MetricRecord
)


@pytest.mark.asyncio
async def test_database_crud(test_repo):
    # Save a run
    await test_repo.save_run(RunRecord(run_id="run_test_001", dry_run=True))
    
    # Save a task
    await test_repo.save_task(TaskRecord(
        task_id="demo_001",
        video_src="/videos/demo_001.mp4",
        statement_count=3,
        status="processing"
    ))

    # Save statements
    await test_repo.save_statement(StatementRecord(
        task_id="demo_001",
        statement_id=1,
        text="hold pan with left hand"
    ))

    # Save decision
    await test_repo.save_decision(DecisionRecord(
        task_id="demo_001",
        statement_id=1,
        statement_text="hold pan with left hand",
        answer=True,
        confidence=0.94,
        confidence_level="high"
    ))

    # Save action
    await test_repo.save_action(ActionRecord(
        task_id="demo_001",
        statement_id=1,
        action_type="click_thumbs_up",
        success=True,
        verified=True
    ))

    # Update task
    await test_repo.update_task_status("demo_001", "completed")

    # Verify retrieval
    task = await test_repo.get_task("demo_001")
    assert task is not None
    assert task["task_id"] == "demo_001"
    assert task["status"] == "completed"

    decisions = await test_repo.get_decisions("demo_001")
    assert len(decisions) == 1
    assert decisions[0]["answer"] == 1  # SQLite boolean
    assert decisions[0]["confidence"] == 0.94

    stats = await test_repo.get_dashboard_stats()
    assert stats["tasks_completed"] == 1
    assert stats["total_statements"] == 1
