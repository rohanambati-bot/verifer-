"""
E2E Test: Full Autonomous Pipeline
LOCAL WEBSITE -> VIDEO -> STATEMENTS -> ANALYSIS -> DECISIONS -> VALIDATION -> SUBMISSION -> RECORD
"""
import os
import json
import pytest
import asyncio
import tempfile

from app.config import AppConfig, AgentConfig, VisionConfig
from app.main import VisionClickAgent
from app.browser.task_parser import ParsedTask, TaskStatement


@pytest.mark.asyncio
async def test_full_pipeline_headless_mock():
    # Setup temporary database
    temp_db = tempfile.mktemp(suffix=".db")
    
    config = AppConfig(
        agent=AgentConfig(dry_run=True, auto_submit=False, max_tasks=1),
        vision=VisionConfig(provider="mock", sample_fps=4),
        db_path=temp_db
    )

    agent = VisionClickAgent(config)
    await agent.initialize()

    # Create synthetic parsed task data to run through pipeline
    task = {
        "task_id": "demo_001",
        "statements": [
            {"id": 1, "text": "hold pan with left hand", "answer": True},
            {"id": 2, "text": "scrub pan with steel wool in right hand", "answer": True},
            {"id": 3, "text": "place mug in basin with right hand", "answer": False}
        ]
    }

    # Set mock context
    agent.vision.set_current_task("demo_001")
    
    # Process video through temporal processor
    temp_video = tempfile.mktemp(suffix=".mp4")
    agent.temporal.extractor._create_placeholder_video(temp_video)
    
    temporal_analysis = await agent.temporal.process_video(temp_video, task_id="demo_001")
    assert len(temporal_analysis.frame_analyses) > 0

    # Classify each statement
    decisions = []
    for stmt in task["statements"]:
        parsed = agent.parser.parse(stmt["text"])
        decision = agent.classifier.classify(
            statement_id=stmt["id"],
            statement_text=stmt["text"],
            parsed=parsed,
            temporal=temporal_analysis,
            task_id="demo_001"
        )
        decisions.append(decision)
        
        # Save to database
        from app.database.models import DecisionRecord
        await agent.repo.save_decision(DecisionRecord(
            task_id="demo_001",
            statement_id=stmt["id"],
            statement_text=stmt["text"],
            answer=decision.answer,
            confidence=decision.confidence,
            confidence_level=decision.confidence_level.value,
        ))

    # Verify decisions match ground truth
    assert decisions[0].answer is True
    assert decisions[0].action_label == "👍"
    assert decisions[1].answer is True
    assert decisions[1].action_label == "👍"
    assert decisions[2].answer is False
    assert decisions[2].action_label == "👎"

    # Verify database persistence
    saved_decisions = await agent.repo.get_decisions("demo_001")
    assert len(saved_decisions) == 3
    assert saved_decisions[0]["statement_id"] == 1
    assert saved_decisions[0]["answer"] == 1
    assert saved_decisions[2]["statement_id"] == 3
    assert saved_decisions[2]["answer"] == 0

    await agent.shutdown()
    if os.path.exists(temp_db):
        os.remove(temp_db)
    if os.path.exists(temp_video):
        os.remove(temp_video)
