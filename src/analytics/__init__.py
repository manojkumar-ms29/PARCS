"""PARCS Analytics Module.

Provides feature engineering, machine-specific statistical baselines,
explainable anomaly detection, and sustained regression detection for
Modern Standby telemetry.
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
from src.analytics.regression import (
    DEFAULT_DIRECTION_MAP,
    DEFAULT_MIN_CONSECUTIVE,
    DEFAULT_REGRESSION_THRESHOLD,
    REGRESSION_SCHEMA_COLUMNS,
    detect_regressions,
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
    # Regression Detection
    "detect_regressions",
    "DEFAULT_REGRESSION_THRESHOLD",
    "DEFAULT_MIN_CONSECUTIVE",
    "DEFAULT_DIRECTION_MAP",
    "REGRESSION_SCHEMA_COLUMNS",
]
