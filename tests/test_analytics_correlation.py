"""Tests for PARCS Change Correlation MVP.

Verifies deterministic temporal matching, machine isolation, boundary equality,
before vs after ordering, explicit no-match representations, non-causal explainability,
handling of missing/invalid timestamps and schemas, duplicate timestamps,
empty inputs, and integration with collectors and regression detection.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd
import pytest

from src.analytics.baseline import build_baseline
from src.analytics.correlation import (
    CHANGE_SCHEMA_COLUMNS,
    CORRELATION_SCHEMA_COLUMNS,
    DEFAULT_WINDOW_AFTER,
    DEFAULT_WINDOW_BEFORE,
    correlate_changes,
    extract_changes_from_collector_result,
    normalize_changes,
)
from src.analytics.features import build_sleepstudy_features
from src.analytics.regression import detect_regressions
from src.collectors.base import CollectorResult


# ======================================================================
# Test Helpers / Fixtures
# ======================================================================


def _make_regression_df(
    rows: list[dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """Helper to build a regressions DataFrame."""
    if rows is None:
        rows = []
    df = pd.DataFrame(rows)
    if "is_regression" not in df.columns and not df.empty:
        df["is_regression"] = True
    if "metric" not in df.columns and not df.empty:
        df["metric"] = "drips_percent"
    return df


def _make_change_df(
    rows: list[dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """Helper to build a changes DataFrame."""
    if rows is None:
        rows = []
    return pd.DataFrame(rows)


class TestChangeCorrelation:
    # ------------------------------------------------------------------
    # 1. A regression with one matching change
    # ------------------------------------------------------------------
    def test_single_matching_change_within_window(self) -> None:
        regressions = _make_regression_df([
            {
                "machine_id": "MACHINE-1",
                "start_time": "2026-09-01T10:00:00Z",
                "end_time": "2026-09-01T10:30:00Z",
                "metric": "drips_percent",
                "is_regression": True,
            }
        ])
        changes = _make_change_df([
            {
                "machine_id": "MACHINE-1",
                "timestamp": "2026-09-01T08:00:00Z",  # 2 hours before
                "change_type": "windows_update",
                "change_id": "KB5034204",
                "description": "Cumulative Update for Windows 11",
            }
        ])

        res = correlate_changes(
            regressions=regressions,
            changes=changes,
            window_before=timedelta(hours=4),
            window_after=timedelta(hours=1),
        )

        assert len(res) == 1
        row = res.iloc[0]
        assert row["machine_id"] == "MACHINE-1"
        assert row["metric"] == "drips_percent"
        assert bool(row["is_correlated"]) is True
        assert row["correlation_status"] == "correlated"
        assert row["change_id"] == "KB5034204"
        assert row["change_type"] == "windows_update"
        assert row["temporal_relation"] == "before"
        assert row["temporal_offset_seconds"] == -7200.0  # -2 hours
        assert "KB5034204" in row["reason"]
        assert "causation is not asserted" in row["reason"]
        assert row["reason"] == row["explanation"]

    # ------------------------------------------------------------------
    # 2. Multiple matching changes
    # ------------------------------------------------------------------
    def test_multiple_matching_changes_returned_separately(self) -> None:
        reg_time = "2026-09-01T10:00:00Z"
        regressions = _make_regression_df([
            {
                "machine_id": "MACHINE-1",
                "start_time": reg_time,
                "end_time": "2026-09-01T10:30:00Z",
                "metric": "battery_drain_rate_mw",
                "is_regression": True,
            }
        ])
        changes = _make_change_df([
            {
                "machine_id": "MACHINE-1",
                "timestamp": "2026-09-01T09:00:00Z",  # 1h before
                "change_type": "driver",
                "change_id": "PCI_VEN_8086",
                "description": "Intel Wi-Fi Driver v22.130",
            },
            {
                "machine_id": "MACHINE-1",
                "timestamp": "2026-09-01T10:30:00Z",  # 30m after
                "change_type": "windows_update",
                "change_id": "KB1234567",
                "description": "Defender Update",
            },
            {
                "machine_id": "MACHINE-1",
                "timestamp": "2026-09-01T08:00:00Z",  # 2h before
                "change_type": "event_log",
                "change_id": "Kernel-Power:506",
                "description": "System standby transition",
            },
        ])

        res = correlate_changes(
            regressions=regressions,
            changes=changes,
            window_before=timedelta(hours=3),
            window_after=timedelta(hours=1),
        )

        # Must produce 3 separate correlation records (do not combine unrelated changes)
        assert len(res) == 3
        assert all(res["is_correlated"])
        assert set(res["change_id"]) == {"PCI_VEN_8086", "KB1234567", "Kernel-Power:506"}

        # Deterministic chronological order of changes
        change_order = list(res["change_id"])
        assert change_order == ["Kernel-Power:506", "PCI_VEN_8086", "KB1234567"]

    # ------------------------------------------------------------------
    # 3. No matching changes
    # ------------------------------------------------------------------
    def test_no_matching_changes_explicit_representation(self) -> None:
        regressions = _make_regression_df([
            {
                "machine_id": "MACHINE-1",
                "start_time": "2026-09-01T10:00:00Z",
                "metric": "drips_percent",
                "is_regression": True,
            }
        ])
        # Changes present, but for a completely different time window
        changes = _make_change_df([
            {
                "machine_id": "MACHINE-1",
                "timestamp": "2026-08-01T10:00:00Z",  # 1 month prior
                "change_type": "driver",
                "change_id": "OLD_DRIVER",
                "description": "Old driver",
            }
        ])

        res = correlate_changes(
            regressions=regressions,
            changes=changes,
            window_before=timedelta(hours=24),
            window_after=timedelta(hours=2),
        )

        assert len(res) == 1
        row = res.iloc[0]
        assert row["machine_id"] == "MACHINE-1"
        assert bool(row["is_correlated"]) is False
        assert row["correlation_status"] == "no_matching_changes"
        assert pd.isna(row["change_id"]) or row["change_id"] is None
        assert pd.isna(row["change_timestamp"])
        assert np.isnan(row["temporal_offset_seconds"])
        assert row["temporal_relation"] == "none"
        assert "No system changes observed" in row["reason"]

    # ------------------------------------------------------------------
    # 4. Changes outside the temporal window
    # ------------------------------------------------------------------
    def test_changes_outside_window_excluded(self) -> None:
        reg_time = "2026-09-01T12:00:00Z"
        regressions = _make_regression_df([
            {"machine_id": "M1", "start_time": reg_time, "is_regression": True}
        ])
        # Window: [-2 hours, +1 hour] -> [10:00:00, 13:00:00]
        changes = _make_change_df([
            {"machine_id": "M1", "timestamp": "2026-09-01T09:59:59Z", "change_type": "driver", "change_id": "TOO_EARLY", "description": "Too early"},
            {"machine_id": "M1", "timestamp": "2026-09-01T13:00:01Z", "change_type": "driver", "change_id": "TOO_LATE", "description": "Too late"},
        ])

        res = correlate_changes(
            regressions=regressions,
            changes=changes,
            window_before=timedelta(hours=2),
            window_after=timedelta(hours=1),
        )

        assert len(res) == 1
        assert bool(res.iloc[0]["is_correlated"]) is False
        assert res.iloc[0]["correlation_status"] == "no_matching_changes"

    # ------------------------------------------------------------------
    # 5. Machine isolation
    # ------------------------------------------------------------------
    def test_machine_isolation_strictly_enforced(self) -> None:
        # Machine A has regression at 10:00
        regressions = _make_regression_df([
            {"machine_id": "MACHINE_A", "start_time": "2026-09-01T10:00:00Z", "metric": "drips_percent", "is_regression": True}
        ])
        # Machine B has a change at exactly the same time 10:00
        changes = _make_change_df([
            {"machine_id": "MACHINE_B", "timestamp": "2026-09-01T10:00:00Z", "change_type": "driver", "change_id": "DRV_B", "description": "Driver on Machine B"}
        ])

        res = correlate_changes(
            regressions=regressions,
            changes=changes,
            window_before=timedelta(hours=2),
            window_after=timedelta(hours=2),
        )

        # Machine A regression must NOT match Machine B change
        assert len(res) == 1
        assert res.iloc[0]["machine_id"] == "MACHINE_A"
        assert bool(res.iloc[0]["is_correlated"]) is False
        assert res.iloc[0]["correlation_status"] == "no_matching_changes"

    # ------------------------------------------------------------------
    # 6. Missing timestamps
    # ------------------------------------------------------------------
    def test_missing_regression_timestamp_yields_invalid_timestamp_status(self) -> None:
        regressions = _make_regression_df([
            {"machine_id": "M1", "start_time": None, "metric": "drips_percent", "is_regression": True}
        ])
        changes = _make_change_df([
            {"machine_id": "M1", "timestamp": "2026-09-01T10:00:00Z", "change_type": "driver", "change_id": "D1", "description": "Driver 1"}
        ])

        res = correlate_changes(regressions, changes)

        assert len(res) == 1
        row = res.iloc[0]
        assert bool(row["is_correlated"]) is False
        assert row["correlation_status"] == "invalid_timestamp"
        assert pd.isna(row["start_time"])
        assert "missing or invalid timestamp" in row["reason"]

    def test_missing_change_timestamp_ignored_during_matching(self) -> None:
        regressions = _make_regression_df([
            {"machine_id": "M1", "start_time": "2026-09-01T10:00:00Z", "is_regression": True}
        ])
        # One change with null timestamp, one valid change
        changes = _make_change_df([
            {"machine_id": "M1", "timestamp": None, "change_type": "driver", "change_id": "D_NULL", "description": "No timestamp"},
            {"machine_id": "M1", "timestamp": "2026-09-01T09:00:00Z", "change_type": "driver", "change_id": "D_VALID", "description": "Valid timestamp"},
        ])

        res = correlate_changes(
            regressions,
            changes,
            window_before=timedelta(hours=2),
            window_after=timedelta(hours=1),
        )

        # Only the valid timestamp change matches
        assert len(res) == 1
        assert res.iloc[0]["change_id"] == "D_VALID"
        assert bool(res.iloc[0]["is_correlated"]) is True


    # ------------------------------------------------------------------
    # 7. Invalid input schemas
    # ------------------------------------------------------------------
    def test_invalid_input_schemas_raise_errors(self) -> None:
        # Non-DataFrame regressions
        with pytest.raises(TypeError, match="Expected regressions as pandas DataFrame"):
            correlate_changes("not_a_df", _make_change_df())

        # Non-DataFrame changes
        with pytest.raises(TypeError, match="Expected changes as pandas DataFrame"):
            correlate_changes(_make_regression_df(), "not_a_df")

        # Regressions missing machine_id
        with pytest.raises(ValueError, match="regressions DataFrame is missing required columns"):
            correlate_changes(pd.DataFrame({"start_time": ["2026-09-01T10:00:00Z"]}), _make_change_df())

        # Regressions missing start_time
        with pytest.raises(ValueError, match="regressions DataFrame is missing required columns"):
            correlate_changes(pd.DataFrame({"machine_id": ["M1"]}), _make_change_df())

        # Changes missing machine_id
        bad_changes = pd.DataFrame({"timestamp": ["2026-09-01T10:00:00Z"], "change_type": ["drv"], "change_id": ["1"]})
        with pytest.raises(ValueError, match="missing required column: 'machine_id'"):
            correlate_changes(_make_regression_df([{"machine_id": "M1", "start_time": "2026-09-01T10:00:00Z"}]), bad_changes)

        # Changes missing timestamp
        bad_changes_ts = pd.DataFrame({"machine_id": ["M1"], "change_type": ["drv"], "change_id": ["1"]})
        with pytest.raises(ValueError, match="missing required timestamp column"):
            correlate_changes(_make_regression_df([{"machine_id": "M1", "start_time": "2026-09-01T10:00:00Z"}]), bad_changes_ts)

        # Changes missing change_type
        bad_changes_type = pd.DataFrame({"machine_id": ["M1"], "timestamp": ["2026-09-01T10:00:00Z"], "change_id": ["1"]})
        with pytest.raises(ValueError, match="missing required change type column"):
            correlate_changes(_make_regression_df([{"machine_id": "M1", "start_time": "2026-09-01T10:00:00Z"}]), bad_changes_type)

        # Negative window_before or window_after
        reg_ok = _make_regression_df([{"machine_id": "M1", "start_time": "2026-09-01T10:00:00Z"}])
        ch_ok = _make_change_df([{"machine_id": "M1", "timestamp": "2026-09-01T10:00:00Z", "change_type": "u", "change_id": "1"}])
        with pytest.raises(ValueError, match="window_before must be non-negative"):
            correlate_changes(reg_ok, ch_ok, window_before=timedelta(hours=-1))
        with pytest.raises(ValueError, match="window_after must be non-negative"):
            correlate_changes(reg_ok, ch_ok, window_after=timedelta(hours=-1))

        # Invalid time_anchor
        with pytest.raises(ValueError, match="time_anchor must be 'start_time', 'end_time', or 'interval'"):
            correlate_changes(reg_ok, ch_ok, time_anchor="invalid_anchor")

    # ------------------------------------------------------------------
    # 8. Temporal-window boundary equality
    # ------------------------------------------------------------------
    def test_window_boundary_equality(self) -> None:
        reg_time = "2026-09-01T10:00:00Z"
        regressions = _make_regression_df([
            {"machine_id": "M1", "start_time": reg_time, "is_regression": True}
        ])
        # Window: 1 hour before, 2 hours after -> [09:00:00, 12:00:00]
        # Test exact lower boundary, exact upper boundary, and 1 second outside each
        changes = _make_change_df([
            {"machine_id": "M1", "timestamp": "2026-09-01T08:59:59Z", "change_type": "driver", "change_id": "JUST_BEFORE", "description": "1s before window"},
            {"machine_id": "M1", "timestamp": "2026-09-01T09:00:00Z", "change_type": "driver", "change_id": "AT_LOWER_BOUND", "description": "exact lower bound"},
            {"machine_id": "M1", "timestamp": "2026-09-01T12:00:00Z", "change_type": "driver", "change_id": "AT_UPPER_BOUND", "description": "exact upper bound"},
            {"machine_id": "M1", "timestamp": "2026-09-01T12:00:01Z", "change_type": "driver", "change_id": "JUST_AFTER", "description": "1s after window"},
        ])

        res = correlate_changes(
            regressions=regressions,
            changes=changes,
            window_before=timedelta(hours=1),
            window_after=timedelta(hours=2),
        )

        matched_ids = list(res["change_id"])
        assert "AT_LOWER_BOUND" in matched_ids
        assert "AT_UPPER_BOUND" in matched_ids
        assert "JUST_BEFORE" not in matched_ids
        assert "JUST_AFTER" not in matched_ids
        assert len(res) == 2

    # ------------------------------------------------------------------
    # 9. Changes occurring before versus after a regression
    # ------------------------------------------------------------------
    def test_before_versus_after_ordering_and_semantics(self) -> None:
        reg_time = "2026-09-01T10:00:00Z"
        regressions = _make_regression_df([
            {"machine_id": "M1", "start_time": reg_time, "is_regression": True}
        ])
        changes = _make_change_df([
            {
                "machine_id": "M1",
                "timestamp": "2026-09-01T08:00:00Z",  # Antecedent (2 hours before)
                "change_type": "driver",
                "change_id": "ANTECEDENT_DRIVER",
                "description": "Driver update",
            },
            {
                "machine_id": "M1",
                "timestamp": "2026-09-01T10:00:00Z",  # Concurrent
                "change_type": "event_log",
                "change_id": "CONCURRENT_EVENT",
                "description": "Log event",
            },
            {
                "machine_id": "M1",
                "timestamp": "2026-09-01T11:00:00Z",  # Subsequent (1 hour after)
                "change_type": "windows_update",
                "change_id": "SUBSEQUENT_UPDATE",
                "description": "Windows update",
            },
        ])

        res = correlate_changes(
            regressions=regressions,
            changes=changes,
            window_before=timedelta(hours=3),
            window_after=timedelta(hours=2),
        )

        assert len(res) == 3
        # Row 1: Antecedent change
        r_before = res.iloc[0]
        assert r_before["change_id"] == "ANTECEDENT_DRIVER"
        assert r_before["temporal_relation"] == "before"
        assert r_before["temporal_offset_seconds"] == -7200.0
        assert "before regression onset" in r_before["reason"]

        # Row 2: Concurrent change
        r_conc = res.iloc[1]
        assert r_conc["change_id"] == "CONCURRENT_EVENT"
        assert r_conc["temporal_relation"] == "concurrent"
        assert r_conc["temporal_offset_seconds"] == 0.0
        assert "concurrently" in r_conc["reason"]

        # Row 3: Subsequent change
        r_after = res.iloc[2]
        assert r_after["change_id"] == "SUBSEQUENT_UPDATE"
        assert r_after["temporal_relation"] == "after"
        assert r_after["temporal_offset_seconds"] == 3600.0
        # Subsequent event must explicitly not claim causation of earlier regression
        assert "Subsequent event; cannot be antecedent to regression" in r_after["reason"]

    # ------------------------------------------------------------------
    # 10. Deterministic ordering of results
    # ------------------------------------------------------------------
    def test_deterministic_ordering_independent_of_input_row_order(self) -> None:
        regressions = _make_regression_df([
            {"machine_id": "BOX-B", "start_time": "2026-09-01T12:00:00Z", "source_row_index": 2, "metric": "drips_percent", "is_regression": True},
            {"machine_id": "BOX-A", "start_time": "2026-09-01T10:00:00Z", "source_row_index": 1, "metric": "drips_percent", "is_regression": True},
        ])
        changes = _make_change_df([
            {"machine_id": "BOX-A", "timestamp": "2026-09-01T10:30:00Z", "change_type": "update", "change_id": "U2", "description": "Update 2"},
            {"machine_id": "BOX-A", "timestamp": "2026-09-01T09:30:00Z", "change_type": "driver", "change_id": "D1", "description": "Driver 1"},
            {"machine_id": "BOX-B", "timestamp": "2026-09-01T11:00:00Z", "change_type": "driver", "change_id": "D2", "description": "Driver 2"},
        ])

        # Run 1: original order
        res1 = correlate_changes(regressions, changes)

        # Run 2: shuffled order
        shuffled_reg = regressions.sample(frac=1.0, random_state=42).reset_index(drop=True)
        shuffled_ch = changes.sample(frac=1.0, random_state=42).reset_index(drop=True)
        res2 = correlate_changes(shuffled_reg, shuffled_ch)

        # Results must be identical
        pd.testing.assert_frame_equal(res1, res2)

        # Verify sorted order: BOX-A comes before BOX-B
        assert list(res1["machine_id"]) == ["BOX-A", "BOX-A", "BOX-B"]

    # ------------------------------------------------------------------
    # 11. Empty regression and change inputs
    # ------------------------------------------------------------------
    def test_empty_inputs_handling(self) -> None:
        empty_reg = pd.DataFrame(columns=["machine_id", "start_time", "is_regression"])
        empty_ch = pd.DataFrame(columns=["machine_id", "timestamp", "change_type", "change_id", "description"])
        valid_reg = _make_regression_df([{"machine_id": "M1", "start_time": "2026-09-01T10:00:00Z", "is_regression": True}])

        # Both empty
        res_both_empty = correlate_changes(empty_reg, empty_ch)
        assert res_both_empty.empty
        for col in CORRELATION_SCHEMA_COLUMNS:
            assert col in res_both_empty.columns

        # Empty regressions, non-empty changes
        valid_ch = _make_change_df([{"machine_id": "M1", "timestamp": "2026-09-01T10:00:00Z", "change_type": "u", "change_id": "1", "description": "d"}])
        res_empty_reg = correlate_changes(empty_reg, valid_ch)
        assert res_empty_reg.empty

        # Non-empty regressions, empty changes -> explicit no_matching_changes
        res_empty_ch = correlate_changes(valid_reg, empty_ch)
        assert len(res_empty_ch) == 1
        assert bool(res_empty_ch.iloc[0]["is_correlated"]) is False
        assert res_empty_ch.iloc[0]["correlation_status"] == "no_matching_changes"

    # ------------------------------------------------------------------
    # 12. Duplicate change timestamps
    # ------------------------------------------------------------------
    def test_duplicate_change_timestamps_deterministic_tie_breaking(self) -> None:
        reg_time = "2026-09-01T10:00:00Z"
        regressions = _make_regression_df([
            {"machine_id": "M1", "start_time": reg_time, "is_regression": True}
        ])
        # Two changes at the exact same second
        changes = _make_change_df([
            {"machine_id": "M1", "timestamp": "2026-09-01T09:30:00Z", "change_type": "driver", "change_id": "DEV_A", "description": "Alpha Driver"},
            {"machine_id": "M1", "timestamp": "2026-09-01T09:30:00Z", "change_type": "driver", "change_id": "DEV_B", "description": "Beta Driver"},
        ])

        res = correlate_changes(regressions, changes)

        assert len(res) == 2
        # Both records are preserved and sorted deterministically
        assert list(res["change_id"]) == ["DEV_A", "DEV_B"]

    # ------------------------------------------------------------------
    # 13. Time anchor options ('start_time', 'end_time', 'interval')
    # ------------------------------------------------------------------
    def test_time_anchor_interval(self) -> None:
        # Session from 10:00 to 12:00
        regressions = _make_regression_df([
            {
                "machine_id": "M1",
                "start_time": "2026-09-01T10:00:00Z",
                "end_time": "2026-09-01T12:00:00Z",
                "is_regression": True,
            }
        ])
        # Change at 12:30 (outside start_time + 1h window, but inside interval + 1h window)
        changes = _make_change_df([
            {
                "machine_id": "M1",
                "timestamp": "2026-09-01T12:30:00Z",
                "change_type": "driver",
                "change_id": "DRV_INTERVAL",
                "description": "Driver after end_time",
            }
        ])

        # Under start_time anchor with window_after=1h: upper bound = 11:00 (12:30 is outside)
        res_start = correlate_changes(
            regressions, changes, window_before=timedelta(hours=1), window_after=timedelta(hours=1), time_anchor="start_time"
        )
        assert bool(res_start.iloc[0]["is_correlated"]) is False

        # Under interval anchor with window_after=1h: upper bound = 12:00 + 1h = 13:00 (12:30 matches!)
        res_interval = correlate_changes(
            regressions, changes, window_before=timedelta(hours=1), window_after=timedelta(hours=1), time_anchor="interval"
        )
        assert bool(res_interval.iloc[0]["is_correlated"]) is True
        assert res_interval.iloc[0]["change_id"] == "DRV_INTERVAL"


    # ------------------------------------------------------------------
    # 14. Normalization and collector result extraction
    # ------------------------------------------------------------------
    def test_normalize_changes_from_collector_results(self) -> None:
        cr_updates = CollectorResult(
            collector="updates",
            collected_at="2026-09-01T12:00:00Z",
            source="powershell",
            data=[
                {
                    "timestamp": "2026-09-01T08:00:00.0000000Z",
                    "title": "Windows Update KB5034204",
                    "kb_id": "KB5034204",
                    "update_id": "1234-uuid",
                }
            ],
        )

        cr_drivers = CollectorResult(
            collector="drivers",
            collected_at="2026-09-01T12:00:00Z",
            source="powershell",
            data=[
                {
                    "device_name": "Intel Wi-Fi",
                    "friendly_name": "Intel(R) Wi-Fi 6 AX201",
                    "provider": "Intel",
                    "version": "22.130.0.5",
                    "date": "2026-09-01T07:30:00.0000000Z",
                    "device_id": "PCI\\VEN_8086",
                }
            ],
        )

        cr_eventlog = CollectorResult(
            collector="eventlog",
            collected_at="2026-09-01T12:00:00Z",
            source="powershell",
            data=[
                {
                    "timestamp": "2026-09-01T09:00:00.0000000Z",
                    "event_id": 506,
                    "provider": "Kernel-Power",
                    "level": "Information",
                    "message": "Entering standby",
                }
            ],
        )

        norm_df = normalize_changes([cr_updates, cr_drivers, cr_eventlog], machine_id="TARGET-BOX")

        assert len(norm_df) == 3
        for col in CHANGE_SCHEMA_COLUMNS:
            assert col in norm_df.columns

        assert all(norm_df["machine_id"] == "TARGET-BOX")
        types = set(norm_df["change_type"])
        assert "windows_update" in types
        assert "driver" in types
        assert "event_log" in types

    # ------------------------------------------------------------------
    # 15. End-to-end integration with detect_regressions
    # ------------------------------------------------------------------
    def test_end_to_end_integration_with_detect_regressions(self) -> None:
        # Create synthetic baseline training data
        train_rows = []
        for i in range(12):
            train_rows.append({
                "machine_id": "TEST-RIG-01",
                "start_time": f"2026-08-{10 + i:02d}T10:00:00Z",
                "end_time": f"2026-08-{10 + i:02d}T10:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 95.0,
                "battery_drain_percent": 2.0,
                "battery_drain_rate_mw": 2500.0,
            })
        features_base = build_sleepstudy_features(pd.DataFrame(train_rows))
        baseline = build_baseline(features_base, min_observations=10)

        # Create evaluation sessions with sustained degradation in DRIPS (60% << 95%)
        eval_rows = []
        for i in range(4):
            eval_rows.append({
                "machine_id": "TEST-RIG-01",
                "start_time": f"2026-09-01T{10 + i:02d}:00:00Z",
                "end_time": f"2026-09-01T{10 + i:02d}:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 60.0,
                "battery_drain_percent": 2.0,
                "battery_drain_rate_mw": 2500.0,
            })
        features_eval = build_sleepstudy_features(pd.DataFrame(eval_rows))

        # Run regression detection
        reg_results = detect_regressions(
            features=features_eval,
            baseline=baseline,
            min_consecutive=3,
            metrics=["drips_percent"],
        )

        # Regressions should be detected on session 3 and 4
        assert (reg_results["is_regression"]).sum() >= 2

        # Create changes occurring before the first regression session
        changes = _make_change_df([
            {
                "machine_id": "TEST-RIG-01",
                "timestamp": "2026-09-01T08:00:00Z",
                "change_type": "driver",
                "change_id": "WIFI_FW_PATCH",
                "description": "Updated Wi-Fi firmware driver",
            }
        ])

        # Run change correlation
        corr_results = correlate_changes(
            regressions=reg_results,
            changes=changes,
            window_before=timedelta(hours=6),
            window_after=timedelta(hours=1),
            only_regressions=True,
        )

        assert not corr_results.empty
        assert all(corr_results["machine_id"] == "TEST-RIG-01")
        assert all(corr_results["metric"] == "drips_percent")
        assert all(corr_results["is_correlated"])
        assert all(corr_results["change_id"] == "WIFI_FW_PATCH")
        assert all(corr_results["temporal_relation"] == "before")
