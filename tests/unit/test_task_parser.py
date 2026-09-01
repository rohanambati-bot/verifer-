"""
Unit tests for DOM task parser data models and logic.
"""
import pytest
from app.browser.task_parser import TaskStatement, ParsedTask


def test_parsed_task_structure():
    task = ParsedTask(
        task_id="demo_001",
        video_src="/videos/demo_001.mp4",
        statements=[
            TaskStatement(id=1, text="hold pan with left hand", index=1),
            TaskStatement(id=2, text="scrub pan with steel wool in right hand", index=2),
            TaskStatement(id=3, text="place mug in basin with right hand", index=3),
        ],
        has_submit=True
    )

    assert task.task_id == "demo_001"
    assert len(task.statements) == 3
    assert task.statements[0].id == 1
    assert task.statements[1].text == "scrub pan with steel wool in right hand"
    assert task.has_submit is True
