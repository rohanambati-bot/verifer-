#!/usr/bin/env python3
"""
VisionClick Agent - CLI Entry Point.

Commands:
  python run.py --demo          Start demo website
  python run.py --dry-run       Run agent in dry-run mode
  python run.py --benchmark     Run benchmark
  python run.py --dashboard     Start dashboard
  python run.py --auto-submit   Run with auto-submit (LOCAL_TEST_URL only)
"""
import os
import sys
import asyncio
import argparse

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def parse_args():
    parser = argparse.ArgumentParser(
        description="VisionClick Agent - Autonomous vision annotation agent"
    )
    parser.add_argument("--demo", action="store_true",
                        help="Start demo annotation website")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run agent in dry-run mode (no actual submissions)")
    parser.add_argument("--benchmark", action="store_true",
                        help="Run benchmark against demo tasks")
    parser.add_argument("--dashboard", action="store_true",
                        help="Start monitoring dashboard")
    parser.add_argument("--auto-submit", action="store_true",
                        help="Enable auto-submit (LOCAL_TEST_URL only)")
    parser.add_argument("--port", type=int, default=None,
                        help="Port number for demo or dashboard server")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to config.yaml")
    parser.add_argument("--headless", action="store_true",
                        help="Run browser in headless mode")
    parser.add_argument("--max-tasks", type=int, default=None,
                        help="Max tasks to process")
    return parser.parse_args()


def run_demo(args=None):
    """Start the demo annotation website."""
    try:
        import uvicorn
        from demo.server.demo_app import create_demo_app

        tasks_dir = os.path.join(os.path.dirname(__file__), "demo", "tasks")
        videos_dir = os.path.join(os.path.dirname(__file__), "demo", "videos")
        app = create_demo_app(tasks_dir=tasks_dir, videos_dir=videos_dir)

        port = (args.port if args and args.port else None) or 3000
        print("\n" + "=" * 50)
        print("  VisionClick Demo Server")
        print(f"  http://127.0.0.1:{port}")
        print("=" * 50 + "\n")

        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
    except ImportError as e:
        print(f"Error: {e}")
        print("Install dependencies: pip install -r requirements.txt")
        sys.exit(1)


def run_dashboard(args=None):
    """Start the monitoring dashboard."""
    try:
        import uvicorn
        from app.config import load_config
        from app.dashboard.server import create_dashboard_app
        from app.database.database import Database

        config = load_config(args.config if args else None)
        port = (args.port if args and args.port else None) or config.dashboard.port or 8000
        host = config.dashboard.host or "127.0.0.1"

        db = Database(config.db_path)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(db.initialize())

        app = create_dashboard_app(db)

        print("\n" + "=" * 50)
        print("  VisionClick Dashboard")
        print(f"  http://{host}:{port}")
        print("=" * 50 + "\n")

        uvicorn.run(app, host=host, port=port, log_level="info")
    except ImportError as e:
        print(f"Error: {e}")
        print("Install dependencies: pip install -r requirements.txt")
        sys.exit(1)


def run_benchmark():
    """Run benchmark mode."""
    sys.path.insert(0, os.path.dirname(__file__))
    from benchmark.benchmark import main as benchmark_main
    asyncio.run(benchmark_main())


async def run_agent(args):
    """Run the agent."""
    from app.config import load_config
    from app.main import VisionClickAgent

    config = load_config(args.config)

    # Apply CLI overrides
    if args.dry_run:
        config.agent.dry_run = True
        config.agent.auto_submit = False
    if args.auto_submit:
        config.agent.dry_run = False
        config.agent.auto_submit = True
    if args.headless:
        config.browser.headless = True
    if args.max_tasks is not None:
        config.agent.max_tasks = args.max_tasks

    agent = VisionClickAgent(config)
    try:
        await agent.initialize()
        await agent.initialize_browser()
        await agent.run_continuous()
    finally:
        await agent.shutdown()


def main():
    args = parse_args()

    if args.demo:
        run_demo(args)
    elif args.dashboard:
        run_dashboard(args)
    elif args.benchmark:
        run_benchmark()
    elif args.dry_run or args.auto_submit:
        asyncio.run(run_agent(args))
    else:
        # Default: dry-run mode
        print("VisionClick Agent")
        print("Usage:")
        print("  python run.py --demo         Start demo website")
        print("  python run.py --dry-run      Run agent (dry-run)")
        print("  python run.py --benchmark    Run benchmark")
        print("  python run.py --dashboard    Start dashboard")
        print("  python run.py --auto-submit  Run with auto-submit")


if __name__ == "__main__":
    main()
