"""Deterministic synthetic data generator for PARCS End-to-End demonstration.

Generates clearly labeled synthetic Standby sessions and System Changes
covering:
  1. DEMO-MACHINE-READY:
     - 14 baseline sessions (readiness = 'ready').
     - 4 evaluation sessions demonstrating sustained performance regression.
     - System changes (driver update, Windows update, event log event)
       occurring around the regression.
  2. DEMO-MACHINE-SPARSE:
     - 4 sparse sessions (< 10 observations).
     - Explicitly tests the 'insufficient_history' baseline readiness and
       regression status without false positives.

IMPORTANT: All generated records are synthetic fixtures and are explicitly
labeled with `is_synthetic: True` and prefixed machine identities. They are NOT
genuine local system observations.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.analytics.correlation import CHANGE_SCHEMA_COLUMNS
from src.etl.transform import SLEEPSTUDY_COLUMNS
from src.storage.parquet import write_parquet
from src.storage.paths import ensure_storage_dirs

logger = logging.getLogger(__name__)


def generate_demo_sessions() -> pd.DataFrame:
    """Generate deterministic synthetic SleepStudy sessions."""
    rows: list[dict[str, Any]] = []

    # 1. DEMO-MACHINE-READY: 14 baseline sessions (August 2026)
    # Median DRIPS ~ 95%, Battery Drain Rate ~ 2400 mW, Drain Percent ~ 2.0%
    for i in range(14):
        day = 10 + i
        fl = float((i % 3) - 1)  # -1.0, 0.0, 1.0
        start_ts = f"2026-08-{day:02d}T10:00:00Z"
        end_ts = f"2026-08-{day:02d}T10:30:00Z"
        rows.append({
            "machine_id": "DEMO-MACHINE-READY",
            "collected_at": f"2026-08-{day:02d}T11:00:00Z",
            "start_time": start_ts,
            "end_time": end_ts,
            "duration_seconds": 1800.0,
            "drips_percent": 95.0 + fl,
            "battery_drain_percent": 2.0,
            "battery_drain_rate_mw": 2400.0 + (fl * 40.0),
            "is_synthetic": True,
        })

    # 1. DEMO-MACHINE-READY: 4 evaluation sessions (September 1, 2026)
    # Severe drop in DRIPS (60% << 95%) and surge in battery drain (5200 mW >> 2400 mW)
    eval_sessions = [
        ("2026-09-01T10:00:00Z", "2026-09-01T10:30:00Z", 60.0, 5200.0, 4.5),
        ("2026-09-01T10:45:00Z", "2026-09-01T11:15:00Z", 58.0, 5350.0, 4.8),
        ("2026-09-01T11:30:00Z", "2026-09-01T12:00:00Z", 55.0, 5500.0, 5.0),
        ("2026-09-01T12:15:00Z", "2026-09-01T12:45:00Z", 57.0, 5400.0, 4.9),
    ]
    for start_ts, end_ts, drips, drain_mw, drain_pct in eval_sessions:
        rows.append({
            "machine_id": "DEMO-MACHINE-READY",
            "collected_at": "2026-09-01T13:00:00Z",
            "start_time": start_ts,
            "end_time": end_ts,
            "duration_seconds": 1800.0,
            "drips_percent": drips,
            "battery_drain_percent": drain_pct,
            "battery_drain_rate_mw": drain_mw,
            "is_synthetic": True,
        })

    # 2. DEMO-MACHINE-SPARSE: 4 sessions only (< 10 required baseline observations)
    for i in range(4):
        day = 1 + i
        rows.append({
            "machine_id": "DEMO-MACHINE-SPARSE",
            "collected_at": f"2026-09-{day:02d}T15:00:00Z",
            "start_time": f"2026-09-{day:02d}T14:00:00Z",
            "end_time": f"2026-09-{day:02d}T14:30:00Z",
            "duration_seconds": 1800.0,
            "drips_percent": 88.0,
            "battery_drain_percent": 2.5,
            "battery_drain_rate_mw": 2900.0,
            "is_synthetic": True,
        })

    df = pd.DataFrame(rows)
    # Ensure all SLEEPSTUDY_COLUMNS are present
    for col in SLEEPSTUDY_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df


def generate_demo_changes() -> pd.DataFrame:
    """Generate deterministic synthetic System Changes."""
    rows: list[dict[str, Any]] = [
        # Driver update 1.5 hours before regression on DEMO-MACHINE-READY
        {
            "machine_id": "DEMO-MACHINE-READY",
            "timestamp": "2026-09-01T08:30:00Z",
            "change_type": "driver",
            "change_id": "PCI\\VEN_8086&DEV_06F0",
            "description": "Intel(R) Wi-Fi 6 AX201 160MHz v22.130.0.5 (Intel)",
            "is_synthetic": True,
        },
        # Kernel power event at regression onset on DEMO-MACHINE-READY
        {
            "machine_id": "DEMO-MACHINE-READY",
            "timestamp": "2026-09-01T10:00:00Z",
            "change_type": "event_log",
            "change_id": "Microsoft-Windows-Kernel-Power:506",
            "description": "[Information] The system is entering connected standby",
            "is_synthetic": True,
        },
        # Windows Update after regression on DEMO-MACHINE-READY
        {
            "machine_id": "DEMO-MACHINE-READY",
            "timestamp": "2026-09-01T13:00:00Z",
            "change_type": "windows_update",
            "change_id": "KB5034204",
            "description": "2026-08 Cumulative Update for Windows 11 Version 22H2 (KB5034204)",
            "is_synthetic": True,
        },
        # System change on DEMO-MACHINE-SPARSE
        {
            "machine_id": "DEMO-MACHINE-SPARSE",
            "timestamp": "2026-09-01T12:00:00Z",
            "change_type": "driver",
            "change_id": "PCI\\VEN_10DE&DEV_1F95",
            "description": "NVIDIA Graphics Driver v535.98",
            "is_synthetic": True,
        },
    ]

    df = pd.DataFrame(rows)
    for col in CHANGE_SCHEMA_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df


def seed_demo_datasets() -> dict[str, Any]:
    """Persist synthetic demonstration datasets into Parquet storage.

    Returns:
        Summary dictionary of seeded records.
    """
    ensure_storage_dirs()

    sessions_df = generate_demo_sessions()
    changes_df = generate_demo_changes()

    sessions_path = write_parquet(sessions_df, "sleepstudy")
    changes_path = write_parquet(changes_df, "changes")

    logger.info("Seeded demo datasets: %s and %s", sessions_path, changes_path)

    return {
        "success": True,
        "is_synthetic": True,
        "session_records": len(sessions_df),
        "change_records": len(changes_df),
        "machines": sorted(sessions_df["machine_id"].unique().tolist()),
        "output_files": [str(sessions_path), str(changes_path)],
    }
