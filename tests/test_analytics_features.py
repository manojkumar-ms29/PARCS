"""Tests for PARCS SleepStudy feature engineering.

Verifies schema validation, timestamp normalization, null preservation,
range validation, and caller immutability using synthetic fixtures.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analytics.features import (
    REQUIRED_SESSION_COLUMNS,
    SLEEPSTUDY_FEATURE_COLUMNS,
    build_sleepstudy_features,
)


def _make_synthetic_sessions(n: int = 5, machine_id: str = "SYNTHETIC-BOX") -> pd.DataFrame:
    """Generate deterministic synthetic session rows for testing."""
    records = []
    for i in range(n):
        records.append({
            "machine_id": machine_id,
            "start_time": f"2026-09-01T{10 + i:02d}:00:00Z",
            "end_time": f"2026-09-01T{10 + i:02d}:30:00Z",
            "duration_seconds": 1800.0,
            "drips_percent": 90.0 + (i % 5),
            "battery_drain_percent": 2.0 + (i * 0.5),
            "battery_drain_rate_mw": 3000.0 + (i * 100),
        })
    return pd.DataFrame(records)


class TestSleepStudyFeatures:
    def test_empty_dataframe_returns_feature_schema(self) -> None:
        empty_input = pd.DataFrame(columns=list(REQUIRED_SESSION_COLUMNS))
        features = build_sleepstudy_features(empty_input)

        assert features.empty
        for col in SLEEPSTUDY_FEATURE_COLUMNS:
            assert col in features.columns

    def test_missing_required_columns_raises_value_error(self) -> None:
        incomplete = pd.DataFrame({
            "machine_id": ["BOX-1"],
            "start_time": ["2026-09-01T10:00:00Z"],
            # Missing duration_seconds, drips_percent, etc.
        })
        with pytest.raises(ValueError, match="missing required SleepStudy columns"):
            build_sleepstudy_features(incomplete)

    def test_invalid_type_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="Expected pandas DataFrame"):
            build_sleepstudy_features([{"machine_id": "BOX-1"}])  # type: ignore[arg-type]

    def test_caller_dataframe_is_not_mutated(self) -> None:
        raw = _make_synthetic_sessions(3)
        raw_copy = raw.copy(deep=True)

        features = build_sleepstudy_features(raw)

        # Raw dataframe columns and values must be strictly identical
        pd.testing.assert_frame_equal(raw, raw_copy)
        # Features must be a distinct object
        assert features is not raw

    def test_timestamp_normalization_to_utc(self) -> None:
        df = _make_synthetic_sessions(2)
        df["start_time"] = ["2026-09-01 10:00:00+00:00", "2026-09-01T12:00:00Z"]
        df["end_time"] = ["2026-09-01 11:00:00+00:00", "2026-09-01T13:00:00Z"]

        features = build_sleepstudy_features(df)

        assert pd.api.types.is_datetime64_any_dtype(features["start_time"])
        assert features["start_time"].dt.tz is not None
        assert features["end_time"].dt.tz is not None

    def test_unparseable_timestamps_become_nat(self) -> None:
        df = _make_synthetic_sessions(2)
        df.loc[0, "start_time"] = "invalid-date-string"

        features = build_sleepstudy_features(df)
        assert pd.isna(features.loc[0, "start_time"])

    def test_null_metrics_preserved_as_nan(self) -> None:
        df = _make_synthetic_sessions(2)
        df.loc[0, "drips_percent"] = None
        df.loc[0, "battery_drain_percent"] = np.nan
        df.loc[0, "battery_drain_rate_mw"] = None

        features = build_sleepstudy_features(df)

        # Must remain NaN and NOT be filled with 0
        assert pd.isna(features.loc[0, "drips_percent"])
        assert pd.isna(features.loc[0, "battery_drain_percent"])
        assert pd.isna(features.loc[0, "battery_drain_rate_mw"])
        assert features.loc[0, "drips_percent"] != 0

    def test_invalid_numerical_ranges_coerced_to_nan(self) -> None:
        df = _make_synthetic_sessions(4)
        df.loc[0, "drips_percent"] = 120.0  # > 100
        df.loc[1, "drips_percent"] = -5.0   # < 0
        df.loc[2, "battery_drain_percent"] = 105.0  # > 100
        df.loc[3, "battery_drain_rate_mw"] = -50.0  # < 0

        features = build_sleepstudy_features(df)

        assert pd.isna(features.loc[0, "drips_percent"])
        assert pd.isna(features.loc[1, "drips_percent"])
        assert pd.isna(features.loc[2, "battery_drain_percent"])
        assert pd.isna(features.loc[3, "battery_drain_rate_mw"])

    def test_duration_hours_derived_correctly(self) -> None:
        df = _make_synthetic_sessions(1)
        df.loc[0, "duration_seconds"] = 7200.0

        features = build_sleepstudy_features(df)

        assert features.loc[0, "duration_hours"] == 2.0

    def test_derive_duration_from_timestamps_flag(self) -> None:
        df = _make_synthetic_sessions(1)
        df.loc[0, "start_time"] = "2026-09-01T10:00:00Z"
        df.loc[0, "end_time"] = "2026-09-01T11:00:00Z"
        df.loc[0, "duration_seconds"] = np.nan

        # When flag is False (default): duration remains NaN
        f_default = build_sleepstudy_features(df, derive_duration_from_timestamps=False)
        assert pd.isna(f_default.loc[0, "duration_seconds"])

        # When flag is True: duration is derived as 3600 seconds
        f_derived = build_sleepstudy_features(df, derive_duration_from_timestamps=True)
        assert f_derived.loc[0, "duration_seconds"] == 3600.0
        assert f_derived.loc[0, "duration_hours"] == 1.0

    def test_collected_at_preserved_when_present(self) -> None:
        df = _make_synthetic_sessions(2)
        df["collected_at"] = ["2026-09-01T12:00:00Z", "2026-09-01T12:00:00Z"]

        features = build_sleepstudy_features(df)
        assert "collected_at" in features.columns
        assert pd.api.types.is_datetime64_any_dtype(features["collected_at"])
