"""Feature engineering for PARCS SleepStudy sessions.

Validates normalized SleepStudy session DataFrames, normalizes timestamps,
and prepares feature sets for statistical baseline modeling and anomaly detection.
"""

from __future__ import annotations

import logging
from typing import Sequence

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Expected input fields from the ETL SleepStudy data contract
REQUIRED_SESSION_COLUMNS: Sequence[str] = (
    "machine_id",
    "start_time",
    "end_time",
    "duration_seconds",
    "drips_percent",
    "battery_drain_percent",
    "battery_drain_rate_mw",
)

# Standard feature output columns
SLEEPSTUDY_FEATURE_COLUMNS: Sequence[str] = (
    "machine_id",
    "start_time",
    "end_time",
    "duration_seconds",
    "duration_hours",
    "drips_percent",
    "battery_drain_percent",
    "battery_drain_rate_mw",
)


def build_sleepstudy_features(
    sessions: pd.DataFrame,
    derive_duration_from_timestamps: bool = False,
) -> pd.DataFrame:
    """Build feature dataset from normalized SleepStudy session records.

    Validates schema requirements, safely normalizes timestamps to UTC,
    preserves null metric values, and derives session duration in hours.

    Args:
        sessions: Input DataFrame adhering to the normalized SleepStudy contract.
        derive_duration_from_timestamps: If True, computes duration from start
            and end timestamps when duration_seconds is missing. Defaults to False.

    Returns:
        New pandas DataFrame containing engineered features without mutating input.

    Raises:
        ValueError: If any required column is missing from sessions.
    """
    if not isinstance(sessions, pd.DataFrame):
        raise TypeError(f"Expected pandas DataFrame, got {type(sessions).__name__}")

    # 1. Validate required columns
    missing_cols = [col for col in REQUIRED_SESSION_COLUMNS if col not in sessions.columns]
    if missing_cols:
        raise ValueError(
            f"Input DataFrame is missing required SleepStudy columns: {missing_cols}"
        )

    # 2. Handle empty input DataFrame cleanly
    if sessions.empty:
        empty_cols = list(SLEEPSTUDY_FEATURE_COLUMNS)
        if "collected_at" in sessions.columns:
            empty_cols.append("collected_at")
        empty_df = pd.DataFrame(columns=empty_cols)
        # Assign explicit dtypes
        empty_df["machine_id"] = empty_df["machine_id"].astype(str)
        empty_df["start_time"] = pd.to_datetime(empty_df["start_time"], utc=True)
        empty_df["end_time"] = pd.to_datetime(empty_df["end_time"], utc=True)
        empty_df["duration_seconds"] = empty_df["duration_seconds"].astype(float)
        empty_df["duration_hours"] = empty_df["duration_hours"].astype(float)
        empty_df["drips_percent"] = empty_df["drips_percent"].astype(float)
        empty_df["battery_drain_percent"] = empty_df["battery_drain_percent"].astype(float)
        empty_df["battery_drain_rate_mw"] = empty_df["battery_drain_rate_mw"].astype(float)
        return empty_df

    # 3. Work on a shallow/deep copy to guarantee caller immutability
    df = sessions.copy()

    # Preserve provenance column if present
    has_collected_at = "collected_at" in df.columns

    # 4. Safe timestamp conversion
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True, errors="coerce", format="mixed")
    df["end_time"] = pd.to_datetime(df["end_time"], utc=True, errors="coerce", format="mixed")
    if has_collected_at:
        df["collected_at"] = pd.to_datetime(df["collected_at"], utc=True, errors="coerce", format="mixed")

    # 5. Machine ID normalization
    df["machine_id"] = df["machine_id"].astype(str).str.strip()

    # 6. Duration handling
    df["duration_seconds"] = pd.to_numeric(df["duration_seconds"], errors="coerce")

    if derive_duration_from_timestamps:
        mask_missing_dur = df["duration_seconds"].isna() | (df["duration_seconds"] < 0)
        valid_ts = df["start_time"].notna() & df["end_time"].notna() & (df["end_time"] >= df["start_time"])
        derive_mask = mask_missing_dur & valid_ts
        if derive_mask.any():
            derived_sec = (df.loc[derive_mask, "end_time"] - df.loc[derive_mask, "start_time"]).dt.total_seconds()
            df.loc[derive_mask, "duration_seconds"] = derived_sec

    # Invalidate negative duration
    df.loc[df["duration_seconds"] < 0, "duration_seconds"] = np.nan

    # Derived feature: duration in hours
    df["duration_hours"] = df["duration_seconds"] / 3600.0

    # 7. Measurement numeric conversion and range validation
    # Coerce non-numerics to NaN; out-of-range values become NaN to exclude from baselines
    df["drips_percent"] = pd.to_numeric(df["drips_percent"], errors="coerce")
    df.loc[(df["drips_percent"] < 0.0) | (df["drips_percent"] > 100.0), "drips_percent"] = np.nan

    df["battery_drain_percent"] = pd.to_numeric(df["battery_drain_percent"], errors="coerce")
    df.loc[
        (df["battery_drain_percent"] < 0.0) | (df["battery_drain_percent"] > 100.0),
        "battery_drain_percent",
    ] = np.nan

    df["battery_drain_rate_mw"] = pd.to_numeric(df["battery_drain_rate_mw"], errors="coerce")
    df.loc[df["battery_drain_rate_mw"] < 0.0, "battery_drain_rate_mw"] = np.nan

    # 8. Assemble output columns preserving original index
    target_columns = list(SLEEPSTUDY_FEATURE_COLUMNS)
    if has_collected_at:
        target_columns.append("collected_at")

    return df[target_columns].copy()
