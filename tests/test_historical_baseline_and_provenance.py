"""Deterministic tests for Historical Baseline Evaluation and Data Provenance.

Demonstrates:
  1. Historical observations establish the reference baseline.
  2. Later degraded observations are evaluated against that reference baseline.
  3. Evaluation observations do not alter the baseline used to score themselves
     (including a dedicated contamination guard test that fails if baseline is
     built across the whole dataset).
  4. Chronological ordering is deterministic.
  5. Insufficient reference history produces explicit unready states without false alarms.
  6. Machine isolation: different machines cannot influence one another's baselines.
  7. Regression and correlation outputs remain fully compatible.
  8. Machine-specific synthetic-data provenance in all-real, all-synthetic, and mixed datasets.
"""

from __future__ import annotations

from datetime import timedelta
import pandas as pd
import pytest

from src.analytics.baseline import build_baseline
from src.analytics.correlation import correlate_changes
from src.analytics.features import build_sleepstudy_features
from src.analytics.regression import detect_regressions
from src.api.service import AnalyticsService


class TestHistoricalBaselineEvaluation:
    """Tests proving prospective evaluation against clean historical baselines."""

    def test_historical_observations_establish_baseline_and_score_subsequent_degradation(self) -> None:
        """Historical normal observations establish reference baseline; degraded sessions are evaluated against it."""
        # 12 normal sessions (August: DRIPS ~ 95%)
        rows = [
            {
                "machine_id": "TEST-PC-01",
                "start_time": f"2026-08-{10 + i:02d}T10:00:00Z",
                "end_time": f"2026-08-{10 + i:02d}T10:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 95.0,
                "battery_drain_percent": 2.0,
                "battery_drain_rate_mw": 2400.0,
            }
            for i in range(12)
        ]
        # 4 degraded sessions (September: DRIPS ~ 55%)
        rows += [
            {
                "machine_id": "TEST-PC-01",
                "start_time": f"2026-09-01T{10 + i:02d}:00:00Z",
                "end_time": f"2026-09-01T{10 + i:02d}:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 55.0,
                "battery_drain_percent": 4.5,
                "battery_drain_rate_mw": 5200.0,
            }
            for i in range(4)
        ]
        sessions_df = pd.DataFrame(rows)
        features_df = build_sleepstudy_features(sessions_df)

        # Partition features via AnalyticsService
        ref_df, eval_df = AnalyticsService.partition_machine_features(features_df, min_observations=10)

        assert len(ref_df) == 12
        assert len(eval_df) == 4

        # Reference baseline describes historical sessions only
        baseline_df = build_baseline(ref_df, min_observations=10)
        drips_base = baseline_df[baseline_df["metric"] == "drips_percent"].iloc[0]
        assert drips_base["readiness"] == "ready"
        assert drips_base["valid_count"] == 12
        assert drips_base["median"] == 95.0

        # Evaluate subsequent degraded observations against reference baseline
        reg_df = detect_regressions(features=eval_df, baseline=baseline_df, threshold=2.0, min_consecutive=3)
        assert len(reg_df) > 0

        # The degraded sessions qualify and form sustained regressions
        flagged = reg_df[reg_df["is_regression"] & (reg_df["metric"] == "drips_percent")]
        assert len(flagged) >= 2
        assert all(flagged["baseline_median"] == 95.0)

    def test_contamination_guard_fails_if_baseline_built_across_entire_dataset(self) -> None:
        """CRITICAL TEST: Proves that degraded observations alter the baseline if not separated.

        This test explicitly verifies that:
          1. The partitioned reference baseline median remains 95.0.
          2. A naive baseline computed across the whole dataset shifts to 72.5.
          3. Demonstrates why separating reference observations is essential.
        """
        # 10 normal sessions (DRIPS = 95.0)
        normal_rows = [
            {
                "machine_id": "CONTAM-PC",
                "start_time": f"2026-08-{10 + i:02d}T10:00:00Z",
                "end_time": f"2026-08-{10 + i:02d}T10:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 95.0,
                "battery_drain_percent": 2.0,
                "battery_drain_rate_mw": 2400.0,
            }
            for i in range(10)
        ]
        # 10 severely degraded sessions (DRIPS = 50.0)
        degraded_rows = [
            {
                "machine_id": "CONTAM-PC",
                "start_time": f"2026-09-01T{10 + i:02d}:00:00Z",
                "end_time": f"2026-09-01T{10 + i:02d}:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 50.0,
                "battery_drain_percent": 5.0,
                "battery_drain_rate_mw": 5500.0,
            }
            for i in range(10)
        ]
        all_features = build_sleepstudy_features(pd.DataFrame(normal_rows + degraded_rows))

        # 1. Clean reference partition
        ref_df, eval_df = AnalyticsService.partition_machine_features(all_features, min_observations=10)
        clean_baseline = build_baseline(ref_df, min_observations=10)
        clean_drips_median = clean_baseline[clean_baseline["metric"] == "drips_percent"]["median"].iloc[0]

        # 2. Contaminated naive baseline (computed over all features)
        contaminated_baseline = build_baseline(all_features, min_observations=10)
        contaminated_drips_median = contaminated_baseline[contaminated_baseline["metric"] == "drips_percent"]["median"].iloc[0]

        # Assert clean baseline is unaffected by later degraded sessions
        assert clean_drips_median == 95.0
        # Assert naive baseline is contaminated (median shifts from 95.0 down to 72.5)
        assert contaminated_drips_median == 72.5
        assert clean_drips_median != contaminated_drips_median

        # If an implementation reverted to building baseline over all observations,
        # clean_drips_median would become 72.5, which would fail this assertion:
        assert clean_drips_median == 95.0

    def test_chronological_ordering_is_deterministic(self) -> None:
        """Sessions passed in shuffled order must be deterministically sorted chronologically."""
        rows = [
            {
                "machine_id": "SHUFFLE-PC",
                "start_time": f"2026-08-{day:02d}T10:00:00Z",
                "end_time": f"2026-08-{day:02d}T10:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 95.0,
                "battery_drain_percent": 2.0,
                "battery_drain_rate_mw": 2400.0,
            }
            for day in [15, 11, 20, 10, 18, 12, 14, 16, 13, 17, 19, 21]
        ]
        shuffled_df = build_sleepstudy_features(pd.DataFrame(rows))
        ref_df, _ = AnalyticsService.partition_machine_features(shuffled_df, min_observations=10, reference_count=10)

        # Must be in chronological order
        timestamps = ref_df["start_time"].tolist()
        assert timestamps == sorted(timestamps)
        assert str(timestamps[0]).startswith("2026-08-10")
        assert str(timestamps[-1]).startswith("2026-08-19")

    def test_insufficient_reference_history_produces_explicit_unready_states(self) -> None:
        """When historical reference observations < min_observations, returns explicit insufficient_history."""
        rows = [
            {
                "machine_id": "SPARSE-PC",
                "start_time": f"2026-09-0{i+1}T10:00:00Z",
                "end_time": f"2026-09-0{i+1}T10:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 50.0,
                "battery_drain_percent": 5.0,
                "battery_drain_rate_mw": 5000.0,
            }
            for i in range(4)
        ]
        sparse_df = build_sleepstudy_features(pd.DataFrame(rows))
        ref_df, eval_df = AnalyticsService.partition_machine_features(sparse_df, min_observations=10)

        baseline_df = build_baseline(ref_df, min_observations=10)
        assert all(baseline_df["readiness"] == "insufficient_history")

        reg_df = detect_regressions(eval_df, baseline_df)
        assert len(reg_df) > 0
        assert all(reg_df["status"] == "insufficient_history")
        assert not any(reg_df["is_regression"])

    def test_machine_isolation_in_partitioning_and_evaluation(self) -> None:
        """Observations from different machines must never be mixed or contaminate each other."""
        rows_pc1 = [
            {
                "machine_id": "ISOLATED-A",
                "start_time": f"2026-08-{10 + i:02d}T10:00:00Z",
                "end_time": f"2026-08-{10 + i:02d}T10:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 98.0,
                "battery_drain_percent": 1.0,
                "battery_drain_rate_mw": 1500.0,
            }
            for i in range(12)
        ]
        rows_pc2 = [
            {
                "machine_id": "ISOLATED-B",
                "start_time": f"2026-08-{10 + i:02d}T10:00:00Z",
                "end_time": f"2026-08-{10 + i:02d}T10:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 70.0,
                "battery_drain_percent": 3.0,
                "battery_drain_rate_mw": 3500.0,
            }
            for i in range(12)
        ]
        combined_features = build_sleepstudy_features(pd.DataFrame(rows_pc1 + rows_pc2))

        # Partition each machine independently
        ref_a, _ = AnalyticsService.partition_machine_features(
            combined_features[combined_features["machine_id"] == "ISOLATED-A"]
        )
        ref_b, _ = AnalyticsService.partition_machine_features(
            combined_features[combined_features["machine_id"] == "ISOLATED-B"]
        )

        base_a = build_baseline(ref_a, min_observations=10)
        base_b = build_baseline(ref_b, min_observations=10)

        drips_a = base_a[base_a["metric"] == "drips_percent"]["median"].iloc[0]
        drips_b = base_b[base_b["metric"] == "drips_percent"]["median"].iloc[0]

        assert drips_a == 98.0
        assert drips_b == 70.0

    def test_regression_and_correlation_compatibility(self) -> None:
        """Regressions produced by historical baseline evaluation seamlessly correlate with system changes."""
        rows = [
            {
                "machine_id": "CORR-TEST-PC",
                "start_time": f"2026-08-{10 + i:02d}T10:00:00Z",
                "end_time": f"2026-08-{10 + i:02d}T10:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 95.0,
                "battery_drain_percent": 2.0,
                "battery_drain_rate_mw": 2400.0,
            }
            for i in range(12)
        ] + [
            {
                "machine_id": "CORR-TEST-PC",
                "start_time": f"2026-09-01T{10 + i:02d}:00:00Z",
                "end_time": f"2026-09-01T{10 + i:02d}:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 55.0,
                "battery_drain_percent": 4.5,
                "battery_drain_rate_mw": 5200.0,
            }
            for i in range(4)
        ]
        features_df = build_sleepstudy_features(pd.DataFrame(rows))
        ref_df, eval_df = AnalyticsService.partition_machine_features(features_df, min_observations=10)
        base_df = build_baseline(ref_df, min_observations=10)
        reg_df = detect_regressions(eval_df, base_df, threshold=2.0, min_consecutive=3)

        changes_df = pd.DataFrame([
            {
                "machine_id": "CORR-TEST-PC",
                "timestamp": "2026-09-01T08:00:00Z",
                "change_type": "driver",
                "change_id": "DEV-TEST-001",
                "description": "Test Display Driver",
            }
        ])

        corr_df = correlate_changes(
            regressions=reg_df,
            changes=changes_df,
            window_before=timedelta(hours=24),
            only_regressions=True,
        )

        assert not corr_df.empty
        assert all(corr_df["is_correlated"])
        assert all(corr_df["change_id"] == "DEV-TEST-001")
        assert all(corr_df["temporal_relation"] == "before")


