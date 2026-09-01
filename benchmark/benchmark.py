#!/usr/bin/env python3
"""
VisionClick Agent - Benchmark Runner.

Runs the agent pipeline against all demo tasks, compares with ground truth,
and outputs accuracy/timing metrics.

Usage:
  python benchmark/benchmark.py
  python run.py --benchmark
"""
import os
import sys
import json
import time
import asyncio

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import load_config
from app.utils.logging import setup_logging, get_logger
from app.vision.base import create_provider
from app.vision.mock import MockVisionProvider
from app.reasoning.statement_parser import StatementParser
from app.reasoning.confidence import ConfidenceConfig
from app.decision.classifier import DecisionClassifier
from app.video.temporal import TemporalProcessor
from benchmark.metrics import compute_metrics, format_benchmark_report


async def run_benchmark_task(
    task: dict,
    vision: MockVisionProvider,
    parser: StatementParser,
    classifier: DecisionClassifier,
    temporal: TemporalProcessor,
    video_path: str,
) -> dict:
    """Run the agent pipeline on a single task and return results."""
    task_id = task["task_id"]
    vision.set_current_task(task_id)
    classifier.reset()

    # Process video
    temporal_analysis = await temporal.process_video(video_path, task_id)

    predictions = []
    ground_truths = []

    for stmt in task["statements"]:
        parsed = parser.parse(stmt["text"])

        decision = classifier.classify(
            statement_id=stmt["id"],
            statement_text=stmt["text"],
            parsed=parsed,
            temporal=temporal_analysis,
            task_id=task_id,
        )

        predictions.append(decision.answer)
        ground_truths.append(stmt["answer"])

    return {
        "task_id": task_id,
        "predictions": predictions,
        "ground_truths": ground_truths,
        "frames_analyzed": len(temporal_analysis.frame_analyses),
    }


async def main():
    """Run the full benchmark."""
    setup_logging()
    logger = get_logger()

    # Load ground truth
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    gt_path = os.path.join(base_dir, "demo", "ground_truth", "ground_truth.json")

    if not os.path.exists(gt_path):
        logger.error(f"Ground truth not found: {gt_path}")
        sys.exit(1)

    with open(gt_path) as f:
        gt_data = json.load(f)

    tasks = gt_data.get("tasks", gt_data if isinstance(gt_data, list) else [])

    logger.info(f"Benchmark: {len(tasks)} tasks loaded")

    # Initialize components
    config = load_config()
    vision = MockVisionProvider(ground_truth_path=gt_path, noise_level=0.03)

    parser = StatementParser()
    conf_config = ConfidenceConfig(
        high_confidence=config.vision.high_confidence,
        review_threshold=config.vision.review_threshold,
    )
    classifier = DecisionClassifier(confidence_config=conf_config)
    temporal = TemporalProcessor(
        vision_provider=vision,
        sample_fps=config.vision.sample_fps,
    )

    # Generate a placeholder video for benchmarking
    import tempfile
    video_path = os.path.join(tempfile.gettempdir(), "benchmark_video.mp4")
    temporal.extractor._create_placeholder_video(video_path)

    # Run benchmark
    all_predictions = []
    all_truths = []
    task_times = []
    total_frames = 0

    print("\nRunning benchmark...")
    print("-" * 40)

    for task in tasks:
        task_start = time.monotonic()

        result = await run_benchmark_task(
            task, vision, parser, classifier, temporal, video_path
        )

        task_ms = (time.monotonic() - task_start) * 1000
        task_times.append(task_ms)

        all_predictions.extend(result["predictions"])
        all_truths.extend(result["ground_truths"])
        total_frames += result["frames_analyzed"]

        # Print per-task results
        correct = sum(1 for p, t in zip(result["predictions"], result["ground_truths"]) if p == t)
        total = len(result["predictions"])
        print(f"  {result['task_id']}: {correct}/{total} correct ({task_ms:.0f}ms)")

    print("-" * 40)

    # Compute and display metrics
    metrics = compute_metrics(all_predictions, all_truths, task_times)
    report = format_benchmark_report(metrics, len(tasks), total_frames)
    print(report)

    return metrics


if __name__ == "__main__":
    asyncio.run(main())
