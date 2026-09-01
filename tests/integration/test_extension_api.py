"""
Integration tests for Chrome Extension backend API endpoints.
"""
import pytest
from httpx import AsyncClient, ASGITransport

from app.dashboard.server import create_dashboard_app


@pytest.fixture
async def dashboard_app(test_db):
    return create_dashboard_app(test_db)


@pytest.mark.asyncio
async def test_extension_analyze_api(dashboard_app):
    transport = ASGITransport(app=dashboard_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test health
        resp = await client.get("/api/status")
        assert resp.status_code == 200

        # Test analyze endpoint
        payload = {
            "task_id": "demo_001",
            "video_url": "",
            "statements": [
                {"id": 1, "text": "hold pan with left hand"},
                {"id": 2, "text": "scrub pan with steel wool in right hand"},
                {"id": 3, "text": "place mug in basin with right hand"}
            ]
        }

        resp = await client.post("/api/extension/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["task_id"] == "demo_001"
        assert len(data["decisions"]) == 3

        # Check answers
        assert data["decisions"][0]["answer"] is True
        assert data["decisions"][0]["action_label"] == "👍"
        assert data["decisions"][1]["answer"] is True
        assert data["decisions"][2]["answer"] is False
        assert data["decisions"][2]["action_label"] == "👎"
