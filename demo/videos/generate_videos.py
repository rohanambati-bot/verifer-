"""
Generate synthetic test videos using OpenCV.
Creates simple animations with colored shapes representing hands and objects.
"""
import os
import sys

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


def generate_video(filepath: str, task_id: str, duration: float = 5.0, fps: int = 30):
    """Generate a synthetic test video."""
    if not HAS_CV2:
        # Create minimal placeholder
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(b"\x00" * 2048)
        print(f"  Created placeholder (no OpenCV): {filepath}")
        return

    width, height = 640, 480
    total_frames = int(duration * fps)

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(filepath, fourcc, float(fps), (width, height))

    # Colors
    bg_color = (30, 30, 40)
    hand_left = (100, 180, 255)   # Blue-ish for left hand
    hand_right = (255, 160, 100)  # Orange-ish for right hand
    obj_color = (120, 220, 120)   # Green for objects
    tool_color = (220, 220, 100)  # Yellow for tools

    for i in range(total_frames):
        frame = np.full((height, width, 3), bg_color, dtype=np.uint8)
        t = i / total_frames  # Normalized time 0-1

        # Simulate hand movements
        # Left hand - oscillates on left side
        lh_x = int(150 + 30 * np.sin(t * 4 * np.pi))
        lh_y = int(250 + 20 * np.cos(t * 2 * np.pi))
        cv2.ellipse(frame, (lh_x, lh_y), (40, 55), 0, 0, 360, hand_left, -1)
        cv2.putText(frame, "L", (lh_x - 8, lh_y + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)

        # Right hand - moves across for action
        rh_x = int(400 + 50 * np.sin(t * 6 * np.pi))
        rh_y = int(250 + 30 * np.cos(t * 3 * np.pi))
        cv2.ellipse(frame, (rh_x, rh_y), (40, 55), 0, 0, 360, hand_right, -1)
        cv2.putText(frame, "R", (rh_x - 8, rh_y + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)

        # Object (pan/plate shape)
        obj_x, obj_y = 300, 320
        cv2.ellipse(frame, (obj_x, obj_y), (80, 30), 0, 0, 360, obj_color, -1)
        cv2.rectangle(frame, (obj_x - 80, obj_y - 5), (obj_x + 80, obj_y + 5),
                      obj_color, -1)

        # Tool (small rectangle near right hand)
        tool_x = rh_x + 30
        tool_y = rh_y + 20
        cv2.rectangle(frame, (tool_x - 15, tool_y - 8),
                      (tool_x + 15, tool_y + 8), tool_color, -1)

        # Frame info
        cv2.putText(frame, f"Task: {task_id}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        cv2.putText(frame, f"Frame: {i}/{total_frames}", (10, height - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)

        writer.write(frame)

    writer.release()
    print(f"  Generated video: {filepath} ({total_frames} frames, {duration}s)")


def main():
    """Generate all demo videos."""
    videos_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "videos")
    os.makedirs(videos_dir, exist_ok=True)

    tasks = ["demo_001", "demo_002", "demo_003", "demo_004", "demo_005"]

    print("Generating demo videos...")
    for task_id in tasks:
        filepath = os.path.join(videos_dir, f"{task_id}.mp4")
        generate_video(filepath, task_id)

    print(f"\nGenerated {len(tasks)} videos in {videos_dir}")


if __name__ == "__main__":
    main()
