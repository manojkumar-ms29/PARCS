"""Deterministic, explainable change correlation for PARCS telemetry.

Associates detected performance regressions with relevant system changes
(driver installations, Windows updates, event log events) occurring within
a configurable temporal window around each regression.

Strict architectural principles:
  - Separate regression detection from change correlation.
  - Strict machine isolation: never correlate a regression on one machine with
    a change recorded on another.
  - Non-causal explainability: states observed temporal evidence without claiming causation.
  - Temporal ordering preservation: clearly distinguishes antecedent changes from subsequent changes.
  - Explicit representation of regressions with no matching changes.
  - Deterministic ordering of correlation records.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Sequence

import numpy as np
import pandas as pd

from src.collectors.base import CollectorResult

logger = logging.getLogger(__name__)

# Default temporal windows
DEFAULT_WINDOW_BEFORE: timedelta = timedelta(hours=24)
DEFAULT_WINDOW_AFTER: timedelta = timedelta(hours=2)

# Canonical change schema columns
CHANGE_SCHEMA_COLUMNS: Sequence[str] = (
    "machine_id",
    "timestamp",
    "change_type",
    "change_id",
    "description",
)

# Output correlation schema columns
CORRELATION_SCHEMA_COLUMNS: Sequence[str] = (
    "source_row_index",
    "machine_id",
    "metric",
    "start_time",
    "end_time",
    "regression_status",
    "is_correlated",
    "correlation_status",
    "change_id",
    "change_type",
    "change_timestamp",
    "change_description",
    "temporal_offset_seconds",
    "temporal_relation",
    "window_before_seconds",
    "window_after_seconds",
    "reason",
    "explanation",
)


def extract_changes_from_collector_result(
    result: CollectorResult,
    machine_id: str | None = None,
) -> list[dict[str, Any]]:
    """Extract normalized system-change records from a collector result.

    Adapts structured data from Driver, Update, and EventLog collectors into
    canonical change record dictionaries.

    Args:
        result: CollectorResult from a PARCS collector.
        machine_id: Optional machine identifier. If not provided, will look for
            'machine_id' in result metadata or use 'UNKNOWN'.

    Returns:
        List of dictionaries conforming to CHANGE_SCHEMA_COLUMNS.
    """
    if not isinstance(result, CollectorResult):
        raise TypeError(f"Expected CollectorResult, got {type(result).__name__}")

    effective_machine = machine_id or "UNKNOWN"
    records: list[dict[str, Any]] = []

    if not result.success or not result.data:
        return records

    raw_items = result.data if isinstance(result.data, list) else [result.data]

    collector_name = (result.collector or "").lower()

    for item in raw_items:
        if not isinstance(item, dict):
            continue

        item_machine = item.get("machine_id") or effective_machine

        if collector_name == "updates":
            records.append({
                "machine_id": item_machine,
                "timestamp": item.get("timestamp"),
                "change_type": "windows_update",
                "change_id": str(item.get("kb_id") or item.get("update_id") or "unknown_update"),
                "description": str(item.get("title") or ""),
            })
        elif collector_name == "drivers":
            friendly = item.get("friendly_name") or item.get("device_name") or "Unknown Device"
            version = item.get("version") or "unknown_version"
            provider = item.get("provider") or "unknown_provider"
            records.append({
                "machine_id": item_machine,
                "timestamp": item.get("date"),
                "change_type": "driver",
                "change_id": str(item.get("device_id") or item.get("device_name") or "unknown_driver"),
                "description": f"{friendly} v{version} ({provider})",
            })
        elif collector_name == "eventlog":
            provider = item.get("provider") or "UnknownProvider"
            event_id = item.get("event_id") or "0"
            level = item.get("level") or "Unknown"
            msg = item.get("message") or ""
            records.append({
                "machine_id": item_machine,
                "timestamp": item.get("timestamp"),
                "change_type": "event_log",
                "change_id": f"{provider}:{event_id}",
                "description": f"[{level}] {msg}".strip(),
            })
        else:
            # Generic collector fallback
            ts = item.get("timestamp") or item.get("collected_at") or result.collected_at
            cid = item.get("change_id") or item.get("id") or str(len(records))
            desc = item.get("description") or item.get("message") or str(item)
            records.append({
                "machine_id": item_machine,
                "timestamp": ts,
                "change_type": collector_name or "system_change",
                "change_id": str(cid),
                "description": str(desc),
            })

    return records


def normalize_changes(
    changes: pd.DataFrame | Sequence[CollectorResult] | Sequence[dict[str, Any]],
    machine_id: str | None = None,
) -> pd.DataFrame:
    """Normalize change records from multiple formats into canonical change DataFrame.

    Accepts:
      - A pandas DataFrame containing changes.
      - A sequence of CollectorResult objects.
      - A sequence of dictionaries.

    Args:
        changes: Input change data.
        machine_id: Optional default machine_id to assign if missing.

    Returns:
        DataFrame conforming to CHANGE_SCHEMA_COLUMNS.

    Raises:
        TypeError: If input is of unsupported type.
        ValueError: If required columns or fields are missing.
    """
    if isinstance(changes, pd.DataFrame):
        df = changes.copy()
        return _validate_and_normalize_changes_df(df, default_machine_id=machine_id)

    if isinstance(changes, (list, tuple)):
        all_records: list[dict[str, Any]] = []
        for item in changes:
            if isinstance(item, CollectorResult):
                all_records.extend(extract_changes_from_collector_result(item, machine_id=machine_id))
            elif isinstance(item, dict):
                rec = dict(item)
                if machine_id and not rec.get("machine_id"):
                    rec["machine_id"] = machine_id
                all_records.append(rec)
            else:
                raise TypeError(
                    f"Unsupported item in changes sequence: expected CollectorResult or dict, got {type(item).__name__}"
                )
        df = pd.DataFrame(all_records)
        return _validate_and_normalize_changes_df(df, default_machine_id=machine_id)

    raise TypeError(f"Expected DataFrame or Sequence of CollectorResult/dict, got {type(changes).__name__}")


def _validate_and_normalize_changes_df(
    df: pd.DataFrame,
    default_machine_id: str | None = None,
) -> pd.DataFrame:
    """Validate and align change DataFrame columns to CHANGE_SCHEMA_COLUMNS."""
    if df.empty:
        empty_df = pd.DataFrame(columns=list(CHANGE_SCHEMA_COLUMNS))
        empty_df["timestamp"] = pd.to_datetime(empty_df["timestamp"], utc=True)
        return empty_df

    # Machine ID check or assignment
    if "machine_id" not in df.columns:
        if default_machine_id:
            df["machine_id"] = default_machine_id
        else:
            raise ValueError("changes DataFrame is missing required column: 'machine_id'")

    # Timestamp column resolution
    ts_col = None
    for cand in ("timestamp", "change_timestamp", "date", "time"):
        if cand in df.columns:
            ts_col = cand
            break
    if ts_col is None:
        raise ValueError(
            "changes DataFrame is missing required timestamp column (expected 'timestamp' or 'change_timestamp')"
        )
    if ts_col != "timestamp":
        df["timestamp"] = df[ts_col]

    # Change type column resolution
    type_col = None
    for cand in ("change_type", "type", "collector"):
        if cand in df.columns:
            type_col = cand
            break
    if type_col is None:
        raise ValueError("changes DataFrame is missing required change type column (expected 'change_type' or 'type')")
    if type_col != "change_type":
        df["change_type"] = df[type_col]

    # Change ID resolution
    id_col = None
    for cand in ("change_id", "id", "identifier", "kb_id", "update_id", "device_id", "event_id"):
        if cand in df.columns:
            id_col = cand
            break
    if id_col is None:
        # Check if description exists before failing; if neither exists, raise
        desc_exists = any(c in df.columns for c in ("description", "change_description", "title", "message"))
        if not desc_exists:
            raise ValueError(
                "changes DataFrame is missing change identifier and description columns "
                "(expected 'change_id' and/or 'description')"
            )
        df["change_id"] = [f"change_{i}" for i in range(len(df))]
    elif id_col != "change_id":
        df["change_id"] = df[id_col]

    # Description resolution
    desc_col = None
    for cand in ("description", "change_description", "title", "message", "device_name", "friendly_name"):
        if cand in df.columns:
            desc_col = cand
            break
    if desc_col is None:
        df["description"] = df["change_id"].astype(str)
    elif desc_col != "description":
        df["description"] = df[desc_col]

    # Parse timestamps to UTC
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")

    # Select canonical columns
    res = df[list(CHANGE_SCHEMA_COLUMNS)].copy()
    res["machine_id"] = res["machine_id"].astype(str)
    res["change_type"] = res["change_type"].astype(str)
    res["change_id"] = res["change_id"].astype(str)
    res["description"] = res["description"].astype(str)
    return res


def correlate_changes(
    regressions: pd.DataFrame,
    changes: pd.DataFrame,
    window_before: timedelta = DEFAULT_WINDOW_BEFORE,
    window_after: timedelta = DEFAULT_WINDOW_AFTER,
    time_anchor: str = "start_time",
    only_regressions: bool = True,
) -> pd.DataFrame:
    """Correlate detected regressions with relevant system changes within a temporal window.

    Evaluates each regression against system changes occurring on the SAME machine
    within the interval [anchor - window_before, anchor + window_after].

    Deterministic Ordering Policy:
        Output records are sorted chronologically and deterministically by:
        1. `machine_id` ascending
        2. `start_time` ascending (valid timestamps first, NaT last)
        3. `metric` ascending
        4. `source_row_index` ascending
        5. `change_timestamp` ascending (valid timestamps first, NaT last)
        6. `change_type` ascending
        7. `change_id` ascending
        8. `_change_source_row_index` ascending (tie-breaker for duplicate timestamps)

    Machine Isolation:
        Regressions on machine M are only compared with changes on machine M.
        Changes on different machines are strictly ignored.

    Non-Causal Semantics:
        - Changes preceding a regression are reported with negative temporal offsets.
        - Changes following a regression are reported with positive temporal offsets
          and explicitly documented as subsequent events that cannot be antecedent causes.
        - Regressions with no qualifying changes produce an explicit no-match row.

    Boundary Semantics:
        The temporal window [anchor - window_before, anchor + window_after] is closed
        (inclusive of both endpoints). Changes occurring precisely at either boundary
        are matched.

    Args:
        regressions: DataFrame from detect_regressions or containing regression sessions.
            Must contain 'machine_id' and 'start_time'.
        changes: DataFrame of system changes, or raw collector output.
            Must contain 'machine_id', timestamp, change_type, and change_id/description.
        window_before: Maximum look-back timedelta before the regression anchor.
            Defaults to 24 hours. Must be >= 0.
        window_after: Maximum look-forward timedelta after the regression anchor.
            Defaults to 2 hours. Must be >= 0.
        time_anchor: Anchor point on the regression to measure window against.
            Options: 'start_time' (default), 'end_time', or 'interval'.
        only_regressions: If True, only evaluates rows where is_regression == True
            (or status == 'regression' if is_regression is absent). Defaults to True.

    Returns:
        pandas DataFrame conforming to CORRELATION_SCHEMA_COLUMNS detailing
        the correlation records for each qualifying regression.

    Raises:
        TypeError: If regressions or changes are not DataFrames, or windows are not timedeltas.
        ValueError: If required columns are missing, windows are negative, or time_anchor is invalid.
    """
    if not isinstance(regressions, pd.DataFrame):
        raise TypeError(f"Expected regressions as pandas DataFrame, got {type(regressions).__name__}")
    if not isinstance(changes, pd.DataFrame):
        raise TypeError(f"Expected changes as pandas DataFrame, got {type(changes).__name__}")

    if not isinstance(window_before, (timedelta, pd.Timedelta)):
        raise TypeError(f"Expected window_before as timedelta, got {type(window_before).__name__}")
    if not isinstance(window_after, (timedelta, pd.Timedelta)):
        raise TypeError(f"Expected window_after as timedelta, got {type(window_after).__name__}")

    if window_before < timedelta(0):
        raise ValueError(f"window_before must be non-negative, got {window_before}")
    if window_after < timedelta(0):
        raise ValueError(f"window_after must be non-negative, got {window_after}")

    if time_anchor not in ("start_time", "end_time", "interval"):
        raise ValueError(f"time_anchor must be 'start_time', 'end_time', or 'interval', got '{time_anchor}'")

    # Validate regressions DataFrame columns
    req_reg_cols = {"machine_id", "start_time"}
    missing_reg = req_reg_cols - set(regressions.columns)
    if missing_reg:
        raise ValueError(f"regressions DataFrame is missing required columns: {missing_reg}")

    # Validate and normalize changes DataFrame
    norm_changes = _validate_and_normalize_changes_df(changes)

    # Empty regressions handling
    if regressions.empty:
        empty_df = pd.DataFrame(columns=list(CORRELATION_SCHEMA_COLUMNS))
        return _cast_correlation_dtypes(empty_df)

    reg_df = regressions.copy()

    # Determine qualifying regressions
    if only_regressions:
        if "is_regression" in reg_df.columns:
            reg_df = reg_df[reg_df["is_regression"].astype(bool)].copy()
        elif "status" in reg_df.columns:
            has_reg_status = (reg_df["status"] == "regression").any()
            if has_reg_status:
                reg_df = reg_df[reg_df["status"] == "regression"].copy()

    if reg_df.empty:
        empty_df = pd.DataFrame(columns=list(CORRELATION_SCHEMA_COLUMNS))
        return _cast_correlation_dtypes(empty_df)

    # Parse regression timestamps
    reg_df["start_time"] = pd.to_datetime(reg_df["start_time"], utc=True, errors="coerce")
    if "end_time" in reg_df.columns:
        reg_df["end_time"] = pd.to_datetime(reg_df["end_time"], utc=True, errors="coerce")
    else:
        reg_df["end_time"] = pd.NaT

    # Assign source row indices for regression traceability
    if "source_row_index" in reg_df.columns:
        reg_df["_source_row_index"] = pd.to_numeric(reg_df["source_row_index"], errors="coerce").fillna(0).astype(int)
    else:
        reg_df["_source_row_index"] = reg_df.index

    # Assign source row indices for changes traceability
    changes_with_idx = norm_changes.copy()
    changes_with_idx["_change_source_row_index"] = changes_with_idx.index

    # Metric and status resolution
    if "metric" not in reg_df.columns:
        reg_df["metric"] = "all"
    if "status" in reg_df.columns:
        reg_df["_regression_status"] = reg_df["status"].astype(str)
    elif "is_regression" in reg_df.columns:
        reg_df["_regression_status"] = np.where(reg_df["is_regression"], "regression", "not_regression")
    else:
        reg_df["_regression_status"] = "regression"

    wb_seconds = float(window_before.total_seconds())
    wa_seconds = float(window_after.total_seconds())

    correlation_rows: list[dict[str, Any]] = []

    # Process each machine in isolation
    unique_machines = sorted(reg_df["machine_id"].dropna().unique())

    for machine in unique_machines:
        m_reg_df = reg_df[reg_df["machine_id"] == machine].copy()
        # Machine isolation: only changes strictly matching this machine identity
        m_changes_df = changes_with_idx[changes_with_idx["machine_id"] == machine].copy()

        # Deterministic sorting of input regressions for this machine
        m_reg_df.sort_values(
            by=["start_time", "end_time", "metric", "_source_row_index"],
            na_position="last",
            inplace=True,
        )

        for _, reg_row in m_reg_df.iterrows():
            r_idx = int(reg_row["_source_row_index"])
            r_metric = str(reg_row["metric"])
            r_start = reg_row["start_time"]
            r_end = reg_row["end_time"]
            r_status = str(reg_row["_regression_status"])

            # 1. Validate regression timestamp
            if pd.isna(r_start):
                reason_msg = (
                    f"Regression record for machine '{machine}' and metric '{r_metric}' "
                    "has missing or invalid timestamp; temporal correlation cannot be established."
                )
                correlation_rows.append({
                    "source_row_index": r_idx,
                    "machine_id": machine,
                    "metric": r_metric,
                    "start_time": pd.NaT,
                    "end_time": r_end,
                    "regression_status": r_status,
                    "is_correlated": False,
                    "correlation_status": "invalid_timestamp",
                    "change_id": None,
                    "change_type": None,
                    "change_timestamp": pd.NaT,
                    "change_description": None,
                    "temporal_offset_seconds": np.nan,
                    "temporal_relation": "none",
                    "window_before_seconds": wb_seconds,
                    "window_after_seconds": wa_seconds,
                    "reason": reason_msg,
                    "explanation": reason_msg,
                    "_change_source_row_index": -1,
                })
                continue

            # 2. Determine temporal window boundaries
            if time_anchor == "start_time":
                anchor_point = r_start
                lower_bound = r_start - window_before
                upper_bound = r_start + window_after
            elif time_anchor == "end_time":
                anchor_point = r_end if pd.notna(r_end) else r_start
                lower_bound = anchor_point - window_before
                upper_bound = anchor_point + window_after
            elif time_anchor == "interval":
                anchor_point = r_start
                interval_end = r_end if pd.notna(r_end) else r_start
                lower_bound = r_start - window_before
                upper_bound = interval_end + window_after

            # 3. Filter qualifying changes within the closed temporal window
            # Exclude changes with missing/invalid timestamps
            valid_changes = m_changes_df[m_changes_df["timestamp"].notna()].copy()

            if valid_changes.empty:
                matching_changes = valid_changes
            else:
                # Closed interval: [lower_bound, upper_bound]
                in_window = (valid_changes["timestamp"] >= lower_bound) & (valid_changes["timestamp"] <= upper_bound)
                matching_changes = valid_changes[in_window].copy()

            # 4. Handle no-match case explicitly
            if matching_changes.empty:
                r_start_str = r_start.isoformat()
                reason_msg = (
                    f"No system changes observed for machine '{machine}' within temporal window "
                    f"[-{wb_seconds:.0f}s, +{wa_seconds:.0f}s] of regression onset in {r_metric} at {r_start_str}."
                )
                correlation_rows.append({
                    "source_row_index": r_idx,
                    "machine_id": machine,
                    "metric": r_metric,
                    "start_time": r_start,
                    "end_time": r_end,
                    "regression_status": r_status,
                    "is_correlated": False,
                    "correlation_status": "no_matching_changes",
                    "change_id": None,
                    "change_type": None,
                    "change_timestamp": pd.NaT,
                    "change_description": None,
                    "temporal_offset_seconds": np.nan,
                    "temporal_relation": "none",
                    "window_before_seconds": wb_seconds,
                    "window_after_seconds": wa_seconds,
                    "reason": reason_msg,
                    "explanation": reason_msg,
                    "_change_source_row_index": -1,
                })
                continue

            # 5. Emit one correlation record per matching change
            for _, ch_row in matching_changes.iterrows():
                ch_idx = int(ch_row["_change_source_row_index"])
                ch_id = str(ch_row["change_id"])
                ch_type = str(ch_row["change_type"])
                ch_ts = ch_row["timestamp"]
                ch_desc = str(ch_row["description"])

                # Calculate signed temporal offset relative to anchor_point
                offset_seconds = round((ch_ts - anchor_point).total_seconds(), 2)

                if offset_seconds < 0:
                    temporal_rel = "before"
                    reason_msg = (
                        f"Observed change '{ch_id}' ({ch_type}) occurred {abs(offset_seconds):.1f}s "
                        f"before regression onset in {r_metric} at {r_start.isoformat()}. "
                        "Temporal proximity observed; causation is not asserted."
                    )
                elif offset_seconds > 0:
                    temporal_rel = "after"
                    reason_msg = (
                        f"Observed change '{ch_id}' ({ch_type}) occurred {offset_seconds:.1f}s "
                        f"after regression onset in {r_metric} at {r_start.isoformat()}. "
                        "Subsequent event; cannot be antecedent to regression; causation is not asserted."
                    )
                else:
                    temporal_rel = "concurrent"
                    reason_msg = (
                        f"Observed change '{ch_id}' ({ch_type}) occurred concurrently (offset 0.0s) "
                        f"with regression onset in {r_metric} at {r_start.isoformat()}. "
                        "Temporal proximity observed; causation is not asserted."
                    )

                correlation_rows.append({
                    "source_row_index": r_idx,
                    "machine_id": machine,
                    "metric": r_metric,
                    "start_time": r_start,
                    "end_time": r_end,
                    "regression_status": r_status,
                    "is_correlated": True,
                    "correlation_status": "correlated",
                    "change_id": ch_id,
                    "change_type": ch_type,
                    "change_timestamp": ch_ts,
                    "change_description": ch_desc,
                    "temporal_offset_seconds": offset_seconds,
                    "temporal_relation": temporal_rel,
                    "window_before_seconds": wb_seconds,
                    "window_after_seconds": wa_seconds,
                    "reason": reason_msg,
                    "explanation": reason_msg,
                    "_change_source_row_index": ch_idx,
                })

    result_df = pd.DataFrame(correlation_rows)

    if result_df.empty:
        empty_df = pd.DataFrame(columns=list(CORRELATION_SCHEMA_COLUMNS))
        return _cast_correlation_dtypes(empty_df)

    # Deterministic sorting policy
    result_df.sort_values(
        by=[
            "machine_id",
            "start_time",
            "metric",
            "source_row_index",
            "change_timestamp",
            "change_type",
            "change_id",
            "_change_source_row_index",
        ],
        na_position="last",
        inplace=True,
    )

    result_df.drop(columns=["_change_source_row_index"], inplace=True)
    result_df.reset_index(drop=True, inplace=True)

    return _cast_correlation_dtypes(result_df)


def _cast_correlation_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure consistent data types across correlation schema columns."""
    for col in CORRELATION_SCHEMA_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan

    df["source_row_index"] = pd.to_numeric(df["source_row_index"], errors="coerce").fillna(0).astype(int)
    df["machine_id"] = df["machine_id"].astype(str)
    df["metric"] = df["metric"].astype(str)
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True, errors="coerce")
    df["end_time"] = pd.to_datetime(df["end_time"], utc=True, errors="coerce")
    df["regression_status"] = df["regression_status"].astype(str)
    df["is_correlated"] = df["is_correlated"].astype(bool)
    df["correlation_status"] = df["correlation_status"].astype(str)

    # Object / nullable types for change attributes to preserve None on no-match
    df["change_id"] = df["change_id"].astype(object)
    df["change_type"] = df["change_type"].astype(object)
    df["change_timestamp"] = pd.to_datetime(df["change_timestamp"], utc=True, errors="coerce")
    df["change_description"] = df["change_description"].astype(object)

    df["temporal_offset_seconds"] = pd.to_numeric(df["temporal_offset_seconds"], errors="coerce").astype(float)
    df["temporal_relation"] = df["temporal_relation"].astype(str)
    df["window_before_seconds"] = pd.to_numeric(df["window_before_seconds"], errors="coerce").astype(float)
    df["window_after_seconds"] = pd.to_numeric(df["window_after_seconds"], errors="coerce").astype(float)
    df["reason"] = df["reason"].astype(str)
    df["explanation"] = df["explanation"].astype(str)

    return df[list(CORRELATION_SCHEMA_COLUMNS)]
