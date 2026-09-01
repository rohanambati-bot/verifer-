"""
Unit tests for Natural Language Statement Parser.
"""
import pytest
from app.reasoning.statement_parser import StatementParser, ParsedStatement


def test_parse_hold_left_hand():
    parser = StatementParser()
    result = parser.parse("hold pan with left hand")
    assert result.action == "hold"
    assert result.primary_object == "pan"
    assert result.hand == "left"
    assert result.tool is None


def test_parse_scrub_with_tool_right_hand():
    parser = StatementParser()
    result = parser.parse("scrub pan with steel wool in right hand")
    assert result.action == "scrub"
    assert result.primary_object == "pan"
    assert result.tool == "steel wool"
    assert result.hand == "right"


def test_parse_place_with_destination():
    parser = StatementParser()
    result = parser.parse("place mug in basin with right hand")
    assert result.action == "place"
    assert result.primary_object == "mug"
    assert result.destination == "basin"
    assert result.hand == "right"


def test_parse_various_actions():
    parser = StatementParser()
    
    actions_to_test = [
        ("pick up knife with right hand", "pick up", "knife", "right"),
        ("put down cup on table with left hand", "put down", "cup", "left"),
        ("wipe counter with cloth in right hand", "wipe", "counter", "right"),
        ("wash plate with sponge in left hand", "wash", "plate", "left"),
        ("touch faucet with right hand", "touch", "faucet", "right"),
        ("open lid with left hand", "open", "lid", "left"),
        ("close door with right hand", "close", "door", "right"),
        ("move bowl into sink with left hand", "move", "bowl", "left"),
    ]

    for sentence, expected_action, expected_obj, expected_hand in actions_to_test:
        parsed = parser.parse(sentence)
        assert parsed.action == expected_action, f"Failed action for: {sentence}"
        assert parsed.primary_object == expected_obj, f"Failed object for: {sentence}"
        assert parsed.hand == expected_hand, f"Failed hand for: {sentence}"


def test_extensibility():
    parser = StatementParser(
        extra_actions={"juggle": {"aliases": ["juggle", "juggling"], "requires_object": True, "can_have_tool": False, "can_have_destination": False, "requires_temporal": True}},
        extra_objects=["orange", "ball"]
    )
    result = parser.parse("juggle ball with left hand")
    assert result.action == "juggle"
    assert result.primary_object == "ball"
    assert result.hand == "left"