class TestSyntheticDataProvenance:
    """Tests proving machine-scoped provenance and prevention of false synthetic flags."""

    def test_all_real_machines_provenance(self, monkeypatch) -> None:
        """When all machines are real, provenance is False for all and is_synthetic is False."""
        real_df = pd.DataFrame([
            {
                "machine_id": "REAL-HOST-01",
                "start_time": "2026-08-10T10:00:00Z",
                "end_time": "2026-08-10T10:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 95.0,
                "battery_drain_percent": 2.0,
                "battery_drain_rate_mw": 2400.0,
                "is_synthetic": False,
            }
        ])
        svc = AnalyticsService()
        monkeypatch.setattr(svc, "load_sessions_df", lambda: real_df)
        monkeypatch.setattr(svc, "load_changes_df", lambda: pd.DataFrame())

        summary = svc.get_telemetry_summary()
        assert summary["is_synthetic"] is False
        assert summary["has_mixed_provenance"] is False
        assert summary["machine_provenance"] == {"REAL-HOST-01": False}

    def test_all_synthetic_machines_provenance(self, monkeypatch) -> None:
        """When all machines are synthetic, provenance is True for all and is_synthetic is True."""
        synth_df = pd.DataFrame([
            {
                "machine_id": "DEMO-MACHINE-READY",
                "start_time": "2026-08-10T10:00:00Z",
                "end_time": "2026-08-10T10:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 95.0,
                "battery_drain_percent": 2.0,
                "battery_drain_rate_mw": 2400.0,
                "is_synthetic": True,
            }
        ])
        svc = AnalyticsService()
        monkeypatch.setattr(svc, "load_sessions_df", lambda: synth_df)
        monkeypatch.setattr(svc, "load_changes_df", lambda: pd.DataFrame())

        summary = svc.get_telemetry_summary()
        assert summary["is_synthetic"] is True
        assert summary["has_mixed_provenance"] is False
        assert summary["machine_provenance"] == {"DEMO-MACHINE-READY": True}

    def test_mixed_provenance_labels_real_machine_correctly(self, monkeypatch) -> None:
        """In a mixed dataset, real machine is labeled False while synthetic is True."""
        mixed_df = pd.DataFrame([
            {
                "machine_id": "REAL-HOST-01",
                "start_time": "2026-08-10T10:00:00Z",
                "end_time": "2026-08-10T10:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 95.0,
                "battery_drain_percent": 2.0,
                "battery_drain_rate_mw": 2400.0,
                "is_synthetic": False,
            },
            {
                "machine_id": "DEMO-MACHINE-READY",
                "start_time": "2026-08-10T10:00:00Z",
                "end_time": "2026-08-10T10:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 95.0,
                "battery_drain_percent": 2.0,
                "battery_drain_rate_mw": 2400.0,
                "is_synthetic": True,
            },
        ])
        svc = AnalyticsService()
        monkeypatch.setattr(svc, "load_sessions_df", lambda: mixed_df)
        monkeypatch.setattr(svc, "load_changes_df", lambda: pd.DataFrame())

        summary = svc.get_telemetry_summary()
        assert summary["has_mixed_provenance"] is True
        assert summary["is_synthetic"] is True  # Dataset-level flag
        assert summary["machine_provenance"]["REAL-HOST-01"] is False  # Real machine is NOT synthetic!
        assert summary["machine_provenance"]["DEMO-MACHINE-READY"] is True

    def test_missing_provenance_metadata_handled_gracefully(self, monkeypatch) -> None:
        """When is_synthetic column is absent, machines are resolved by naming prefix without error."""
        legacy_df = pd.DataFrame([
            {
                "machine_id": "MY-LAPTOP",
                "start_time": "2026-08-10T10:00:00Z",
                "end_time": "2026-08-10T10:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 95.0,
                "battery_drain_percent": 2.0,
                "battery_drain_rate_mw": 2400.0,
            },
            {
                "machine_id": "DEMO-FIXTURE",
                "start_time": "2026-08-10T10:00:00Z",
                "end_time": "2026-08-10T10:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 95.0,
                "battery_drain_percent": 2.0,
                "battery_drain_rate_mw": 2400.0,
            },
        ])
        svc = AnalyticsService()
        monkeypatch.setattr(svc, "load_sessions_df", lambda: legacy_df)
        monkeypatch.setattr(svc, "load_changes_df", lambda: pd.DataFrame())

        summary = svc.get_telemetry_summary()
        assert summary["machine_provenance"]["MY-LAPTOP"] is False
        assert summary["machine_provenance"]["DEMO-FIXTURE"] is True
        assert summary["has_mixed_provenance"] is True


