"""Tests for PARCS SleepStudy anomaly detection.

Verifies explainable anomaly decisions, robust Modified Z-scores,
isolation between machines, handling of missing data and insufficient history,
and zero-MAD resilience using synthetic fixtures.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analytics.anomaly import (
    ANOMALY_SCHEMA_COLUMNS,
    DEFAULT_ANOMALY_THRESHOLD,
    detect_anomalies,
)
from src.analytics.baseline import build_baseline
from src.analytics.features import build_sleepstudy_features


def _make_training_sessions(machine_id: str, n: int = 15, drips_center: float = 95.0) -> pd.DataFrame:
    """Generate synthetic baseline training sessions."""
    rows = []
    for i in range(n):
        # Small deterministic fluctuation around center
        fluctuation = (i % 3) - 1.0  # -1, 0, 1
        rows.append({
            "machine_id": machine_id,
            "start_time": f"2026-09-01T{10 + (i % 10):02d}:00:00Z",
            "end_time": f"2026-09-01T{10 + (i % 10):02d}:30:00Z",
            "duration_seconds": 1800.0,
            "drips_percent": drips_center + fluctuation,
            "battery_drain_percent": 2.0,
            "battery_drain_rate_mw": 3000.0 + (fluctuation * 100),
        })
    return pd.DataFrame(rows)


class TestAnomalyDetection:
    def test_empty_input_returns_anomaly_schema(self) -> None:
        empty_features = pd.DataFrame(columns=["machine_id", "start_time", "end_time", "drips_percent"])
        empty_baseline = pd.DataFrame(columns=["machine_id", "metric", "median", "dispersion_scale", "readiness"])

        anomalies = detect_anomalies(empty_features, empty_baseline)
        assert anomalies.empty
        for col in ANOMALY_SCHEMA_COLUMNS:
            assert col in anomalies.columns

    def test_missing_required_columns_raises_value_error(self) -> None:
        features = pd.DataFrame({"machine_id": ["BOX-1"]})
        baseline = pd.DataFrame({"machine_id": ["BOX-1"], "metric": ["drips_percent"]})

        with pytest.raises(ValueError, match="features DataFrame is missing required columns"):
            detect_anomalies(features, baseline)

    def test_invalid_threshold_raises_value_error(self) -> None:
        features = pd.DataFrame(columns=["machine_id", "start_time", "end_time"])
        baseline = pd.DataFrame(columns=["machine_id", "metric", "median", "dispersion_scale", "readiness"])

        with pytest.raises(ValueError, match="threshold must be positive"):
            detect_anomalies(features, baseline, threshold=0.0)

    def test_normal_observation_within_baseline_is_not_anomalous(self) -> None:
        # Train baseline with DRIPS centered around 95%
        train_df = build_sleepstudy_features(_make_training_sessions("BOX-STABLE", 15, drips_center=95.0))
        baseline = build_baseline(train_df, min_observations=10)

        # Test session with 94.5% DRIPS (normal variation)
        test_session = pd.DataFrame([{
            "machine_id": "BOX-STABLE",
            "start_time": "2026-09-02T10:00:00Z",
            "end_time": "2026-09-02T10:30:00Z",
            "duration_seconds": 1800.0,
            "drips_percent": 94.5,
            "battery_drain_percent": 2.0,
            "battery_drain_rate_mw": 3050.0,
        }])
        test_features = build_sleepstudy_features(test_session)

        anomalies = detect_anomalies(test_features, baseline, metrics=["drips_percent"])
        assert len(anomalies) == 1
        res = anomalies.iloc[0]

        assert bool(res["is_anomaly"]) is False
        assert res["status"] == "normal"
        assert res["deviation_score"] <= DEFAULT_ANOMALY_THRESHOLD
        assert "within normal variation" in res["reason"]

    def test_clear_synthetic_outlier_is_flagged_anomalous(self) -> None:
        # Train baseline with DRIPS around 95% (MAD is small)
        train_df = build_sleepstudy_features(_make_training_sessions("BOX-STABLE", 15, drips_center=95.0))
        baseline = build_baseline(train_df, min_observations=10)

        # Extreme outlier: 35% DRIPS (severe power regression)
        outlier_session = pd.DataFrame([{
            "machine_id": "BOX-STABLE",
            "start_time": "2026-09-02T11:00:00Z",
            "end_time": "2026-09-02T11:30:00Z",
            "duration_seconds": 1800.0,
            "drips_percent": 35.0,
            "battery_drain_percent": 15.0,
            "battery_drain_rate_mw": 12000.0,
        }])
        outlier_features = build_sleepstudy_features(outlier_session)

        anomalies = detect_anomalies(outlier_features, baseline, metrics=["drips_percent"])
        assert len(anomalies) == 1
        res = anomalies.iloc[0]

        assert bool(res["is_anomaly"]) is True
        assert res["status"] == "anomaly"
        assert res["deviation_score"] > DEFAULT_ANOMALY_THRESHOLD
        assert res["observed_value"] == 35.0
        assert res["baseline_median"] == 95.0
        assert "deviates significantly" in res["reason"]
        # Must not make causal claims (e.g. no mentions of drivers or updates causing it)
        assert "driver" not in res["reason"].lower()
        assert "update" not in res["reason"].lower()

    def test_insufficient_history_is_never_labeled_anomalous(self) -> None:
        # Only 4 sessions (< min 10)
        train_df = build_sleepstudy_features(_make_training_sessions("BOX-NEW", 4, drips_center=95.0))
        baseline = build_baseline(train_df, min_observations=10)

        test_session = pd.DataFrame([{
            "machine_id": "BOX-NEW",
            "start_time": "2026-09-02T12:00:00Z",
            "end_time": "2026-09-02T12:30:00Z",
            "duration_seconds": 1800.0,
            "drips_percent": 20.0,  # Highly divergent, but baseline is not ready!
            "battery_drain_percent": 5.0,
            "battery_drain_rate_mw": 5000.0,
        }])
        test_features = build_sleepstudy_features(test_session)

        anomalies = detect_anomalies(test_features, baseline, metrics=["drips_percent"])
        res = anomalies.iloc[0]

        # Requirement: never label anomalous when baseline is unavailable/insufficient
        assert bool(res["is_anomaly"]) is False
        assert res["status"] == "insufficient_history"
        assert pd.isna(res["deviation_score"])
        assert "insufficient history" in res["reason"]

    def test_missing_metric_in_observation_is_handled(self) -> None:
        train_df = build_sleepstudy_features(_make_training_sessions("BOX-READY", 15))
        baseline = build_baseline(train_df, min_observations=10)

        # Test session where DRIPS is null
        test_session = pd.DataFrame([{
            "machine_id": "BOX-READY",
            "start_time": "2026-09-02T12:00:00Z",
            "end_time": "2026-09-02T12:30:00Z",
            "duration_seconds": 1800.0,
            "drips_percent": None,
            "battery_drain_percent": 2.0,
            "battery_drain_rate_mw": 3000.0,
        }])
        test_features = build_sleepstudy_features(test_session)

        anomalies = detect_anomalies(test_features, baseline, metrics=["drips_percent"])
        res = anomalies.iloc[0]

        assert bool(res["is_anomaly"]) is False
        assert res["status"] == "missing_metric"
        assert pd.isna(res["observed_value"])
        assert pd.isna(res["deviation_score"])
        assert "missing or null" in res["reason"]

    def test_no_cross_machine_baseline_leakage(self) -> None:
        # Machine Alpha has high baseline (~95%), Machine Beta has low baseline (~50%)
        alpha_train = _make_training_sessions("MACHINE-ALPHA", 15, drips_center=95.0)
        beta_train = _make_training_sessions("MACHINE-BETA", 15, drips_center=50.0)
        baseline = build_baseline(build_sleepstudy_features(pd.concat([alpha_train, beta_train])))

        # Test observation: 50.0% DRIPS
        # For Machine Alpha: 50.0% is a massive anomaly!
        # For Machine Beta: 50.0% is normal!
        session_alpha = pd.DataFrame([{
            "machine_id": "MACHINE-ALPHA",
            "start_time": "2026-09-02T10:00:00Z",
            "end_time": "2026-09-02T10:30:00Z",
            "duration_seconds": 1800.0,
            "drips_percent": 50.0,
            "battery_drain_percent": 2.0,
            "battery_drain_rate_mw": 3000.0,
        }])
        session_beta = pd.DataFrame([{
            "machine_id": "MACHINE-BETA",
            "start_time": "2026-09-02T10:00:00Z",
            "end_time": "2026-09-02T10:30:00Z",
            "duration_seconds": 1800.0,
            "drips_percent": 50.0,
            "battery_drain_percent": 2.0,
            "battery_drain_rate_mw": 3000.0,
        }])

        res_alpha = detect_anomalies(build_sleepstudy_features(session_alpha), baseline, metrics=["drips_percent"]).iloc[0]
        res_beta = detect_anomalies(build_sleepstudy_features(session_beta), baseline, metrics=["drips_percent"]).iloc[0]

        assert bool(res_alpha["is_anomaly"]) is True
        assert res_alpha["status"] == "anomaly"
        assert res_alpha["baseline_median"] == 95.0

        assert bool(res_beta["is_anomaly"]) is False
        assert res_beta["status"] == "normal"
        assert res_beta["baseline_median"] == 50.0

    def test_zero_mad_baseline_anomaly_detection(self) -> None:
        # 15 sessions with identical 100.0% DRIPS -> MAD is 0
        train_sessions = []
        for i in range(15):
            train_sessions.append({
                "machine_id": "BOX-PERFECT",
                "start_time": f"2026-09-01T{10 + (i % 10):02d}:00:00Z",
                "end_time": f"2026-09-01T{10 + (i % 10):02d}:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 100.0,
                "battery_drain_percent": 1.0,
                "battery_drain_rate_mw": 2000.0,
            })
        baseline = build_baseline(build_sleepstudy_features(pd.DataFrame(train_sessions)))

        # 1. Normal session with 100.0% DRIPS
        norm_sess = pd.DataFrame([{
            "machine_id": "BOX-PERFECT",
            "start_time": "2026-09-02T10:00:00Z",
            "end_time": "2026-09-02T10:30:00Z",
            "duration_seconds": 1800.0,
            "drips_percent": 100.0,
            "battery_drain_percent": 1.0,
            "battery_drain_rate_mw": 2000.0,
        }])
        res_norm = detect_anomalies(build_sleepstudy_features(norm_sess), baseline, metrics=["drips_percent"]).iloc[0]
        assert bool(res_norm["is_anomaly"]) is False
        assert res_norm["deviation_score"] == 0.0

        # 2. Regression session with 80.0% DRIPS
        reg_sess = pd.DataFrame([{
            "machine_id": "BOX-PERFECT",
            "start_time": "2026-09-02T11:00:00Z",
            "end_time": "2026-09-02T11:30:00Z",
            "duration_seconds": 1800.0,
            "drips_percent": 80.0,
            "battery_drain_percent": 1.0,
            "battery_drain_rate_mw": 2000.0,
        }])
        res_reg = detect_anomalies(build_sleepstudy_features(reg_sess), baseline, metrics=["drips_percent"]).iloc[0]
        # Must detect anomaly without crashing with ZeroDivisionError or infinite float
        assert bool(res_reg["is_anomaly"]) is True
        assert res_reg["status"] == "anomaly"
        assert not np.isinf(res_reg["deviation_score"])

    def test_row_traceability_to_source_dataframe(self) -> None:
        train_df = build_sleepstudy_features(_make_training_sessions("BOX-TRACE", 15))
        baseline = build_baseline(train_df)

        test_sessions = pd.DataFrame([
            {
                "machine_id": "BOX-TRACE",
                "start_time": "2026-09-02T10:00:00Z",
                "end_time": "2026-09-02T10:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 95.0,
                "battery_drain_percent": 2.0,
                "battery_drain_rate_mw": 3000.0,
            },
            {
                "machine_id": "BOX-TRACE",
                "start_time": "2026-09-02T12:00:00Z",
                "end_time": "2026-09-02T12:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 50.0,
                "battery_drain_percent": 2.0,
                "battery_drain_rate_mw": 3000.0,
            },
        ], index=[101, 202])  # Non-standard indices
        test_features = build_sleepstudy_features(test_sessions)

        anomalies = detect_anomalies(test_features, baseline, metrics=["drips_percent"])
        assert list(anomalies["source_row_index"]) == [101, 202]

    def test_deterministic_output_across_repeated_runs(self) -> None:
        train_df = build_sleepstudy_features(_make_training_sessions("BOX-DET", 15))
        baseline = build_baseline(train_df)
        test_features = build_sleepstudy_features(_make_training_sessions("BOX-DET", 2))

        run1 = detect_anomalies(test_features, baseline)
        run2 = detect_anomalies(test_features, baseline)

        pd.testing.assert_frame_equal(run1, run2)
