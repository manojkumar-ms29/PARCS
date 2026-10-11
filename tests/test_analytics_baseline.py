"""Tests for PARCS machine-specific statistical baseline modeling.

Verifies isolation across machines, readiness thresholds, robust statistics
(Median, MAD, IQR), zero-MAD fallback, and exclusion auditing using synthetic fixtures.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analytics.baseline import (
    BASELINE_SCHEMA_COLUMNS,
    DEFAULT_BASELINE_METRICS,
    DEFAULT_MIN_OBSERVATIONS,
    build_baseline,
)
from src.analytics.features import build_sleepstudy_features


def _make_machine_sessions(
    machine_id: str,
    n: int,
    drips_values: list[float] | None = None,
    drain_rates: list[float] | None = None,
) -> pd.DataFrame:
    """Generate synthetic SleepStudy sessions for a specific machine."""
    rows = []
    for i in range(n):
        drips = drips_values[i % len(drips_values)] if drips_values else 90.0 + (i % 5)
        drain = drain_rates[i % len(drain_rates)] if drain_rates else 3000.0 + (i * 50)
        rows.append({
            "machine_id": machine_id,
            "start_time": f"2026-09-01T{10 + (i % 10):02d}:00:00Z",
            "end_time": f"2026-09-01T{10 + (i % 10):02d}:30:00Z",
            "duration_seconds": 1800.0,
            "drips_percent": drips,
            "battery_drain_percent": 2.5,
            "battery_drain_rate_mw": drain,
        })
    return pd.DataFrame(rows)


class TestStatisticalBaseline:
    def test_empty_input_returns_baseline_schema(self) -> None:
        empty_features = pd.DataFrame(columns=["machine_id"] + list(DEFAULT_BASELINE_METRICS))
        baseline = build_baseline(empty_features)

        assert baseline.empty
        for col in BASELINE_SCHEMA_COLUMNS:
            assert col in baseline.columns

    def test_missing_machine_id_column_raises_value_error(self) -> None:
        df = pd.DataFrame({"drips_percent": [90.0, 95.0]})
        with pytest.raises(ValueError, match="missing required column 'machine_id'"):
            build_baseline(df)

    def test_sufficient_observations_produces_ready_baseline(self) -> None:
        # Generate 15 observations (>= default min 10)
        drips_vals = [90.0, 91.0, 92.0, 92.0, 93.0, 94.0, 95.0, 95.0, 96.0, 97.0, 98.0, 98.0, 99.0, 99.0, 100.0]
        sessions = _make_machine_sessions("BOX-READY", 15, drips_values=drips_vals)
        features = build_sleepstudy_features(sessions)

        baseline = build_baseline(features, min_observations=10)

        drips_base = baseline[(baseline["machine_id"] == "BOX-READY") & (baseline["metric"] == "drips_percent")]
        assert len(drips_base) == 1
        row = drips_base.iloc[0]

        assert row["readiness"] == "ready"
        assert row["valid_count"] == 15
        assert row["excluded_count"] == 0
        assert row["median"] == 95.0
        assert row["mad"] > 0
        assert row["iqr"] > 0
        assert row["dispersion_scale"] > 0
        assert bool(row["zero_mad_fallback"]) is False

    def test_insufficient_observations_produces_insufficient_history(self) -> None:
        # Generate 5 observations (< min 10)
        sessions = _make_machine_sessions("BOX-SPARSE", 5)
        features = build_sleepstudy_features(sessions)

        baseline = build_baseline(features, min_observations=10)

        for _, row in baseline.iterrows():
            assert row["readiness"] == "insufficient_history"
            assert row["valid_count"] == 5
            assert row["min_observations"] == 10

    def test_strict_machine_isolation(self) -> None:
        # Machine Alpha has high DRIPS (~95%), Machine Beta has low DRIPS (~50%)
        alpha_sessions = _make_machine_sessions("MACHINE-ALPHA", 12, drips_values=[94.0, 95.0, 96.0])
        beta_sessions = _make_machine_sessions("MACHINE-BETA", 12, drips_values=[49.0, 50.0, 51.0])
        combined = pd.concat([alpha_sessions, beta_sessions], ignore_index=True)
        features = build_sleepstudy_features(combined)

        baseline = build_baseline(features)

        alpha_drips = baseline[(baseline["machine_id"] == "MACHINE-ALPHA") & (baseline["metric"] == "drips_percent")].iloc[0]
        beta_drips = baseline[(baseline["machine_id"] == "MACHINE-BETA") & (baseline["metric"] == "drips_percent")].iloc[0]

        assert alpha_drips["median"] == 95.0
        assert beta_drips["median"] == 50.0
        # Baselines must never be averaged across machines
        assert alpha_drips["median"] != beta_drips["median"]

    def test_zero_mad_fallback_handling(self) -> None:
        # All 15 sessions have identical DRIPS (100.0) -> MAD is 0
        sessions = _make_machine_sessions("BOX-ZERO-MAD", 15, drips_values=[100.0])
        features = build_sleepstudy_features(sessions)

        baseline = build_baseline(features, min_observations=10)

        row = baseline[(baseline["machine_id"] == "BOX-ZERO-MAD") & (baseline["metric"] == "drips_percent")].iloc[0]
        assert row["readiness"] == "ready"
        assert row["median"] == 100.0
        assert row["mad"] == 0.0
        assert bool(row["zero_mad_fallback"]) is True
        # Critical: dispersion_scale must be positive non-zero to prevent div-by-zero
        assert row["dispersion_scale"] > 0.0

    def test_iqr_fallback_when_mad_is_zero_with_some_variation(self) -> None:
        # Asymmetric distribution: values clustered at lower end so median=50, MAD=0, but upper tail gives IQR > 0
        vals = [50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        sessions = _make_machine_sessions("BOX-IQR-MAD", len(vals), drips_values=vals)
        features = build_sleepstudy_features(sessions)

        baseline = build_baseline(features, min_observations=10)

        row = baseline[(baseline["machine_id"] == "BOX-IQR-MAD") & (baseline["metric"] == "drips_percent")].iloc[0]
        assert row["mad"] == 0.0
        assert row["iqr"] > 0.0
        assert bool(row["zero_mad_fallback"]) is True
        assert row["dispersion_scale"] == pytest.approx(row["iqr"] / 1.3490, rel=1e-3)

    def test_null_measurements_excluded_and_audited(self) -> None:
        # 12 sessions total, but 4 have null battery_drain_rate_mw
        sessions = _make_machine_sessions("BOX-NULLS", 12)
        sessions.loc[0:3, "battery_drain_rate_mw"] = None
        features = build_sleepstudy_features(sessions)

        baseline = build_baseline(features, min_observations=10)

        row = baseline[(baseline["machine_id"] == "BOX-NULLS") & (baseline["metric"] == "battery_drain_rate_mw")].iloc[0]
        assert row["observation_count"] == 12
        assert row["valid_count"] == 8
        assert row["excluded_count"] == 4
        # 8 valid < min_observations 10 -> insufficient history
        assert row["readiness"] == "insufficient_history"

    def test_deterministic_output_across_repeated_runs(self) -> None:
        sessions = _make_machine_sessions("BOX-DETERMINISTIC", 15)
        features = build_sleepstudy_features(sessions)

        base1 = build_baseline(features)
        base2 = build_baseline(features)

        pd.testing.assert_frame_equal(base1, base2)
