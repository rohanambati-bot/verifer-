"""
VisionClick Agent - Object detection models and utilities.
Defines object classes, relationships, and spatial reasoning.
"""
from typing import List, Dict, Set


# Known object categories for kitchen/hand-activity tasks
OBJECT_CATEGORIES: Dict[str, Set[str]] = {
    "cookware": {"pan", "pot", "skillet", "wok", "saucepan", "frying pan"},
    "utensils": {"spatula", "spoon", "fork", "knife", "ladle", "tongs", "whisk"},
    "cleaning": {"steel wool", "sponge", "scrub brush", "cloth", "towel", "rag"},
    "containers": {"mug", "cup", "bowl", "plate", "basin", "sink", "glass", "jar"},
    "food": {"vegetable", "fruit", "meat", "bread", "egg", "rice"},
    "appliances": {"stove", "faucet", "tap", "oven", "microwave"},
    "surfaces": {"counter", "table", "cutting board", "rack", "shelf"},
}

# Flatten to a single set of known objects
ALL_KNOWN_OBJECTS: Set[str] = set()
for category_items in OBJECT_CATEGORIES.values():
    ALL_KNOWN_OBJECTS.update(category_items)


def normalize_object_name(name: str) -> str:
    """Normalize an object name to a canonical form."""
    name = name.lower().strip()
    # Common aliases
    aliases = {
        "frying pan": "pan",
        "wash basin": "basin",
        "steel wool pad": "steel wool",
        "scrubber": "steel wool",
        "coffee mug": "mug",
        "drinking cup": "cup",
    }
    return aliases.get(name, name)


def get_object_category(obj_name: str) -> str:
    """Get the category of an object."""
    obj_name = normalize_object_name(obj_name)
    for category, items in OBJECT_CATEGORIES.items():
        if obj_name in items:
            return category
    return "unknown"


def are_objects_compatible(obj1: str, obj2: str, relation: str) -> bool:
    """Check if two objects can have a given relationship."""
    obj1 = normalize_object_name(obj1)
    obj2 = normalize_object_name(obj2)

    # Cleaning tools can contact cookware/containers
    if relation in ("scrubbing", "wiping", "contacting"):
        cat1 = get_object_category(obj1)
        cat2 = get_object_category(obj2)
        if cat1 == "cleaning" or cat2 == "cleaning":
            return True

    # Containers can be placed in other containers/surfaces
    if relation in ("placed_in", "placed_on"):
        return True

    # General: objects can be held, touched, moved
    if relation in ("holding", "touching", "moving"):
        return True

    return True  # Default permissive
