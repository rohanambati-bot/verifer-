"""
VisionClick Agent - Confidence System.

Implements thresholded decision routing:
- HIGH_CONFIDENCE (>=0.90): Accept immediately
- REVIEW_THRESHOLD (0.75-0.90): Run second analysis pass
- Below 0.75: Mark as uncertain
"""
from typing import Optional, Tuple
from enum import Enum


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    REVIEW = "review"
    UNCERTAIN = "uncertain"


class ConfidenceConfig:
    """Confidence thresholds configuration."""

    def __init__(
        self,
        high_confidence: float = 0.90,
        review_threshold: float = 0.75,
    ):
        self.high_confidence = high_confidence
        self.review_threshold = review_threshold

    def classify(self, confidence: float) -> ConfidenceLevel:
        """Classify a confidence score into a level."""
        if confidence >= self.high_confidence:
            return ConfidenceLevel.HIGH
        elif confidence >= self.review_threshold:
            return ConfidenceLevel.REVIEW
        else:
            return ConfidenceLevel.UNCERTAIN

    def should_accept(self, confidence: float) -> bool:
        """Check if confidence is high enough to accept."""
        return confidence >= self.high_confidence

    def needs_review(self, confidence: float) -> bool:
        """Check if confidence requires a second pass."""
        return self.review_threshold <= confidence < self.high_confidence

    def is_uncertain(self, confidence: float) -> bool:
        """Check if confidence is too low."""
        return confidence < self.review_threshold


class ConfidenceTracker:
    """Track confidence across first and second passes."""

    def __init__(self, config: Optional[ConfidenceConfig] = None):
        self.config = config or ConfidenceConfig()
        self._first_pass: dict = {}  # statement_id -> (answer, confidence)
        self._second_pass: dict = {}

    def record_first_pass(
        self, statement_id: int, answer: bool, confidence: float
    ) -> ConfidenceLevel:
        """Record first pass result and return confidence level."""
        self._first_pass[statement_id] = (answer, confidence)
        return self.config.classify(confidence)

    def record_second_pass(
        self, statement_id: int, answer: bool, confidence: float
    ) -> Tuple[bool, float]:
        """Record second pass and return final decision."""
        self._second_pass[statement_id] = (answer, confidence)
        first = self._first_pass.get(statement_id)

        if first:
            first_answer, first_conf = first
            # If second pass has higher confidence, use it
            if confidence > first_conf:
                return answer, confidence
            else:
                return first_answer, first_conf
        return answer, confidence

    def get_final_decision(
        self, statement_id: int
    ) -> Optional[Tuple[bool, float]]:
        """Get the final decision for a statement."""
        if statement_id in self._second_pass:
            second = self._second_pass[statement_id]
            first = self._first_pass.get(statement_id, (None, 0))
            if second[1] > first[1]:
                return second
            return first
        return self._first_pass.get(statement_id)

    def needs_second_pass(self, statement_id: int) -> bool:
        """Check if a statement needs a second pass."""
        result = self._first_pass.get(statement_id)
        if not result:
            return False
        _, confidence = result
        return self.config.needs_review(confidence)

    def reset(self):
        """Reset all tracked confidence."""
        self._first_pass.clear()
        self._second_pass.clear()
