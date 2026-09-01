"""
VisionClick Agent - Adaptive Frame Sampler.

Implements configurable frame sampling with deduplication.
Initial sampling at SAMPLE_FPS, increases around high-motion intervals.
"""
from typing import List, Tuple, Optional
from pydantic import BaseModel, Field

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

from app.video.extractor import VideoMetadata
from app.utils.logging import get_logger


class SampledFrame(BaseModel):
    """A sampled video frame with metadata."""
    frame_number: int
    timestamp: float
    motion_score: float = 0.0
    is_duplicate: bool = False


class FrameSampler:
    """
    Adaptive frame sampler with deduplication.

    Strategy:
    1. Initial uniform sampling at sample_fps
    2. Detect high-motion regions
    3. Increase sampling density around motion peaks
    4. Deduplicate near-identical frames
    """

    def __init__(
        self,
        sample_fps: int = 4,
        adaptive: bool = True,
        dedup_threshold: float = 0.95,
    ):
        self.sample_fps = sample_fps
        self.adaptive = adaptive
        self.dedup_threshold = dedup_threshold

    def compute_sample_indices(
        self, metadata: VideoMetadata
    ) -> List[SampledFrame]:
        """Compute which frames to sample from the video."""
        if metadata.fps <= 0 or metadata.frame_count <= 0:
            return []

        # Initial uniform sampling
        step = max(1, int(metadata.fps / self.sample_fps))
        indices = list(range(0, metadata.frame_count, step))

        # Ensure first and last frames are included
        if 0 not in indices:
            indices.insert(0, 0)
        if metadata.frame_count - 1 not in indices:
            indices.append(metadata.frame_count - 1)

        samples = []
        for idx in sorted(set(indices)):
            ts = idx / metadata.fps if metadata.fps > 0 else 0.0
            samples.append(SampledFrame(
                frame_number=idx,
                timestamp=ts,
            ))

        return samples

    def compute_motion_scores(
        self, frames: list
    ) -> List[float]:
        """Compute motion scores between consecutive frames."""
        if not HAS_CV2 or len(frames) < 2:
            return [0.5] * len(frames)

        scores = [0.0]  # First frame has no previous

        for i in range(1, len(frames)):
            if frames[i] is None or frames[i-1] is None:
                scores.append(0.0)
                continue

            # Convert to grayscale
            prev_gray = cv2.cvtColor(frames[i-1], cv2.COLOR_BGR2GRAY)
            curr_gray = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)

            # Compute absolute difference
            diff = cv2.absdiff(prev_gray, curr_gray)
            motion_score = float(np.mean(diff)) / 255.0

            scores.append(motion_score)

        return scores

    def adaptive_resample(
        self,
        metadata: VideoMetadata,
        motion_scores: List[float],
        initial_samples: List[SampledFrame],
    ) -> List[SampledFrame]:
        """Add more samples around high-motion regions."""
        if not self.adaptive or not motion_scores:
            return initial_samples

        # Find high-motion peaks (above mean + 1 std)
        if len(motion_scores) < 3:
            return initial_samples

        mean_score = sum(motion_scores) / len(motion_scores)
        variance = sum((s - mean_score) ** 2 for s in motion_scores) / len(motion_scores)
        std_score = variance ** 0.5
        threshold = mean_score + std_score

        extra_samples = []
        for i, (sample, score) in enumerate(zip(initial_samples, motion_scores)):
            if score > threshold and i > 0 and i < len(initial_samples) - 1:
                # Add frames between this and neighbors
                prev = initial_samples[i-1]
                mid_frame = (prev.frame_number + sample.frame_number) // 2
                mid_ts = (prev.timestamp + sample.timestamp) / 2
                extra_samples.append(SampledFrame(
                    frame_number=mid_frame,
                    timestamp=mid_ts,
                    motion_score=score,
                ))

        # Merge and sort
        all_samples = initial_samples + extra_samples
        seen = set()
        unique_samples = []
        for s in sorted(all_samples, key=lambda x: x.frame_number):
            if s.frame_number not in seen:
                seen.add(s.frame_number)
                unique_samples.append(s)

        return unique_samples

    def deduplicate_frames(
        self, frames: list, samples: List[SampledFrame]
    ) -> Tuple[list, List[SampledFrame]]:
        """Remove near-duplicate frames."""
        if not HAS_CV2 or len(frames) < 2:
            return frames, samples

        kept_frames = [frames[0]]
        kept_samples = [samples[0]]

        for i in range(1, len(frames)):
            if frames[i] is None:
                continue

            # Compare with previous kept frame using histogram correlation
            is_dup = False
            if kept_frames[-1] is not None:
                hist1 = cv2.calcHist([frames[i]], [0], None, [64], [0, 256])
                hist2 = cv2.calcHist([kept_frames[-1]], [0], None, [64], [0, 256])
                cv2.normalize(hist1, hist1)
                cv2.normalize(hist2, hist2)
                correlation = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)

                if correlation > self.dedup_threshold:
                    is_dup = True
                    if i < len(samples):
                        samples[i].is_duplicate = True

            if not is_dup:
                kept_frames.append(frames[i])
                if i < len(samples):
                    kept_samples.append(samples[i])

        return kept_frames, kept_samples
