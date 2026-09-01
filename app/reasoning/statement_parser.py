"""
VisionClick Agent - Natural Language Statement Parser.

Converts statements like "scrub pan with steel wool in right hand"
into structured predicates for reasoning.

Supports: hold, pick up, put down, place, move, scrub, wipe, wash,
          touch, open, close. Extensible for new actions.
"""
import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ParsedStatement(BaseModel):
    """Structured predicate from a natural language statement."""
    original_text: str
    action: str
    primary_object: str
    hand: Optional[str] = None
    tool: Optional[str] = None
    destination: Optional[str] = None
    secondary_objects: List[str] = Field(default_factory=list)


# ─── Action Definitions ──────────────────────────────────────────────────────

# Each action definition has: aliases, requires_object, can_have_tool,
# can_have_destination, requires_temporal_evidence
ACTION_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "hold": {
        "aliases": ["hold", "holding", "holds"],
        "requires_object": True,
        "can_have_tool": False,
        "can_have_destination": False,
        "requires_temporal": False,
    },
    "pick up": {
        "aliases": ["pick up", "picks up", "picking up", "lift", "grab"],
        "requires_object": True,
        "can_have_tool": False,
        "can_have_destination": False,
        "requires_temporal": True,
    },
    "put down": {
        "aliases": ["put down", "puts down", "putting down", "set down", "release"],
        "requires_object": True,
        "can_have_tool": False,
        "can_have_destination": True,
        "requires_temporal": True,
    },
    "place": {
        "aliases": ["place", "places", "placing", "put"],
        "requires_object": True,
        "can_have_tool": False,
        "can_have_destination": True,
        "requires_temporal": True,
    },
    "move": {
        "aliases": ["move", "moves", "moving", "transfer", "slide", "push"],
        "requires_object": True,
        "can_have_tool": False,
        "can_have_destination": True,
        "requires_temporal": True,
    },
    "scrub": {
        "aliases": ["scrub", "scrubs", "scrubbing"],
        "requires_object": True,
        "can_have_tool": True,
        "can_have_destination": False,
        "requires_temporal": True,
    },
    "wipe": {
        "aliases": ["wipe", "wipes", "wiping"],
        "requires_object": True,
        "can_have_tool": True,
        "can_have_destination": False,
        "requires_temporal": True,
    },
    "wash": {
        "aliases": ["wash", "washes", "washing", "rinse"],
        "requires_object": True,
        "can_have_tool": True,
        "can_have_destination": False,
        "requires_temporal": True,
    },
    "touch": {
        "aliases": ["touch", "touches", "touching", "tap"],
        "requires_object": True,
        "can_have_tool": False,
        "can_have_destination": False,
        "requires_temporal": False,
    },
    "open": {
        "aliases": ["open", "opens", "opening"],
        "requires_object": True,
        "can_have_tool": False,
        "can_have_destination": False,
        "requires_temporal": True,
    },
    "close": {
        "aliases": ["close", "closes", "closing", "shut"],
        "requires_object": True,
        "can_have_tool": False,
        "can_have_destination": False,
        "requires_temporal": True,
    },
    "pour": {
        "aliases": ["pour", "pours", "pouring"],
        "requires_object": True,
        "can_have_tool": False,
        "can_have_destination": True,
        "requires_temporal": True,
    },
    "stir": {
        "aliases": ["stir", "stirs", "stirring", "mix"],
        "requires_object": True,
        "can_have_tool": True,
        "can_have_destination": False,
        "requires_temporal": True,
    },
    "cut": {
        "aliases": ["cut", "cuts", "cutting", "slice", "chop"],
        "requires_object": True,
        "can_have_tool": True,
        "can_have_destination": False,
        "requires_temporal": True,
    },
}

# Known objects for extraction
KNOWN_OBJECTS = [
    "steel wool", "cutting board", "scrub brush",  # Multi-word first
    "pan", "mug", "basin", "sponge", "plate", "bowl", "cup", "knife",
    "spoon", "fork", "pot", "lid", "towel", "faucet", "glass", "jar",
    "wok", "spatula", "ladle", "tongs", "whisk", "cloth", "rag",
    "bottle", "sink", "counter", "table", "rack", "stove",
    "vegetable", "fruit", "meat", "bread", "egg", "food",
]


# Prepositions for parsing
TOOL_PREPS = ["with", "using"]
DEST_PREPS = ["in", "into", "on", "onto", "inside"]
HAND_PATTERNS = [
    r"(?:with|in|using)\s+(left|right)\s+hand",
    r"(left|right)\s+hand",
]


