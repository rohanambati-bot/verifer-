"""
Integration tests for Demo Website API endpoints.
"""
import os
import pytest
from httpx import AsyncClient, ASGITransport

from demo.server.demo_app import create_demo_app


@pytest.fixture
def demo_app():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    tasks_dir = os.path.join(base_dir, "demo", "tasks")
    videos_dir = os.path.join(base_dir, "demo", "videos")
    return create_demo_app(tasks_dir=tasks_dir, videos_dir=videos_dir)


@pytest.mark.asyncio
async def test_demo_app_routes(demo_app):
    transport = ASGITransport(app=demo_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Index page
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "Video Annotation Task" in resp.text

        # Task list
        resp = await client.get("/api/tasks")
        assert resp.status_code == 200
        tasks = resp.json()
        assert len(tasks) >= 1
        assert tasks[0]["task_id"] == "demo_001"

        # Specific task
        resp = await client.get("/api/tasks/demo_001")
        assert resp.status_code == 200
        task = resp.json()
        assert task["task_id"] == "demo_001"
        assert len(task["statements"]) == 3

        # Submit task
        resp = await client.post("/api/submit", json={
            "task_id": "demo_001",
            "answers": {1: True, 2: True, 3: False}
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["task_id"] == "demo_001"

        # Results endpoint
        resp = await client.get("/api/results")
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) >= 1
        assert results[0]["task_id"] == "demo_001"
