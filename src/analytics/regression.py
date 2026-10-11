"""Deterministic, explainable regression detection for PARCS SleepStudy telemetry.

Detects sustained performance regressions (e.g. drop in DRIPS residency or surge
in battery drain) by evaluating consecutive qualifying sessions against
machine-specific statistical baselines.

Strict architectural principles:
  - Separate regression detection from anomaly detection.
  - Directional evaluation: regressions are directional harmful deviations.
  - Sustained rule: requires consecutive qualifying observations in timestamp order.
  - Strict machine isolation: observations from different machines are never combined.
  - Non-causal explainability: states statistical facts without claiming driver/update causation.
"""

from __future__ import annotations

import logging
from typing import Sequence

import numpy as np
import pandas as pd

from src.analytics.features import build_sleepstudy_features

logger = logging.getLogger(__name__)

# Default configuration parameters
DEFAULT_REGRESSION_THRESHOLD: float = 2.0  # Modified Z-score harmful cutoff
DEFAULT_MIN_CONSECUTIVE: int = 3          # Required consecutive qualifying sessions

# Metric harmful direction mapping
# 'lower': lower values represent degradation (e.g. DRIPS low residency)
# 'higher': higher values represent degradation (e.g. excessive battery drain)
DEFAULT_DIRECTION_MAP: dict[str, str] = {
    "drips_percent": "lower",
    "battery_drain_percent": "higher",
    "battery_drain_rate_mw": "higher",
}

# Output schema columns
REGRESSION_SCHEMA_COLUMNS: Sequence[str] = (
    "source_row_index",
    "machine_id",
    "start_time",
    "end_time",
    "metric",
    "observed_value",
    "baseline_median",
    "deviation_score",
    "direction",
    "is_regression",
    "status",
    "consecutive_count",
    "required_consecutive",
    "reason",
)


