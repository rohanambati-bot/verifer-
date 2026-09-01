"""
VisionClick Agent - Demo Annotation Website.

Local test website at http://127.0.0.1:3000 that imitates a video annotation UI.
Serves tasks with video, statements, 👍/👎 buttons, and submit.
"""
import os
import json
from typing import Dict, List, Any

try:
    from fastapi import FastAPI, Request
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse, JSONResponse
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


def load_tasks(tasks_dir: str) -> List[Dict]:
    """Load task definitions from JSON files."""
    tasks = []
    tasks_file = os.path.join(tasks_dir, "demo_tasks.json")
    if os.path.exists(tasks_file):
        with open(tasks_file) as f:
            data = json.load(f)
            if isinstance(data, list):
                tasks = data
            elif isinstance(data, dict) and "tasks" in data:
                tasks = data["tasks"]
    return tasks


def create_demo_app(
    tasks_dir: str = None,
    videos_dir: str = None,
) -> Any:
    """Create the demo annotation website."""
    if not HAS_FASTAPI:
        raise RuntimeError("FastAPI not installed")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if tasks_dir is None:
        tasks_dir = os.path.join(base_dir, "tasks")
    if videos_dir is None:
        videos_dir = os.path.join(base_dir, "videos")

    app = FastAPI(title="VisionClick Demo - Annotation Tasks")

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    if os.path.exists(videos_dir):
        app.mount("/videos", StaticFiles(directory=videos_dir), name="videos")

    tasks = load_tasks(tasks_dir)
    submissions: List[Dict] = []

    @app.get("/", response_class=HTMLResponse)
    async def index():
        """Serve the annotation page for the first unsubmitted task."""
        submitted_ids = {s["task_id"] for s in submissions}
        current = None
        for task in tasks:
            if task["task_id"] not in submitted_ids:
                current = task
                break

        if not current and tasks:
            current = tasks[0]  # Loop back

        html_path = os.path.join(static_dir, "index.html")
        if os.path.exists(html_path):
            with open(html_path) as f:
                template = f.read()
            # Inject task data
            template = template.replace(
                "/*TASK_DATA*/",
                json.dumps(current) if current else "{}"
            )
            return template
        return "<h1>Demo task page</h1>"


    @app.get("/api/tasks")
    async def list_tasks():
        return tasks

    @app.get("/api/tasks/{task_id}")
    async def get_task(task_id: str):
        for task in tasks:
            if task["task_id"] == task_id:
                # Return task without ground truth answers
                safe_task = {
                    "task_id": task["task_id"],
                    "video": task.get("video", ""),
                    "statements": [
                        {"id": s["id"], "text": s["text"]}
                        for s in task.get("statements", [])
                    ],
                }
                return safe_task
        return JSONResponse({"error": "Task not found"}, status_code=404)

    @app.post("/api/submit")
    async def submit_task(request: Request):
        data = await request.json()
        task_id = data.get("task_id", "")
        answers = data.get("answers", {})
        submissions.append({
            "task_id": task_id,
            "answers": answers,
        })
        # Find next task
        submitted_ids = {s["task_id"] for s in submissions}
        next_task = None
        for task in tasks:
            if task["task_id"] not in submitted_ids:
                next_task = task["task_id"]
                break
        return {
            "status": "ok",
            "task_id": task_id,
            "next_task": next_task,
        }

    @app.get("/api/results")
    async def get_results():
        return submissions

    return app