class TestEvaluationScopeFallbackPrevention:
    """Tests verifying that subsequent-only evaluation never falls back to scoring reference observations."""

    def test_reference_count_equals_observation_count_produces_empty_evaluation(self) -> None:
        """1. reference_count equal to the observation count produces an empty subsequent evaluation partition."""
        rows = [
            {
                "machine_id": "TEST-PC-EQUAL",
                "start_time": f"2026-08-{10 + i:02d}T10:00:00Z",
                "end_time": f"2026-08-{10 + i:02d}T10:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 95.0,
                "battery_drain_percent": 2.0,
                "battery_drain_rate_mw": 2400.0,
            }
            for i in range(12)
        ]
        df = build_sleepstudy_features(pd.DataFrame(rows))
        ref_df, eval_df = AnalyticsService.partition_machine_features(df, reference_count=len(df))

        assert len(ref_df) == 12
        assert len(eval_df) == 0
        assert eval_df.empty

    def test_anomaly_service_does_not_score_reference_observations_when_evaluation_empty(self, monkeypatch) -> None:
        """2. The anomaly service does not score the reference observations when evaluation partition is empty."""
        rows = [
            {
                "machine_id": "TEST-PC-ANOM-EMPTY",
                "start_time": f"2026-08-{10 + i:02d}T10:00:00Z",
                "end_time": f"2026-08-{10 + i:02d}T10:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 95.0,
                "battery_drain_percent": 2.0,
                "battery_drain_rate_mw": 2400.0,
            }
            for i in range(12)
        ]
        test_df = pd.DataFrame(rows)
        svc = AnalyticsService()
        monkeypatch.setattr(svc, "load_sessions_df", lambda: test_df)

        # Subsequent evaluation must NOT fall back to scoring m_feat; must return []
        results = svc.get_anomalies(
            machine_id="TEST-PC-ANOM-EMPTY",
            reference_count=12,
            evaluation_scope="subsequent",
        )
        assert results == []

        # When evaluation_scope='all', scoring the full dataset is explicitly requested
        all_results = svc.get_anomalies(
            machine_id="TEST-PC-ANOM-EMPTY",
            reference_count=12,
            evaluation_scope="all",
        )
        assert len(all_results) > 0
        assert {r["source_row_index"] for r in all_results} == set(range(12))

    def test_regression_service_does_not_score_reference_observations_when_evaluation_empty(self, monkeypatch) -> None:
        """3. The regression service does not score the reference observations when evaluation partition is empty."""
        rows = [
            {
                "machine_id": "TEST-PC-REG-EMPTY",
                "start_time": f"2026-08-{10 + i:02d}T10:00:00Z",
                "end_time": f"2026-08-{10 + i:02d}T10:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 95.0,
                "battery_drain_percent": 2.0,
                "battery_drain_rate_mw": 2400.0,
            }
            for i in range(12)
        ]
        test_df = pd.DataFrame(rows)
        svc = AnalyticsService()
        monkeypatch.setattr(svc, "load_sessions_df", lambda: test_df)

        # Subsequent evaluation must NOT fall back to scoring m_feat; must return []
        results = svc.get_regressions(
            machine_id="TEST-PC-REG-EMPTY",
            reference_count=12,
            only_regressions=False,
            evaluation_scope="subsequent",
        )
        assert results == []

        # Contrast with explicit evaluation_scope='all'
        all_results = svc.get_regressions(
            machine_id="TEST-PC-REG-EMPTY",
            reference_count=12,
            only_regressions=False,
            evaluation_scope="all",
        )
        assert len(all_results) > 0
        assert {r["source_row_index"] for r in all_results} == set(range(12))

    def test_nonempty_evaluation_partition_detects_intended_degraded_observations(self, monkeypatch) -> None:
        """4. A nonempty evaluation partition still detects the intended degraded observations."""
        rows = [
            {
                "machine_id": "TEST-PC-NONEMPTY",
                "start_time": f"2026-08-{10 + i:02d}T10:00:00Z",
                "end_time": f"2026-08-{10 + i:02d}T10:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 95.0,
                "battery_drain_percent": 2.0,
                "battery_drain_rate_mw": 2400.0,
            }
            for i in range(12)
        ] + [
            {
                "machine_id": "TEST-PC-NONEMPTY",
                "start_time": f"2026-09-01T{10 + i:02d}:00:00Z",
                "end_time": f"2026-09-01T{10 + i:02d}:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 50.0,
                "battery_drain_percent": 5.0,
                "battery_drain_rate_mw": 5500.0,
            }
            for i in range(4)
        ]
        test_df = pd.DataFrame(rows)
        svc = AnalyticsService()
        monkeypatch.setattr(svc, "load_sessions_df", lambda: test_df)

        # Regressions in subsequent evaluation
        reg_records = svc.get_regressions(
            machine_id="TEST-PC-NONEMPTY",
            reference_count=12,
            only_regressions=False,
            evaluation_scope="subsequent",
        )
        assert len(reg_records) > 0
        # Only the 4 evaluation sessions should be evaluated (indices 12, 13, 14, 15)
        eval_indices = {r["source_row_index"] for r in reg_records}
        assert eval_indices == {12, 13, 14, 15}

        # Verify sustained regressions are detected
        flagged_regs = [r for r in reg_records if r["is_regression"]]
        assert len(flagged_regs) > 0
        assert all(r["baseline_median"] == 95.0 for r in flagged_regs if r["metric"] == "drips_percent")

        # Anomalies in subsequent evaluation
        anom_records = svc.get_anomalies(
            machine_id="TEST-PC-NONEMPTY",
            reference_count=12,
            evaluation_scope="subsequent",
        )
        assert len(anom_records) > 0
        anom_eval_indices = {r["source_row_index"] for r in anom_records}
        assert anom_eval_indices == {12, 13, 14, 15}
        flagged_anoms = [r for r in anom_records if r["is_anomaly"]]
        assert len(flagged_anoms) > 0

    def test_unready_baseline_produces_explicit_insufficient_history_when_evaluation_exists(self, monkeypatch) -> None:
        """5. An unready baseline still produces explicit insufficient-history states when evaluation observations exist."""
        # 4 reference observations (< min_observations=10 -> unready baseline)
        # 2 evaluation observations
        rows = [
            {
                "machine_id": "TEST-PC-UNREADY",
                "start_time": f"2026-08-{10 + i:02d}T10:00:00Z",
                "end_time": f"2026-08-{10 + i:02d}T10:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 95.0,
                "battery_drain_percent": 2.0,
                "battery_drain_rate_mw": 2400.0,
            }
            for i in range(4)
        ] + [
            {
                "machine_id": "TEST-PC-UNREADY",
                "start_time": f"2026-09-01T{10 + i:02d}:00:00Z",
                "end_time": f"2026-09-01T{10 + i:02d}:30:00Z",
                "duration_seconds": 1800.0,
                "drips_percent": 55.0,
                "battery_drain_percent": 4.5,
                "battery_drain_rate_mw": 5200.0,
            }
            for i in range(2)
        ]
        test_df = pd.DataFrame(rows)
        svc = AnalyticsService()
        monkeypatch.setattr(svc, "load_sessions_df", lambda: test_df)

        # Regressions: evaluation rows exist and baseline is unready
        reg_records = svc.get_regressions(
            machine_id="TEST-PC-UNREADY",
            min_observations=10,
            reference_count=4,
            only_regressions=False,
            evaluation_scope="subsequent",
        )
        assert len(reg_records) > 0
        assert {r["source_row_index"] for r in reg_records} == {4, 5}
        assert all(r["status"] == "insufficient_history" for r in reg_records)
        assert all(r["is_regression"] is False for r in reg_records)

        # Anomalies: evaluation rows exist and baseline is unready
        anom_records = svc.get_anomalies(
            machine_id="TEST-PC-UNREADY",
            min_observations=10,
            reference_count=4,
            evaluation_scope="subsequent",
        )
        assert len(anom_records) > 0
        assert {r["source_row_index"] for r in anom_records} == {4, 5}
        assert all(r["status"] == "insufficient_history" for r in anom_records)
        assert all(r["is_anomaly"] is False for r in anom_records)

        # Default policy on sparse machine (N <= min_observations -> eval_df = df)
        sparse_df = pd.DataFrame(rows[:4])
        monkeypatch.setattr(svc, "load_sessions_df", lambda: sparse_df)
        default_regs = svc.get_regressions(
            machine_id="TEST-PC-UNREADY",
            min_observations=10,
            only_regressions=False,
            evaluation_scope="subsequent",
        )
        assert len(default_regs) > 0
        assert all(r["status"] == "insufficient_history" for r in default_regs)
        assert all(r["is_regression"] is False for r in default_regs)

    def test_existing_api_response_contracts_and_validation(self) -> None:
        """6. Existing API response contracts remain compatible and invalid evaluation_scopes are rejected."""
        from fastapi.testclient import TestClient
        from src.api.app import app

        client = TestClient(app)
        svc = AnalyticsService()

        # Service layer validation
        with pytest.raises(ValueError, match="Invalid evaluation_scope"):
            svc.get_anomalies(evaluation_scope="invalid_scope")

        with pytest.raises(ValueError, match="Invalid evaluation_scope"):
            svc.get_regressions(evaluation_scope="invalid_scope")

        with pytest.raises(ValueError, match="Invalid evaluation_scope"):
            svc.get_correlations(evaluation_scope="invalid_scope")

        # API endpoint validation returns 422
        res_anom = client.get("/api/analytics/anomalies?evaluation_scope=invalid_scope")
        assert res_anom.status_code == 422

        res_reg = client.get("/api/analytics/regressions?evaluation_scope=invalid_scope")
        assert res_reg.status_code == 422

        res_corr = client.get("/api/analytics/correlations?evaluation_scope=invalid_scope")
        assert res_corr.status_code == 422

        # API response contracts with subsequent and all
        res_ok_sub = client.get("/api/analytics/regressions?evaluation_scope=subsequent")
        assert res_ok_sub.status_code == 200
        assert isinstance(res_ok_sub.json(), list)

        res_ok_all = client.get("/api/analytics/regressions?evaluation_scope=all")
        assert res_ok_all.status_code == 200
        assert isinstance(res_ok_all.json(), list)

        # When reference_count covers all sessions, subsequent API evaluation returns empty list
        summary_res = client.get("/api/telemetry/summary")
        assert summary_res.status_code == 200
        total_sessions = summary_res.json()["total_sessions"]
        if total_sessions > 0:
            res_cov = client.get(
                f"/api/analytics/regressions?evaluation_scope=subsequent&reference_count={total_sessions}"
            )
            assert res_cov.status_code == 200
            assert res_cov.json() == []