def detect_regressions(
    features: pd.DataFrame,
    baseline: pd.DataFrame,
    threshold: float = DEFAULT_REGRESSION_THRESHOLD,
    min_consecutive: int = DEFAULT_MIN_CONSECUTIVE,
    metrics: Sequence[str] | None = None,
    direction_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Detect sustained performance regressions in SleepStudy telemetry.

    Evaluates observations sequentially per machine and metric in deterministic
    timestamp order. A regression event is flagged when at least `min_consecutive`
    consecutive qualifying observations meet the harmful deviation threshold
    against a ready machine baseline.

    Deterministic Ordering Policy:
        Sessions are ordered chronologically by:
        1. `start_time` ascending (valid timestamps first)
        2. `end_time` ascending (tie-breaker for duplicate start_time)
        3. `source_row_index` ascending (tie-breaker for duplicate timestamps)

    Streak Continuity Rules:
        - Intervening valid observations that do not meet the threshold reset the streak.
        - Missing or invalid measurements reset the streak (cannot bridge gaps).
        - Missing or unparseable timestamps reset the streak.
        - Baselines that are unready or absent yield explicit non-regression statuses.

    Args:
        features: DataFrame containing SleepStudy features or normalized sessions.
        baseline: DataFrame output from build_baseline.
        threshold: Minimum directional Modified Z-score to qualify as harmful.
            Defaults to 2.0.
        min_consecutive: Number of consecutive qualifying observations required.
            Defaults to 3.
        metrics: Sequence of metric names to evaluate. Defaults to all metrics
            configured in direction_map.
        direction_map: Mapping of metric name to 'lower' or 'higher'.
            Defaults to DEFAULT_DIRECTION_MAP.

    Returns:
        pandas DataFrame detailing regression evaluation for each session and metric.

    Raises:
        ValueError: If required columns are missing, threshold <= 0, or min_consecutive < 1.
    """
    if not isinstance(features, pd.DataFrame):
        raise TypeError(f"Expected features as pandas DataFrame, got {type(features).__name__}")
    if not isinstance(baseline, pd.DataFrame):
        raise TypeError(f"Expected baseline as pandas DataFrame, got {type(baseline).__name__}")

    if threshold <= 0:
        raise ValueError(f"threshold must be positive, got {threshold}")
    if min_consecutive < 1:
        raise ValueError(f"min_consecutive must be >= 1, got {min_consecutive}")

    # Validate feature columns
    req_feat_cols = {"machine_id", "start_time"}
    missing_feat = req_feat_cols - set(features.columns)
    if missing_feat:
        raise ValueError(f"features DataFrame is missing required columns: {missing_feat}")

    # Validate baseline columns
    req_base_cols = {"machine_id", "metric", "median", "dispersion_scale", "readiness"}
    missing_base = req_base_cols - set(baseline.columns)
    if missing_base:
        raise ValueError(f"baseline DataFrame is missing required columns: {missing_base}")

    # Handle empty input
    if features.empty:
        empty_df = pd.DataFrame(columns=list(REGRESSION_SCHEMA_COLUMNS))
        return _cast_regression_dtypes(empty_df)

    # Ensure feature engineering is present if raw sessions were provided
    df = features.copy()
    if "duration_hours" not in df.columns and "duration_seconds" in df.columns:
        df = build_sleepstudy_features(df)
    else:
        df["start_time"] = pd.to_datetime(df["start_time"], utc=True, errors="coerce", format="mixed")
        if "end_time" in df.columns:
            df["end_time"] = pd.to_datetime(df["end_time"], utc=True, errors="coerce", format="mixed")
        else:
            df["end_time"] = pd.NaT

    # Assign source row index for traceability
    df["_source_row_index"] = df.index

    # Resolve metric list and directions
    dirs = dict(DEFAULT_DIRECTION_MAP)
    if direction_map is not None:
        dirs.update(direction_map)

    if metrics is not None:
        target_metrics = list(metrics)
    elif not baseline.empty and "metric" in baseline.columns:
        target_metrics = sorted(baseline["metric"].dropna().unique())
    else:
        target_metrics = list(dirs.keys())

    # Build baseline lookup map: (machine_id, metric) -> dict
    baseline_lookup: dict[tuple[str, str], dict[str, object]] = {}
    for _, b_row in baseline.iterrows():
        b_mach = str(b_row["machine_id"]).strip()
        b_met = str(b_row["metric"]).strip()
        baseline_lookup[(b_mach, b_met)] = b_row.to_dict()

    evaluation_rows: list[dict[str, object]] = []
    unique_machines = sorted(df["machine_id"].dropna().unique())

    for machine in unique_machines:
        machine_df = df[df["machine_id"] == machine].copy()

        # Deterministic sorting policy:
        # Sort by start_time ascending (NaT last), then end_time ascending, then _source_row_index
        # NaT timestamps are placed at the end so valid sequences are evaluated first
        machine_df.sort_values(
            by=["start_time", "end_time", "_source_row_index"],
            na_position="last",
            inplace=True,
        )

        for metric in target_metrics:
            direction = dirs.get(metric, "lower")
            b_data = baseline_lookup.get((machine, metric))

            # Running streak counter for this machine and metric
            consecutive_count = 0

            for _, row in machine_df.iterrows():
                row_idx = row["_source_row_index"]
                start_ts = row["start_time"]
                end_ts = row.get("end_time", pd.NaT)

                # 1. Check timestamp validity
                if pd.isna(start_ts):
                    consecutive_count = 0  # Missing timestamp breaks continuity
                    evaluation_rows.append({
                        "source_row_index": row_idx,
                        "machine_id": machine,
                        "start_time": pd.NaT,
                        "end_time": end_ts,
                        "metric": metric,
                        "observed_value": np.nan,
                        "baseline_median": np.nan,
                        "deviation_score": np.nan,
                        "direction": direction,
                        "is_regression": False,
                        "status": "invalid_timestamp",
                        "consecutive_count": 0,
                        "required_consecutive": min_consecutive,
                        "reason": "Session has invalid or missing start_time; temporal continuity cannot be established",
                    })
                    continue

                # 2. Check observation presence and numeric validity
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
                    consecutive_count = 0  # Missing measurement breaks consecutive streak
                    evaluation_rows.append({
                        "source_row_index": row_idx,
                        "machine_id": machine,
                        "start_time": start_ts,
                        "end_time": end_ts,
                        "metric": metric,
                        "observed_value": np.nan,
                        "baseline_median": np.nan,
                        "deviation_score": np.nan,
                        "direction": direction,
                        "is_regression": False,
                        "status": "missing_metric",
                        "consecutive_count": 0,
                        "required_consecutive": min_consecutive,
                        "reason": f"Metric '{metric}' is missing or null; cannot contribute to sustained regression",
                    })
                    continue

                # 3. Check baseline availability and readiness
                if b_data is None:
                    consecutive_count = 0
                    evaluation_rows.append({
                        "source_row_index": row_idx,
                        "machine_id": machine,
                        "start_time": start_ts,
                        "end_time": end_ts,
                        "metric": metric,
                        "observed_value": observed_val,
                        "baseline_median": np.nan,
                        "deviation_score": np.nan,
                        "direction": direction,
                        "is_regression": False,
                        "status": "no_baseline",
                        "consecutive_count": 0,
                        "required_consecutive": min_consecutive,
                        "reason": f"No baseline found for machine '{machine}' and metric '{metric}'",
                    })
                    continue

                readiness = str(b_data.get("readiness", "no_data"))
                median_val = float(b_data["median"]) if pd.notna(b_data.get("median")) else np.nan
                scale_val = float(b_data["dispersion_scale"]) if pd.notna(b_data.get("dispersion_scale")) else np.nan
                valid_count = int(b_data.get("valid_count", 0))
                min_obs = int(b_data.get("min_observations", 0))

                if readiness != "ready" or pd.isna(median_val) or pd.isna(scale_val) or scale_val <= 0:
                    consecutive_count = 0
                    evaluation_rows.append({
                        "source_row_index": row_idx,
                        "machine_id": machine,
                        "start_time": start_ts,
                        "end_time": end_ts,
                        "metric": metric,
                        "observed_value": observed_val,
                        "baseline_median": median_val,
                        "deviation_score": np.nan,
                        "direction": direction,
                        "is_regression": False,
                        "status": "insufficient_history",
                        "consecutive_count": 0,
                        "required_consecutive": min_consecutive,
                        "reason": (
                            f"Baseline for machine '{machine}' and metric '{metric}' has insufficient history "
                            f"({valid_count} < {min_obs} valid observations)"
                        ),
                    })
                    continue

                # 4. Calculate directional harmful deviation score
                # Direction 'lower': harmful when observed < median (median - observed > 0)
                # Direction 'higher': harmful when observed > median (observed - median > 0)
                if direction == "lower":
                    harmful_delta = median_val - observed_val
                elif direction == "higher":
                    harmful_delta = observed_val - median_val
                else:
                    harmful_delta = 0.0

                dev_score = round(harmful_delta / scale_val, 4)

                # 5. Evaluate consecutive qualifying streak
                # Qualifying harmful observation requires dev_score > threshold
                is_qualifying = dev_score > threshold

                if is_qualifying:
                    consecutive_count += 1
                    if consecutive_count >= min_consecutive:
                        is_reg = True
                        status = "regression"
                        reason = (
                            f"Sustained regression in {metric}: observed {observed_val:.2f} deviates harmfully "
                            f"from baseline {median_val:.2f} (score={dev_score:.2f} > threshold {threshold:.2f}) "
                            f"for {consecutive_count} consecutive sessions (required {min_consecutive})"
                        )
                    else:
                        is_reg = False
                        status = "not_regression"
                        reason = (
                            f"Harmful deviation in {metric}: observed {observed_val:.2f} deviates from baseline {median_val:.2f} "
                            f"(score={dev_score:.2f} > threshold {threshold:.2f}), but sequence length {consecutive_count} "
                            f"< required {min_consecutive}"
                        )
                else:
                    consecutive_count = 0  # Normal or improving observation breaks the regression streak
                    is_reg = False
                    status = "not_regression"
                    reason = (
                        f"Observed {metric}={observed_val:.2f} does not meet harmful deviation threshold "
                        f"against baseline median {median_val:.2f} (score={dev_score:.2f} <= threshold {threshold:.2f})"
                    )

                evaluation_rows.append({
                    "source_row_index": row_idx,
                    "machine_id": machine,
                    "start_time": start_ts,
                    "end_time": end_ts,
                    "metric": metric,
                    "observed_value": observed_val,
                    "baseline_median": median_val,
                    "deviation_score": dev_score,
                    "direction": direction,
                    "is_regression": is_reg,
                    "status": status,
                    "consecutive_count": consecutive_count,
                    "required_consecutive": min_consecutive,
                    "reason": reason,
                })

    result_df = pd.DataFrame(evaluation_rows, columns=list(REGRESSION_SCHEMA_COLUMNS))
    return _cast_regression_dtypes(result_df)


def _cast_regression_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure consistent data types across regression detection columns."""
    df["source_row_index"] = pd.to_numeric(df["source_row_index"], errors="coerce").fillna(0).astype(int)
    df["machine_id"] = df["machine_id"].astype(str)
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True, errors="coerce")
    df["end_time"] = pd.to_datetime(df["end_time"], utc=True, errors="coerce")
    df["metric"] = df["metric"].astype(str)
    df["observed_value"] = pd.to_numeric(df["observed_value"], errors="coerce").astype(float)
    df["baseline_median"] = pd.to_numeric(df["baseline_median"], errors="coerce").astype(float)
    df["deviation_score"] = pd.to_numeric(df["deviation_score"], errors="coerce").astype(float)
    df["direction"] = df["direction"].astype(str)
    df["is_regression"] = df["is_regression"].astype(bool)
    df["status"] = df["status"].astype(str)
    df["consecutive_count"] = pd.to_numeric(df["consecutive_count"], errors="coerce").fillna(0).astype(int)
    df["required_consecutive"] = pd.to_numeric(df["required_consecutive"], errors="coerce").fillna(0).astype(int)
    df["reason"] = df["reason"].astype(str)
    return df
