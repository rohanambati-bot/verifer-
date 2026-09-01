"""
VisionClick Agent - Decision Classifier.

Converts evidence + confidence into TRUE/FALSE decisions.
Maps TRUE → 👍, FALSE → 👎. Logs everything before any action.
"""
from typing import List, Dict, Any, Optional
from app.reasoning.evidence import EvidenceCollection, EvidenceEngine
from app.reasoning.confidence import ConfidenceConfig, ConfidenceLevel, ConfidenceTracker
from app.reasoning.action_reasoner import ActionReasoner, EvidenceRequirement
from app.reasoning.statement_parser import ParsedStatement
from app.vision.base import TemporalAnalysis
from app.utils.logging import log_decision, get_logger


class Decision:
    """A single statement decision with full audit trail."""

    def __init__(
        self,
        statement_id: int,
        statement_text: str,
        answer: bool,
        confidence: float,
        evidence: EvidenceCollection,
        confidence_level: ConfidenceLevel,
    ):
        self.statement_id = statement_id
        self.statement_text = statement_text
        self.answer = answer
        self.confidence = confidence
        self.evidence = evidence
        self.confidence_level = confidence_level

    @property
    def thumbs_up(self) -> bool:
        return self.answer

    @property
    def action_label(self) -> str:
        return "👍" if self.answer else "👎"

    def to_dict(self) -> Dict[str, Any]:
        first_ev = self.evidence.evidence[0].reason if self.evidence.evidence else "Visual verification completed"
        return {
            "statement_id": self.statement_id,
            "statement_text": self.statement_text,
            "answer": self.answer,
            "confidence": self.confidence,
            "action": self.action_label,
            "action_label": self.action_label,
            "confidence_level": self.confidence_level.value,
            "explanation": first_ev,
            "evidence_count": len(self.evidence.evidence),
            "evidence": [{"reason": ev.reason, "score": ev.score, "start": ev.start, "end": ev.end} for ev in self.evidence.evidence],
            "is_second_pass": self.evidence.is_second_pass,
        }



class DecisionClassifier:
    """
    Classifies statements as TRUE/FALSE using evidence and confidence.

    Pipeline:
    1. Parse statement
    2. Build evidence requirements
    3. Evaluate vision evidence
    4. Compute confidence
    5. Apply thresholds
    6. Log decision
    """

    def __init__(self, confidence_config: Optional[ConfidenceConfig] = None):
        self.reasoner = ActionReasoner()
        self.evidence_engine = EvidenceEngine()
        self.confidence_config = confidence_config or ConfidenceConfig()
        self.confidence_tracker = ConfidenceTracker(self.confidence_config)
        self.decisions: Dict[int, Decision] = {}

    def classify(
        self,
        statement_id: int,
        statement_text: str,
        parsed: ParsedStatement,
        temporal: TemporalAnalysis,
        task_id: str = "",
        is_second_pass: bool = False,
    ) -> Decision:
        """Classify a statement as TRUE or FALSE with evidence."""
        logger = get_logger()

        # Build evidence requirements
        requirement = self.reasoner.build_requirements(statement_id, parsed)

        # Create evidence collection
        collection = self.evidence_engine.create_collection(
            statement_id, statement_text
        )

        # Evaluate temporal evidence
        evaluation = self.reasoner.evaluate_temporal_evidence(
            requirement, temporal
        )

        # Build evidence items from evaluation
        self.evidence_engine.build_evidence_from_evaluation(
            statement_id,
            evaluation,
            temporal_start=temporal.start_time,
            temporal_end=temporal.end_time,
        )

        # Compute confidence
        overall_score = evaluation.get("overall_score", 0.0)
        confidence = self.evidence_engine.compute_confidence(statement_id)
        # Blend with evaluation score
        confidence = 0.5 * confidence + 0.5 * overall_score

        # Decision: TRUE if evidence score is above 0.5
        answer = overall_score > 0.5

        # Record in confidence tracker
        if is_second_pass:
            answer, confidence = self.confidence_tracker.record_second_pass(
                statement_id, answer, confidence
            )
        else:
            self.confidence_tracker.record_first_pass(
                statement_id, answer, confidence
            )

        confidence_level = self.confidence_config.classify(confidence)

        # Finalize evidence
        self.evidence_engine.finalize_decision(
            statement_id, answer, confidence, is_second_pass
        )

        # Log before any action
        evidence_summary = "; ".join(
            e.reason for e in collection.evidence[:3]
        ) or "No specific evidence"

        log_decision(
            task_id=task_id,
            statement_id=statement_id,
            decision=answer,
            confidence=confidence,
            latency_ms=0,
            evidence=evidence_summary,
        )

        decision = Decision(
            statement_id=statement_id,
            statement_text=statement_text,
            answer=answer,
            confidence=confidence,
            evidence=collection,
            confidence_level=confidence_level,
        )
        self.decisions[statement_id] = decision
        return decision

    def needs_second_pass(self, statement_id: int) -> bool:
        """Check if statement needs second-pass verification."""
        return self.confidence_tracker.needs_second_pass(statement_id)

    def get_all_decisions(self) -> List[Decision]:
        """Get all decisions made."""
        return list(self.decisions.values())

    def all_decided(self, statement_ids: List[int]) -> bool:
        """Check if all statements have decisions."""
        return all(sid in self.decisions for sid in statement_ids)

    def reset(self):
        """Reset classifier state."""
        self.decisions.clear()
        self.evidence_engine.reset()
        self.confidence_tracker.reset()
