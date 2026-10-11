"""Tests for PARCS SleepStudy regression detection.

Verifies deterministic sustained regression rules, metric directionality,
streak continuity and interruptions, machine isolation, handling of missing
and invalid data, and row traceability using synthetic fixtures.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analytics.baseline import build_baseline
from src.analytics.features import build_sleepstudy_features
from src.analytics.regression import (
    DEFAULT_MIN_CONSECUTIVE,
    DEFAULT_REGRESSION_THRESHOLD,
    REGRESSION_SCHEMA_COLUMNS,
    detect_regressions,
)


def _make_baseline_data(
    machine_id: str,
    n: int = 15,
    drips_center: float = 95.0,
    drain_center: float = 3000.0,
) -> pd.DataFrame:
    """Generate synthetic baseline training data with narrow variance."""
    rows = []
    for i in range(n):
        fl = (i % 3) - 1.0  # -1, 0, 1
        rows.append({
            "machine_id": machine_id,
            "start_time": f"2026-09-01T{10 + (i % 10):02d}:00:00Z",
            "end_time": f"2026-09-01T{10 + (i % 10):02d}:30:00Z",
            "duration_seconds": 1800.0,
            "drips_percent": drips_center + fl,
            "battery_drain_percent": 2.0,
            "battery_drain_rate_mw": drain_center + (fl * 50),
        })
    return pd.DataFrame(rows)


def _make_test_session(
    machine_id: str,
    start_time: str | None,
    end_time: str | None = None,
    drips_percent: float | None = 95.0,
    battery_drain_rate_mw: float | None = 3000.0,
    battery_drain_percent: float | None = 2.0,
    duration_seconds: float | None = 1800.0,
) -> dict[str, object]:
    """Generate a single synthetic session dictionary."""
    return {
        "machine_id": machine_id,
        "start_time": start_time,
        "end_time": end_time or (f"{start_time[:14]}30:00Z" if start_time else None),
        "duration_seconds": duration_seconds,
        "drips_percent": drips_percent,
        "battery_drain_percent": battery_drain_percent,
        "battery_drain_rate_mw": battery_drain_rate_mw,
    }


class TestRegressionDetection:
    # ------------------------------------------------------------------
    # 1. Empty input
    # ------------------------------------------------------------------
    def test_empty_input_returns_regression_schema(self) -> None:
        empty_features = pd.DataFrame(columns=["machine_id", "start_time", "end_time", "drips_percent"])
        empty_baseline = pd.DataFrame(columns=["machine_id", "metric", "median", "dispersion_scale", "readiness"])

        res = detect_regressions(empty_features, empty_baseline)
        assert res.empty
        for col in REGRESSION_SCHEMA_COLUMNS:
            assert col in res.columns

    # ------------------------------------------------------------------
    # 2. Missing required columns
    # ------------------------------------------------------------------
    def test_missing_required_columns_raises_value_error(self) -> None:
        incomplete_features = pd.DataFrame({"start_time": ["2026-09-01T10:00:00Z"]})  # missing machine_id
        baseline = pd.DataFrame({"machine_id": ["BOX-1"], "metric": ["drips_percent"]})

        with pytest.raises(ValueError, match="features DataFrame is missing required columns"):
            detect_regressions(incomplete_features, baseline)

    # ------------------------------------------------------------------
    # 3. Insufficient baseline history
    # ------------------------------------------------------------------
    def test_insufficient_baseline_history_yields_explicit_status(self) -> None:
        # Train with only 3 sessions (< 10)
        train_df = build_sleepstudy_features(_make_baseline_data("BOX-SPARSE", 3))
        baseline = build_baseline(train_df, min_observations=10)

        # Severe drop in DRIPS
        sessions = pd.DataFrame([
            _make_test_session("BOX-SPARSE", "2026-09-02T10:00:00Z", drips_percent=30.0),
            _make_test_session("BOX-SPARSE", "2026-09-02T11:00:00Z", drips_percent=30.0),
            _make_test_session("BOX-SPARSE", "2026-09-02T12:00:00Z", drips_percent=30.0),
        ])
        res = detect_regressions(sessions, baseline, metrics=["drips_percent"])

        for _, row in res.iterrows():
            assert bool(row["is_regression"]) is False
            assert row["status"] == "insufficient_history"
            assert row["consecutive_count"] == 0
            assert "insufficient history" in row["reason"]

    # ------------------------------------------------------------------
    # 4. Lower DRIPS sustained across sequence length
    # ------------------------------------------------------------------
    def test_lower_drips_sustained_across_sequence_length(self) -> None:
        # Baseline DRIPS ~ 95%
        train_df = build_sleepstudy_features(_make_baseline_data("BOX-DRIPS", 15, drips_center=95.0))
        baseline = build_baseline(train_df, min_observations=10)

        # 3 consecutive sessions with severe DRIPS regression (40%)
        sessions = pd.DataFrame([
            _make_test_session("BOX-DRIPS", "2026-09-02T10:00:00Z", drips_percent=40.0),
            _make_test_session("BOX-DRIPS", "2026-09-02T11:00:00Z", drips_percent=40.0),
            _make_test_session("BOX-DRIPS", "2026-09-02T12:00:00Z", drips_percent=40.0),
        ])
        res = detect_regressions(sessions, baseline, metrics=["drips_percent"], min_consecutive=3)

        assert len(res) == 3
        # Session 1: count=1, not yet sustained regression
        assert bool(res.iloc[0]["is_regression"]) is False
        assert res.iloc[0]["consecutive_count"] == 1
        assert res.iloc[0]["status"] == "not_regression"

        # Session 2: count=2, not yet sustained regression
        assert bool(res.iloc[1]["is_regression"]) is False
        assert res.iloc[1]["consecutive_count"] == 2
        assert res.iloc[1]["status"] == "not_regression"

        # Session 3: count=3, qualifies as sustained regression!
        assert bool(res.iloc[2]["is_regression"]) is True
        assert res.iloc[2]["consecutive_count"] == 3
        assert res.iloc[2]["status"] == "regression"
        assert "Sustained regression" in res.iloc[2]["reason"]
        # Non-causal assertion: must not claim drivers or updates caused it
        assert "driver" not in res.iloc[2]["reason"].lower()
        assert "update" not in res.iloc[2]["reason"].lower()

    # ------------------------------------------------------------------
    # 5. Higher battery drain sustained across sequence length
    # ------------------------------------------------------------------
    def test_higher_battery_drain_sustained_across_sequence_length(self) -> None:
        # Baseline drain rate ~ 3000 mW
        train_df = build_sleepstudy_features(_make_baseline_data("BOX-POWER", 15, drain_center=3000.0))
        baseline = build_baseline(train_df, min_observations=10)

        # 3 consecutive sessions with high drain (8500 mW)
        sessions = pd.DataFrame([
            _make_test_session("BOX-POWER", "2026-09-02T10:00:00Z", battery_drain_rate_mw=8500.0),
            _make_test_session("BOX-POWER", "2026-09-02T11:00:00Z", battery_drain_rate_mw=8500.0),
            _make_test_session("BOX-POWER", "2026-09-02T12:00:00Z", battery_drain_rate_mw=8500.0),
        ])
        res = detect_regressions(sessions, baseline, metrics=["battery_drain_rate_mw"], min_consecutive=3)

        assert bool(res.iloc[0]["is_regression"]) is False
        assert bool(res.iloc[1]["is_regression"]) is False
        assert bool(res.iloc[2]["is_regression"]) is True
        assert res.iloc[2]["status"] == "regression"
        assert res.iloc[2]["direction"] == "higher"

    # ------------------------------------------------------------------
    # 6. Single harmful outlier does not qualify as sustained regression
    # ------------------------------------------------------------------
    def test_single_harmful_outlier_does_not_qualify(self) -> None:
        train_df = build_sleepstudy_features(_make_baseline_data("BOX-OUTLIER", 15, drips_center=95.0))
        baseline = build_baseline(train_df, min_observations=10)

        # One harmful outlier followed by normal sessions
        sessions = pd.DataFrame([
            _make_test_session("BOX-OUTLIER", "2026-09-02T10:00:00Z", drips_percent=40.0),  # Outlier
            _make_test_session("BOX-OUTLIER", "2026-09-02T11:00:00Z", drips_percent=95.0),  # Normal
            _make_test_session("BOX-OUTLIER", "2026-09-02T12:00:00Z", drips_percent=95.0),  # Normal
        ])
        res = detect_regressions(sessions, baseline, metrics=["drips_percent"], min_consecutive=3)

        # The outlier alone must NOT be flagged as a regression
        assert bool(res.iloc[0]["is_regression"]) is False
        assert res.iloc[0]["consecutive_count"] == 1
        assert res.iloc[0]["status"] == "not_regression"
        assert "sequence length 1 < required 3" in res.iloc[0]["reason"]

    # ------------------------------------------------------------------
    # 7. Sequence interrupted by valid non-regression observation
    # ------------------------------------------------------------------
    def test_sequence_interrupted_by_valid_non_regression_observation(self) -> None:
        train_df = build_sleepstudy_features(_make_baseline_data("BOX-INTERRUPT", 15, drips_center=95.0))
        baseline = build_baseline(train_df, min_observations=10)

        # Harmful (1), Harmful (2), Normal (0 - reset!), Harmful (1), Harmful (2)
        sessions = pd.DataFrame([
            _make_test_session("BOX-INTERRUPT", "2026-09-02T10:00:00Z", drips_percent=40.0),
            _make_test_session("BOX-INTERRUPT", "2026-09-02T11:00:00Z", drips_percent=40.0),
            _make_test_session("BOX-INTERRUPT", "2026-09-02T12:00:00Z", drips_percent=95.0),  # Interruption!
            _make_test_session("BOX-INTERRUPT", "2026-09-02T13:00:00Z", drips_percent=40.0),
            _make_test_session("BOX-INTERRUPT", "2026-09-02T14:00:00Z", drips_percent=40.0),
        ])
        res = detect_regressions(sessions, baseline, metrics=["drips_percent"], min_consecutive=3)

        counts = list(res["consecutive_count"])
        assert counts == [1, 2, 0, 1, 2]
        # None should be flagged as regression since streak was interrupted
        assert not any(res["is_regression"])

    # ------------------------------------------------------------------
    # 8. Missing metric values
    # ------------------------------------------------------------------
    def test_missing_metric_values_break_continuity(self) -> None:
        train_df = build_sleepstudy_features(_make_baseline_data("BOX-NULLS", 15, drips_center=95.0))
        baseline = build_baseline(train_df, min_observations=10)

        # Harmful (1), Null (0 - reset!), Harmful (1)
        sessions = pd.DataFrame([
            _make_test_session("BOX-NULLS", "2026-09-02T10:00:00Z", drips_percent=40.0),
            _make_test_session("BOX-NULLS", "2026-09-02T11:00:00Z", drips_percent=None),  # Null!
            _make_test_session("BOX-NULLS", "2026-09-02T12:00:00Z", drips_percent=40.0),
        ])
        res = detect_regressions(sessions, baseline, metrics=["drips_percent"], min_consecutive=3)

        assert res.iloc[1]["status"] == "missing_metric"
        assert res.iloc[1]["consecutive_count"] == 0
        assert pd.isna(res.iloc[1]["observed_value"])
        # Missing data cannot bridge the gap to create a false streak
        assert res.iloc[2]["consecutive_count"] == 1

    # ------------------------------------------------------------------
    # 9. Missing or invalid timestamps
    # ------------------------------------------------------------------
    def test_invalid_timestamps_handled_and_break_continuity(self) -> None:
        train_df = build_sleepstudy_features(_make_baseline_data("BOX-TS", 15, drips_center=95.0))
        baseline = build_baseline(train_df, min_observations=10)

        sessions = pd.DataFrame([
            _make_test_session("BOX-TS", "2026-09-02T10:00:00Z", drips_percent=40.0),
            _make_test_session("BOX-TS", None, drips_percent=40.0),  # Missing timestamp
            _make_test_session("BOX-TS", "2026-09-02T12:00:00Z", drips_percent=40.0),
        ])
        res = detect_regressions(sessions, baseline, metrics=["drips_percent"], min_consecutive=3)

        invalid_row = res[res["status"] == "invalid_timestamp"].iloc[0]
        assert bool(invalid_row["is_regression"]) is False
        assert invalid_row["consecutive_count"] == 0
        assert "invalid or missing start_time" in invalid_row["reason"]

    # ------------------------------------------------------------------
    # 10. Different machines with different baselines
    # ------------------------------------------------------------------
    def test_different_machines_with_different_baselines(self) -> None:
        # Machine Alpha has high DRIPS (95%), Machine Beta has low DRIPS (50%)
        alpha_train = _make_baseline_data("MACHINE-ALPHA", 15, drips_center=95.0)
        beta_train = _make_baseline_data("MACHINE-BETA", 15, drips_center=50.0)
        baseline = build_baseline(build_sleepstudy_features(pd.concat([alpha_train, beta_train])))

        # Both machines experience 3 sessions of 50.0% DRIPS
        test_sessions = []
        for i in range(3):
            test_sessions.append(_make_test_session("MACHINE-ALPHA", f"2026-09-02T{10+i}:00:00Z", drips_percent=50.0))
            test_sessions.append(_make_test_session("MACHINE-BETA", f"2026-09-02T{10+i}:00:00Z", drips_percent=50.0))
        test_df = pd.DataFrame(test_sessions)

        res = detect_regressions(test_df, baseline, metrics=["drips_percent"], min_consecutive=3)

        alpha_res = res[res["machine_id"] == "MACHINE-ALPHA"]
        beta_res = res[res["machine_id"] == "MACHINE-BETA"]

        # For Machine Alpha: 50.0% is a severe regression! Session 3 must flag regression.
        assert bool(alpha_res.iloc[2]["is_regression"]) is True
        assert alpha_res.iloc[2]["status"] == "regression"

        # For Machine Beta: 50.0% is normal! None should flag regression.
        assert not any(beta_res["is_regression"])
        assert beta_res.iloc[2]["status"] == "not_regression"

    # ------------------------------------------------------------------
    # 11. Duplicate timestamps
    # ------------------------------------------------------------------
    def test_duplicate_timestamps_handled_deterministically(self) -> None:
        train_df = build_sleepstudy_features(_make_baseline_data("BOX-DUP", 15, drips_center=95.0))
        baseline = build_baseline(train_df, min_observations=10)

        # Multiple sessions with the exact same start_time
        sessions = pd.DataFrame([
            _make_test_session("BOX-DUP", "2026-09-02T10:00:00Z", end_time="2026-09-02T10:30:00Z", drips_percent=40.0),
            _make_test_session("BOX-DUP", "2026-09-02T10:00:00Z", end_time="2026-09-02T11:00:00Z", drips_percent=40.0),
            _make_test_session("BOX-DUP", "2026-09-02T10:00:00Z", end_time="2026-09-02T11:30:00Z", drips_percent=40.0),
        ])

        run1 = detect_regressions(sessions, baseline, metrics=["drips_percent"], min_consecutive=3)
        run2 = detect_regressions(sessions, baseline, metrics=["drips_percent"], min_consecutive=3)

        # Ordering and outcomes must be 100% deterministic
        pd.testing.assert_frame_equal(run1, run2)
        assert bool(run1.iloc[2]["is_regression"]) is True

    # ------------------------------------------------------------------
    # 12. Exactly the required number of qualifying observations
    # ------------------------------------------------------------------
    def test_exactly_required_consecutive_qualifies(self) -> None:
        train_df = build_sleepstudy_features(_make_baseline_data("BOX-EXACT", 15, drips_center=95.0))
        baseline = build_baseline(train_df, min_observations=10)

        sessions = pd.DataFrame([
            _make_test_session("BOX-EXACT", "2026-09-02T10:00:00Z", drips_percent=40.0),
            _make_test_session("BOX-EXACT", "2026-09-02T11:00:00Z", drips_percent=40.0),
            _make_test_session("BOX-EXACT", "2026-09-02T12:00:00Z", drips_percent=40.0),
        ])
        res = detect_regressions(sessions, baseline, metrics=["drips_percent"], min_consecutive=3)

        assert bool(res.iloc[0]["is_regression"]) is False
        assert bool(res.iloc[1]["is_regression"]) is False
        assert bool(res.iloc[2]["is_regression"]) is True
        assert res.iloc[2]["consecutive_count"] == 3

    # ------------------------------------------------------------------
    # 13. Sequence shorter than the configured minimum
    # ------------------------------------------------------------------
    def test_sequence_shorter_than_minimum_does_not_qualify(self) -> None:
        train_df = build_sleepstudy_features(_make_baseline_data("BOX-SHORT", 15, drips_center=95.0))
        baseline = build_baseline(train_df, min_observations=10)

        # 2 sessions when 3 are required
        sessions = pd.DataFrame([
            _make_test_session("BOX-SHORT", "2026-09-02T10:00:00Z", drips_percent=40.0),
            _make_test_session("BOX-SHORT", "2026-09-02T11:00:00Z", drips_percent=40.0),
        ])
        res = detect_regressions(sessions, baseline, metrics=["drips_percent"], min_consecutive=3)

        assert not any(res["is_regression"])
        assert list(res["consecutive_count"]) == [1, 2]

    # ------------------------------------------------------------------
    # 14. Deterministic results across repeated executions
    # ------------------------------------------------------------------
    def test_deterministic_results_across_repeated_runs(self) -> None:
        train_df = build_sleepstudy_features(_make_baseline_data("BOX-DETERM", 15))
        baseline = build_baseline(train_df)
        test_df = pd.DataFrame([
            _make_test_session("BOX-DETERM", "2026-09-02T10:00:00Z", drips_percent=40.0),
            _make_test_session("BOX-DETERM", "2026-09-02T11:00:00Z", drips_percent=40.0),
            _make_test_session("BOX-DETERM", "2026-09-02T12:00:00Z", drips_percent=40.0),
        ])

        run1 = detect_regressions(test_df, baseline)
        run2 = detect_regressions(test_df, baseline)

        pd.testing.assert_frame_equal(run1, run2)

    # ------------------------------------------------------------------
    # 15. Traceability to source DataFrame rows
    # ------------------------------------------------------------------
    def test_source_row_index_traceability(self) -> None:
        train_df = build_sleepstudy_features(_make_baseline_data("BOX-TRACE", 15))
        baseline = build_baseline(train_df)

        test_df = pd.DataFrame([
            _make_test_session("BOX-TRACE", "2026-09-02T10:00:00Z", drips_percent=40.0),
            _make_test_session("BOX-TRACE", "2026-09-02T11:00:00Z", drips_percent=40.0),
        ], index=[501, 702])  # Custom indices

        res = detect_regressions(test_df, baseline, metrics=["drips_percent"])
        assert list(res["source_row_index"]) == [501, 702]

    # ------------------------------------------------------------------
    # 16. Beneficially divergent observation is not a regression
    # ------------------------------------------------------------------
    def test_improving_observation_is_never_a_regression(self) -> None:
        # Baseline DRIPS is 60.0%
        train_df = build_sleepstudy_features(_make_baseline_data("BOX-IMPROVE", 15, drips_center=60.0))
        baseline = build_baseline(train_df, min_observations=10)

        # Device improves dramatically to 100.0% DRIPS
        sessions = pd.DataFrame([
            _make_test_session("BOX-IMPROVE", "2026-09-02T10:00:00Z", drips_percent=100.0),
            _make_test_session("BOX-IMPROVE", "2026-09-02T11:00:00Z", drips_percent=100.0),
            _make_test_session("BOX-IMPROVE", "2026-09-02T12:00:00Z", drips_percent=100.0),
        ])
        res = detect_regressions(sessions, baseline, metrics=["drips_percent"], min_consecutive=3)

        # Even though absolute difference is huge (|100 - 60| = 40), it is IMPROVEMENT, not regression!
        for _, row in res.iterrows():
            assert bool(row["is_regression"]) is False
            assert row["deviation_score"] < 0.0  # Negative score denotes improvement
            assert row["consecutive_count"] == 0
            assert "does not meet harmful deviation threshold" in row["reason"]
