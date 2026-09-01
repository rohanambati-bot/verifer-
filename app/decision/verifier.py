"""
VisionClick Agent - Second-Pass Verifier.

For low-confidence decisions: analyze additional frames, temporal context,
compare beginning/middle/end, re-evaluate, and produce new confidence.
Records both passes in the database.
"""
from typing import List, Optional, Dict, Any
import numpy as np

from app.decision.classifier import Decision, DecisionClassifier
from app.reasoning.statement_parser import ParsedStatement
from app.vision.base import VisionProvider, TemporalAnalysis
from app.utils.logging import get_logger


class Verifier:
    """
    Second-pass verification for low-confidence decisions.

    Analyzes additional frames and temporal context to improve accuracy.
    """

    def __init__(self, vision_provider: VisionProvider):
        self.vision_provider = vision_provider

    async def verify_decision(
        self,
        decision: Decision,
        parsed: ParsedStatement,
        frames: List[Any],
        timestamps: List[float],
        classifier: DecisionClassifier,
        task_id: str = "",
    ) -> Decision:
        """
        Run second-pass verification on a low-confidence decision.

        Strategy:
        1. Sample additional frames from beginning, middle, and end
        2. Re-analyze with temporal context
        3. Compare temporal segments
        4. Produce new confidence score
        """
        logger = get_logger()
        logger.info(
            f"Second-pass verification for statement {decision.statement_id} "
            f"(first pass: {'TRUE' if decision.answer else 'FALSE'} @ {decision.confidence:.2f})",
            extra={"task_id": task_id, "stage": "verification"}
        )

        if len(frames) < 3:
            # Not enough frames for temporal comparison
            logger.warning(
                "Insufficient frames for second-pass verification",
                extra={"task_id": task_id, "stage": "verification"}
            )
            return decision

        # Segment analysis: beginning, middle, end
        n = len(frames)
        segment_size = max(1, n // 3)

        segments = {
            "beginning": (frames[:segment_size], timestamps[:segment_size]),
            "middle": (frames[n//3:2*n//3], timestamps[n//3:2*n//3]),
            "end": (frames[-segment_size:], timestamps[-segment_size:]),
        }

        segment_analyses = {}
        for name, (seg_frames, seg_ts) in segments.items():
            if seg_frames and seg_ts:
                analysis = await self.vision_provider.analyze_temporal_segment(
                    seg_frames, seg_ts
                )
                segment_analyses[name] = analysis

        # Combine all segment analyses into a richer temporal view
        all_frame_analyses = []
        all_timestamps = []
        for name, analysis in segment_analyses.items():
            all_frame_analyses.extend(analysis.frame_analyses)
            if analysis.start_time >= 0:
                all_timestamps.extend([analysis.start_time, analysis.end_time])

        if not all_timestamps:
            all_timestamps = timestamps

        combined_temporal = TemporalAnalysis(
            start_time=min(all_timestamps) if all_timestamps else 0,
            end_time=max(all_timestamps) if all_timestamps else 0,
            frame_analyses=all_frame_analyses,
            detected_actions=[],
            motion_pattern="analyzed",
            confidence=0.0,
            summary="Second-pass combined analysis",
        )

        # Re-classify with enhanced evidence
        new_decision = classifier.classify(
            statement_id=decision.statement_id,
            statement_text=decision.statement_text,
            parsed=parsed,
            temporal=combined_temporal,
            task_id=task_id,
            is_second_pass=True,
        )

        logger.info(
            f"Second-pass result: {'TRUE' if new_decision.answer else 'FALSE'} "
            f"@ {new_decision.confidence:.2f} "
            f"(was {'TRUE' if decision.answer else 'FALSE'} @ {decision.confidence:.2f})",
            extra={"task_id": task_id, "stage": "verification"}
        )

        return new_decision
