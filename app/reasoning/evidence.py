"""
VisionClick Agent - Evidence Engine.

Every decision MUST contain evidence. This module collects, structures,
and scores evidence from vision analysis. Never produces a bare TRUE/FALSE.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """A single piece of evidence supporting a decision."""
    start: float = 0.0       # Start timestamp (seconds)
    end: float = 0.0         # End timestamp (seconds)
    reason: str = ""         # Human-readable explanation
    frame_numbers: List[int] = Field(default_factory=list)
    score: float = 0.0       # Evidence strength (0-1)
    evidence_type: str = ""  # "object", "hand", "relation", "temporal", "motion"


class EvidenceCollection(BaseModel):
    """Complete evidence for a statement decision."""
    statement_id: int
    statement_text: str = ""
    answer: bool = False
    confidence: float = 0.0
    evidence: List[EvidenceItem] = Field(default_factory=list)
    first_pass_answer: Optional[bool] = None
    first_pass_confidence: Optional[float] = None
    second_pass_answer: Optional[bool] = None
    second_pass_confidence: Optional[float] = None
    is_second_pass: bool = False
    status: str = "pending"  # pending, accepted, uncertain, review


class EvidenceEngine:
    """Collect and evaluate evidence for decisions."""

    def __init__(self):
        self.collections: Dict[int, EvidenceCollection] = {}

    def create_collection(
        self, statement_id: int, statement_text: str
    ) -> EvidenceCollection:
        """Create a new evidence collection for a statement."""
        collection = EvidenceCollection(
            statement_id=statement_id,
            statement_text=statement_text,
        )
        self.collections[statement_id] = collection
        return collection

    def add_evidence(
        self,
        statement_id: int,
        start: float,
        end: float,
        reason: str,
        score: float = 0.0,
        evidence_type: str = "general",
        frame_numbers: Optional[List[int]] = None,
    ):
        """Add evidence to a statement's collection."""
        collection = self.collections.get(statement_id)
        if not collection:
            return

        collection.evidence.append(EvidenceItem(
            start=start,
            end=end,
            reason=reason,
            score=score,
            evidence_type=evidence_type,
            frame_numbers=frame_numbers or [],
        ))

    def build_evidence_from_evaluation(
        self,
        statement_id: int,
        evaluation: Dict[str, Any],
        temporal_start: float = 0.0,
        temporal_end: float = 0.0,
    ):
        """Build evidence items from action reasoner evaluation."""
        collection = self.collections.get(statement_id)
        if not collection:
            return

        overall = evaluation.get("overall_score", 0.0)

        # Object evidence
        if evaluation.get("avg_score", 0) > 0:
            self.add_evidence(
                statement_id,
                start=temporal_start,
                end=temporal_end,
                reason=f"Visual evidence score: {evaluation.get('avg_score', 0):.2f} "
                       f"across {len(evaluation.get('frame_scores', []))} frames",
                score=evaluation.get("avg_score", 0),
                evidence_type="visual",
            )

        # Temporal consistency
        consistency = evaluation.get("temporal_consistency", 0)
        if consistency > 0:
            self.add_evidence(
                statement_id,
                start=temporal_start,
                end=temporal_end,
                reason=f"Action observed consistently in "
                       f"{consistency * 100:.0f}% of analyzed frames",
                score=consistency,
                evidence_type="temporal",
            )

        # Motion evidence
        if evaluation.get("motion_detected", False):
            self.add_evidence(
                statement_id,
                start=temporal_start,
                end=temporal_end,
                reason="Motion/movement detected in video segment",
                score=0.8,
                evidence_type="motion",
            )

        if evaluation.get("repeated_motion", False):
            self.add_evidence(
                statement_id,
                start=temporal_start,
                end=temporal_end,
                reason="Repeated motion pattern detected (consistent with scrubbing/wiping)",
                score=0.9,
                evidence_type="motion",
            )

    def compute_confidence(self, statement_id: int) -> float:
        """Compute overall confidence from evidence."""
        collection = self.collections.get(statement_id)
        if not collection or not collection.evidence:
            return 0.0

        scores = [e.score for e in collection.evidence if e.score > 0]
        if not scores:
            return 0.0

        # Weighted average favoring higher scores
        avg = sum(scores) / len(scores)
        max_score = max(scores)
        # Blend average and max for robustness
        confidence = 0.6 * avg + 0.4 * max_score
        return min(1.0, max(0.0, confidence))

    def finalize_decision(
        self,
        statement_id: int,
        answer: bool,
        confidence: float,
        is_second_pass: bool = False,
    ) -> EvidenceCollection:
        """Finalize a decision with answer and confidence."""
        collection = self.collections.get(statement_id)
        if not collection:
            collection = EvidenceCollection(statement_id=statement_id)
            self.collections[statement_id] = collection

        if is_second_pass:
            collection.second_pass_answer = answer
            collection.second_pass_confidence = confidence
            collection.is_second_pass = True
        else:
            collection.first_pass_answer = answer
            collection.first_pass_confidence = confidence

        collection.answer = answer
        collection.confidence = confidence

        if confidence >= 0.90:
            collection.status = "accepted"
        elif confidence >= 0.75:
            collection.status = "review"
        else:
            collection.status = "uncertain"

        return collection

    def get_collection(self, statement_id: int) -> Optional[EvidenceCollection]:
        """Get evidence collection for a statement."""
        return self.collections.get(statement_id)

    def get_all_collections(self) -> List[EvidenceCollection]:
        """Get all evidence collections."""
        return list(self.collections.values())

    def reset(self):
        """Reset all evidence collections."""
        self.collections.clear()
