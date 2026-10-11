"""Explainable SleepStudy anomaly detection.

Evaluates sessions against machine-specific statistical baselines using robust
Modified Z-scores. Distinguishes missing metrics and insufficient history from
actual anomalies without making causal claims.
"""

from __future__ import annotations

import logging
from typing import Sequence

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Standard recommended threshold for Modified Z-score (Iglewicz & Hoaglin, 1993)
DEFAULT_ANOMALY_THRESHOLD: float = 3.5

# Schema columns for anomaly detection output
ANOMALY_SCHEMA_COLUMNS: Sequence[str] = (
    "source_row_index",
    "machine_id",
    "start_time",
    "end_time",
    "metric",
    "observed_value",
    "baseline_median",
    "deviation_score",
    "threshold",
    "is_anomaly",
    "status",
    "reason",
)


def detect_anomalies(
    features: pd.DataFrame,
    baseline: pd.DataFrame,
    threshold: float = DEFAULT_ANOMALY_THRESHOLD,
    metrics: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Detect statistical anomalies by comparing sessions to machine-specific baselines.

    Calculates the Modified Z-score deviation:
        score = |observed_value - baseline_median| / dispersion_scale

    Where:
        dispersion_scale = 1.4826 * MAD (or IQR/epsilon fallback for zero-MAD baselines)

    Decisions and statuses:
        - 'anomaly': score > threshold and baseline is 'ready' (is_anomaly = True)
        - 'normal': score <= threshold and baseline is 'ready' (is_anomaly = False)
        - 'insufficient_history': baseline observation count < min_observations (is_anomaly = False)
        - 'missing_metric': observation is null or invalid in features (is_anomaly = False)
        - 'no_baseline': machine or metric has no matching baseline entry (is_anomaly = False)

    Strict rules:
        - Never compares an observation to another machine's baseline.
        - Never flags an anomaly if data or baseline is missing.
        - Preserves source row indices for full traceability.
        - Human-readable reasons state statistical deviations without making causal claims.

    Args:
        features: DataFrame output from build_sleepstudy_features.
        baseline: DataFrame output from build_baseline.
        threshold: Modified Z-score cutoff for anomaly flag. Defaults to 3.5.
        metrics: Optional subset of metric names to evaluate. Defaults to all
            metrics present in the baseline.

    Returns:
        pandas DataFrame detailing anomaly evaluation for each session and metric.

    Raises:
        ValueError: If required columns are missing or threshold <= 0.
    """
    if not isinstance(features, pd.DataFrame):
        raise TypeError(f"Expected features as pandas DataFrame, got {type(features).__name__}")
    if not isinstance(baseline, pd.DataFrame):
        raise TypeError(f"Expected baseline as pandas DataFrame, got {type(baseline).__name__}")

    if threshold <= 0:
        raise ValueError(f"threshold must be positive, got {threshold}")

    req_feat_cols = {"machine_id", "start_time", "end_time"}
    missing_feat = req_feat_cols - set(features.columns)
    if missing_feat:
        raise ValueError(f"features DataFrame is missing required columns: {missing_feat}")

    req_base_cols = {"machine_id", "metric", "median", "dispersion_scale", "readiness"}
    missing_base = req_base_cols - set(baseline.columns)
    if missing_base:
        raise ValueError(f"baseline DataFrame is missing required columns: {missing_base}")

    # Handle empty input
    if features.empty:
        empty_df = pd.DataFrame(columns=list(ANOMALY_SCHEMA_COLUMNS))
        return _cast_anomaly_dtypes(empty_df)

    # Determine metrics to evaluate
    if metrics is not None:
        target_metrics = list(metrics)
    elif not baseline.empty and "metric" in baseline.columns:
        target_metrics = sorted(baseline["metric"].dropna().unique())
    else:
        target_metrics = ["drips_percent", "battery_drain_rate_mw", "battery_drain_percent"]

    # Build fast baseline lookup map: (machine_id, metric) -> dict
    baseline_lookup: dict[tuple[str, str], dict[str, object]] = {}
    for _, b_row in baseline.iterrows():
        b_mach = str(b_row["machine_id"]).strip()
        b_met = str(b_row["metric"]).strip()
        baseline_lookup[(b_mach, b_met)] = b_row.to_dict()

    anomaly_rows: list[dict[str, object]] = []

    for row_idx, row in features.iterrows():
        machine = str(row["machine_id"]).strip()
        start_ts = row["start_time"]
        end_ts = row["end_time"]

        for metric in target_metrics:
            # 1. Check if observation exists and is non-null
            has_metric_col = metric in row.index
            observed_raw = row[metric] if has_metric_col else np.nan
            is_valid_obs = False

            if has_metric_col and pd.notna(observed_raw):
                try:
                    observed_val = float(observed_raw)
                    if not np.isneginf(observed_val) and not np.isposinf(observed_val):
                        is_valid_obs = True
                except (ValueError, TypeError):
                    observed_val = np.nan
            else:
                observed_val = np.nan

            if not is_valid_obs:
                anomaly_rows.append({
                    "source_row_index": row_idx,
                    "machine_id": machine,
                    "start_time": start_ts,
                    "end_time": end_ts,
                    "metric": metric,
                    "observed_value": np.nan,
                    "baseline_median": np.nan,
                    "deviation_score": np.nan,
                    "threshold": float(threshold),
                    "is_anomaly": False,
                    "status": "missing_metric",
                    "reason": f"Metric '{metric}' is missing or null for this session",
                })
                continue

            # 2. Check matching baseline
            b_data = baseline_lookup.get((machine, metric))
            if b_data is None:
                anomaly_rows.append({
                    "source_row_index": row_idx,
                    "machine_id": machine,
                    "start_time": start_ts,
                    "end_time": end_ts,
                    "metric": metric,
                    "observed_value": observed_val,
                    "baseline_median": np.nan,
                    "deviation_score": np.nan,
                    "threshold": float(threshold),
                    "is_anomaly": False,
                    "status": "no_baseline",
                    "reason": f"No baseline found for machine '{machine}' and metric '{metric}'",
                })
                continue

            readiness = str(b_data.get("readiness", "no_data"))
            median_val = float(b_data["median"]) if pd.notna(b_data.get("median")) else np.nan
            scale_val = float(b_data["dispersion_scale"]) if pd.notna(b_data.get("dispersion_scale")) else np.nan
            valid_count = int(b_data.get("valid_count", 0))
            min_obs = int(b_data.get("min_observations", 0))

            if readiness != "ready" or pd.isna(median_val) or pd.isna(scale_val) or scale_val <= 0:
                anomaly_rows.append({
                    "source_row_index": row_idx,
                    "machine_id": machine,
                    "start_time": start_ts,
                    "end_time": end_ts,
                    "metric": metric,
                    "observed_value": observed_val,
                    "baseline_median": median_val,
                    "deviation_score": np.nan,
                    "threshold": float(threshold),
                    "is_anomaly": False,
                    "status": "insufficient_history",
                    "reason": (
                        f"Baseline for machine '{machine}' and metric '{metric}' has insufficient history "
                        f"({valid_count} < {min_obs} valid observations)"
                    ),
                })
                continue

            # 3. Calculate deviation score
            delta = abs(observed_val - median_val)
            if delta == 0.0:
                dev_score = 0.0
            else:
                dev_score = round(delta / scale_val, 4)

            # 4. Anomaly decision
            if dev_score > threshold:
                is_anom = True
                status = "anomaly"
                reason = (
                    f"Observed {metric}={observed_val:.2f} deviates significantly from baseline median {median_val:.2f} "
                    f"(score={dev_score:.2f} > threshold {threshold:.2f})"
                )
            else:
                is_anom = False
                status = "normal"
                reason = (
                    f"Observed {metric}={observed_val:.2f} is within normal variation of baseline median {median_val:.2f} "
                    f"(score={dev_score:.2f} <= threshold {threshold:.2f})"
                )

            anomaly_rows.append({
                "source_row_index": row_idx,
                "machine_id": machine,
                "start_time": start_ts,
                "end_time": end_ts,
                "metric": metric,
                "observed_value": observed_val,
                "baseline_median": median_val,
                "deviation_score": dev_score,
                "threshold": float(threshold),
                "is_anomaly": is_anom,
                "status": status,
                "reason": reason,
            })

    result_df = pd.DataFrame(anomaly_rows, columns=list(ANOMALY_SCHEMA_COLUMNS))
    return _cast_anomaly_dtypes(result_df)


def _cast_anomaly_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure consistent data types across anomaly detection columns."""
    df["source_row_index"] = pd.to_numeric(df["source_row_index"], errors="coerce").fillna(0).astype(int)
    df["machine_id"] = df["machine_id"].astype(str)
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True, errors="coerce")
    df["end_time"] = pd.to_datetime(df["end_time"], utc=True, errors="coerce")
    df["metric"] = df["metric"].astype(str)
    df["observed_value"] = pd.to_numeric(df["observed_value"], errors="coerce").astype(float)
    df["baseline_median"] = pd.to_numeric(df["baseline_median"], errors="coerce").astype(float)
    df["deviation_score"] = pd.to_numeric(df["deviation_score"], errors="coerce").astype(float)
    df["threshold"] = pd.to_numeric(df["threshold"], errors="coerce").astype(float)
    df["is_anomaly"] = df["is_anomaly"].astype(bool)
    df["status"] = df["status"].astype(str)
    df["reason"] = df["reason"].astype(str)
    return df
