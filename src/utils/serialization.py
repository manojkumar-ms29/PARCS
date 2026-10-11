"""Data serialization utilities for PARCS API and Dashboard.

Converts pandas DataFrames, numpy scalars, and timestamps into
JSON-safe, API-compatible Python data structures.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


def serialize_df_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert DataFrame rows to JSON-safe dictionaries.

    Ensures:
      - pd.NaT and np.nan are serialized to None.
      - Timestamps and datetimes are serialized to ISO 8601 strings.
      - numpy scalar types (np.bool_, np.integer, np.floating) are cast to Python primitives.
      - Infinite values are serialized to None.

    Args:
        df: Input pandas DataFrame.

    Returns:
        List of dictionaries with JSON-compatible values.
    """
    if df is None or df.empty:
        return []

    records: list[dict[str, Any]] = []
    for row in df.to_dict(orient="records"):
        clean_row: dict[str, Any] = {}
        for key, val in row.items():
            clean_row[key] = serialize_value(val)
        records.append(clean_row)
    return records


def serialize_value(val: Any) -> Any:
    """Recursively convert a single value to a JSON-safe Python primitive."""
    if val is None:
        return None

    # Handle pandas NaT and NaN
    if pd.isna(val):
        return None

    if isinstance(val, (pd.Timestamp, datetime)):
        return val.isoformat()

    if isinstance(val, (np.bool_, bool)):
        return bool(val)

    if isinstance(val, (np.integer, int)):
        return int(val)

    if isinstance(val, (np.floating, float)):
        f_val = float(val)
        if np.isnan(f_val) or np.isinf(f_val):
            return None
        return f_val

    if isinstance(val, dict):
        return {k: serialize_value(v) for k, v in val.items()}

    if isinstance(val, (list, tuple, set)):
        return [serialize_value(item) for item in val]

    return val
