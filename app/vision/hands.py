"""
VisionClick Agent - Hand detection models and hand-object relationship reasoning.
"""
from typing import List, Optional, Dict, Any
from app.vision.base import (
    HandSide, HandDetection, HandObjectRelation, RelationType, ObjectDetection
)


# Map action verbs to relation types
ACTION_TO_RELATION: Dict[str, RelationType] = {
    "hold": RelationType.HOLDING,
    "pick up": RelationType.PICKING_UP,
    "pick_up": RelationType.PICKING_UP,
    "put down": RelationType.PUTTING_DOWN,
    "put_down": RelationType.PUTTING_DOWN,
    "place": RelationType.PLACED_IN,
    "move": RelationType.MOVING,
    "scrub": RelationType.SCRUBBING,
    "wipe": RelationType.WIPING,
    "wash": RelationType.WASHING,
    "touch": RelationType.TOUCHING,
    "open": RelationType.OPENING,
    "close": RelationType.CLOSING,
    "cut": RelationType.CUTTING,
    "pour": RelationType.POURING,
    "stir": RelationType.STIRRING,
    "contact": RelationType.CONTACTING,

}


def requires_repeated_motion(action: str) -> bool:
    """Check if an action requires repeated/continuous motion evidence."""
    return action in ("scrub", "wipe", "wash", "scrubbing", "wiping", "washing")


def requires_trajectory(action: str) -> bool:
    """Check if an action requires trajectory/movement evidence."""
    return action in (
        "place", "move", "pick up", "put down", "pick_up", "put_down",
        "placed_in", "placed_on", "moving", "picking_up", "putting_down",
    )


def parse_hand_side(text: str) -> HandSide:
    """Parse hand side from text."""
    text = text.lower().strip()
    if "left" in text:
        return HandSide.LEFT
    elif "right" in text:
        return HandSide.RIGHT
    return HandSide.UNKNOWN


def build_expected_relations(
    action: str,
    hand: HandSide,
    primary_object: str,
    tool: Optional[str] = None,
    destination: Optional[str] = None,
) -> List[HandObjectRelation]:
    """Build expected hand-object relations from a parsed statement."""
    relations = []
    relation_type = ACTION_TO_RELATION.get(action, RelationType.TOUCHING)

    # Primary relation: hand → action → object
    relations.append(HandObjectRelation(
        hand=hand,
        relation=relation_type,
        target_object=primary_object,
        tool=tool,
        temporal_evidence=requires_repeated_motion(action) or requires_trajectory(action),
    ))

    # If there's a tool, hand must also be holding/contacting the tool
    if tool:
        relations.append(HandObjectRelation(
            hand=hand,
            relation=RelationType.HOLDING,
            target_object=tool,
            temporal_evidence=False,
        ))

    # If there's a destination, object must move to destination
    if destination:
        relations.append(HandObjectRelation(
            hand=hand,
            relation=RelationType.PLACED_IN,
            target_object=primary_object,
            tool=None,
            temporal_evidence=True,
        ))

    return relations
