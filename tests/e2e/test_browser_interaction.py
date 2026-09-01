"""
E2E Playwright Browser Test:
Starts local demo server, launches Chromium, observes task, clicks 👍/👎, verifies button state and submits.
"""
import os
import sys
import pytest
import asyncio
import threading
import time
import uvicorn

from app.config import AppConfig, BrowserConfig, AgentConfig, VisionConfig
from app.main import VisionClickAgent
from demo.server.demo_app import create_demo_app


@pytest.mark.asyncio
async def test_browser_e2e_playwright():
    port = 3127
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    tasks_dir = os.path.join(base_dir, "demo", "tasks")
    videos_dir = os.path.join(base_dir, "demo", "videos")
    app = create_demo_app(tasks_dir=tasks_dir, videos_dir=videos_dir)

    server_config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config=server_config)
    
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Give server a moment to start
    await asyncio.sleep(1.0)

    config = AppConfig(
        browser=BrowserConfig(headless=True, slow_mo=0),
        agent=AgentConfig(dry_run=False, auto_submit=True, max_tasks=1),
        vision=VisionConfig(provider="mock", sample_fps=4),
        demo={"url": f"http://127.0.0.1:{port}"},
        db_path="./data/test_e2e_browser.db"
    )

    agent = VisionClickAgent(config)
    try:
        await agent.initialize()
        await agent.initialize_browser()

        # Run task through actual browser against demo server
        success = await agent.process_single_task(task_url=f"http://127.0.0.1:{port}")
        assert success is True

        # Verify task was completed and recorded in database
        task_rec = await agent.repo.get_task("demo_001")
        assert task_rec is not None
        assert task_rec["status"] == "completed"

        decisions = await agent.repo.get_decisions("demo_001")
        assert len(decisions) == 3

    finally:
        await agent.shutdown()
        server.should_exit = True
        if os.path.exists("./data/test_e2e_browser.db"):
            os.remove("./data/test_e2e_browser.db")
