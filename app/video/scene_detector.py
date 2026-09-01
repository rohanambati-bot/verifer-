"""
VisionClick Agent - Scene/change detection.

Detects significant scene transitions, identifies action vs static segments.
"""
from typing import List, Tuple

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class SceneSegment:
    """A detected scene segment."""
    def __init__(self, start_frame: int, end_frame: int,
                 start_time: float, end_time: float,
                 avg_motion: float, is_action: bool):
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.start_time = start_time
        self.end_time = end_time
        self.avg_motion = avg_motion
        self.is_action = is_action


class SceneDetector:
    """Detect scene changes and segment videos into action/static regions."""

    def __init__(self, change_threshold: float = 0.3,
                 action_threshold: float = 0.05,
                 min_segment_frames: int = 5):
        self.change_threshold = change_threshold
        self.action_threshold = action_threshold
        self.min_segment_frames = min_segment_frames

    def detect_scene_changes(
        self, frames: list, timestamps: list
    ) -> List[int]:
        """Detect frame indices where scene changes occur."""
        if not HAS_CV2 or len(frames) < 2:
            return []

        changes = []
        for i in range(1, len(frames)):
            if frames[i] is None or frames[i-1] is None:
                continue

            prev_gray = cv2.cvtColor(frames[i-1], cv2.COLOR_BGR2GRAY)
            curr_gray = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
            diff = cv2.absdiff(prev_gray, curr_gray)
            score = float(np.mean(diff)) / 255.0

            if score > self.change_threshold:
                changes.append(i)

        return changes

    def segment_by_motion(
        self, motion_scores: List[float],
        frame_numbers: List[int],
        timestamps: List[float],
    ) -> List[SceneSegment]:
        """Segment video into action and static regions based on motion."""
        if not motion_scores:
            return []

        segments = []
        current_start = 0
        current_is_action = motion_scores[0] > self.action_threshold

        for i in range(1, len(motion_scores)):
            is_action = motion_scores[i] > self.action_threshold

            if is_action != current_is_action:
                # Segment boundary
                if i - current_start >= self.min_segment_frames:
                    segment_scores = motion_scores[current_start:i]
                    avg_motion = sum(segment_scores) / len(segment_scores)
                    segments.append(SceneSegment(
                        start_frame=frame_numbers[current_start] if current_start < len(frame_numbers) else 0,
                        end_frame=frame_numbers[i-1] if i-1 < len(frame_numbers) else 0,
                        start_time=timestamps[current_start] if current_start < len(timestamps) else 0,
                        end_time=timestamps[i-1] if i-1 < len(timestamps) else 0,
                        avg_motion=avg_motion,
                        is_action=current_is_action,
                    ))
                current_start = i
                current_is_action = is_action

        # Final segment
        if len(motion_scores) - current_start >= self.min_segment_frames:
            segment_scores = motion_scores[current_start:]
            avg_motion = sum(segment_scores) / len(segment_scores)
            segments.append(SceneSegment(
                start_frame=frame_numbers[current_start] if current_start < len(frame_numbers) else 0,
                end_frame=frame_numbers[-1] if frame_numbers else 0,
                start_time=timestamps[current_start] if current_start < len(timestamps) else 0,
                end_time=timestamps[-1] if timestamps else 0,
                avg_motion=avg_motion,
                is_action=current_is_action,
            ))

        return segments

    def get_action_segments(
        self, segments: List[SceneSegment]
    ) -> List[SceneSegment]:
        """Get only the action (non-static) segments."""
        return [s for s in segments if s.is_action]
