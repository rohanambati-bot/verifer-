"""
VisionClick Agent - Benchmark Metrics Calculator.

Computes accuracy, precision, recall, F1, timing stats.
"""
from typing import List, Dict, Tuple
import statistics


def compute_metrics(
    predictions: List[bool],
    ground_truth: List[bool],
    task_times_ms: List[float],
) -> Dict[str, float]:
    """Compute all benchmark metrics."""
    assert len(predictions) == len(ground_truth), "Prediction/truth length mismatch"

    tp = fp = tn = fn = 0
    for pred, truth in zip(predictions, ground_truth):
        if pred and truth:
            tp += 1
        elif pred and not truth:
            fp += 1
        elif not pred and not truth:
            tn += 1
        else:
            fn += 1

    total = len(predictions)
    accuracy = (tp + tn) / total if total > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = (2 * precision * recall / (precision + recall)
           if (precision + recall) > 0 else 0)

    # Timing
    avg_time = statistics.mean(task_times_ms) if task_times_ms else 0
    median_time = statistics.median(task_times_ms) if task_times_ms else 0

    sorted_times = sorted(task_times_ms)
    p95_idx = int(len(sorted_times) * 0.95) if sorted_times else 0
    p95_time = sorted_times[min(p95_idx, len(sorted_times) - 1)] if sorted_times else 0

    tasks_per_hour = 0
    if avg_time > 0:
        tasks_per_hour = 3600000 / avg_time  # ms to tasks/hour

    return {
        "total_statements": total,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "avg_task_ms": avg_time,
        "median_task_ms": median_time,
        "p95_task_ms": p95_time,
        "tasks_per_hour": tasks_per_hour,
    }


def format_benchmark_report(
    metrics: Dict[str, float],
    total_tasks: int,
    total_frames: int,
) -> str:
    """Format a human-readable benchmark report."""
    lines = [
        "",
        "=" * 40,
        "  VISIONCLICK BENCHMARK",
        "=" * 40,
        "",
        f"  Tasks:             {total_tasks}",
        f"  Statements:        {metrics['total_statements']}",
        f"  Accuracy:          {metrics['accuracy'] * 100:.1f}%",
        f"  Precision:         {metrics['precision'] * 100:.1f}%",
        f"  Recall:            {metrics['recall'] * 100:.1f}%",
        f"  F1:                {metrics['f1'] * 100:.1f}%",
        "",
        f"  True Positives:    {metrics['true_positives']}",
        f"  False Positives:   {metrics['false_positives']}",
        f"  True Negatives:    {metrics['true_negatives']}",
        f"  False Negatives:   {metrics['false_negatives']}",
        "",
        f"  Average task:      {metrics['avg_task_ms'] / 1000:.1f} sec",
        f"  Median task:       {metrics['median_task_ms'] / 1000:.1f} sec",
        f"  P95 task:          {metrics['p95_task_ms'] / 1000:.1f} sec",
        "",
        f"  Frames analyzed:   {total_frames:,}",
        f"  Tasks/hour:        {metrics['tasks_per_hour']:.0f}",
        "",
        "=" * 40,
        "",
    ]
    return "\n".join(lines)
