"""
VisionClick Agent - Mock Vision Provider.

Fully functional provider for testing. Uses ground truth data to generate
realistic detection results with configurable noise and confidence levels.
Enables complete E2E testing without any AI model installed.
"""
import json
import os
import random
from typing import List, Any, Optional, Dict

from app.vision.base import (
    VisionProvider, FrameAnalysis, TemporalAnalysis,
    HandDetection, ObjectDetection, HandObjectRelation,
    HandSide, RelationType, BoundingBox
)


class MockVisionProvider(VisionProvider):
    """
    Mock vision provider that simulates AI analysis using ground truth.

    For testing: provides realistic-looking detections that match ground truth.
    Adds configurable noise to simulate real-world variability.
    """

    def __init__(
        self,
        ground_truth_path: Optional[str] = None,
        noise_level: float = 0.05,
        base_confidence: float = 0.92,
        **kwargs,
    ):
        self.noise_level = noise_level
        self.base_confidence = base_confidence
        self.ground_truth: Dict[str, Any] = {}
        self._current_task_id: Optional[str] = None
        self._current_task_data: Optional[Dict] = None

        if ground_truth_path and os.path.exists(ground_truth_path):
            with open(ground_truth_path, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for task in data:
                        self.ground_truth[task["task_id"]] = task
                elif isinstance(data, dict):
                    if "tasks" in data:
                        for task in data["tasks"]:
                            self.ground_truth[task["task_id"]] = task
                    else:
                        self.ground_truth[data.get("task_id", "unknown")] = data

    def set_current_task(self, task_id: str):
        """Set the current task for context-aware mock responses."""
        self._current_task_id = task_id
        self._current_task_data = self.ground_truth.get(task_id)

    def _add_noise(self, confidence: float) -> float:
        """Add realistic noise to confidence."""
        noise = random.uniform(-self.noise_level, self.noise_level)
        return max(0.1, min(1.0, confidence + noise))

    def _get_task_objects(self) -> List[str]:
        """Get objects mentioned in current task statements."""
        if not self._current_task_data:
            return ["pan", "mug", "basin"]
        objects = set()
        for stmt in self._current_task_data.get("statements", []):
            text = stmt.get("text", "").lower()
            # Extract known objects from text
            for obj in ["pan", "mug", "basin", "steel wool", "sponge", "plate",
                         "bowl", "cup", "knife", "spoon", "fork", "pot",
                         "cutting board", "towel", "faucet", "lid"]:
                if obj in text:
                    objects.add(obj)
        return list(objects) if objects else ["pan", "mug"]

    def _get_task_hands(self) -> List[HandSide]:
        """Get hands mentioned in current task."""
        if not self._current_task_data:
            return [HandSide.LEFT, HandSide.RIGHT]
        hands = set()
        for stmt in self._current_task_data.get("statements", []):
            text = stmt.get("text", "").lower()
            if "left hand" in text:
                hands.add(HandSide.LEFT)
            if "right hand" in text:
                hands.add(HandSide.RIGHT)
        return list(hands) if hands else [HandSide.LEFT, HandSide.RIGHT]

    async def analyze_frame(self, frame: Any) -> FrameAnalysis:
        """Analyze a single frame using mock data."""
        objects = []
        for obj_name in self._get_task_objects():
            objects.append(ObjectDetection(
                label=obj_name,
                confidence=self._add_noise(self.base_confidence),
                bbox=BoundingBox(
                    x=random.uniform(0.1, 0.5),
                    y=random.uniform(0.1, 0.5),
                    width=random.uniform(0.1, 0.3),
                    height=random.uniform(0.1, 0.3),
                    confidence=self._add_noise(self.base_confidence),
                ),
            ))

        hands = []
        for side in self._get_task_hands():
            hands.append(HandDetection(
                side=side,
                confidence=self._add_noise(self.base_confidence),
                bbox=BoundingBox(
                    x=random.uniform(0.2, 0.6),
                    y=random.uniform(0.2, 0.6),
                    width=random.uniform(0.1, 0.2),
                    height=random.uniform(0.1, 0.2),
                    confidence=self._add_noise(self.base_confidence),
                ),
                objects_held=self._get_task_objects()[:1],
            ))

        # Build relations based on ground truth
        relations = self._build_mock_relations()

        return FrameAnalysis(
            frame_number=0,
            timestamp=0.0,
            objects=objects,
            hands=hands,
            relations=relations,
            motion_score=random.uniform(0.3, 0.8),
            scene_description="Mock frame analysis",
        )

    async def analyze_frames(self, frames: List[Any]) -> List[FrameAnalysis]:
        """Analyze multiple frames."""
        results = []
        for i, frame in enumerate(frames):
            analysis = await self.analyze_frame(frame)
            analysis.frame_number = i
            analysis.timestamp = i * 0.25  # Assume 4fps
            results.append(analysis)
        return results

    async def analyze_temporal_segment(
        self, frames: List[Any], timestamps: List[float]
    ) -> TemporalAnalysis:
        """Analyze temporal segment using mock data."""
        frame_analyses = await self.analyze_frames(frames)
        for i, ts in enumerate(timestamps):
            if i < len(frame_analyses):
                frame_analyses[i].timestamp = ts

        actions = []
        if self._current_task_data:
            for stmt in self._current_task_data.get("statements", []):
                if stmt.get("answer", False):
                    actions.append({
                        "action": stmt.get("text", ""),
                        "start_time": timestamps[0] if timestamps else 0.0,
                        "end_time": timestamps[-1] if timestamps else 1.0,
                        "confidence": self._add_noise(self.base_confidence),
                        "verified": True,
                    })

        return TemporalAnalysis(
            start_time=timestamps[0] if timestamps else 0.0,
            end_time=timestamps[-1] if timestamps else 1.0,
            frame_analyses=frame_analyses,
            detected_actions=actions,
            motion_pattern="repeated" if actions else "static",
            confidence=self._add_noise(self.base_confidence),
            summary="Mock temporal analysis",
        )

    async def detect_hands(self, frame: Any) -> List[HandDetection]:
        """Detect hands in a frame."""
        analysis = await self.analyze_frame(frame)
        return analysis.hands

    async def detect_objects(self, frame: Any) -> List[ObjectDetection]:
        """Detect objects in a frame."""
        analysis = await self.analyze_frame(frame)
        return analysis.objects

    def _build_mock_relations(self) -> List[HandObjectRelation]:
        """Build mock hand-object relations from ground truth."""
        relations = []
        if not self._current_task_data:
            return relations

        for stmt in self._current_task_data.get("statements", []):
            if not stmt.get("answer", False):
                continue

            text = stmt.get("text", "").lower()
            hand = HandSide.UNKNOWN
            if "left hand" in text:
                hand = HandSide.LEFT
            elif "right hand" in text:
                hand = HandSide.RIGHT

            # Determine relation type from action verb
            relation = RelationType.TOUCHING
            for verb, rel in [
                ("hold", RelationType.HOLDING),
                ("scrub", RelationType.SCRUBBING),
                ("place", RelationType.PLACED_IN),
                ("move", RelationType.MOVING),
                ("pick up", RelationType.PICKING_UP),
                ("put down", RelationType.PUTTING_DOWN),
                ("wipe", RelationType.WIPING),
                ("wash", RelationType.WASHING),
                ("touch", RelationType.TOUCHING),
                ("open", RelationType.OPENING),
                ("close", RelationType.CLOSING),
                ("cut", RelationType.CUTTING),
                ("pour", RelationType.POURING),
                ("stir", RelationType.STIRRING),
            ]:
                if text.startswith(verb):
                    relation = rel
                    break

            # Extract first noun-like object from text
            target = self._extract_primary_object(text)
            tool = self._extract_tool(text)

            relations.append(HandObjectRelation(
                hand=hand,
                relation=relation,
                target_object=target,
                tool=tool,
                confidence=self._add_noise(self.base_confidence),
                temporal_evidence=True,
            ))

        return relations

    def _extract_primary_object(self, text: str) -> str:
        """Extract the primary object from statement text."""
        import re
        known_objects = sorted([
            "cutting board", "steel wool", "scrub brush",
            "pan", "mug", "basin", "sponge", "plate",
            "bowl", "cup", "knife", "spoon", "pot", "lid",
            "towel", "faucet", "fork", "vegetable", "fruit",
            "meat", "bread", "egg", "food",
        ], key=len, reverse=True)

        # Remove trailing modifier phrases (on X, in Y, with Z)
        text_clean = re.sub(r"\b(?:on|in|into|onto|with|using)\s+[a-z\s]+", "", text)
        for obj in known_objects:
            pattern = r"\b" + re.escape(obj) + r"\b"
            if re.search(pattern, text_clean):
                return obj

        for obj in known_objects:
            pattern = r"\b" + re.escape(obj) + r"\b"
            if re.search(pattern, text):
                return obj

        return "object"


    def _extract_tool(self, text: str) -> Optional[str]:
        """Extract tool from 'with X' pattern."""
        tools = ["steel wool", "sponge", "scrub brush", "cloth", "towel", "knife"]
        with_pos = text.find("with")
        if with_pos == -1:
            return None
        after_with = text[with_pos + 5:]
        for tool in tools:
            if tool in after_with:
                return tool
        return None