class StatementParser:
    """
    Parse natural language statements into structured predicates.

    Usage:
        parser = StatementParser()
        result = parser.parse("scrub pan with steel wool in right hand")
        # result.action = "scrub"
        # result.primary_object = "pan"
        # result.tool = "steel wool"
        # result.hand = "right"
    """

    def __init__(self, extra_actions: Optional[Dict] = None,
                 extra_objects: Optional[List[str]] = None):
        self.actions = dict(ACTION_DEFINITIONS)
        if extra_actions:
            self.actions.update(extra_actions)

        self.objects = list(KNOWN_OBJECTS)
        if extra_objects:
            self.objects = extra_objects + self.objects

        # Sort objects longest first to prefer multi-word and specific matches
        self.objects = sorted(list(set(self.objects)), key=len, reverse=True)

        # Build alias lookup: alias → canonical action name
        self._alias_map: Dict[str, str] = {}
        for action_name, defn in self.actions.items():
            for alias in defn["aliases"]:
                self._alias_map[alias] = action_name

        # Sort aliases by length (longest first for greedy matching)
        self._sorted_aliases = sorted(
            self._alias_map.keys(), key=len, reverse=True
        )


    def parse(self, text: str) -> ParsedStatement:
        """Parse a statement into structured predicates."""
        original = text
        text = text.lower().strip()

        # Extract hand
        hand = self._extract_hand(text)
        # Remove hand phrase from text for cleaner parsing
        text_no_hand = text
        for pattern in HAND_PATTERNS:
            text_no_hand = re.sub(pattern, "", text_no_hand).strip()

        # Extract action
        action = self._extract_action(text_no_hand)

        # Remove action from text
        remainder = text_no_hand
        if action:
            for alias in self.actions[action]["aliases"]:
                if remainder.startswith(alias):
                    remainder = remainder[len(alias):].strip()
                    break

        # Extract tool (with/using X)
        tool = self._extract_tool(remainder, action)

        # Remove tool phrase
        if tool:
            for prep in TOOL_PREPS:
                pattern = re.escape(prep) + r"\s+" + re.escape(tool)
                remainder = re.sub(pattern, "", remainder).strip()

        # Extract destination (in/into/on/onto X)
        destination = self._extract_destination(remainder, action)

        # Remove destination phrase
        if destination:
            for prep in DEST_PREPS:
                pattern = re.escape(prep) + r"\s+" + re.escape(destination)
                remainder = re.sub(pattern, "", remainder).strip()

        # Extract primary object from remainder
        primary_object = self._extract_object(remainder)

        return ParsedStatement(
            original_text=original,
            action=action or "unknown",
            primary_object=primary_object or "unknown",
            hand=hand,
            tool=tool,
            destination=destination,
        )

    def _extract_hand(self, text: str) -> Optional[str]:
        """Extract hand side from text."""
        for pattern in HAND_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(1)  # "left" or "right"
        return None

    def _extract_action(self, text: str) -> Optional[str]:
        """Extract action verb from text."""
        for alias in self._sorted_aliases:
            if text.startswith(alias):
                return self._alias_map[alias]
        return None

    def _extract_tool(self, text: str, action: Optional[str]) -> Optional[str]:
        """Extract tool from 'with/using X' pattern."""
        if action and not self.actions.get(action, {}).get("can_have_tool", False):
            # Check if "with" is for tool or hand
            # Still try to extract if present
            pass

        for prep in TOOL_PREPS:
            pattern = r"(?:^|[\s,])" + re.escape(prep) + r"\s+(.+?)(?:\s+(?:in|on|into|onto)\s+|\s+(?:left|right)\s+hand|$)"
            match = re.search(pattern, text)
            if match:
                tool_text = match.group(1).strip()
                # Try to match known objects
                for obj in self.objects:
                    if obj in tool_text:
                        return obj
                # Return first reasonable chunk
                if tool_text and not tool_text.endswith("hand"):
                    return tool_text
        return None

    def _extract_destination(self, text: str, action: Optional[str]) -> Optional[str]:
        """Extract destination from 'in/into/on/onto X' pattern."""
        # Look for "in/into/on/onto <object>"
        for prep in DEST_PREPS:
            # Match "prep OBJECT" but not "prep left/right hand"
            pattern = r"(?:^|[\s,])" + re.escape(prep) + r"\s+(\S+(?:\s+\S+)?)"
            match = re.search(pattern, text)
            if match:
                dest_text = match.group(1).strip()
                # Filter out hand references
                if "hand" in dest_text:
                    continue
                # Try known objects
                for obj in self.objects:
                    if obj in dest_text:
                        return obj
                if dest_text:
                    return dest_text.split()[0]  # First word
        return None

    def _extract_object(self, text: str) -> Optional[str]:
        """Extract the primary object from remaining text."""
        for obj in self.objects:
            pattern = r"\b" + re.escape(obj) + r"\b"
            if re.search(pattern, text):
                return obj
        # Fallback: first non-stopword
        stopwords = {"the", "a", "an", "and", "or", "with", "in", "on", "to", "into", "onto"}
        words = text.split()
        for word in words:
            if word not in stopwords and len(word) > 1:
                return word
        return None


    def get_action_definition(self, action: str) -> Optional[Dict]:
        """Get definition for an action."""
        return self.actions.get(action)
