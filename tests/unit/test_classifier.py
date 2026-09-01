"""
Unit tests for Decision Classifier.
"""
import pytest
from app.decision.classifier import DecisionClassifier
from app.reasoning.statement_parser import StatementParser
from app.vision.base import (
    TemporalAnalysis, FrameAnalysis, HandDetection, ObjectDetection,
    HandObjectRelation, HandSide, RelationType
)


def test_decision_classifier_true_mapping(statement_parser, decision_classifier):
    text = "hold pan with left hand"
    parsed = statement_parser.parse(text)

    # Construct temporal analysis where left hand is holding pan
    frame_analysis = FrameAnalysis(
        frame_number=0,
        timestamp=0.0,
        objects=[ObjectDetection(label="pan", confidence=0.95)],
        hands=[HandDetection(side=HandSide.LEFT, confidence=0.95)],
        relations=[
            HandObjectRelation(
                hand=HandSide.LEFT,
                relation=RelationType.HOLDING,
                target_object="pan",
                confidence=0.95,
                temporal_evidence=False
            )
        ]
    )

    temporal = TemporalAnalysis(
        start_time=0.0,
        end_time=1.0,
        frame_analyses=[frame_analysis],
        motion_pattern="static",
        confidence=0.95
    )

    decision = decision_classifier.classify(
        statement_id=1,
        statement_text=text,
        parsed=parsed,
        temporal=temporal,
        task_id="test_001"
    )

    assert decision.answer is True
    assert decision.thumbs_up is True
    assert decision.action_label == "👍"
    assert len(decision.evidence.evidence) > 0
    assert decision.confidence >= 0.70


def test_decision_classifier_false_mapping(statement_parser, decision_classifier):
    text = "place mug in basin with right hand"
    parsed = statement_parser.parse(text)

    # Empty frame analysis - no mug, no basin, no right hand action
    frame_analysis = FrameAnalysis(
        frame_number=0,
        timestamp=0.0,
        objects=[ObjectDetection(label="pan", confidence=0.95)],
        hands=[HandDetection(side=HandSide.LEFT, confidence=0.95)],
        relations=[]
    )

    temporal = TemporalAnalysis(
        start_time=0.0,
        end_time=1.0,
        frame_analyses=[frame_analysis],
        motion_pattern="static",
        confidence=0.1
    )

    decision = decision_classifier.classify(
        statement_id=2,
        statement_text=text,
        parsed=parsed,
        temporal=temporal,
        task_id="test_001"
    )

    assert decision.answer is False
    assert decision.thumbs_up is False
    assert decision.action_label == "👎"
