"""Machine-specific statistical baseline for PARCS SleepStudy telemetry.

Calculates robust descriptive statistics (Median, MAD, IQR) partitioned strictly
by machine identity. Enforces minimum observation requirements and handles zero-MAD.
"""

from __future__ import annotations

import logging
from typing import Sequence

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Default minimum observations required before a baseline is marked ready
DEFAULT_MIN_OBSERVATIONS: int = 10

# Supported SleepStudy performance metrics
DEFAULT_BASELINE_METRICS: Sequence[str] = (
    "drips_percent",
    "battery_drain_rate_mw",
    "battery_drain_percent",
)

# Robust scaling constants based on standard normal distribution
MAD_NORMAL_SCALE: float = 1.4826  # MAD * 1.4826 ~ standard deviation
IQR_NORMAL_SCALE: float = 1.3490  # IQR / 1.3490 ~ standard deviation
MIN_DISPERSION_EPSILON: float = 1e-4  # Non-zero minimum scale when variance is 0

# Baseline schema columns
BASELINE_SCHEMA_COLUMNS: Sequence[str] = (
    "machine_id",
    "metric",
    "observation_count",
    "valid_count",
    "excluded_count",
    "median",
    "mad",
    "iqr",
    "dispersion_scale",
    "zero_mad_fallback",
    "readiness",
    "min_observations",
)


