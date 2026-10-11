"""PARCS Analytics Module.

Provides feature engineering, machine-specific statistical baselines,
and explainable anomaly detection for Modern Standby telemetry.
"""

from src.analytics.anomaly import (
    ANOMALY_SCHEMA_COLUMNS,
    DEFAULT_ANOMALY_THRESHOLD,
    detect_anomalies,
)
from src.analytics.baseline import (
    BASELINE_SCHEMA_COLUMNS,
    DEFAULT_BASELINE_METRICS,
    DEFAULT_MIN_OBSERVATIONS,
    build_baseline,
)
from src.analytics.features import (
    REQUIRED_SESSION_COLUMNS,
    SLEEPSTUDY_FEATURE_COLUMNS,
    build_sleepstudy_features,
)

__all__ = [
    # Feature Engineering
    "build_sleepstudy_features",
    "REQUIRED_SESSION_COLUMNS",
    "SLEEPSTUDY_FEATURE_COLUMNS",
    # Baseline
    "build_baseline",
    "DEFAULT_MIN_OBSERVATIONS",
    "DEFAULT_BASELINE_METRICS",
    "BASELINE_SCHEMA_COLUMNS",
    # Anomaly Detection
    "detect_anomalies",
    "DEFAULT_ANOMALY_THRESHOLD",
    "ANOMALY_SCHEMA_COLUMNS",
]
