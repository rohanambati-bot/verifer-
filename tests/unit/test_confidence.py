"""
Unit tests for Confidence System and threshold routing.
"""
import pytest
from app.reasoning.confidence import (
    ConfidenceConfig, ConfidenceLevel, ConfidenceTracker
)


def test_confidence_classification():
    config = ConfidenceConfig(high_confidence=0.90, review_threshold=0.75)
    
    assert config.classify(0.95) == ConfidenceLevel.HIGH
    assert config.classify(0.90) == ConfidenceLevel.HIGH
    assert config.classify(0.85) == ConfidenceLevel.REVIEW
    assert config.classify(0.75) == ConfidenceLevel.REVIEW
    assert config.classify(0.74) == ConfidenceLevel.UNCERTAIN
    assert config.classify(0.50) == ConfidenceLevel.UNCERTAIN


def test_confidence_tracker_first_and_second_pass():
    config = ConfidenceConfig(high_confidence=0.90, review_threshold=0.75)
    tracker = ConfidenceTracker(config)

    # First pass: low confidence
    level = tracker.record_first_pass(statement_id=1, answer=False, confidence=0.71)
    assert level == ConfidenceLevel.UNCERTAIN
    
    # Statement 2: review threshold
    level2 = tracker.record_first_pass(statement_id=2, answer=False, confidence=0.80)
    assert level2 == ConfidenceLevel.REVIEW
    assert tracker.needs_second_pass(statement_id=2) is True

    # Second pass for statement 2: increases confidence
    final_ans, final_conf = tracker.record_second_pass(statement_id=2, answer=True, confidence=0.93)
    assert final_ans is True
    assert final_conf == 0.93
    assert tracker.get_final_decision(statement_id=2) == (True, 0.93)
