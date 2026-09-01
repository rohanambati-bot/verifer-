"""
Unit tests for Evidence Engine.
"""
import pytest
from app.reasoning.evidence import EvidenceEngine, EvidenceItem


def test_evidence_collection_lifecycle():
    engine = EvidenceEngine()
    
    collection = engine.create_collection(statement_id=1, statement_text="hold pan with left hand")
    assert collection.statement_id == 1
    assert collection.statement_text == "hold pan with left hand"
    assert len(collection.evidence) == 0

    engine.add_evidence(
        statement_id=1,
        start=1.2,
        end=2.8,
        reason="Left hand holding pan detected",
        score=0.92,
        evidence_type="relation"
    )

    assert len(collection.evidence) == 1
    item = collection.evidence[0]
    assert item.start == 1.2
    assert item.end == 2.8
    assert item.score == 0.92

    confidence = engine.compute_confidence(statement_id=1)
    assert confidence > 0.85

    finalized = engine.finalize_decision(statement_id=1, answer=True, confidence=confidence)
    assert finalized.answer is True
    assert finalized.status == "accepted"
