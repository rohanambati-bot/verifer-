"""
VisionClick Agent - Action Reasoner.

Maps parsed predicates to required evidence patterns.
Determines what vision evidence is needed to verify each statement.
"""
from typing import List, Dict, Any, Optional
from app.reasoning.statement_parser import ParsedStatement
from app.vision.base import (
    HandSide, RelationType, HandObjectRelation,
    FrameAnalysis, TemporalAnalysis
)
from app.vision.hands import (
    ACTION_TO_RELATION, requires_repeated_motion,
    requires_trajectory, parse_hand_side, build_expected_relations
)


class EvidenceRequirement:
    """What evidence is needed to verify a statement."""

    def __init__(
        self,
        statement_id: int,
        parsed: ParsedStatement,
        required_hand: Optional[HandSide] = None,
        required_objects: Optional[List[str]] = None,
        required_relations: Optional[List[HandObjectRelation]] = None,
        needs_temporal: bool = False,
        needs_repeated_motion: bool = False,
        needs_trajectory: bool = False,
    ):
        self.statement_id = statement_id
        self.parsed = parsed
        self.required_hand = required_hand
        self.required_objects = required_objects or []
        self.required_relations = required_relations or []
        self.needs_temporal = needs_temporal
        self.needs_repeated_motion = needs_repeated_motion
        self.needs_trajectory = needs_trajectory


class ActionReasoner:
    """
    Reasons about what evidence is needed for each statement
    and evaluates whether collected evidence satisfies requirements.
    """

    def build_requirements(
        self, statement_id: int, parsed: ParsedStatement
    ) -> EvidenceRequirement:
        """Build evidence requirements from a parsed statement."""
        hand = None
        if parsed.hand:
            hand = parse_hand_side(parsed.hand)

        # Required objects
        objects = []
        if parsed.primary_object and parsed.primary_object != "unknown":
            objects.append(parsed.primary_object)
        if parsed.tool:
            objects.append(parsed.tool)
        if parsed.destination:
            objects.append(parsed.destination)

        # Build expected relations
        relations = []
        if hand and parsed.primary_object:
            relations = build_expected_relations(
                action=parsed.action,
                hand=hand,
                primary_object=parsed.primary_object,
                tool=parsed.tool,
                destination=parsed.destination,
            )

        needs_repeated = requires_repeated_motion(parsed.action)
        needs_traj = requires_trajectory(parsed.action)

        return EvidenceRequirement(
            statement_id=statement_id,
            parsed=parsed,
            required_hand=hand,
            required_objects=objects,
            required_relations=relations,
            needs_temporal=needs_repeated or needs_traj,
            needs_repeated_motion=needs_repeated,
            needs_trajectory=needs_traj,
        )

    def evaluate_frame_evidence(
        self, requirement: EvidenceRequirement, analysis: FrameAnalysis
    ) -> Dict[str, Any]:
        """Evaluate how well a single frame satisfies requirements."""
        scores = {
            "hand_found": False,
            "objects_found": [],
            "objects_missing": [],
            "relations_matched": 0,
            "relations_total": len(requirement.required_relations),
            "frame_score": 0.0,
        }

        # Check hand presence
        if requirement.required_hand:
            for hand in analysis.hands:
                if hand.side == requirement.required_hand:
                    scores["hand_found"] = True
                    break
        else:
            scores["hand_found"] = True  # No specific hand required

        # Check objects
        detected_labels = {obj.label.lower() for obj in analysis.objects}
        for req_obj in requirement.required_objects:
            if req_obj.lower() in detected_labels:
                scores["objects_found"].append(req_obj)
            else:
                scores["objects_missing"].append(req_obj)

        # Check relations
        for req_rel in requirement.required_relations:
            for detected_rel in analysis.relations:
                if (detected_rel.hand == req_rel.hand and
                    detected_rel.relation == req_rel.relation and
                    detected_rel.target_object.lower() == req_rel.target_object.lower()):
                    scores["relations_matched"] += 1
                    break

        # Check relations
        if scores["relations_total"] > 0:
            if scores["relations_matched"] == 0:
                scores["frame_score"] = 0.0
                return scores
            rel_ratio = scores["relations_matched"] / scores["relations_total"]
        else:
            rel_ratio = 1.0

        hand_score = 1.0 if scores["hand_found"] else 0.0
        obj_score = len(scores["objects_found"]) / len(requirement.required_objects) if requirement.required_objects else 1.0

        scores["frame_score"] = hand_score * 0.2 + obj_score * 0.2 + rel_ratio * 0.6
        return scores

    def evaluate_temporal_evidence(
        self, requirement: EvidenceRequirement, temporal: TemporalAnalysis
    ) -> Dict[str, Any]:
        """Evaluate temporal evidence across multiple frames."""
        result = {
            "frame_scores": [],
            "avg_score": 0.0,
            "max_score": 0.0,
            "temporal_consistency": 0.0,
            "motion_detected": temporal.motion_pattern != "static",
            "repeated_motion": False,
            "trajectory_detected": False,
            "overall_score": 0.0,
        }

        # Evaluate each frame
        for frame_analysis in temporal.frame_analyses:
            frame_score = self.evaluate_frame_evidence(requirement, frame_analysis)
            result["frame_scores"].append(frame_score["frame_score"])

        if result["frame_scores"]:
            result["avg_score"] = sum(result["frame_scores"]) / len(result["frame_scores"])
            result["max_score"] = max(result["frame_scores"])

            # Temporal consistency: how many frames show evidence
            positive_frames = sum(1 for s in result["frame_scores"] if s >= 0.5)
            result["temporal_consistency"] = positive_frames / len(result["frame_scores"])

        # Check temporal requirements
        if requirement.needs_repeated_motion:
            # Multiple frames showing similar relations = repeated motion
            result["repeated_motion"] = result["temporal_consistency"] > 0.3
        if requirement.needs_trajectory:
            result["trajectory_detected"] = result["motion_detected"]

        # If avg_score is negligible (no relation observed), overall_score is 0
        if result["avg_score"] < 0.1:
            result["overall_score"] = result["avg_score"]
        else:
            components = [result["avg_score"]]
            if requirement.needs_temporal:
                components.append(result["temporal_consistency"])
            if requirement.needs_repeated_motion:
                components.append(1.0 if result["repeated_motion"] else 0.3)
            if requirement.needs_trajectory:
                components.append(1.0 if result["trajectory_detected"] else 0.3)
            result["overall_score"] = sum(components) / len(components)

        return result

