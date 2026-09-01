"""
VisionClick Agent - Temporal action reasoning.

Analyzes motion across frame sequences, detects repeated motions,
trajectory analysis, and temporal evidence windowing.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.video.extractor import VideoExtractor, VideoMetadata
from app.video.sampler import FrameSampler, SampledFrame
from app.video.scene_detector import SceneDetector, SceneSegment
from app.vision.base import VisionProvider, FrameAnalysis, TemporalAnalysis
from app.utils.logging import get_logger
from app.utils.timing import get_timer


class FrameRecord(BaseModel):
    """Stored frame analysis record."""
    timestamp: float
    frame_number: int
    frame_path: str = ""
    motion_score: float = 0.0
    objects: List[str] = Field(default_factory=list)
    hands: List[str] = Field(default_factory=list)


class TemporalProcessor:
    """
    Complete temporal video analysis pipeline.

    Pipeline:
    video → metadata → adaptive sampling → scene detection →
    relevant segment detection → hand/object analysis → temporal reasoning
    """

    def __init__(
        self,
        vision_provider: VisionProvider,
        sample_fps: int = 4,
        adaptive_sampling: bool = True,
    ):
        self.vision = vision_provider
        self.extractor = VideoExtractor()
        self.sampler = FrameSampler(sample_fps=sample_fps, adaptive=adaptive_sampling)
        self.scene_detector = SceneDetector()
        self.frame_records: List[FrameRecord] = []

    async def process_video(
        self, video_path: str, task_id: str = ""
    ) -> TemporalAnalysis:
        """
        Complete video processing pipeline.

        Returns TemporalAnalysis with all frame analyses and detected actions.
        """
        logger = get_logger()
        timer = get_timer()

        with timer.measure("video_analysis", task_id):
            # Step 1: Extract metadata
            logger.info(f"Extracting video metadata: {video_path}",
                        extra={"task_id": task_id, "stage": "video"})
            metadata = self.extractor.extract_metadata(video_path)
            logger.info(
                f"Video: {metadata.width}x{metadata.height}, "
                f"{metadata.fps:.1f}fps, {metadata.duration:.1f}s, "
                f"{metadata.frame_count} frames",
                extra={"task_id": task_id, "stage": "video"}
            )

            # Step 2: Compute sample indices
            samples = self.sampler.compute_sample_indices(metadata)
            logger.info(
                f"Sampling {len(samples)} frames at {self.sampler.sample_fps}fps",
                extra={"task_id": task_id, "stage": "sampling"}
            )

            # Step 3: Extract frames
            timestamps = [s.timestamp for s in samples]
            frames = self.extractor.extract_frames_at_timestamps(
                video_path, timestamps
            )

            # Filter out None frames
            valid_pairs = [
                (f, s, t) for f, s, t in zip(frames, samples, timestamps)
                if f is not None
            ]
            if not valid_pairs:
                logger.warning("No valid frames extracted",
                               extra={"task_id": task_id, "stage": "video"})
                return TemporalAnalysis()

            frames = [p[0] for p in valid_pairs]
            samples = [p[1] for p in valid_pairs]
            timestamps = [p[2] for p in valid_pairs]

            # Step 4: Compute motion scores
            motion_scores = self.sampler.compute_motion_scores(frames)
            for i, score in enumerate(motion_scores):
                if i < len(samples):
                    samples[i].motion_score = score

            # Step 5: Adaptive resampling if enabled
            if self.sampler.adaptive:
                enhanced_samples = self.sampler.adaptive_resample(
                    metadata, motion_scores, samples
                )
                if len(enhanced_samples) > len(samples):
                    # Extract additional frames
                    new_ts = [s.timestamp for s in enhanced_samples
                              if s.frame_number not in {s2.frame_number for s2 in samples}]
                    if new_ts:
                        new_frames = self.extractor.extract_frames_at_timestamps(
                            video_path, new_ts
                        )
                        frames.extend([f for f in new_frames if f is not None])
                        timestamps.extend(new_ts[:len([f for f in new_frames if f is not None])])
                    samples = enhanced_samples

            # Step 6: Deduplicate frames
            frames, samples = self.sampler.deduplicate_frames(frames, samples)
            logger.info(
                f"After dedup: {len(frames)} unique frames",
                extra={"task_id": task_id, "stage": "sampling"}
            )

            # Step 7: Vision analysis on sampled frames
            logger.info(
                f"Analyzing {len(frames)} frames with vision provider",
                extra={"task_id": task_id, "stage": "analysis"}
            )

            temporal = await self.vision.analyze_temporal_segment(
                frames, timestamps
            )

            # Step 8: Store frame records
            self.frame_records.clear()
            for i, fa in enumerate(temporal.frame_analyses):
                record = FrameRecord(
                    timestamp=fa.timestamp,
                    frame_number=fa.frame_number if fa.frame_number else i,
                    motion_score=fa.motion_score,
                    objects=[obj.label for obj in fa.objects],
                    hands=[h.side.value for h in fa.hands],
                )
                self.frame_records.append(record)

            logger.info(
                f"Analysis complete: {len(temporal.frame_analyses)} frames, "
                f"{len(temporal.detected_actions)} actions detected",
                extra={"task_id": task_id, "stage": "analysis"}
            )

            return temporal

    def get_frames_for_verification(self, video_path: str) -> tuple:
        """Get frames and timestamps for second-pass verification."""
        metadata = self.extractor.extract_metadata(video_path)
        # Sample more densely for verification
        dense_sampler = FrameSampler(
            sample_fps=self.sampler.sample_fps * 2,
            adaptive=True,
        )
        samples = dense_sampler.compute_sample_indices(metadata)
        timestamps = [s.timestamp for s in samples]
        frames = self.extractor.extract_frames_at_timestamps(
            video_path, timestamps
        )
        return frames, timestamps
