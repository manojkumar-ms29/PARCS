"""Main entry point for PARCS application."""

from __future__ import annotations

import argparse
import subprocess
import sys

import uvicorn

from src.utils.demo_data import seed_demo_datasets


def main():
    parser = argparse.ArgumentParser(
        description="PARCS: Predictive Analytics & Real-Time Intelligence System for Modern Standby",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="api",
        choices=["api", "dashboard", "seed-demo", "info"],
        help="Command to execute: 'api' (default), 'dashboard', 'seed-demo', or 'info'.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host interface for API (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port for API (default: 8000)")

    args = parser.parse_args()

    print(f"Initializing PARCS application (command: {args.command})...")

    if args.command == "seed-demo":
        summary = seed_demo_datasets()
        print(f"Seeded demo datasets successfully: {summary}")
    elif args.command == "info":
        from src.api.service import AnalyticsService
        svc = AnalyticsService()
        print("Telemetry summary:", svc.get_telemetry_summary())
    elif args.command == "dashboard":
        cmd = [sys.executable, "-m", "streamlit", "run", "src/dashboard/app.py"]
        print(f"Starting Streamlit dashboard: {' '.join(cmd)}")
        subprocess.run(cmd, check=False)
    else:  # 'api'
        print(f"Starting FastAPI backend on http://{args.host}:{args.port}")
        uvicorn.run("src.api.app:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
