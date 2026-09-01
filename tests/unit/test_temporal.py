"""
Unit tests for Temporal reasoning and video sampling components.
"""
import pytest
from app.video.extractor import VideoMetadata
from app.video.sampler import FrameSampler, SampledFrame
from app.video.scene_detector import SceneDetector


def test_frame_sampler_indices():
    sampler = FrameSampler(sample_fps=4, adaptive=False)
    metadata = VideoMetadata(
        fps=30.0,
        duration=5.0,
        frame_count=150,
        width=640,
        height=480
    )
    
    samples = sampler.compute_sample_indices(metadata)
    assert len(samples) > 0
    assert samples[0].frame_number == 0
    assert samples[-1].frame_number == 149
    # Expect approximately 4 * 5 = 20-22 frames
    assert 18 <= len(samples) <= 25


def test_scene_detector_motion_segmentation():
    detector = SceneDetector(action_threshold=0.1, min_segment_frames=2)
    motion_scores = [0.02, 0.03, 0.5, 0.6, 0.7, 0.01, 0.02]
    frame_numbers = list(range(len(motion_scores)))
    timestamps = [i * 0.25 for i in range(len(motion_scores))]

    segments = detector.segment_by_motion(motion_scores, frame_numbers, timestamps)
    assert len(segments) >= 1
    action_segments = detector.get_action_segments(segments)
    # The middle region should be detected as action
    for seg in action_segments:
        assert seg.is_action is True
        assert seg.avg_motion >= 0.1