def build_baseline(
    features: pd.DataFrame,
    min_observations: int = DEFAULT_MIN_OBSERVATIONS,
    metrics: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Build robust, machine-specific statistical baselines from feature observations.

    For each machine and metric, calculates:
      - Valid observation count
      - Excluded observation count
      - Median
      - Median Absolute Deviation (MAD)
      - Interquartile Range (IQR)
      - Effective dispersion scale (with documented zero-MAD fallback)
      - Readiness status ('ready', 'insufficient_history', or 'no_data')

    Machines and metrics are calculated strictly in isolation. Observations from
    different machines are never aggregated together.

    Args:
        features: DataFrame output from build_sleepstudy_features.
        min_observations: Minimum valid observations required for readiness.
            Defaults to 10.
        metrics: Sequence of metric column names to baseline.
            Defaults to ('drips_percent', 'battery_drain_rate_mw', 'battery_drain_percent').

    Returns:
        pandas DataFrame detailing statistical baselines per machine and metric.

    Raises:
        ValueError: If 'machine_id' column is missing or min_observations < 1.
    """
    if not isinstance(features, pd.DataFrame):
        raise TypeError(f"Expected pandas DataFrame, got {type(features).__name__}")

    if "machine_id" not in features.columns:
        raise ValueError("Input DataFrame is missing required column 'machine_id'")

    if min_observations < 1:
        raise ValueError(f"min_observations must be >= 1, got {min_observations}")

    target_metrics = list(metrics) if metrics is not None else list(DEFAULT_BASELINE_METRICS)

    # Empty input handling
    if features.empty:
        empty_df = pd.DataFrame(columns=list(BASELINE_SCHEMA_COLUMNS))
        return _cast_baseline_dtypes(empty_df)

    rows: list[dict[str, object]] = []
    unique_machines = sorted(features["machine_id"].dropna().unique())

    for machine in unique_machines:
        machine_df = features[features["machine_id"] == machine]

        for metric in target_metrics:
            if metric not in machine_df.columns:
                # Metric column does not exist in features
                rows.append({
                    "machine_id": machine,
                    "metric": metric,
                    "observation_count": 0,
                    "valid_count": 0,
                    "excluded_count": 0,
                    "median": np.nan,
                    "mad": np.nan,
                    "iqr": np.nan,
                    "dispersion_scale": np.nan,
                    "zero_mad_fallback": False,
                    "readiness": "no_data",
                    "min_observations": min_observations,
                })
                continue

            series = pd.to_numeric(machine_df[metric], errors="coerce")
            total_obs = len(series)

            # Filter valid (non-null, finite) observations
            valid_vals = series.dropna().to_numpy(dtype=float)
            valid_count = len(valid_vals)
            excluded_count = total_obs - valid_count

            if valid_count == 0:
                rows.append({
                    "machine_id": machine,
                    "metric": metric,
                    "observation_count": total_obs,
                    "valid_count": 0,
                    "excluded_count": excluded_count,
                    "median": np.nan,
                    "mad": np.nan,
                    "iqr": np.nan,
                    "dispersion_scale": np.nan,
                    "zero_mad_fallback": False,
                    "readiness": "no_data",
                    "min_observations": min_observations,
                })
                continue

            # Compute robust location & scale statistics
            median_val = float(np.median(valid_vals))
            abs_devs = np.abs(valid_vals - median_val)
            mad_val = float(np.median(abs_devs))

            q75, q25 = np.percentile(valid_vals, [75, 25])
            iqr_val = float(q75 - q25)

            # Zero-MAD fallback strategy:
            # 1. Primary scale: MAD * 1.4826
            # 2. If MAD == 0: fallback to IQR / 1.3490 (if IQR > 0)
            # 3. If IQR == 0: fallback to MIN_DISPERSION_EPSILON to avoid div-by-zero
            zero_mad = False
            if mad_val > 0.0:
                dispersion_scale = mad_val * MAD_NORMAL_SCALE
            elif iqr_val > 0.0:
                dispersion_scale = iqr_val / IQR_NORMAL_SCALE
                zero_mad = True
                logger.info(
                    "Machine '%s' metric '%s': MAD is 0; using IQR fallback scale %.4f",
                    machine, metric, dispersion_scale,
                )
            else:
                dispersion_scale = MIN_DISPERSION_EPSILON
                zero_mad = True
                logger.info(
                    "Machine '%s' metric '%s': Both MAD and IQR are 0; using epsilon fallback %.4f",
                    machine, metric, dispersion_scale,
                )

            # Readiness evaluation: require at least min_observations
            readiness = "ready" if valid_count >= min_observations else "insufficient_history"

            rows.append({
                "machine_id": machine,
                "metric": metric,
                "observation_count": total_obs,
                "valid_count": valid_count,
                "excluded_count": excluded_count,
                "median": median_val,
                "mad": mad_val,
                "iqr": iqr_val,
                "dispersion_scale": dispersion_scale,
                "zero_mad_fallback": zero_mad,
                "readiness": readiness,
                "min_observations": min_observations,
            })

    result_df = pd.DataFrame(rows, columns=list(BASELINE_SCHEMA_COLUMNS))
    return _cast_baseline_dtypes(result_df)


def _cast_baseline_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure consistent data types across all baseline columns."""
    df["machine_id"] = df["machine_id"].astype(str)
    df["metric"] = df["metric"].astype(str)
    df["observation_count"] = pd.to_numeric(df["observation_count"], errors="coerce").fillna(0).astype(int)
    df["valid_count"] = pd.to_numeric(df["valid_count"], errors="coerce").fillna(0).astype(int)
    df["excluded_count"] = pd.to_numeric(df["excluded_count"], errors="coerce").fillna(0).astype(int)
    df["median"] = pd.to_numeric(df["median"], errors="coerce").astype(float)
    df["mad"] = pd.to_numeric(df["mad"], errors="coerce").astype(float)
    df["iqr"] = pd.to_numeric(df["iqr"], errors="coerce").astype(float)
    df["dispersion_scale"] = pd.to_numeric(df["dispersion_scale"], errors="coerce").astype(float)
    df["zero_mad_fallback"] = df["zero_mad_fallback"].astype(bool)
    df["readiness"] = df["readiness"].astype(str)
    df["min_observations"] = pd.to_numeric(df["min_observations"], errors="coerce").fillna(0).astype(int)
    return df
