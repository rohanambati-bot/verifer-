"""
VisionClick Agent - Vision provider base interface.

All vision analysis goes through this abstraction. The rest of the application
NEVER depends on a specific model directly.

To add a new vision model:
1. Create a new class extending VisionProvider
2. Implement all abstract methods
3. Register it in the provider factory
"""
import abc
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field


# ─── Data Models ──────────────────────────────────────────────────────────────

class HandSide(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    UNKNOWN = "unknown"


class RelationType(str, Enum):
    HOLDING = "holding"
    TOUCHING = "touching"
    MOVING = "moving"
    PLACED_ON = "placed_on"
    PLACED_IN = "placed_in"
    CONTACTING = "contacting"
    SCRUBBING = "scrubbing"
    WIPING = "wiping"
    WASHING = "washing"
    PICKING_UP = "picking_up"
    PUTTING_DOWN = "putting_down"
    OPENING = "opening"
    CLOSING = "closing"
    CUTTING = "cutting"
    POURING = "pouring"
    STIRRING = "stirring"



class BoundingBox(BaseModel):
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    confidence: float = 0.0


class ObjectDetection(BaseModel):
    label: str
    confidence: float = 0.0
    bbox: Optional[BoundingBox] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)


class HandDetection(BaseModel):
    side: HandSide
    confidence: float = 0.0
    bbox: Optional[BoundingBox] = None
    objects_held: List[str] = Field(default_factory=list)
    relations: List[Dict[str, Any]] = Field(default_factory=list)


class HandObjectRelation(BaseModel):
    hand: HandSide
    relation: RelationType
    target_object: str
    tool: Optional[str] = None
    confidence: float = 0.0
    temporal_evidence: bool = False


class FrameAnalysis(BaseModel):
    frame_number: int = 0
    timestamp: float = 0.0
    objects: List[ObjectDetection] = Field(default_factory=list)
    hands: List[HandDetection] = Field(default_factory=list)
    relations: List[HandObjectRelation] = Field(default_factory=list)
    motion_score: float = 0.0
    scene_description: str = ""


class TemporalAnalysis(BaseModel):
    start_time: float = 0.0
    end_time: float = 0.0
    frame_analyses: List[FrameAnalysis] = Field(default_factory=list)
    detected_actions: List[Dict[str, Any]] = Field(default_factory=list)
    motion_pattern: str = ""
    confidence: float = 0.0
    summary: str = ""


# ─── Abstract Provider ────────────────────────────────────────────────────────

class VisionProvider(abc.ABC):
    """
    Abstract base class for vision analysis providers.

    Implementations:
    - MockVisionProvider: Uses ground truth for testing (no AI model needed)
    - LocalVisionProvider: Stub for connecting local models (LLaVA, Florence-2, etc.)

    To implement a custom provider:
    1. Subclass VisionProvider
    2. Implement all @abstractmethod methods
    3. Use `create_provider()` factory to instantiate
    """

    @abc.abstractmethod
    async def analyze_frame(self, frame: Any) -> FrameAnalysis:
        """Analyze a single frame for objects, hands, and relations."""
        pass

    @abc.abstractmethod
    async def analyze_frames(self, frames: List[Any]) -> List[FrameAnalysis]:
        """Analyze multiple frames (may batch for efficiency)."""
        pass

    @abc.abstractmethod
    async def analyze_temporal_segment(
        self, frames: List[Any], timestamps: List[float]
    ) -> TemporalAnalysis:
        """Analyze a temporal segment for actions and motion patterns."""
        pass

    @abc.abstractmethod
    async def detect_hands(self, frame: Any) -> List[HandDetection]:
        """Detect hands in a frame."""
        pass

    @abc.abstractmethod
    async def detect_objects(self, frame: Any) -> List[ObjectDetection]:
        """Detect objects in a frame."""
        pass

    async def close(self):
        """Cleanup resources."""
        pass


def create_provider(provider_type: str, **kwargs) -> VisionProvider:
    """Factory to create vision providers."""
    if provider_type == "mock":
        from app.vision.mock import MockVisionProvider
        return MockVisionProvider(**kwargs)
    elif provider_type == "local":
        from app.vision.local import LocalVisionProvider
        return LocalVisionProvider(**kwargs)
    else:
        raise ValueError(f"Unknown vision provider: {provider_type}")
